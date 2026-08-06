"""Identyfikacja wizualna i przygotowanie grafiki do posta.

Sam obraz rysuje przeglądarka na elemencie canvas — ten moduł dostarcza
wyłącznie dane: kolory, kroje, logo i treść do złożenia. Dzięki temu podgląd
i pobrany plik PNG powstają z tego samego kodu, bez dokładania bibliotek
graficznych do instalacji u operatorki (CLAUDE.md: zero build stepu, jak
najmniej zależności do utrzymania).
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("forces_content_studio.grafika")

NAZWA_BRAND_KITU = "brand-kit.yaml"
PODKATALOG_LOGO = "logo"
ROZSZERZENIA_LOGO = (".png", ".svg", ".jpg", ".jpeg", ".webp")
TYPY_LOGO = {
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

WZORZEC_KOLORU = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

BRAND_KIT_DOMYSLNY: dict[str, Any] = {
    "nazwa_firmy": "Forces DC",
    "podpis": "",
    # Kolory z paczki brand kitu Forces DC. To wartości awaryjne — używane,
    # gdy brakuje `brand-kit.yaml` albo pojedynczego pola. Wpisujemy tu barwy
    # marki, a nie neutralne zastępniki: aplikacja ma jednego klienta, więc
    # grafika z brakującym plikiem ma nadal wyglądać jak jego, a nie jak nic.
    "kolory": {
        "tlo": "#32373C",
        "tekst": "#FFFFFF",
        "akcent": "#BBA470",
        "tlo_alternatywne": "#FFFFFF",
        "tekst_alternatywny": "#000000",
        # Czarny pasek ze znakiem u dołu jasnych projektów.
        "pasek_stopki": "#111111",
    },
    "kroje": {
        "naglowek": "Montserrat, Helvetica Neue, Helvetica, Arial, sans-serif",
        "podpis": "Montserrat, Helvetica Neue, Helvetica, Arial, sans-serif",
    },
    "logo": {"plik": "", "plik_na_ciemnym": "", "wysokosc_px": 64},
    # Pion 4:5 — format, w którym operatorka robi projekty w Canvie i który
    # LinkedIn pokazuje największy. Kwadrat, od którego zaczynaliśmy, zajmuje
    # w kanale wyraźnie mniej miejsca.
    "format": {"szerokosc": 1080, "wysokosc": 1350},
    "adres_www": "www.forces.no",
}


def _scal(domyslne: dict[str, Any], wczytane: dict[str, Any]) -> dict[str, Any]:
    """Scala wczytany plik z wartościami domyślnymi.

    Brakujące pole ma nie wywalać generowania grafiki — operatorka edytuje
    ten plik ręcznie i literówka albo usunięta linia nie może zablokować
    całej funkcji.
    """
    wynik = dict(domyslne)
    for klucz, wartosc in (wczytane or {}).items():
        if isinstance(wartosc, dict) and isinstance(wynik.get(klucz), dict):
            wynik[klucz] = _scal(wynik[klucz], wartosc)
        elif wartosc not in (None, ""):
            wynik[klucz] = wartosc
    return wynik


def sciezka_brand_kitu(katalog_danych: Path) -> Path:
    return katalog_danych / NAZWA_BRAND_KITU


def wczytaj_brand_kit(katalog_danych: Path) -> tuple[dict[str, Any], list[str]]:
    """Zwraca (identyfikacja, ostrzeżenia). Ostrzeżenia trafiają do UI —
    lepiej narysować grafikę na kolorach zastępczych i powiedzieć o tym,
    niż odmówić działania."""
    plik = sciezka_brand_kitu(katalog_danych)
    ostrzezenia: list[str] = []
    wczytane: dict[str, Any] = {}

    if plik.is_file():
        try:
            wczytane = yaml.safe_load(plik.read_text(encoding="utf-8")) or {}
            if not isinstance(wczytane, dict):
                ostrzezenia.append("Plik identyfikacji ma nieoczekiwany format — użyto wartości domyślnych.")
                wczytane = {}
        except yaml.YAMLError as blad:
            logger.warning("Błąd formatu brand-kit.yaml: %s", blad)
            ostrzezenia.append(
                f"Plik identyfikacji ma błąd formatu ({blad}). Użyto wartości domyślnych — popraw go w zakładce Styl."
            )
    else:
        ostrzezenia.append("Nie ma jeszcze pliku identyfikacji wizualnej — grafika powstanie na kolorach zastępczych.")

    kit = _scal(BRAND_KIT_DOMYSLNY, wczytane)

    for nazwa, wartosc in kit["kolory"].items():
        if not WZORZEC_KOLORU.match(str(wartosc)):
            ostrzezenia.append(
                f"Kolor „{nazwa}” ({wartosc}) nie jest poprawnym kodem szesnastkowym — użyto zastępczego."
            )
            kit["kolory"][nazwa] = BRAND_KIT_DOMYSLNY["kolory"][nazwa]

    return kit, ostrzezenia


def _logo_jako_data_uri(katalog_danych: Path, nazwa_pliku: str) -> str:
    """Logo wstawiamy do danych jako data URI, żeby przeglądarka mogła je
    narysować na canvasie bez osobnego żądania (i bez blokady zapisu PNG
    z powodu „skażonego" canvasu obrazem z innego źródła)."""
    if not nazwa_pliku:
        return ""
    plik = katalog_danych / PODKATALOG_LOGO / Path(nazwa_pliku).name
    if not plik.is_file():
        return ""
    # Typ ustalamy z własnej tabelki, a nie z `mimetypes`: na Windowsie
    # rozpoznawanie typów opiera się o rejestr systemowy i potrafi zwrócić
    # dla `.svg` coś innego niż `image/svg+xml` albo nic. Zły typ oznacza
    # logo, którego przeglądarka nie narysuje.
    typ = TYPY_LOGO.get(plik.suffix.lower()) or mimetypes.guess_type(plik.name)[0] or "image/png"
    return f"data:{typ};base64,{base64.b64encode(plik.read_bytes()).decode()}"


def lista_logo(katalog_danych: Path) -> list[str]:
    katalog = katalog_danych / PODKATALOG_LOGO
    if not katalog.is_dir():
        return []
    return sorted(
        plik.name
        for plik in katalog.iterdir()
        if plik.is_file() and plik.suffix.lower() in ROZSZERZENIA_LOGO
    )


def przygotuj_miejsce_na_logo(katalog_danych: Path, nazwa_pliku: str) -> Path:
    katalog = katalog_danych / PODKATALOG_LOGO
    katalog.mkdir(parents=True, exist_ok=True)
    return katalog / Path(nazwa_pliku).name


def zbuduj_dane_grafiki(
    katalog_danych: Path,
    *,
    haslo: str,
    podtytul: str = "",
    wariant_kolorystyczny: str = "ciemny",
) -> dict[str, Any]:
    """Komplet danych, z których przeglądarka rysuje grafikę."""
    kit, ostrzezenia = wczytaj_brand_kit(katalog_danych)
    ciemny = wariant_kolorystyczny != "jasny"

    # Znak zawsze leży na ciemnym: albo na ciemnym tle grafiki, albo na czarnym
    # pasku stopki w wariancie jasnym. Wersja na jasne tło (czarny napis) jest
    # tu więc zawsze zła — zostaje wyłącznie jako zabezpieczenie, gdyby wersji
    # na ciemne tło nie wgrano.
    nazwa_logo = kit["logo"].get("plik_na_ciemnym") or kit["logo"].get("plik", "")
    logo = _logo_jako_data_uri(katalog_danych, nazwa_logo)

    return {
        "haslo": haslo,
        "podtytul": podtytul,
        "nazwa_firmy": kit["nazwa_firmy"],
        "podpis": kit["podpis"],
        "kolory": {
            "tlo": kit["kolory"]["tlo"] if ciemny else kit["kolory"]["tlo_alternatywne"],
            "tekst": kit["kolory"]["tekst"] if ciemny else kit["kolory"]["tekst_alternatywny"],
            "akcent": kit["kolory"]["akcent"],
            "pasek_stopki": kit["kolory"].get("pasek_stopki", "#111111"),
        },
        "adres_www": kit.get("adres_www", ""),
        "kroje": kit["kroje"],
        "logo": logo,
        "wysokosc_logo": int(kit["logo"].get("wysokosc_px") or 64),
        "format": kit["format"],
        "wariant_kolorystyczny": "ciemny" if ciemny else "jasny",
        "ostrzezenia": ostrzezenia,
    }


# --- Polecenie do Canvy ---
#
# Grafiki karuzelowe i gęste infografiki powstają w Canvie, nie tutaj (patrz
# baza-wiedzy/wzory-graficzne.md). Zamiast udawać, że aplikacja je narysuje,
# składamy gotowe polecenie do wklejenia Claude'owi z podpiętym konektorem
# Canva. Robimy to w backendzie, bez wywołania modelu: wszystkie dane już mamy,
# więc polecenie jest darmowe i natychmiastowe.
#
# Polecenie jest po angielsku, bo w tym języku Forces DC publikuje i w tym
# języku mają być teksty na grafice.

SZABLONY_DOMYSLNE = {
    "karuzela": "Forces DC — carousel",
    "infografika": "Forces DC — infographic",
    "kluczowe-punkty": "Forces DC — key points",
    "wydarzenie": "Forces DC — event",
    "plansza": "Forces DC — statement",
}

# Polecenie jest w całości po angielsku, więc opisy szablonów też — klucze
# w brand-kit.yaml zostają po polsku, bo edytuje je operatorka.
OPISY_SZABLONOW_EN = {
    "karuzela": "carousel",
    "infografika": "infographic (numbered list)",
    "kluczowe-punkty": "key points with icons",
    "wydarzenie": "event announcement",
    "plansza": "single statement card",
}


def zbuduj_polecenie_do_canvy(
    katalog_danych: Path, brief_graficzny: str, haslo: str = ""
) -> str:
    """Gotowy tekst do wklejenia Claude'owi z konektorem Canva.

    Część techniczną (format, kolory, krój, stałe elementy) składamy sami —
    zawsze jest poprawna. Część treściową bierzemy wprost z briefu napisanego
    przez redaktora, bez przepisywania: to on wie, co ma być na grafice.
    """
    kit, _ = wczytaj_brand_kit(katalog_danych)
    kolory = kit["kolory"]
    krój = kit["kroje"]["naglowek"].split(",")[0].strip()
    szablony = {**SZABLONY_DOMYSLNE, **(kit.get("szablony_canva") or {})}

    linie = [
        "Create a LinkedIn graphic for Forces DC in Canva, using our brand "
        "template and brand kit.",
        "",
        "## Brand specification (do not deviate)",
        f"- Size: {kit['format']['szerokosc']}×{kit['format']['wysokosc']} px "
        "(portrait 4:5 — the format LinkedIn displays largest)",
        f"- Typeface: {krój}, all text",
        f"- Dark background: {kolory['tlo']} with white text",
        f"- Light background: {kolory['tlo_alternatywne']} with "
        f"{kolory['tekst_alternatywny']} text",
        f"- Accent colour: {kolory['akcent']} — the only accent. Use it for "
        "step numbers, rules under headings, frames and highlight blocks. "
        "Never introduce another colour.",
        "- Frames and boxes: 2–3 px outline, white on dark or black on light",
        f"- Footer: black bar ({kolory['pasek_stopki']}) across the full width "
        "with the Forces DC logo centred in it. On a dark background use no "
        "bar — place the logo directly on the background, bottom left.",
    ]
    if kit.get("adres_www"):
        linie.append(f"- Top of the design: {kit['adres_www']}, centred, small")
    linie += [
        "- All text in English",
        "- No stock photos of people unless I supply one; keep it typographic",
        "",
        "## Templates to start from",
        *[
            f'- {OPISY_SZABLONOW_EN.get(klucz, klucz)}: "{nazwa}"'
            for klucz, nazwa in szablony.items()
        ],
        "",
        "## What to make",
    ]

    if haslo.strip():
        linie += [f"Key message: {haslo.strip()}", ""]

    linie += [
        brief_graficzny.strip() or "[brak briefu graficznego — opisz temat sam]",
        "",
        "If the brief describes a carousel, create one page per slide. "
        "If it describes an infographic, keep it to a single page. "
        "Show me the result and wait before making any changes.",
    ]
    return "\n".join(linie)
