"""Cała styczność z Claude Agent SDK żyje w tym module (patrz CLAUDE.md).

Gdy API SDK się zmieni, poprawka ma być w jednym pliku — dlatego nawet
tryb testowy z Fazy 1 buduje `ClaudeAgentOptions` w ten sam sposób, w jaki
będą to robić tryby Strateg/Redaktor/Wywiad w kolejnych fazach.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import os
from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    PermissionResultAllow,
    PermissionResultDeny,
    ProcessError,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolPermissionContext,
    ToolUseBlock,
    create_sdk_mcp_server,
    query,
)
from claude_agent_sdk import tool as sdk_tool

logger = logging.getLogger("forces_content_studio.silnik")

# Katalogi, w których agent wolno mu zapisywać pliki (SPEC 10.1, CLAUDE.md #3).
# Ścieżki względem katalogu roboczego (cwd = katalog danych).
KATALOGI_ZAPISU = ("plan", "output")

# Zamknięta lista narzędzi. "Skill" NIE jest tu wpisywane literałem: w
# zainstalowanej wersji SDK (0.2.128) `allowed_tools=["Skill"]` jest
# oznaczone jako deprecated na rzecz parametru `skills=` — ten parametr sam
# dopisuje "Skill" do efektywnej listy narzędzi (patrz `claude_agent_sdk.types`,
# pole `ClaudeAgentOptions.skills`). "Write" też celowo nie jest tu wpisane:
# gdyby było wpisane wprost jako cały tool, SDK zezwalałby na każdy zapis
# bez pytania — łamałoby to wymóg "zapis tylko do plan/ i output/, wymuszony
# w backendzie" (SPEC 10.1). Zamiast zgadywać, czy zapis widziany przez SDK
# jako `Write(plan/**)` jest honorowany (udokumentowane tylko dla Bash),
# egzekwujemy ścieżkę w `_zezwol_na_narzedzie` poniżej — to udokumentowany
# mechanizm (`can_use_tool`), więc nic tu nie jest zgadywane.
DOZWOLONE_NARZEDZIA = ["Read", "Grep", "Glob", "Agent", "WebSearch", "WebFetch"]
ZABRONIONE_NARZEDZIA = ["Bash", "Edit"]

# Zawężone zestawy narzędzi dla poszczególnych trybów. Każde narzędzie to
# koszt: jego definicja siedzi w kontekście każdej tury. Ważniejsze jednak,
# że `WebSearch`/`WebFetch` w rękach głównego agenta wciągają całe strony do
# jego kontekstu — a ten jest przeładowywany przy każdej turze. Research
# oddajemy więc podagentowi, który ma własny, czysty kontekst i zwraca samo
# streszczenie.
NARZEDZIA_BEZ_SIECI = ["Read", "Grep", "Glob"]
NARZEDZIA_Z_PODAGENTEM = ["Read", "Grep", "Glob", "Agent"]

# Nazwy pól `ClaudeAgentOptions`, których faktycznie używa ten moduł.
# `app/diagnostyka.py` porównuje ten zbiór z introspekcją zainstalowanej
# wersji SDK — jeśli nazwa zniknie albo zmieni się, diagnostyka to zgłosi
# zamiast dowiadywać się o tym dopiero przy pierwszym wywołaniu modelu.
PARAMETRY_UZYWANE_PRZEZ_KOD = frozenset(
    {
        "cwd",
        "setting_sources",
        "skills",
        "tools",
        "allowed_tools",
        "disallowed_tools",
        "system_prompt",
        "can_use_tool",
        "model",
        "agents",
        "mcp_servers",
        "max_budget_usd",
        "max_turns",
    }
)


def _sciezka_w_dozwolonym_katalogu(katalog_danych: Path, sciezka_pliku: str) -> bool:
    """Sprawdza, czy zapis mieści się w plan/ albo output/ (bez wychodzenia przez '..')."""
    cel = (katalog_danych / sciezka_pliku).resolve()
    return any(
        cel == (katalog_danych / dozwolony).resolve()
        or (katalog_danych / dozwolony).resolve() in cel.parents
        for dozwolony in KATALOGI_ZAPISU
    )


def _zbuduj_zezwalacz(katalog_danych: Path):
    """Zwraca `can_use_tool` spięty z konkretnym katalogiem danych tej sesji."""

    async def _zezwol_na_narzedzie(
        nazwa_narzedzia: str,
        wejscie_narzedzia: dict[str, Any],
        _kontekst: ToolPermissionContext,
    ) -> PermissionResultAllow | PermissionResultDeny:
        if nazwa_narzedzia != "Write":
            # Reszta zamkniętej listy (Read/Grep/Glob/Agent/WebSearch/WebFetch)
            # jest już auto-zatwierdzona przez allowed_tools i nigdy tu nie
            # trafia; to gałąź na wszelki wypadek, gdyby CLI kiedyś zapytało
            # o coś spoza listy — odmawiamy z logiem, nie po cichu.
            logger.warning("Odmowa dla narzędzia spoza zamkniętej listy: %s", nazwa_narzedzia)
            return PermissionResultDeny(
                message=f"Narzędzie '{nazwa_narzedzia}' nie jest dozwolone w tej aplikacji."
            )

        sciezka = wejscie_narzedzia.get("file_path", "")
        logger.info("Żądanie zapisu: %s (katalog danych: %s)", sciezka, katalog_danych)
        if _sciezka_w_dozwolonym_katalogu(katalog_danych, sciezka):
            return PermissionResultAllow()

        logger.warning("Zablokowano próbę zapisu poza plan/ i output/: %s", sciezka)
        return PermissionResultDeny(
            message=(
                "Zapis dozwolony wyłącznie w katalogach 'plan/' i 'output/'. "
                f"Odrzucono próbę zapisu: {sciezka}"
            )
        )

    return _zezwol_na_narzedzie


# Sufit kosztów pojedynczej operacji (SPEC-frontend 2.2: „nie da się
# przekroczyć limitu"). Każde wywołanie modelu niesie ok. 25 tys. tokenów
# narzutu (definicje narzędzi i prompt systemowy CLI) — przy kilkunastu
# turach agenta i podagencie badawczym rachunek potrafi urosnąć do kilku
# dolarów za jeden post, jeśli nic go nie zatrzyma. Limit jest twardy:
# SDK przerywa pracę po jego przekroczeniu.
LIMIT_USD_DOMYSLNY = 1.00
LIMIT_USD_PLAN = 2.00  # plan miesiąca czyta więcej i robi research, ma wyższy sufit
# Wyciąg z dokumentu robimy raz na dokument, ale wielostronicowy raport potrafi
# ważyć więcej niż wszystko inne w tej aplikacji razem wzięte — stąd osobny,
# wyższy sufit. Koszt jest jednorazowy i pokazywany operatorce przed kliknięciem.
LIMIT_USD_WYCIAG = 1.50
# Wywiad to jedna wymiana zdań naraz, ale ostatnia tura zwraca treść dwóch
# plików — stąd sufit wyższy niż w zwykłym czacie.
LIMIT_USD_WYWIAD = 0.60
# Przegląd branży chodzi po sieci przez podagenta — najdroższa operacja
# w aplikacji. Zmierzony realny przebieg: 1,31 USD przy pełnej liście źródeł,
# więc sufit 1,50 byłby na styk i ucinałby przegląd w połowie. Robi się go raz
# na kilka tygodni, a wynik służy potem wszystkim postom i planowi.
LIMIT_USD_PRZEGLAD = 2.50

# Ile tur agenta wolno wykonać. Bez tego zapętlony agent (np. gdy zapis
# pliku raz za razem się nie udaje) potrafi spalić limit w całości.
MAKS_TUR_DOMYSLNIE = 30


def limit_kosztu(domyslny: float) -> float:
    """Sufit kosztów operacji; nadpisywalny przez `.env` bez zmian w kodzie."""
    z_env = os.environ.get("LIMIT_USD_NA_OPERACJE", "").strip()
    if not z_env:
        return domyslny
    try:
        return float(z_env.replace(",", "."))
    except ValueError:
        logger.warning(
            "LIMIT_USD_NA_OPERACJE w .env nie jest liczbą (%r) — używam %.2f USD.",
            z_env,
            domyslny,
        )
        return domyslny


def zbuduj_opcje(
    katalog_danych: Path,
    system_prompt: str,
    *,
    model: str | None = None,
    agents: dict[str, Any] | None = None,
    dodatkowe_dozwolone_narzedzia: list[str] | None = None,
    narzedzia: list[str] | None = None,
    mcp_servers: dict[str, Any] | None = None,
    limit_usd: float | None = None,
    maks_tur: int | None = None,
    bez_narzedzi: bool = False,
) -> ClaudeAgentOptions:
    """Buduje `ClaudeAgentOptions` wspólne dla wszystkich trybów agenta.

    `bez_narzedzi=True` wyłącza wbudowane narzędzia całkowicie (parametr
    `tools=[]` w SDK). Używane tam, gdzie potrzebna jest jedna odpowiedź
    tekstowa i nic więcej — model nie marnuje wtedy tur na szukanie plików,
    które i tak podajemy mu wprost w poleceniu.
    """
    lista_narzedzi = (narzedzia if narzedzia is not None else DOZWOLONE_NARZEDZIA) + (
        dodatkowe_dozwolone_narzedzia or []
    )
    return ClaudeAgentOptions(
        cwd=katalog_danych,
        setting_sources=["project"],
        skills="all",
        tools=[] if bez_narzedzi else None,
        allowed_tools=[] if bez_narzedzi else lista_narzedzi,
        disallowed_tools=ZABRONIONE_NARZEDZIA,
        system_prompt=system_prompt,
        can_use_tool=_zbuduj_zezwalacz(katalog_danych),
        model=model or os.environ.get("MODEL") or None,
        agents=agents,
        mcp_servers=mcp_servers or {},
        max_budget_usd=limit_kosztu(limit_usd if limit_usd is not None else LIMIT_USD_DOMYSLNY),
        max_turns=maks_tur or MAKS_TUR_DOMYSLNIE,
    )


def sprawdz_zgodnosc_parametrow() -> dict[str, Any]:
    """Introspekcja `ClaudeAgentOptions` — używana przez diagnostykę, nie wywołuje modelu."""
    pola_w_sdk = {pole.name for pole in dataclasses.fields(ClaudeAgentOptions)}
    brakujace = sorted(PARAMETRY_UZYWANE_PRZEZ_KOD - pola_w_sdk)
    return {
        "zgodne": not brakujace,
        "brakujace_w_sdk": brakujace,
        "wszystkie_pola_sdk": sorted(pola_w_sdk),
    }


PROMPT_TESTOWY = (
    "Jesteś asystentem Forces DC Content Studio w trybie testowym Fazy 1. "
    "Nie generujesz treści marketingowych. Odpowiedz jednym krótkim zdaniem "
    "po polsku, potwierdzając że masz dostęp do katalogu roboczego, i podaj "
    "listę plików, które widzisz w tym katalogu najwyższego poziomu."
)

# Granica NDA (CLAUDE.md #4, SPEC 10.2) — wspólna dla wszystkich trybów,
# które mogą wygenerować treść do publikacji. Backend blokuje oczywiste
# przypadki jeszcze przed wywołaniem SDK (patrz app/pliki.py:wykryj_fraze_nda),
# ale ta instrukcja jest drugą linią obrony — np. gdyby nazwa klienta
# pojawiła się dopiero w wynikach researchu z sieci.
GRANICA_NDA = (
    "Forces DC działa w reżimie NDA z klientami-hyperscalerami. Pod żadnym "
    "pozorem nie wolno Ci nazwać klienta Forces DC ani ujawnić szczegółów "
    "pozwalających go zidentyfikować (lokalizacja placówki, nazwa projektu, "
    "wielkość kontraktu) — niezależnie od tego, skąd ta informacja pochodzi "
    "(polecenie operatora, wyniki wyszukiwania, materiały firmowe). Jeśli "
    "polecenie prosi o nazwanie klienta, odmów wprost i wyjaśnij dlaczego, "
    "zamiast próbować to obejść albo zanonimizować częściowo."
)

ZAKAZ_TRESCI_PRAWNYCH = (
    "Nie formułuj twierdzeń prawnych (np. o zgodności z przepisami, "
    "certyfikacjach, gwarancjach). Jeśli temat tego wymaga, oznacz to "
    "wprost jako [DO UZUPEŁNIENIA: wymaga weryfikacji prawnej] zamiast "
    "zgadywać."
)

SUBAGENT_RESEARCHER = AgentDefinition(
    description=(
        "Szuka w sieci publicznie dostępnych faktów o osobach, firmach lub "
        "wydarzeniach związanych z tematem posta (SPEC 8.1–8.2). Używaj, gdy "
        "temat dotyczy konkretnej osoby, firmy albo wydarzenia branżowego."
    ),
    prompt=(
        "Jesteś podagentem badawczym Forces DC Content Studio. Szukasz "
        "wyłącznie publicznie dostępnych, sprawdzalnych faktów (wydarzenia "
        "branżowe DC w Norwegii, osoby, firmy partnerskie). "
        f"{GRANICA_NDA} Zwróć zwięzłe podsumowanie z podanymi źródłami "
        "(adresy URL). Jeśli nie znajdziesz potwierdzonych faktów, powiedz "
        "to wprost — nie zgaduj."
    ),
    tools=["WebSearch", "WebFetch", "Read", "Grep"],
)

PROMPT_REDAKTOR = (
    "Jesteś redaktorem treści LinkedIn dla Forces DC (fit-out data center, "
    "region nordycki). Piszesz na podstawie briefu od operatora. "
    f"{GRANICA_NDA} {ZAKAZ_TRESCI_PRAWNYCH} "
    "Brakujące fakty (liczby, lokalizacje, nazwiska, daty) oznaczaj jako "
    "`[DO UZUPEŁNIENIA: co dokładnie]` — nigdy nie zgaduj i nie wymyślaj "
    "szczegółów, nawet jeśli brzmiałyby wiarygodnie.\n\n"
    "WAŻNE — nie szukaj plików. Zasady stylu, fakty o firmie i posty do "
    "kalibracji dostajesz gotowe w poleceniu. Nie masz narzędzi do czytania "
    "dysku i nie są Ci potrzebne. Jedyne narzędzie, jakie masz, to podagent "
    "`researcher` (Agent, subagent_type='researcher') — użyj go WYŁĄCZNIE "
    "wtedy, gdy temat dotyczy konkretnej osoby, firmy albo wydarzenia i "
    "naprawdę potrzebujesz faktów z zewnątrz. W innych przypadkach pisz od razu.\n\n"
    "Skalibruj się na podanych postach z korpusu: trzymaj ich rytm, długość "
    "i sposób budowania zdań. Jeśli korpus był pusty, napisz o tym w Brakach.\n\n"
    "Wygeneruj DOKŁADNIE trzy warianty LinkedIn (różne podejścia redakcyjne — "
    "np. faktograficzny / przez problem / przez osobę — nie kosmetyczne "
    "różnice tego samego tekstu), wersję na Facebooka (skrót ~30%, "
    "łagodniejszy żargon) i brief graficzny.\n\n"
    "ODPOWIEDŹ: zwróć samą treść w poniższej strukturze, bez wstępu i bez "
    "komentarza. Zaczynaj od razu od „## Wariant 1”. Kolejność sekcji jest "
    "sztywna, bo inny program parsuje ten tekst:\n\n"
    "## Wariant 1\n**Podejście:** <jedno-dwa słowa>\n<treść posta>\n\n"
    "## Wariant 2\n**Podejście:** <jedno-dwa słowa>\n<treść posta>\n\n"
    "## Wariant 3\n**Podejście:** <jedno-dwa słowa>\n<treść posta>\n\n"
    "## Facebook\n<treść posta na Facebooka>\n\n"
    "## Brief graficzny\n<opis dla grafika: co ma przedstawiać, format, "
    "tekst na obrazie, sugerowany szablon>\n\n"
    "## Braki\n<lista punktowana, każdy punkt od \'- \', albo dokładnie "
    "\'Brak braków.\' jeśli niczego nie brakuje>\n"
)


PROMPT_STRATEG = (
    "Jesteś strategiem contentu dla Forces DC Content Studio (fit-out data "
    "center, Norwegia). Budujesz plan postów na wskazany miesiąc. "
    f"{GRANICA_NDA} {ZAKAZ_TRESCI_PRAWNYCH}\n\n"
    "Przebieg (SPEC 8.1):\n"
    "1. Przeczytaj baza-wiedzy/zrodla-branzowe.md — to lista źródeł, z których "
    "masz korzystać, wraz z kalendarzem wydarzeń i tematami, które regularnie "
    "generują newsy.\n"
    "2. Użyj podagenta `researcher` (narzędzie Agent, subagent_type="
    "'researcher'), żeby zebrać wydarzenia z branży data center w Norwegii "
    "z ostatnich ~30 dni oraz zbliżające się wydarzenia branżowe.\n"
    "3. Przeczytaj `artykuly/wyciagi/*.md` — to gotowe wyciągi z artykułów "
    "i raportów wgranych przez operatora: fakty, liczby i zaproponowane "
    "tematy. Traktuj je na równi z newsami z sieci i sięgaj po nie w pierwszej "
    "kolejności; same pliki w `artykuly/` czytaj tylko wtedy, gdy dokument "
    "nie ma jeszcze wyciągu.\n"
    "4. Przeczytaj materiały z firmy: input-firmowy/ dla wskazanego miesiąca "
    "ORAZ dla miesiąca poprzedniego.\n"
    "5. Przejrzyj korpus/linkedin/ i wyklucz tematy poruszane w ostatnich "
    "60 dniach, żeby plan się nie powtarzał.\n"
    "6. Zbuduj plan zgodnie z proporcją typów opisaną w zasadach planowania "
    "(.claude/skills/strategia-contentu). Jeśli ten plik jest placeholderem "
    "bez konkretnych proporcji, napisz to wprost w sekcji „Czego zabrakło”.\n\n"
    "ZACHOWANIE KRYTYCZNE — najważniejsza reguła tego trybu:\n"
    "Jeśli materiały z firmy (input-firmowy) są puste albo ubogie, NIE "
    "uzupełniaj planu tematami branżowymi do pełnej liczby pozycji. Zwróć "
    "plan KRÓTSZY i wypisz w sekcji „Czego zabrakło”, czego konkretnie "
    "brakowało i o co trzeba dopytać w firmie. Content oparty wyłącznie na "
    "newsach branżowych jest nieodróżnialny od konkurencji — to zdiagnozowany "
    "problem tego klienta, nie hipoteza. Krótszy, ale konkretny plan jest "
    "poprawnym wynikiem; rozdmuchany plan z samych newsów jest błędem.\n\n"
    "ILE MASZ ZROBIĆ SAM\n"
    "Operatorka jest jedną osobą i nie ma czasu domyślać się, co miałeś na "
    "myśli. Krótkość dotyczy LICZBY POZYCJI, a nie tego, ile pracy wykonujesz "
    "przy każdej z nich. Przy każdej pozycji planu masz podać konkretny kąt "
    "ujęcia: od czego zacząć post i dlaczego akurat Forces DC ma w tej sprawie "
    "coś do powiedzenia jako wykonawca fit-outu, a nie komentator cudzych "
    "newsów. „Post o rynku data center” to zła pozycja; „Moc rośnie o 18%, "
    "ale wąskim gardłem są ekipy — pokazać to od strony czasu montażu” to "
    "dobra.\n\n"
    "Zamiast pisać, że czegoś brakuje, sformułuj GOTOWE PYTANIE do wysłania "
    "do firmy — takie, na które da się odpowiedzieć jednym zdaniem. Nie "
    "„brakuje danych o realizacji”, tylko „Ile osób pracowało przy odbiorze "
    "w lipcu i ile to trwało od wejścia na plac?”.\n\n"
    "Zapisz też wszystko, co ustaliłeś w researchu: liczby, daty wydarzeń, "
    "nazwy instytucji, adresy źródeł. Redaktor dostanie te ustalenia przy "
    "pisaniu każdego posta z tego planu, więc nie będzie ich szukał od nowa. "
    "Research jest najdroższą operacją w tej aplikacji — ma być zrobiony raz.\n\n"
    "Na koniec zaproponuj zapas tematów: 3–5 tematów eksperckich, które da "
    "się napisać z samej wiedzy branżowej i doświadczenia firmy, BEZ nowych "
    "materiałów z firmy. To nie są pozycje planu i nie wliczają się do niego "
    "— to rezerwa na wypadek, gdyby miesiąc okazał się chudy. Oznacz je jako "
    "zapas, żeby nikt nie pomylił ich z tematami opartymi na realnych "
    "wydarzeniach.\n\n"
    "Zapisz wynik narzędziem Write pod ścieżką WZGLĘDNĄ `plan/RRRR-MM.md` "
    "(dla wskazanego miesiąca). WAŻNE: podaj dokładnie taką względną ścieżkę, "
    "zaczynającą się od 'plan/' — bez ścieżki bezwzględnej, Twój katalog "
    "roboczy już wskazuje właściwe miejsce. Użyj DOKŁADNIE tej struktury, "
    "bo inny program parsuje ten plik:\n\n"
    "# Plan na RRRR-MM\n\n"
    "| # | Data | Typ | Temat | Kąt ujęcia | Źródło | Do potwierdzenia | Status |\n"
    "|---|---|---|---|---|---|---|---|\n"
    "| 1 | RRRR-MM-DD | <typ z listy> | <temat> | <od czego zacząć i dlaczego "
    "Forces DC ma tu głos — jedno-dwa zdania> | <źródło lub materiały z firmy> "
    "| <czego brakuje, puste jeśli nic> | szkic |\n\n"
    "## Ustalenia z researchu\n\n"
    "<fakty, liczby, daty wydarzeń i adresy źródeł zebrane przy budowaniu "
    "tego planu — tekstem albo listą; napisz 'Brak zapisanych ustaleń.', "
    "jeśli research niczego nie dał>\n\n"
    "## Pytania do firmy\n\n"
    "<lista punktowana gotowych pytań do wysłania, każdy punkt od '- ', "
    "albo dokładnie 'Brak pytań.'>\n\n"
    "## Zapas tematów\n\n"
    "<lista punktowana tematów eksperckich niewymagających materiałów z firmy, "
    "każdy punkt od '- ', albo dokładnie 'Brak zapasu.'>\n\n"
    "## Czego zabrakło\n\n"
    "<lista punktowana, każdy punkt od '- ', albo dokładnie 'Brak uwag.'>\n\n"
    "Dozwolone wartości kolumny Typ: branzowy, realizacja, zajawka-eventu, "
    "prelegent, partner, employer-branding, ekspercki, event-relacja, "
    "obecnosc-branzowa, podsumowanie, okolicznosciowy. "
    "W kolumnie Status wpisuj zawsze 'szkic'. W treści tabeli nie używaj "
    "znaku '|' — rozbija kolumny. Dłuższe wywody zostaw do sekcji pod tabelą; "
    "w kolumnie „Kąt ujęcia” zmieść się w jednym-dwóch zdaniach."
)

# Nazwa narzędzia MCP tak, jak zobaczy ją model i jak trafia do allowed_tools/
# ToolUseBlock.name — konwencja `mcp__<serwer>__<narzędzie>` (ta sama, którą
# widać w nazwach narzędzi MCP używanych w tej rozmowie, np. `mcp__github__*`;
# SPEC tego nie definiował, więc opieramy się na obserwowanej konwencji, nie
# na zgadywaniu).
NAZWA_NARZEDZIA_PROPOZYCJI = "mcp__asystent__zaproponuj_napisanie_posta"


@sdk_tool(
    "zaproponuj_napisanie_posta",
    "Zgłasza operatorowi propozycję napisania posta LinkedIn do zatwierdzenia "
    "(SPEC-frontend 5, karta 'Uruchom/Anuluj'). Użyj tego narzędzia zamiast "
    "pisania treści posta samodzielnie w tej rozmowie.",
    {"brief": str, "zasoby": str, "szacowane_tokeny": int},
)
async def _narzedzie_propozycji(_args: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": (
                    "Propozycja przekazana operatorowi do zatwierdzenia. Nie "
                    "generuj treści posta w tej rozmowie — zakończ krótkim "
                    "potwierdzeniem, że czekasz na decyzję."
                ),
            }
        ]
    }


SERWER_ASYSTENTA = create_sdk_mcp_server(name="asystent", tools=[_narzedzie_propozycji])

PROMPT_ASYSTENT = (
    "Jesteś asystentem Forces DC Content Studio — pomagasz operatorce "
    "(Magdzie) korzystać z narzędzia. Pisz po polsku, bez żargonu "
    "technicznego: nie mów 'prompt', 'agent', 'skill' — mów 'zasady stylu', "
    "'asystent', 'plan miesiąca'.\n\n"
    "Stan aplikacji poznajesz, czytając pliki w katalogu roboczym:\n"
    "- plan miesiąca: plan/RRRR-MM.md (np. plan/2026-08.md dla sierpnia)\n"
    "- korpus opublikowanych postów: korpus/linkedin/*.md\n"
    "- materiały z firmy: input-firmowy/RRRR-MM.md\n"
    "- wgrane artykuły i dokumenty: artykuly/\n"
    "- wygenerowane posty: output/*.md\n"
    "- zasady stylu: .claude/skills/, fakty o firmie i zakazane zwroty: baza-wiedzy/\n\n"
    "ZAWSZE najpierw sprawdź pliki, zanim odpowiesz. Gdy ktoś pyta o plan na "
    "dany miesiąc, przeczytaj odpowiedni plik z plan/ i streść jego treść: "
    "ile pozycji, jakie tematy i daty, co jest w sekcji „Czego zabrakło”. "
    "Nie odsyłaj do zakładek ani nie mów, że czegoś nie umiesz sprawdzić — "
    "masz dostęp do tych plików i to jest Twoje główne zadanie. Jeśli pliku "
    "nie ma, powiedz wprost, że planu na ten miesiąc jeszcze nie zbudowano, "
    "i zaproponuj zbudowanie go w zakładce Plan.\n\n"
    "Odpowiadaj na podstawie tego, co faktycznie jest w plikach — jeśli "
    "czegoś brakuje albo katalog jest pusty, powiedz to wprost zamiast zgadywać.\n\n"
    f"{GRANICA_NDA} {ZAKAZ_TRESCI_PRAWNYCH}\n\n"
    "Jeśli operator prosi o napisanie albo wygenerowanie posta: NIE pisz "
    "treści sam. Wywołaj narzędzie zaproponuj_napisanie_posta z argumentami "
    "brief (samodzielny, konkretny opis tematu — tak, żeby redaktor mógł "
    "napisać post bez dodatkowych pytań), zasoby (krótki opis czego "
    "użyjesz, np. 'zasady stylu, korpus, wyszukiwanie w sieci') i "
    "szacowane_tokeny (Twój przybliżony szacunek jako liczba całkowita — to "
    "tylko orientacyjna wartość, ma prawo być niedokładna). Jeśli prośba "
    "dotyczy zbudowania planu na cały miesiąc, nie wywołuj tego narzędzia — "
    "odeślij do zakładki Plan, gdzie jest przycisk budowania planu."
)


async def _jako_strumien_wejscia(
    tekst: str, zakonczono: asyncio.Event
) -> AsyncIterator[dict[str, Any]]:
    """Opakowuje pojedynczy prompt jako AsyncIterable, trzymane otwarte do
    końca zapytania.

    Wymagane przez zainstalowaną wersję SDK (0.2.128): `can_use_tool`
    działa tylko w trybie strumieniowym wejścia — zwykły `str` jako prompt
    rzuca `ValueError("can_use_tool callback requires streaming mode")`.
    To nie jest udokumentowane w SPEC (sekcja 13 tego nie przewidywała),
    więc odnotowujemy to tutaj zamiast gdzie indziej zgadywać.

    Drugi, poważniejszy szczegół tej samej wersji SDK: gdyby ten generator
    zakończył się od razu po jednej wiadomości, `query.py` w SDK zamyka
    stdin natychmiast (`wait_for_result_and_end_input` trzyma stdin otwarte
    tylko gdy ustawione są `hooks` albo `sdk_mcp_servers` — nie sprawdza
    `can_use_tool`, mimo że ten mechanizm też wymaga dwukierunkowej
    komunikacji z CLI o zgodę na narzędzie). Skutek: pierwsze wywołanie
    `Write` kończy się `AbortError: Stream closed`, bo kanał do zapytania
    o pozwolenie jest już zamknięty. Obejście: trzymamy generator otwarty
    (czekamy na `zakonczono`), dopóki `_przetworz_zapytanie` nie skończy
    odbierać wiadomości z `query()`.
    """
    yield {
        "type": "user",
        "session_id": "",
        "message": {"role": "user", "content": tekst},
        "parent_tool_use_id": None,
    }
    await zakonczono.wait()


def _opisz_uzycie_narzedzia(blok: ToolUseBlock) -> str:
    """Krok agenta jako czytelny status po polsku (SPEC-frontend 5:
    "Czytam zasady stylu…" · "Szukam w branży (3 źródła)…" · "Sprawdzam korpus…")."""
    if blok.name == "Read":
        return f"Czytam: {blok.input.get('file_path', '?')}"
    if blok.name in ("Grep", "Glob"):
        return "Przeszukuję pliki…"
    if blok.name == "WebSearch":
        return f"Szukam w sieci: {blok.input.get('query', '…')}"
    if blok.name == "WebFetch":
        return f"Pobieram stronę: {blok.input.get('url', '…')}"
    if blok.name == "Agent":
        return f"Uruchamiam podproces badawczy ({blok.input.get('subagent_type', '?')})…"
    if blok.name == "Write":
        return f"Zapisuję: {blok.input.get('file_path', '?')}"
    if blok.name == "Skill":
        return "Korzystam z zasad stylu…"
    return f"Wywołuję narzędzie: {blok.name}…"


KOMUNIKAT_BRAK_LOGOWANIA = (
    "Asystent nie ma dostępu do konta Anthropic, więc nie może odpowiadać.\n\n"
    "Najczęstsza przyczyna: w pliku .env brakuje klucza albo jest on "
    "niepoprawny. Otwórz .env w katalogu aplikacji, sprawdź linię "
    "ANTHROPIC_API_KEY= (klucz zaczyna się od sk-ant- i nie ma wokół siebie "
    "cudzysłowów ani spacji), zapisz plik i uruchom aplikację ponownie.\n\n"
    "Nowy klucz wygenerujesz na console.anthropic.com w sekcji API Keys."
)

# CLI zgłasza brak poświadczeń zwykłym tekstem po angielsku. Bez tego
# wykrywania trafiał on do interfejsu jako normalna wypowiedź asystenta
# („Not logged in · Please run /login"), co dla operatorki wyglądało jak
# awaria samego czatu, a nie jak brak klucza.
FRAZY_BRAKU_LOGOWANIA = ("not logged in", "please run /login", "invalid api key", "authentication_error")


def _czy_brak_logowania(tekst: str) -> bool:
    maly = tekst.lower()
    return any(fraza in maly for fraza in FRAZY_BRAKU_LOGOWANIA)


async def _przetworz_zapytanie(
    opcje: ClaudeAgentOptions,
    tresc_polecenia: str,
    *,
    obserwuj_zapis_z_prefiksem: str | None = None,
    narzedzie_propozycji: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Wspólna pętla nad `query()`: zamienia wiadomości SDK na zdarzenia SSE.

    Używana przez wszystkie tryby agenta (Faza 1: test; Faza 2: Redaktor,
    Asystent; kolejne fazy: Strateg, Wywiad) — jedno miejsce do poprawki, gdy
    zmieni się kształt wiadomości SDK (CLAUDE.md: cała styczność z SDK tutaj).

    Jeśli `obserwuj_zapis_z_prefiksem` jest podane (np. "output/"), ostatnia
    ścieżka z wywołania Write zaczynająca się od tego prefiksu trafia do
    zdarzenia "wynik" pod kluczem "sciezka_pliku".

    Jeśli `narzedzie_propozycji` jest podane (patrz `NAZWA_NARZEDZIA_PROPOZYCJI`),
    wywołanie tego narzędzia MCP trafia jako osobne zdarzenie "propozycja"
    zamiast zwykłego statusu — frontend renderuje je jako kartę
    Uruchom/Anuluj (SPEC-frontend 5), zamiast surowego kroku agenta.
    """
    sciezka_zapisu: str | None = None
    zakonczono = asyncio.Event()
    try:
        prompt = _jako_strumien_wejscia(tresc_polecenia, zakonczono)
        async for wiadomosc in query(prompt=prompt, options=opcje):
            if isinstance(wiadomosc, SystemMessage) and wiadomosc.subtype == "init":
                yield {"typ": "status", "tekst": "Sesja zainicjowana, model odpowiada…"}
            elif isinstance(wiadomosc, AssistantMessage):
                if wiadomosc.error in ("authentication_failed", "billing_error"):
                    logger.error("Silnik zgłosił błąd konta: %s", wiadomosc.error)
                    yield {"typ": "blad", "tekst": KOMUNIKAT_BRAK_LOGOWANIA}
                    break
                for blok in wiadomosc.content:
                    if isinstance(blok, TextBlock):
                        if _czy_brak_logowania(blok.text):
                            logger.error("Silnik zgłosił brak poświadczeń: %s", blok.text.strip())
                            yield {"typ": "blad", "tekst": KOMUNIKAT_BRAK_LOGOWANIA}
                            return
                        yield {"typ": "fragment", "tekst": blok.text}
                    elif isinstance(blok, ToolUseBlock):
                        if narzedzie_propozycji and blok.name == narzedzie_propozycji:
                            yield {"typ": "propozycja", "dane": blok.input}
                            continue
                        yield {"typ": "status", "tekst": _opisz_uzycie_narzedzia(blok)}
                        sciezka = str(blok.input.get("file_path", ""))
                        if (
                            obserwuj_zapis_z_prefiksem
                            and blok.name == "Write"
                            and sciezka.replace("\\", "/").startswith(obserwuj_zapis_z_prefiksem)
                        ):
                            sciezka_zapisu = sciezka
            elif isinstance(wiadomosc, ResultMessage):
                if "budget" in (wiadomosc.subtype or ""):
                    logger.warning(
                        "Operacja przerwana po przekroczeniu limitu kosztów (%s USD).",
                        wiadomosc.total_cost_usd,
                    )
                    yield {
                        "typ": "blad",
                        "tekst": (
                            "Przerwano — operacja przekroczyła ustawiony limit kosztu "
                            f"(wydano {wiadomosc.total_cost_usd or 0:.2f} USD). "
                            "To zabezpieczenie przed niespodziewanym rachunkiem. "
                            "Spróbuj z węższym tematem, albo poproś administratora "
                            "o podniesienie limitu w ustawieniach."
                        ),
                    }
                yield {
                    "typ": "wynik",
                    "bledny": wiadomosc.is_error,
                    "tury": wiadomosc.num_turns,
                    "koszt_usd": wiadomosc.total_cost_usd,
                    "uzycie": wiadomosc.usage,
                    "sciezka_pliku": sciezka_zapisu,
                }
                # Wychodzimy z pętli od razu po wyniku, zamiast czekać, aż
                # iterator sam się skończy. Inaczej powstaje zakleszczenie:
                # strumień wejścia trzymamy otwarty do końca pętli (bo wymaga
                # tego can_use_tool), CLI nie kończy się, dopóki wejście jest
                # otwarte, a pętla czeka na koniec CLI. Objawiało się to tak,
                # że plik był już zapisany na dysku, a przeglądarka w
                # nieskończoność pokazywała „buduję…”.
                break
    except ProcessError as blad:
        logger.error("Błąd procesu CLI Claude Code: %s", blad)
        yield {
            "typ": "blad",
            "tekst": (
                "Nie udało się uruchomić silnika agentowego. Sprawdź, czy klucz "
                "ANTHROPIC_API_KEY jest ustawiony w pliku .env i czy jest poprawny."
            ),
        }
    finally:
        zakonczono.set()


async def testowe_wywolanie(katalog_danych: Path) -> AsyncIterator[dict[str, Any]]:
    """Jeden pełny przelot przez SDK: potwierdza, że CLI startuje, czyta klucz
    API ze środowiska i zwraca odpowiedź. Używane przez ekran diagnostyki
    (Faza 1) — jedyne miejsce w tej fazie, które faktycznie woła model.
    """
    opcje = zbuduj_opcje(katalog_danych, PROMPT_TESTOWY)
    yield {"typ": "status", "tekst": "Uruchamiam CLI Claude Code…"}
    async for zdarzenie in _przetworz_zapytanie(opcje, "Testowe wywołanie startowe."):
        yield zdarzenie


async def uruchom_redaktor(
    katalog_danych: Path, brief: str, material: str = ""
) -> AsyncIterator[dict[str, Any]]:
    """Tryb Redaktor (SPEC 8.2): generuje 3 warianty LI + FB + brief graficzny
    + braki na podstawie briefu operatora.

    Zasady stylu, fakty o firmie i posty do kalibracji dostaje wprost
    w poleceniu — nie szuka ich narzędziami. Zostawiamy tylko podagenta
    badawczego, bo jego wywołanie ma sens wyłącznie przy tematach o osobach,
    firmach i wydarzeniach.
    """
    opcje = zbuduj_opcje(
        katalog_danych,
        PROMPT_REDAKTOR,
        agents={"researcher": SUBAGENT_RESEARCHER},
        narzedzia=["Agent"],
    )
    czesci = [f"Dzisiejsza data: {date.today().isoformat()}."]
    if material.strip():
        czesci.append(f"\n{material.strip()}")
    czesci.append(f"\n### Brief od operatora\n{brief.strip()}")

    yield {"typ": "status", "tekst": "Piszę warianty…"}
    async for zdarzenie in _przetworz_zapytanie(opcje, "\n".join(czesci)):
        yield zdarzenie


async def uruchom_asystenta(katalog_danych: Path, wiadomosc: str) -> AsyncIterator[dict[str, Any]]:
    """Tryb Asystent (SPEC-frontend sekcja 5): czat świadomy stanu aplikacji
    (czyta pliki, nie zgaduje). Nie pisze postów sam — kosztowną operację
    (Redaktor) zgłasza jako zdarzenie "propozycja" do zatwierdzenia przez
    operatora, zamiast generować treść od razu."""
    # Asystent nie pisze postów ani nie robi researchu — odpowiada na pytania
    # o stan aplikacji i zgłasza propozycje. Bez sieci i bez podagenta jego
    # kontekst (a więc i koszt każdej odpowiedzi) jest wyraźnie mniejszy.
    opcje = zbuduj_opcje(
        katalog_danych,
        PROMPT_ASYSTENT,
        narzedzia=NARZEDZIA_BEZ_SIECI,
        dodatkowe_dozwolone_narzedzia=[NAZWA_NARZEDZIA_PROPOZYCJI],
        mcp_servers={"asystent": SERWER_ASYSTENTA},
        limit_usd=0.25,
    )
    async for zdarzenie in _przetworz_zapytanie(
        opcje, wiadomosc, narzedzie_propozycji=NAZWA_NARZEDZIA_PROPOZYCJI
    ):
        yield zdarzenie


# Znaczniki, po których backend rozpoznaje w odpowiedzi gotową propozycję
# treści pliku. Agent nie ma prawa zapisu do warstwy jakości (SPEC 8.3:
# „nie modyfikuje tego pliku samodzielnie"), więc propozycja wraca tekstem,
# a zapisuje ją dopiero operatorka jednym kliknięciem.
ZNACZNIK_POCZATKU_PROPOZYCJI = "=== PROPOZYCJA: "
ZNACZNIK_KONCA_PROPOZYCJI = "=== KONIEC PROPOZYCJI ==="

PROMPT_WYWIAD = (
    "Prowadzisz rozmowę z Magdą — osobą nietechniczną, która zajmuje się "
    "contentem Forces DC (fit-out data center, region nordycki). Celem "
    "rozmowy jest domknięcie dwóch rzeczy: **jak Forces DC pisze** (głos "
    "marki) oraz **jakie typy postów publikuje i jak są zbudowane** "
    "(rodzaje postów).\n\n"
    "Piszesz po polsku, bez żargonu technicznego: nie mów „prompt”, „agent”, "
    f"„skill”, „plik SKILL.md”. Mów „zasady stylu”, „asystent”. {GRANICA_NDA}\n\n"
    "JAK PROWADZISZ ROZMOWĘ\n"
    "- Zaczynasz od krótkiego podsumowania tego, co już widzisz w "
    "opublikowanych postach: ton, długość, sposób zwracania się do "
    "czytelnika, hashtagi. Konkretnie, z przykładami i liczbami — nie "
    "ogólnikami. To pokazuje, że nie pytasz o rzeczy, które już wiesz.\n"
    "- Potem zadajesz JEDNO pytanie i czekasz na odpowiedź. Nigdy kilku "
    "naraz — to najczęstszy błąd i przez niego takie rozmowy się urywają.\n"
    "- Jeśli odpowiedź na pytanie widać już w korpusie, nie pytaj od zera: "
    "powiedz, co odczytałeś, i poproś o potwierdzenie albo poprawkę.\n"
    "- Pytania i ich kolejność masz podane w poleceniu. Możesz pominąć te, "
    "na które korpus już odpowiada, ale powiedz wtedy, że je pomijasz i "
    "dlaczego.\n"
    "- Po każdej odpowiedzi krótko potwierdź, co z niej zapisałeś, zanim "
    "zadasz kolejne pytanie.\n"
    "- Nie zgaduj. Jeśli czegoś nie wiesz, a operatorka nie odpowiedziała, "
    "zostaw w propozycji `[DO UZUPEŁNIENIA: co dokładnie]`.\n\n"
    "ZAKOŃCZENIE ROZMOWY\n"
    "Gdy przejdziesz wszystkie pytania albo operatorka powie, że chce "
    "kończyć, zaproponuj gotowe treści obu plików. Format jest sztywny — "
    "aplikacja rozpoznaje po nim propozycję i pokazuje przycisk zapisu:\n\n"
    f"{ZNACZNIK_POCZATKU_PROPOZYCJI}glos-marki ===\n"
    "(pełna treść pliku „Głos marki” w Markdown, gotowa do zapisania — "
    "nie fragment, nie lista zmian)\n"
    f"{ZNACZNIK_KONCA_PROPOZYCJI}\n\n"
    f"{ZNACZNIK_POCZATKU_PROPOZYCJI}rodzaje-postow ===\n"
    "(pełna treść pliku „Rodzaje postów” w Markdown)\n"
    f"{ZNACZNIK_KONCA_PROPOZYCJI}\n\n"
    "Każdy plik zaczynaj nagłówkiem YAML w postaci:\n"
    "---\nname: brand-voice\ndescription: (jedno zdanie po polsku)\n---\n"
    "(dla rodzajów postów: `name: schematy-postow`). Bez tego nagłówka "
    "asystent nie odczyta pliku.\n\n"
    "Propozycję pokazujesz raz, na końcu. Nie wypisuj jej po każdym pytaniu. "
    "SAM NICZEGO NIE ZAPISUJESZ — nie masz do tego narzędzi i tak ma być: "
    "operatorka zatwierdza treść w aplikacji."
)


async def uruchom_wywiad(
    katalog_danych: Path,
    material: str,
    historia: list[dict[str, str]],
    zakoncz: bool = False,
) -> AsyncIterator[dict[str, Any]]:
    """Tryb Wywiad (SPEC 8.3): rozmowa domykająca głos marki i rodzaje postów.

    Bez narzędzi — komplet (pytania, obecna treść plików, korpus) dostaje
    wstrzyknięty. Historia rozmowy wraca z przeglądarki przy każdej turze,
    bo pojedyncze wywołanie SDK nie pamięta poprzednich.
    """
    opcje = zbuduj_opcje(
        katalog_danych,
        PROMPT_WYWIAD,
        bez_narzedzi=True,
        limit_usd=LIMIT_USD_WYWIAD,
        maks_tur=3,
    )

    czesci = [material]
    if historia:
        rozmowa = "\n\n".join(
            f"{'OPERATORKA' if wpis['rola'] == 'operator' else 'TY'}: {wpis['tresc'].strip()}"
            for wpis in historia
        )
        czesci.append(f"### Dotychczasowa rozmowa\n{rozmowa}")
        if zakoncz:
            # Prośba o zakończenie w treści czatu nie wystarczała — model
            # dopytywał mimo niej. Operatorka kliknęła przycisk „Zakończ",
            # więc ta tura ma zwrócić propozycje i nic poza nimi.
            czesci.append(
                "### TO JEST OSTATNIA TURA ROZMOWY\n"
                "Operatorka zakończyła wywiad. NIE zadawaj już żadnego pytania, "
                "nawet doprecyzowującego, i nie proponuj kontynuacji. Zwróć "
                "krótkie zdanie podsumowania, a po nim obie propozycje plików "
                "w podanym formacie ze znacznikami. Wszystko, czego nie ustaliliście, "
                "wpisz jako [DO UZUPEŁNIENIA: co dokładnie] — to poprawny wynik, "
                "nie brak. Odpowiedź bez obu propozycji jest błędem."
            )
        else:
            czesci.append(
                "Kontynuuj rozmowę od tego miejsca: odnieś się do ostatniej "
                "wypowiedzi operatorki i zadaj kolejne pytanie."
            )
    else:
        czesci.append(
            "### Zacznij rozmowę\n"
            "Podsumuj, co widzisz w opublikowanych postach, i zadaj pierwsze pytanie."
        )

    yield {"typ": "status", "tekst": "Zbieram, co już wiadomo…"}
    async for zdarzenie in _przetworz_zapytanie(opcje, "\n\n".join(czesci)):
        yield zdarzenie


PROMPT_PRZEGLAD_BRANZY = (
    "Jesteś researcherem branżowym Forces DC (fit-out data center, region "
    f"nordycki). {GRANICA_NDA} {ZAKAZ_TRESCI_PRAWNYCH}\n\n"
    "Zadanie: sprawdź, co dzieje się teraz w branży data center w Norwegii "
    "i regionie nordyckim, i zapisz to w formie, z której da się potem "
    "budować plan miesiąca i pisać posty. Korzystaj ze źródeł podanych "
    "w poleceniu — zaczynaj od poziomu 1.\n\n"
    "Piszesz po polsku, nawet jeśli źródła są po angielsku albo norwesku. "
    "Przy KAŻDYM fakcie podaj adres, z którego pochodzi. Fakt bez adresu jest "
    "bezwartościowy — pomiń go zamiast zgadywać. Nie przeliczaj i nie "
    "zaokrąglaj liczb.\n\n"
    "Zwróć DOKŁADNIE takie sekcje i nic poza nimi:\n\n"
    "## O czym jest\n"
    "Dwa–trzy zdania: co się w tej chwili dzieje w branży, jednym akapitem.\n\n"
    "## Fakty i liczby\n"
    "Lista konkretów z ostatnich ~30 dni: dane, decyzje, inwestycje, zmiany "
    "regulacyjne. Każdy punkt z adresem źródła i datą.\n\n"
    "## Kalendarz\n"
    "Nadchodzące wydarzenia branżowe z datami i miejscem. Jeśli nie znajdziesz "
    "żadnego, napisz to wprost.\n\n"
    "## Tematy na posty dla Forces DC\n"
    "3–6 zajawek: konkretny kąt, z którego Forces DC może się odnieść ze swojej "
    "perspektywy — wykonawcy fit-outu i dostawcy zespołów. Każda zajawka to "
    "zdanie tematu plus zdanie, dlaczego akurat ta firma ma tu coś do "
    "powiedzenia. Odrzucaj tematy, w których byłaby tylko komentatorem.\n\n"
    "## Czego tu nie ma\n"
    "Czego nie udało się ustalić, a przydałoby się do postów."
)


async def zrob_przeglad_branzy(
    katalog_danych: Path, zrodla: str
) -> AsyncIterator[dict[str, Any]]:
    """Research branżowy uruchamiany na żądanie, niezależnie od planu.

    Wynik zapisuje backend do `artykuly/wyciagi/` — tam, gdzie leżą wyciągi
    z dokumentów, więc trafia automatycznie i do planu, i do każdego posta.
    Dzięki temu research jest opłacony raz, a nie przy każdym użyciu.
    """
    opcje = zbuduj_opcje(
        katalog_danych,
        PROMPT_PRZEGLAD_BRANZY,
        agents={"researcher": SUBAGENT_RESEARCHER},
        dodatkowe_dozwolone_narzedzia=["WebSearch", "WebFetch"],
        narzedzia=["Agent", "WebSearch", "WebFetch"],
        limit_usd=LIMIT_USD_PRZEGLAD,
        maks_tur=20,
    )
    polecenie = (
        f"Dzisiejsza data: {date.today().isoformat()}.\n\n"
        f"### Źródła, z których masz korzystać\n{zrodla}\n\n"
        "Zrób przegląd branży i zwróć go w opisanym formacie."
    )
    yield {"typ": "status", "tekst": "Przeglądam źródła branżowe…"}
    async for zdarzenie in _przetworz_zapytanie(opcje, polecenie):
        yield zdarzenie


PROMPT_POPRAWKA = (
    "Jesteś redaktorem treści LinkedIn dla Forces DC (fit-out data center, "
    "Norwegia). Dostajesz gotowy post i jedno polecenie od operatorki, co "
    "w nim zmienić. Twoim zadaniem jest przepisać ten post zgodnie z "
    "poleceniem.\n\n"
    f"{GRANICA_NDA} {ZAKAZ_TRESCI_PRAWNYCH}\n\n"
    "Zasady:\n"
    "- Zmieniaj tylko to, o co prosi polecenie. Reszta tekstu ma zostać "
    "rozpoznawalnie tym samym postem, nie nową wersją napisaną od zera.\n"
    "- Zachowaj istniejące znaczniki [DO UZUPEŁNIENIA: ...], chyba że "
    "polecenie wprost każe je usunąć. Nie wymyślaj faktów, liczb ani nazw, "
    "żeby je zastąpić.\n"
    "- Trzymaj się zasad stylu podanych w poleceniu.\n\n"
    "ODPOWIEDŹ: zwróć wyłącznie gotową treść posta. Bez wstępu, bez "
    "komentarza, bez cudzysłowów, bez nagłówków markdown i bez wyjaśniania, "
    "co zmieniłeś. Sama treść, gotowa do wklejenia na LinkedIn."
)


async def popraw_wariant(
    katalog_danych: Path, tresc: str, polecenie: str, zasady_stylu: str = ""
) -> AsyncIterator[dict[str, Any]]:
    """Przepisuje jeden wariant posta według polecenia operatorki
    (SPEC-frontend 7, „Poprawianie").

    Tryb bez narzędzi i z niskim sufitem kosztu: to ma być szybka pętla
    poprawek, nie ponowne generowanie. Zasady stylu wstrzykujemy w polecenie,
    zamiast pozwalać modelowi ich szukać — oszczędza to kilka tur.
    """
    opcje = zbuduj_opcje(
        katalog_danych,
        PROMPT_POPRAWKA,
        bez_narzedzi=True,
        limit_usd=0.20,
        maks_tur=3,
    )
    czesci = []
    if zasady_stylu.strip():
        czesci.append(f"ZASADY STYLU:\n{zasady_stylu.strip()}\n")
    czesci.append(f"OBECNA TREŚĆ POSTA:\n{tresc.strip()}\n")
    czesci.append(f"CO ZMIENIĆ:\n{polecenie.strip()}")

    yield {"typ": "status", "tekst": "Poprawiam tekst…"}
    async for zdarzenie in _przetworz_zapytanie(opcje, "\n".join(czesci)):
        yield zdarzenie


PROMPT_WYCIAG = (
    "Jesteś researcherem contentowym Forces DC (fit-out data center, region "
    "nordycki). Dostajesz jeden dokument — artykuł, raport branżowy albo "
    "notatkę — wgrany przez operatorkę. Przeczytaj go w całości narzędziem "
    f"Read i zrób z niego wyciąg do dalszej pracy nad treścią. {GRANICA_NDA} "
    f"{ZAKAZ_TRESCI_PRAWNYCH}\n\n"
    "Piszesz po polsku, nawet jeśli dokument jest po angielsku albo norwesku.\n\n"
    "Zwróć DOKŁADNIE takie sekcje, w tej kolejności, i nic poza nimi:\n\n"
    "## O czym jest\n"
    "Dwa–trzy zdania: co to za dokument, kto go wydał, z kiedy pochodzi.\n\n"
    "## Fakty i liczby\n"
    "Lista konkretów, które da się zacytować w poście: dane liczbowe, daty, "
    "nazwy instytucji, trendy. Przy każdym podaj, skąd w dokumencie pochodzi "
    "(rozdział, strona albo cytat). Nie zaokrąglaj i nie przeliczaj liczb — "
    "przepisz je tak, jak są. Jeśli dokument czegoś nie podaje, nie zgaduj.\n\n"
    "## Tematy na posty dla Forces DC\n"
    "3–6 zajawek: konkretny kąt, z którego Forces DC może się do tego odnieść "
    "ze swojej perspektywy — wykonawcy fit-outu i dostawcy zespołów. Każda "
    "zajawka to jedno zdanie tematu plus jedno zdanie, dlaczego akurat "
    "Forces DC ma tu coś do powiedzenia. Odrzucaj tematy, w których firma "
    "byłaby tylko komentatorem cudzych newsów.\n\n"
    "## Czego tu nie ma\n"
    "Czego w dokumencie zabrakło, a przydałoby się do postów — żeby "
    "operatorka wiedziała, o co dopytać w firmie.\n\n"
    "Nie streszczaj dokumentu zdanie po zdaniu i nie przepisuj całych "
    "akapitów. Wyciąg ma być krótszy niż dokument i ma się nadawać do "
    "wielokrotnego użycia."
)


async def zrob_wyciag_z_dokumentu(
    katalog_danych: Path, sciezka_wzgledna: str
) -> AsyncIterator[dict[str, Any]]:
    """Jednorazowo czyta wgrany dokument i zwraca z niego wyciąg.

    Płacimy za przeczytanie dokumentu raz, przy wgraniu, a nie przy każdym
    poście: wyciąg ma kilka kilobajtów i to on trafia potem do redaktora
    i do planu. Bez tego albo dokument nie jest w ogóle używany, albo każdy
    post ciągnie za sobą cały raport.
    """
    opcje = zbuduj_opcje(
        katalog_danych,
        PROMPT_WYCIAG,
        narzedzia=["Read"],
        limit_usd=LIMIT_USD_WYCIAG,
        maks_tur=8,
    )
    polecenie = (
        f"Dokument do przeczytania: `{sciezka_wzgledna}` (ścieżka względem "
        "katalogu roboczego). Przeczytaj go narzędziem Read i zwróć wyciąg "
        "w opisanym formacie."
    )
    yield {"typ": "status", "tekst": "Czytam dokument…"}
    async for zdarzenie in _przetworz_zapytanie(opcje, polecenie):
        yield zdarzenie


PROMPT_HASLO_GRAFIKI = (
    "Jesteś dyrektorem artystycznym pracującym dla Forces DC (fit-out data "
    "center, Norwegia). Dostajesz treść posta na LinkedIn. Twoim zadaniem "
    "jest wybrać tekst na grafikę, która będzie towarzyszyć temu postowi.\n\n"
    f"{GRANICA_NDA} {ZAKAZ_TRESCI_PRAWNYCH}\n\n"
    "Zasady:\n"
    "- HASŁO: najwyżej 60 znaków. Ma działać samo, bez czytania posta, i "
    "zatrzymywać scrollowanie. Wyciągnij najmocniejszą myśl z tekstu — nie "
    "streszczaj całości i nie powtarzaj pierwszego zdania posta słowo w słowo.\n"
    "- PODTYTUŁ: najwyżej 80 znaków, może być pusty. Doprecyzowuje hasło.\n"
    "- Nie używaj liczb, nazw ani faktów, których nie ma w poście. Jeśli post "
    "zawiera znaczniki [DO UZUPEŁNIENIA], nie przenoś ich na grafikę — po "
    "prostu ich nie używaj.\n"
    "- Bez cudzysłowów wokół hasła, bez emotikon, bez hashtagów.\n"
    "- TEKST ALTERNATYWNY: jedno zdanie opisujące grafikę dla osób "
    "korzystających z czytnika ekranu.\n\n"
    "ODPOWIEDŹ: dokładnie trzy linie, bez żadnego wstępu ani komentarza:\n"
    "HASLO: <treść>\n"
    "PODTYTUL: <treść albo puste>\n"
    "ALT: <treść>"
)


def rozbierz_odpowiedz_o_grafice(tekst: str) -> dict[str, str]:
    """Wyciąga trzy pola z odpowiedzi modelu. Format jest prosty i sztywny,
    więc nie ma tu parsowania JSON-a, które psuje się przy każdym dodatkowym
    zdaniu od modelu."""
    wynik = {"haslo": "", "podtytul": "", "alt": ""}
    etykiety = {"HASLO": "haslo", "HASŁO": "haslo", "PODTYTUL": "podtytul", "PODTYTUŁ": "podtytul", "ALT": "alt"}
    for linia in tekst.splitlines():
        etykieta, _, wartosc = linia.partition(":")
        klucz = etykiety.get(etykieta.strip().upper())
        if klucz and not wynik[klucz]:
            wynik[klucz] = wartosc.strip().strip('"„”')
    return wynik


async def zaproponuj_haslo_grafiki(
    katalog_danych: Path, tresc_posta: str, brief_graficzny: str = ""
) -> AsyncIterator[dict[str, Any]]:
    """Wybiera tekst na grafikę do posta. Tryb bez narzędzi i z niskim
    sufitem — to jeden krótki wybór redakcyjny, nie generowanie treści."""
    opcje = zbuduj_opcje(
        katalog_danych,
        PROMPT_HASLO_GRAFIKI,
        bez_narzedzi=True,
        limit_usd=0.15,
        maks_tur=3,
    )
    czesci = [f"TREŚĆ POSTA:\n{tresc_posta.strip()}"]
    if brief_graficzny.strip():
        czesci.append(f"\nBRIEF GRAFICZNY OD REDAKTORA (może zawierać gotowy pomysł na hasło):\n{brief_graficzny.strip()}")

    yield {"typ": "status", "tekst": "Dobieram hasło na grafikę…"}
    async for zdarzenie in _przetworz_zapytanie(opcje, "\n".join(czesci)):
        yield zdarzenie


async def uruchom_stratega(
    katalog_danych: Path, miesiac: str, uwagi: str = ""
) -> AsyncIterator[dict[str, Any]]:
    """Tryb Strateg (SPEC 8.1): buduje plan contentu na miesiąc i zapisuje
    go do plan/RRRR-MM.md."""
    opcje = zbuduj_opcje(
        katalog_danych,
        PROMPT_STRATEG,
        agents={"researcher": SUBAGENT_RESEARCHER},
        narzedzia=NARZEDZIA_Z_PODAGENTEM,
        limit_usd=LIMIT_USD_PLAN,
    )
    tresc_polecenia = (
        f"Dzisiejsza data: {date.today().isoformat()}.\n"
        f"Zbuduj plan na miesiąc: {miesiac}.\n"
    )
    if uwagi.strip():
        tresc_polecenia += f"\nUwagi od operatora:\n{uwagi.strip()}\n"

    yield {"typ": "status", "tekst": "Czytam źródła branżowe i materiały z firmy…"}
    async for zdarzenie in _przetworz_zapytanie(
        opcje, tresc_polecenia, obserwuj_zapis_z_prefiksem="plan/"
    ):
        yield zdarzenie
