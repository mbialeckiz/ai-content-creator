"""Sprawdzenia środowiska — bez wywołania modelu (SPEC 8.6, 11).

Musi być darmowe i szybkie: ten moduł nie importuje niczego, co uruchamia
proces CLI Claude Code. Jedyny import z `silnik.py` to introspekcja
`ClaudeAgentOptions`, która sama w sobie nie łączy się z niczym.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from app import silnik

WYMAGANA_WERSJA_PYTHONA = (3, 10)

OCZEKIWANA_STRUKTURA = (
    ".claude/skills/brand-voice/SKILL.md",
    ".claude/skills/schematy-postow/SKILL.md",
    ".claude/skills/strategia-contentu/SKILL.md",
    ".claude/skills/wywiad-tov/SKILL.md",
    "baza-wiedzy/forces-dc-fakty.md",
    "baza-wiedzy/zrodla-branzowe.md",
    "baza-wiedzy/zakazane-zwroty.md",
    "input-firmowy",
    "korpus/linkedin",
    "plan",
    "output",
)

ZNACZNIK_LUKI = "[DO UZUPEŁNIENIA"


@dataclass
class WynikSprawdzenia:
    id: str
    etykieta: str
    status: str  # "ok" | "ostrzezenie" | "blad"
    szczegoly: str
    instrukcja_naprawy: str | None = None


@dataclass
class RaportDiagnostyczny:
    sprawdzenia: list[WynikSprawdzenia] = field(default_factory=list)
    liczniki: dict[str, int] = field(default_factory=dict)


def _sprawdz_wersje_pythona() -> WynikSprawdzenia:
    aktualna = sys.version_info[:2]
    if aktualna >= WYMAGANA_WERSJA_PYTHONA:
        return WynikSprawdzenia(
            "python", "Wersja Pythona", "ok", f"{aktualna[0]}.{aktualna[1]}"
        )
    return WynikSprawdzenia(
        "python",
        "Wersja Pythona",
        "blad",
        f"Wykryto {aktualna[0]}.{aktualna[1]}, wymagane co najmniej 3.10.",
        "Zainstaluj Pythona 3.10 lub nowszego i uruchom start.command ponownie.",
    )


def _sprawdz_sdk() -> WynikSprawdzenia:
    try:
        import claude_agent_sdk
    except ImportError:
        return WynikSprawdzenia(
            "sdk",
            "Silnik agentowy (claude-agent-sdk)",
            "blad",
            "Pakiet nie jest zainstalowany.",
            "Uruchom: pip install -r requirements.txt",
        )
    wersja = getattr(claude_agent_sdk, "__version__", "nieznana")
    return WynikSprawdzenia(
        "sdk", "Silnik agentowy (claude-agent-sdk)", "ok", f"wersja {wersja}"
    )


def _sprawdz_zgodnosc_parametrow() -> WynikSprawdzenia:
    wynik = silnik.sprawdz_zgodnosc_parametrow()
    if wynik["zgodne"]:
        return WynikSprawdzenia(
            "parametry_sdk",
            "Zgodność parametrów ClaudeAgentOptions",
            "ok",
            "Wszystkie parametry używane przez kod istnieją w zainstalowanej wersji SDK.",
        )
    brakujace = ", ".join(wynik["brakujace_w_sdk"])
    return WynikSprawdzenia(
        "parametry_sdk",
        "Zgodność parametrów ClaudeAgentOptions",
        "blad",
        f"Zainstalowana wersja SDK nie ma pól: {brakujace}.",
        "API SDK się zmieniło — zgłoś to administratorowi, nie próbuj obejść "
        "problemu zmianą zachowania bez sprawdzenia dokumentacji.",
    )


def _sprawdz_strukture(katalog_danych: Path) -> WynikSprawdzenia:
    brakujace = [
        sciezka
        for sciezka in OCZEKIWANA_STRUKTURA
        if not (katalog_danych / sciezka).exists()
    ]
    if not brakujace:
        return WynikSprawdzenia(
            "struktura", "Struktura katalogu danych", "ok", "Wszystkie oczekiwane elementy istnieją."
        )
    return WynikSprawdzenia(
        "struktura",
        "Struktura katalogu danych",
        "blad",
        "Brakuje: " + ", ".join(brakujace),
        f"Sprawdź zawartość katalogu {katalog_danych} — brakujące pliki/foldery trzeba dodać "
        "(skille i bazę wiedzy dostarcza administrator jako gotową paczkę).",
    )


def _policz_posty_korpusu(katalog_danych: Path) -> int:
    katalog = katalog_danych / "korpus" / "linkedin"
    if not katalog.exists():
        return 0
    return len(list(katalog.glob("*.md")))


def _policz_luki_bazy_wiedzy(katalog_danych: Path) -> int:
    katalog = katalog_danych / "baza-wiedzy"
    if not katalog.exists():
        return 0
    return sum(
        plik.read_text(encoding="utf-8").count(ZNACZNIK_LUKI)
        for plik in katalog.glob("*.md")
    )


def _policz_dokumenty(katalog_danych: Path) -> int:
    katalog = katalog_danych / "artykuly"
    if not katalog.is_dir():
        return 0
    return sum(1 for plik in katalog.iterdir() if plik.is_file() and not plik.name.startswith("."))


def _policz_miesiace_materialow(katalog_danych: Path) -> int:
    katalog = katalog_danych / "input-firmowy"
    if not katalog.is_dir():
        return 0
    return len(list(katalog.glob("*.md")))


def _sprawdz_klucz_api() -> WynikSprawdzenia:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return WynikSprawdzenia(
            "klucz_api", "Klucz API", "ok", "Zmienna ANTHROPIC_API_KEY jest ustawiona."
        )
    return WynikSprawdzenia(
        "klucz_api",
        "Klucz API",
        "blad",
        "Brak zmiennej ANTHROPIC_API_KEY w środowisku.",
        "Uzupełnij ANTHROPIC_API_KEY w pliku .env i uruchom aplikację ponownie.",
    )


def _sprawdz_katalog_danych(katalog_danych: Path) -> WynikSprawdzenia:
    if katalog_danych.is_dir():
        return WynikSprawdzenia(
            "katalog_danych",
            "Ścieżka katalogu danych",
            "ok",
            str(katalog_danych.resolve()),
            "Jeśli Twoje wcześniejsze posty i materiały „zniknęły”, sprawdź, "
            "czy to na pewno ten folder — aplikacja czyta i zapisuje wyłącznie tutaj.",
        )
    return WynikSprawdzenia(
        "katalog_danych",
        "Ścieżka katalogu danych",
        "blad",
        f"Katalog {katalog_danych} nie istnieje.",
        "Sprawdź zmienną KATALOG_DANYCH w pliku .env — powinna wskazywać na "
        "istniejący folder (domyślnie ./dane).",
    )


def uruchom_diagnostyke(katalog_danych: Path) -> RaportDiagnostyczny:
    """Wykonuje wszystkie sprawdzenia. Nie łączy się z modelem ani z siecią."""
    raport = RaportDiagnostyczny()
    raport.sprawdzenia = [
        _sprawdz_wersje_pythona(),
        _sprawdz_sdk(),
        _sprawdz_zgodnosc_parametrow(),
        _sprawdz_katalog_danych(katalog_danych),
        _sprawdz_strukture(katalog_danych),
        _sprawdz_klucz_api(),
    ]
    raport.liczniki = {
        "postow_w_korpusie": _policz_posty_korpusu(katalog_danych),
        "luk_w_bazie_wiedzy": _policz_luki_bazy_wiedzy(katalog_danych),
        "wgranych_dokumentow": _policz_dokumenty(katalog_danych),
        "miesiecy_z_materialami": _policz_miesiace_materialow(katalog_danych),
    }
    return raport
