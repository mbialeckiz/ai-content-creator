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

# Nazwy pól `ClaudeAgentOptions`, których faktycznie używa ten moduł.
# `app/diagnostyka.py` porównuje ten zbiór z introspekcją zainstalowanej
# wersji SDK — jeśli nazwa zniknie albo zmieni się, diagnostyka to zgłosi
# zamiast dowiadywać się o tym dopiero przy pierwszym wywołaniu modelu.
PARAMETRY_UZYWANE_PRZEZ_KOD = frozenset(
    {
        "cwd",
        "setting_sources",
        "skills",
        "allowed_tools",
        "disallowed_tools",
        "system_prompt",
        "can_use_tool",
        "model",
        "agents",
        "mcp_servers",
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


def zbuduj_opcje(
    katalog_danych: Path,
    system_prompt: str,
    *,
    model: str | None = None,
    agents: dict[str, Any] | None = None,
    dodatkowe_dozwolone_narzedzia: list[str] | None = None,
    mcp_servers: dict[str, Any] | None = None,
) -> ClaudeAgentOptions:
    """Buduje `ClaudeAgentOptions` wspólne dla wszystkich trybów agenta."""
    return ClaudeAgentOptions(
        cwd=katalog_danych,
        setting_sources=["project"],
        skills="all",
        allowed_tools=DOZWOLONE_NARZEDZIA + (dodatkowe_dozwolone_narzedzia or []),
        disallowed_tools=ZABRONIONE_NARZEDZIA,
        system_prompt=system_prompt,
        can_use_tool=_zbuduj_zezwalacz(katalog_danych),
        model=model or os.environ.get("MODEL") or None,
        agents=agents,
        mcp_servers=mcp_servers or {},
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
    "Jesteś redaktorem treści LinkedIn dla Forces DC Content Studio "
    "(fit-out data center, Norwegia). Piszesz na podstawie briefu od "
    "operatora. "
    f"{GRANICA_NDA} {ZAKAZ_TRESCI_PRAWNYCH} "
    "Brakujące fakty (liczby, lokalizacje, nazwiska, daty) oznaczaj jako "
    "`[DO UZUPEŁNIENIA: co dokładnie]` — nigdy nie zgaduj i nie wymyślaj "
    "szczegółów, nawet jeśli brzmiałyby wiarygodnie.\n\n"
    "Przebieg (SPEC 8.2):\n"
    "1. Jeśli temat dotyczy konkretnej osoby, firmy lub wydarzenia, użyj "
    "podagenta `researcher` (narzędzie Agent, subagent_type='researcher').\n"
    "2. Przeczytaj zasady stylu i pasujący schemat posta z zasad stylu "
    "(katalog .claude/skills/ — brand-voice i schematy-postow) oraz listę "
    "zakazanych zwrotów (baza-wiedzy/zakazane-zwroty.md).\n"
    "3. Skalibruj się: przeczytaj 3–5 postów z korpusu (korpus/linkedin/) "
    "tego samego typu co temat, z priorytetem dla wysokiego pola `reakcje` "
    "w nagłówku YAML. Jeśli korpus jest pusty albo nie ma postów pasującego "
    "typu, napisz to wprost w sekcji Braki zamiast pisać bez wzorca po cichu.\n"
    "4. Wygeneruj DOKŁADNIE trzy warianty LinkedIn (różne podejścia "
    "redakcyjne — np. faktograficzny / przez problem / przez osobę — nie "
    "kosmetyczne różnice tego samego tekstu), wersję na Facebooka (skrót "
    "~30%, łagodniejszy żargon) i brief graficzny (co potrzebuje grafik: "
    "opis, format, tekst na obrazie, sugerowany szablon).\n"
    "5. Zapisz wynik narzędziem Write pod ścieżką WZGLĘDNĄ "
    "`output/RRRR-MM-DD_krotki-slug-tematu.md` (użyj podanej dzisiejszej "
    "daty). WAŻNE: podaj DOKŁADNIE tę względną ścieżkę, zaczynającą się od "
    "'output/' — nie dodawaj przed nią żadnego katalogu ani ścieżki "
    "bezwzględnej (np. '/home/...'); Twój katalog roboczy już wskazuje na "
    "właściwe miejsce. Jeśli zapis zostanie odrzucony, spróbuj ponownie z "
    "krótszą, w pełni względną ścieżką zaczynającą się od 'output/', zamiast "
    "powtarzać tę samą odrzuconą ścieżkę. Użyj DOKŁADNIE tej struktury "
    "nagłówków markdown, bo inny program parsuje ten plik:\n\n"
    "## Wariant 1\n**Podejście:** <jedno-dwa słowa>\n<treść posta>\n\n"
    "## Wariant 2\n**Podejście:** <jedno-dwa słowa>\n<treść posta>\n\n"
    "## Wariant 3\n**Podejście:** <jedno-dwa słowa>\n<treść posta>\n\n"
    "## Facebook\n<treść posta na Facebooka>\n\n"
    "## Brief graficzny\n<opis dla grafika>\n\n"
    "## Braki\n<lista punktowana braków, każdy jako osobna linia zaczynająca "
    "się od '- ', albo dokładnie 'Brak braków.' jeśli niczego nie brakuje>\n"
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
    "Stan aplikacji poznajesz, czytając pliki w katalogu roboczym: korpus "
    "(korpus/linkedin/*.md), plan miesiąca (plan/RRRR-MM.md — jeśli nie "
    "istnieje, tryb budowania planu jeszcze nie jest dostępny w tej wersji "
    "narzędzia, powiedz to wprost), materiały firmowe "
    "(input-firmowy/RRRR-MM.md), zasady stylu (.claude/skills/), fakty o "
    "firmie i zakazane zwroty (baza-wiedzy/). Odpowiadaj na podstawie tego, "
    "co faktycznie jest w plikach — jeśli czegoś brakuje albo katalog jest "
    "pusty, powiedz to wprost zamiast zgadywać.\n\n"
    f"{GRANICA_NDA} {ZAKAZ_TRESCI_PRAWNYCH}\n\n"
    "Jeśli operator prosi o napisanie albo wygenerowanie posta: NIE pisz "
    "treści sam. Wywołaj narzędzie zaproponuj_napisanie_posta z argumentami "
    "brief (samodzielny, konkretny opis tematu — tak, żeby redaktor mógł "
    "napisać post bez dodatkowych pytań), zasoby (krótki opis czego "
    "użyjesz, np. 'zasady stylu, korpus, wyszukiwanie w sieci') i "
    "szacowane_tokeny (Twój przybliżony szacunek jako liczba całkowita — to "
    "tylko orientacyjna wartość, ma prawo być niedokładna). Jeśli prośba "
    "dotyczy budowania planu miesiąca, wyjaśnij, że ta funkcja pojawi się w "
    "kolejnej fazie narzędzia, zamiast wywoływać to narzędzie."
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
                for blok in wiadomosc.content:
                    if isinstance(blok, TextBlock):
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
                yield {
                    "typ": "wynik",
                    "bledny": wiadomosc.is_error,
                    "tury": wiadomosc.num_turns,
                    "koszt_usd": wiadomosc.total_cost_usd,
                    "uzycie": wiadomosc.usage,
                    "sciezka_pliku": sciezka_zapisu,
                }
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


async def uruchom_redaktor(katalog_danych: Path, brief: str) -> AsyncIterator[dict[str, Any]]:
    """Tryb Redaktor (SPEC 8.2): generuje 3 warianty LI + FB + brief graficzny
    + braki na podstawie briefu operatora, zapisuje wynik do output/."""
    opcje = zbuduj_opcje(
        katalog_danych,
        PROMPT_REDAKTOR,
        agents={"researcher": SUBAGENT_RESEARCHER},
    )
    tresc_polecenia = (
        f"Dzisiejsza data: {date.today().isoformat()}.\n\n"
        f"Brief od operatora:\n{brief}"
    )
    yield {"typ": "status", "tekst": "Czytam zasady stylu i schematy postów…"}
    async for zdarzenie in _przetworz_zapytanie(
        opcje, tresc_polecenia, obserwuj_zapis_z_prefiksem="output/"
    ):
        yield zdarzenie


async def uruchom_asystenta(katalog_danych: Path, wiadomosc: str) -> AsyncIterator[dict[str, Any]]:
    """Tryb Asystent (SPEC-frontend sekcja 5): czat świadomy stanu aplikacji
    (czyta pliki, nie zgaduje). Nie pisze postów sam — kosztowną operację
    (Redaktor) zgłasza jako zdarzenie "propozycja" do zatwierdzenia przez
    operatora, zamiast generować treść od razu."""
    opcje = zbuduj_opcje(
        katalog_danych,
        PROMPT_ASYSTENT,
        agents={"researcher": SUBAGENT_RESEARCHER},
        dodatkowe_dozwolone_narzedzia=[NAZWA_NARZEDZIA_PROPOZYCJI],
        mcp_servers={"asystent": SERWER_ASYSTENTA},
    )
    async for zdarzenie in _przetworz_zapytanie(
        opcje, wiadomosc, narzedzie_propozycji=NAZWA_NARZEDZIA_PROPOZYCJI
    ):
        yield zdarzenie
