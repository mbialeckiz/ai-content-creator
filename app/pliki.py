"""CRUD i walidacja plików `.md` (CLAUDE.md). Bez styczności z SDK."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

NAGLOWEK_NDA = "## Czego NIE wolno publikować"
WZORZEC_POGRUBIENIA = re.compile(r"\*\*(.+?)\*\*")

NAGLOWKI_POSTA = ("Wariant 1", "Wariant 2", "Wariant 3", "Facebook", "Brief graficzny", "Braki")
WZORZEC_PODEJSCIA = re.compile(r"^\*\*Podejście:\*\*\s*(.+)$", re.MULTILINE)


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
