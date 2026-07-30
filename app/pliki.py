"""CRUD i walidacja plików `.md` (CLAUDE.md). Bez styczności z SDK."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

NAGLOWEK_NDA = "## Czego NIE wolno publikować"
WZORZEC_POGRUBIENIA = re.compile(r"\*\*(.+?)\*\*")

NAGLOWKI_POSTA = ("Wariant 1", "Wariant 2", "Wariant 3", "Facebook", "Brief graficzny", "Braki")
WZORZEC_PODEJSCIA = re.compile(r"^\*\*Podejście:\*\*\s*(.+)$", re.MULTILINE)

ZNACZNIKI_LUK = ("[DO UZUPEŁNIENIA", "[DO POTWIERDZENIA")

# Warstwa jakości — pliki, które operatorka edytuje przez ekran „Styl"
# (SPEC-frontend 9). Klucz to identyfikator używany w API; ścieżka jest
# ustalona po stronie serwera, żeby żądanie z przeglądarki nie mogło wskazać
# dowolnego pliku na dysku (nazwy plików nie pojawiają się też w UI —
# operatorka widzi tylko nazwę i opis po polsku).
PLIKI_WARSTWY_JAKOSCI: dict[str, dict[str, str]] = {
    "glos-marki": {
        "nazwa": "Głos marki",
        "opis": "Jak Forces DC pisze: ton, zasady, czego unikać",
        "sciezka": ".claude/skills/brand-voice/SKILL.md",
    },
    "rodzaje-postow": {
        "nazwa": "Rodzaje postów",
        "opis": "Struktura i długość każdego typu posta",
        "sciezka": ".claude/skills/schematy-postow/SKILL.md",
    },
    "zasady-planowania": {
        "nazwa": "Zasady planowania",
        "opis": "Jak asystent buduje plan miesiąca",
        "sciezka": ".claude/skills/strategia-contentu/SKILL.md",
    },
    "zakazane-zwroty": {
        "nazwa": "Zakazane zwroty",
        "opis": "Lista zwrotów, które nie mają wyjść",
        "sciezka": "baza-wiedzy/zakazane-zwroty.md",
    },
    "fakty-o-firmie": {
        "nazwa": "Fakty o firmie",
        "opis": "Co asystent wie o Forces DC i czego nie wolno publikować",
        "sciezka": "baza-wiedzy/forces-dc-fakty.md",
    },
    "zrodla-branzowe": {
        "nazwa": "Źródła branżowe",
        "opis": "Skąd asystent bierze newsy z branży",
        "sciezka": "baza-wiedzy/zrodla-branzowe.md",
    },
}


def policz_luki(tresc: str) -> int:
    """Liczy miejsca wymagające uzupełnienia przez człowieka (SPEC-frontend 9)."""
    return sum(tresc.count(znacznik) for znacznik in ZNACZNIKI_LUK)


def lista_plikow_jakosci(katalog_danych: Path) -> list[dict[str, object]]:
    """Lista plików sterujących na ekran „Styl" — bez treści, z licznikiem luk."""
    wynik: list[dict[str, object]] = []
    for identyfikator, opis_pliku in PLIKI_WARSTWY_JAKOSCI.items():
        plik = katalog_danych / opis_pliku["sciezka"]
        istnieje = plik.is_file()
        tresc = plik.read_text(encoding="utf-8") if istnieje else ""
        wynik.append(
            {
                "id": identyfikator,
                "nazwa": opis_pliku["nazwa"],
                "opis": opis_pliku["opis"],
                "istnieje": istnieje,
                "luki": policz_luki(tresc),
            }
        )
    return wynik


def czytaj_plik_jakosci(katalog_danych: Path, identyfikator: str) -> str:
    """Treść pliku sterującego. `KeyError` dla nieznanego identyfikatora."""
    opis_pliku = PLIKI_WARSTWY_JAKOSCI[identyfikator]
    plik = katalog_danych / opis_pliku["sciezka"]
    return plik.read_text(encoding="utf-8") if plik.is_file() else ""


def zapisz_plik_jakosci(katalog_danych: Path, identyfikator: str, tresc: str) -> None:
    """Zapisuje plik sterujący. Zmiana działa od następnego pytania do
    asystenta — silnik czyta te pliki z dysku przy każdym wywołaniu, więc
    restart serwera nie jest potrzebny (SPEC sekcja 11)."""
    opis_pliku = PLIKI_WARSTWY_JAKOSCI[identyfikator]
    plik = katalog_danych / opis_pliku["sciezka"]
    plik.parent.mkdir(parents=True, exist_ok=True)
    plik.write_text(tresc, encoding="utf-8")


def czytaj_frazy_nda(katalog_danych: Path) -> list[str]:
    """Wyciąga listę fraz z sekcji "Czego NIE wolno publikować" w
    baza-wiedzy/forces-dc-fakty.md (SPEC 10.2–10.3). Pozycje to punkty
    listy markdown; pogrubiona część linii to dokładna fraza do wykrycia,
    reszta linii to komentarz administratora i jest pomijana."""
    plik = katalog_danych / "baza-wiedzy" / "forces-dc-fakty.md"
    if not plik.exists():
        return []

    tresc = plik.read_text(encoding="utf-8")
    poczatek = tresc.find(NAGLOWEK_NDA)
    if poczatek == -1:
        return []
    sekcja = tresc[poczatek + len(NAGLOWEK_NDA) :]
    koniec = sekcja.find("\n## ")
    if koniec != -1:
        sekcja = sekcja[:koniec]

    frazy = []
    for linia in sekcja.splitlines():
        linia = linia.strip()
        if not linia.startswith("-"):
            continue
        linia = linia.lstrip("- ").strip()
        dopasowanie = WZORZEC_POGRUBIENIA.search(linia)
        fraza = dopasowanie.group(1).strip() if dopasowanie else linia
        if fraza:
            frazy.append(fraza)
    return frazy


def wykryj_fraze_nda(tekst: str, katalog_danych: Path) -> str | None:
    """Zwraca pierwszą frazę objętą NDA znalezioną w `tekst`, albo None.

    Dopasowanie bez rozróżniania wielkości liter — lepiej wykryć za dużo
    niż przepuścić nazwę klienta (SPEC 10.2, blocker wydania)."""
    tekst_malymi = tekst.lower()
    for fraza in czytaj_frazy_nda(katalog_danych):
        if fraza.lower() in tekst_malymi:
            return fraza
    return None


@dataclass
class WariantPosta:
    etykieta: str
    tresc: str
    znaki: int


@dataclass
class WygenerowanyPost:
    warianty: list[WariantPosta] = field(default_factory=list)
    facebook: str = ""
    brief_graficzny: str = ""
    braki: list[str] = field(default_factory=list)
    kompletny: bool = True
    surowy_markdown: str = ""


def _wytnij_sekcje(tresc: str) -> dict[str, str]:
    """Dzieli markdown na sekcje wg nagłówków `## Nazwa`."""
    sekcje: dict[str, str] = {}
    czesci = re.split(r"^## (.+)$", tresc, flags=re.MULTILINE)
    # re.split z grupą przechwytującą zwraca [przed, nagłówek1, treść1, nagłówek2, treść2, ...]
    for i in range(1, len(czesci), 2):
        nazwa = czesci[i].strip()
        tresc_sekcji = czesci[i + 1].strip() if i + 1 < len(czesci) else ""
        sekcje[nazwa] = tresc_sekcji
    return sekcje


def _rozbierz_wariant(nazwa: str, tresc_sekcji: str) -> WariantPosta:
    dopasowanie = WZORZEC_PODEJSCIA.search(tresc_sekcji)
    if dopasowanie:
        etykieta = dopasowanie.group(1).strip()
        tresc_posta = (tresc_sekcji[: dopasowanie.start()] + tresc_sekcji[dopasowanie.end() :]).strip()
    else:
        etykieta = nazwa
        tresc_posta = tresc_sekcji
    return WariantPosta(etykieta=etykieta, tresc=tresc_posta, znaki=len(tresc_posta))


def _rozbierz_braki(tresc_sekcji: str) -> list[str]:
    punkty = [
        linia.lstrip("- ").strip()
        for linia in tresc_sekcji.splitlines()
        if linia.strip().startswith("-")
    ]
    if punkty:
        return punkty
    if not tresc_sekcji or "brak braków" in tresc_sekcji.lower():
        return []
    # Agent nie trzymał się formatu punktowanego — pokazujemy całą treść,
    # zamiast po cichu zgubić informację o brakach.
    return [tresc_sekcji]


def wczytaj_wygenerowany_post(sciezka: Path) -> WygenerowanyPost:
    """Parsuje plik zapisany przez tryb Redaktor (SPEC 7, sekcje: Wariant
    1/2/3, Facebook, Brief graficzny, Braki). Nie rzuca wyjątku przy
    niekompletnym pliku — zwraca to, co się dało odczytać, z `kompletny=False`,
    żeby operator zobaczył surową treść zamiast pustego ekranu."""
    tresc = sciezka.read_text(encoding="utf-8")
    sekcje = _wytnij_sekcje(tresc)

    post = WygenerowanyPost(surowy_markdown=tresc)
    for nazwa_wariantu in ("Wariant 1", "Wariant 2", "Wariant 3"):
        if nazwa_wariantu in sekcje:
            post.warianty.append(_rozbierz_wariant(nazwa_wariantu, sekcje[nazwa_wariantu]))
    post.facebook = sekcje.get("Facebook", "")
    post.brief_graficzny = sekcje.get("Brief graficzny", "")
    post.braki = _rozbierz_braki(sekcje.get("Braki", ""))
    post.kompletny = all(naglowek in sekcje for naglowek in NAGLOWKI_POSTA)
    return post


# --- Plan miesiąca (SPEC 7 i 8.1, SPEC-frontend 6) ---

NAGLOWEK_CZEGO_ZABRAKLO = "Czego zabrakło"

# SPEC sekcja 7 podaje statusy jako `draft` → `zatwierdzony` → `napisany` →
# `opublikowany`, a SPEC-frontend sekcja 6 ten sam pierwszy status nazywa
# `szkic`. Rozbieżność w dokumentach; zapisujemy polskie `szkic` (spójnie
# z resztą interfejsu i z tym, że operatorka edytuje te pliki ręcznie),
# ale przy odczycie przyjmujemy też `draft`, żeby plan napisany według
# litery SPEC sekcja 7 nie wyświetlał się z pustym statusem.
STATUSY_PLANU = ("szkic", "zatwierdzony", "napisany", "opublikowany")
SYNONIMY_STATUSOW = {"draft": "szkic"}

KOLUMNY_PLANU = ("#", "Data", "Typ", "Temat", "Źródło", "Do potwierdzenia", "Status")


@dataclass
class PozycjaPlanu:
    numer: str = ""
    data: str = ""
    typ: str = ""
    temat: str = ""
    zrodlo: str = ""
    do_potwierdzenia: str = ""
    status: str = "szkic"


@dataclass
class PlanMiesiaca:
    miesiac: str
    istnieje: bool = False
    pozycje: list[PozycjaPlanu] = field(default_factory=list)
    czego_zabraklo: list[str] = field(default_factory=list)
    surowy_markdown: str = ""


def _sciezka_planu(katalog_danych: Path, miesiac: str) -> Path:
    return katalog_danych / "plan" / f"{Path(miesiac).name}.md"


def _komorki_wiersza(linia: str) -> list[str]:
    return [komorka.strip() for komorka in linia.strip().strip("|").split("|")]


def _czy_linia_rozdzielajaca(linia: str) -> bool:
    return bool(re.fullmatch(r"[\s|:-]+", linia.strip()))


def wczytaj_plan(katalog_danych: Path, miesiac: str) -> PlanMiesiaca:
    """Parsuje plan miesiąca z tabeli markdown. Nieznane kolumny są pomijane,
    brakujące zostają puste — operatorka edytuje ten plik ręcznie, więc
    parser ma być wyrozumiały, a nie odrzucać cały plan przez jedną literówkę."""
    plan = PlanMiesiaca(miesiac=miesiac)
    plik = _sciezka_planu(katalog_danych, miesiac)
    if not plik.is_file():
        return plan

    tresc = plik.read_text(encoding="utf-8")
    plan.istnieje = True
    plan.surowy_markdown = tresc

    sekcje = _wytnij_sekcje(tresc)
    plan.czego_zabraklo = _rozbierz_braki(sekcje.get(NAGLOWEK_CZEGO_ZABRAKLO, ""))

    # Tabela jest przed pierwszym nagłówkiem `## `, więc bierzemy tekst do niego.
    czesc_z_tabela = re.split(r"^## ", tresc, maxsplit=1, flags=re.MULTILINE)[0]
    naglowki: list[str] = []
    for linia in czesc_z_tabela.splitlines():
        if "|" not in linia:
            continue
        if _czy_linia_rozdzielajaca(linia):
            continue
        komorki = _komorki_wiersza(linia)
        if not naglowki:
            naglowki = komorki
            continue
        wiersz = dict(zip(naglowki, komorki))
        status = wiersz.get("Status", "").strip().lower()
        plan.pozycje.append(
            PozycjaPlanu(
                numer=wiersz.get("#", ""),
                data=wiersz.get("Data", ""),
                typ=wiersz.get("Typ", ""),
                temat=wiersz.get("Temat", ""),
                zrodlo=wiersz.get("Źródło", ""),
                do_potwierdzenia=wiersz.get("Do potwierdzenia", ""),
                status=SYNONIMY_STATUSOW.get(status, status) or "szkic",
            )
        )
    return plan


def _plan_jako_markdown(plan: PlanMiesiaca) -> str:
    naglowek = "| " + " | ".join(KOLUMNY_PLANU) + " |"
    rozdzielacz = "|" + "|".join(["---"] * len(KOLUMNY_PLANU)) + "|"
    wiersze = [
        "| "
        + " | ".join(
            (
                pozycja.numer or str(indeks),
                pozycja.data,
                pozycja.typ,
                pozycja.temat,
                pozycja.zrodlo,
                pozycja.do_potwierdzenia,
                pozycja.status,
            )
        )
        + " |"
        for indeks, pozycja in enumerate(plan.pozycje, start=1)
    ]
    braki = "\n".join(f"- {brak}" for brak in plan.czego_zabraklo) or "Brak uwag."
    return (
        f"# Plan na {plan.miesiac}\n\n"
        + "\n".join([naglowek, rozdzielacz, *wiersze])
        + f"\n\n## {NAGLOWEK_CZEGO_ZABRAKLO}\n\n{braki}\n"
    )


def zmien_status_pozycji(
    katalog_danych: Path, miesiac: str, numer_wiersza: int, status: str
) -> None:
    """Zmienia status jednej pozycji planu i przepisuje plik.

    Przepisujemy całą tabelę, a nie podmieniamy tekst w miejscu: plan bywa
    edytowany ręcznie i formatowanie tabeli po takiej edycji nie musi być
    regularne, więc podmiana tekstem trafiałaby czasem w zły wiersz.
    """
    if status not in STATUSY_PLANU:
        raise ValueError(f"Nieznany status planu: {status}")

    plan = wczytaj_plan(katalog_danych, miesiac)
    if not plan.istnieje:
        raise FileNotFoundError(f"Nie ma planu na {miesiac}.")
    if not 0 <= numer_wiersza < len(plan.pozycje):
        raise IndexError(f"Plan na {miesiac} nie ma pozycji numer {numer_wiersza + 1}.")

    plan.pozycje[numer_wiersza].status = status
    _sciezka_planu(katalog_danych, miesiac).write_text(
        _plan_jako_markdown(plan), encoding="utf-8"
    )


def lista_miesiecy_planow(katalog_danych: Path) -> list[str]:
    katalog = katalog_danych / "plan"
    if not katalog.is_dir():
        return []
    return sorted((plik.stem for plik in katalog.glob("*.md")), reverse=True)


# --- Materiały z firmy (input firmowy, SPEC-frontend 8) ---

SEKCJE_MATERIALOW = (
    "Projekty — start",
    "Projekty — zakończenie / odbiór",
    "Kamienie milowe, certyfikaty",
    "Ludzie — zatrudnienia, awanse",
    "Obecność branżowa",
)


def _sciezka_materialow(katalog_danych: Path, miesiac: str) -> Path:
    return katalog_danych / "input-firmowy" / f"{Path(miesiac).name}.md"


def wczytaj_materialy(katalog_danych: Path, miesiac: str) -> dict[str, list[str]]:
    """Materiały z firmy na dany miesiąc, jako sekcja → lista wpisów.
    Zawsze zwraca wszystkie sekcje (puste, jeśli brak) — pusty miesiąc ma się
    pokazać jako wyróżniony brak, nie jako biała plama (SPEC-frontend 8)."""
    plik = _sciezka_materialow(katalog_danych, miesiac)
    sekcje = _wytnij_sekcje(plik.read_text(encoding="utf-8")) if plik.is_file() else {}
    return {
        nazwa: [
            linia.strip().lstrip("-").strip()
            for linia in sekcje.get(nazwa, "").splitlines()
            if linia.strip().startswith("-")
        ]
        for nazwa in SEKCJE_MATERIALOW
    }


def zapisz_materialy(
    katalog_danych: Path, miesiac: str, materialy: dict[str, list[str]]
) -> None:
    plik = _sciezka_materialow(katalog_danych, miesiac)
    plik.parent.mkdir(parents=True, exist_ok=True)

    czesci = [f"# Materiały z firmy — {Path(miesiac).name}\n"]
    for nazwa in SEKCJE_MATERIALOW:
        wpisy = materialy.get(nazwa) or []
        tresc = "\n".join(f"- {wpis}" for wpis in wpisy if wpis.strip()) or "(pusto)"
        czesci.append(f"## {nazwa}\n\n{tresc}\n")
    plik.write_text("\n".join(czesci), encoding="utf-8")


def czy_materialy_puste(materialy: dict[str, list[str]]) -> bool:
    return not any(wpisy for wpisy in materialy.values())
