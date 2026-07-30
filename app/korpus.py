"""Korpus opublikowanych postów: odczyt, dopisywanie, import eksportu
LinkedIn (SPEC 7 i 8.5). Bez styczności z SDK."""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("forces_content_studio.korpus")

PODKATALOG_KORPUSU = Path("korpus") / "linkedin"

# SPEC sekcja 7 — zamknięta lista. `DO-OZNACZENIA` nie jest tu wymienione
# celowo: import ustawia je jako znacznik „wymaga ręcznej klasyfikacji"
# (SPEC 8.5), ale ręczne zapisanie posta z takim typem nie ma sensu.
DOZWOLONE_TYPY = (
    "branzowy",
    "realizacja",
    "zajawka-eventu",
    "prelegent",
    "partner",
    "employer-branding",
    "ekspercki",
    "event-relacja",
    "obecnosc-branzowa",
    "podsumowanie",
    "okolicznosciowy",
)
TYP_DO_OZNACZENIA = "DO-OZNACZENIA"

MINIMALNA_DLUGOSC_TRESCI = 150
DOCELOWA_LICZBA_POSTOW = 20

# Artefakt eksportu LinkedIn: sekwencja "hashtag\n#Tag" zamiast samego "#Tag".
WZORZEC_ARTEFAKTU_HASHTAG = re.compile(r"hashtag\s*\n\s*(#)", re.IGNORECASE)

# Nazwy kolumn spotykane w eksportach LinkedIn (różne wersje, PL i EN).
KOLUMNY_TRESCI = ("treść", "tresc", "content", "sharecommentary", "commentary", "text", "post")
KOLUMNY_DATY = ("data", "date", "createdat", "created", "datapublikacji", "publisheddate", "time")
KOLUMNY_REAKCJI = ("reakcje", "reactions", "likes", "polubienia", "numlikes")
KOLUMNY_KOMENTARZY = ("komentarze", "comments", "numcomments")
KOLUMNY_URL = ("url", "link", "postlink", "shareurl", "permalink")
KOLUMNY_REPOSTA = ("repost", "reshare", "isrepost", "shared", "udostepnienie")


class BladWalidacji(ValueError):
    """Dane posta nie przechodzą walidacji — komunikat jest po polsku i
    trafia wprost do UI (SPEC sekcja 7: błąd → komunikat, nie cichy zapis)."""


@dataclass
class PostKorpusu:
    plik: str
    data: str
    typ: str
    jezyk: str
    reakcje: int
    komentarze: int
    url: str
    tresc: str

    @property
    def wymaga_oznaczenia(self) -> bool:
        return self.typ not in DOZWOLONE_TYPY


def _katalog_korpusu(katalog_danych: Path) -> Path:
    return katalog_danych / PODKATALOG_KORPUSU


def _rozdziel_naglowek(tekst: str) -> tuple[dict[str, Any], str]:
    """Dzieli plik na nagłówek YAML i treść. Rzuca `BladWalidacji`, gdy
    nagłówka nie da się sparsować — cichy zapis jest zabroniony (SPEC 7)."""
    if not tekst.startswith("---"):
        raise BladWalidacji(
            "Plik nie zaczyna się od nagłówka '---'. Dodaj nagłówek z datą, "
            "typem i liczbą reakcji na początku pliku."
        )
    czesci = tekst.split("---", 2)
    if len(czesci) < 3:
        raise BladWalidacji(
            "Nagłówek nie jest zamknięty drugą linią '---'. Sprawdź początek pliku."
        )
    try:
        naglowek = yaml.safe_load(czesci[1]) or {}
    except yaml.YAMLError as blad:
        raise BladWalidacji(
            f"Nagłówek na górze pliku ma błąd formatu: {blad}. Popraw go i zapisz ponownie."
        ) from blad
    if not isinstance(naglowek, dict):
        raise BladWalidacji("Nagłówek na górze pliku powinien być listą pól 'nazwa: wartość'.")
    return naglowek, czesci[2].strip()


def _jako_int(wartosc: Any) -> int:
    try:
        return int(str(wartosc).strip() or 0)
    except (TypeError, ValueError):
        return 0


def wczytaj_korpus(katalog_danych: Path) -> tuple[list[PostKorpusu], list[str]]:
    """Wczytuje wszystkie posty korpusu. Zwraca (posty, ostrzeżenia) —
    pojedynczy uszkodzony plik nie może wywalić całego ekranu, więc trafia
    na listę ostrzeżeń zamiast przerywać odczyt."""
    katalog = _katalog_korpusu(katalog_danych)
    if not katalog.is_dir():
        return [], []

    posty: list[PostKorpusu] = []
    ostrzezenia: list[str] = []
    for plik in sorted(katalog.glob("*.md")):
        try:
            naglowek, tresc = _rozdziel_naglowek(plik.read_text(encoding="utf-8"))
        except (BladWalidacji, OSError) as blad:
            logger.warning("Pomijam uszkodzony plik korpusu %s: %s", plik.name, blad)
            ostrzezenia.append(f"{plik.name}: {blad}")
            continue
        posty.append(
            PostKorpusu(
                plik=plik.name,
                data=str(naglowek.get("data", "")),
                typ=str(naglowek.get("typ", TYP_DO_OZNACZENIA)),
                jezyk=str(naglowek.get("jezyk", "")),
                reakcje=_jako_int(naglowek.get("reakcje")),
                komentarze=_jako_int(naglowek.get("komentarze")),
                url=str(naglowek.get("url", "")),
                tresc=tresc,
            )
        )
    return posty, ostrzezenia


def zbuduj_slug(tekst: str, maks_dlugosc: int = 40) -> str:
    """Slug z polskimi znakami sprowadzonymi do ASCII (nazwa pliku trafia
    na Dysk Google i do nazw plików w systemie operatorki)."""
    bez_ogonkow = unicodedata.normalize("NFKD", tekst).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", bez_ogonkow).strip("-").lower()
    return slug[:maks_dlugosc].strip("-") or "post"


def _sprawdz_dane_posta(data: str, typ: str, tresc: str) -> None:
    if not tresc.strip():
        raise BladWalidacji("Treść posta jest pusta — wklej treść opublikowanego posta.")
    if not data.strip():
        raise BladWalidacji("Podaj datę publikacji posta.")
    try:
        date.fromisoformat(data)
    except ValueError as blad:
        raise BladWalidacji(
            f"Data '{data}' nie jest poprawna — użyj formatu RRRR-MM-DD, na przykład 2025-08-22."
        ) from blad
    if typ not in DOZWOLONE_TYPY:
        raise BladWalidacji(
            f"Typ '{typ}' nie jest na liście dozwolonych typów. Wybierz jeden z: "
            + ", ".join(DOZWOLONE_TYPY)
        )


def zapisz_post(
    katalog_danych: Path,
    *,
    data: str,
    typ: str,
    jezyk: str,
    reakcje: int,
    komentarze: int,
    url: str,
    tresc: str,
    nazwa_pliku: str | None = None,
) -> str:
    """Zapisuje post do korpusu i zwraca nazwę pliku. Waliduje przed zapisem
    (SPEC sekcja 7) — błędne dane kończą się `BladWalidacji`, nie cichym zapisem."""
    _sprawdz_dane_posta(data, typ, tresc)

    katalog = _katalog_korpusu(katalog_danych)
    katalog.mkdir(parents=True, exist_ok=True)

    if nazwa_pliku:
        # Edycja istniejącego wpisu — bierzemy samą nazwę, żeby wartość
        # z przeglądarki nie mogła wskazać pliku poza katalogiem korpusu.
        plik = katalog / Path(nazwa_pliku).name
    else:
        plik = katalog / f"{data}_{zbuduj_slug(tresc)}.md"
        licznik = 2
        while plik.exists():
            plik = katalog / f"{data}_{zbuduj_slug(tresc)}-{licznik}.md"
            licznik += 1

    naglowek = yaml.safe_dump(
        {
            "data": data,
            "typ": typ,
            "jezyk": jezyk or "pl",
            "reakcje": int(reakcje),
            "komentarze": int(komentarze),
            "url": url,
        },
        allow_unicode=True,
        sort_keys=False,
    )
    plik.write_text(f"---\n{naglowek}---\n\n{tresc.strip()}\n", encoding="utf-8")
    return plik.name


def oznacz_typ(katalog_danych: Path, nazwa_pliku: str, typ: str) -> None:
    """Ustawia typ istniejącego posta (ręczna klasyfikacja po imporcie)."""
    if typ not in DOZWOLONE_TYPY:
        raise BladWalidacji(
            f"Typ '{typ}' nie jest na liście dozwolonych typów. Wybierz jeden z: "
            + ", ".join(DOZWOLONE_TYPY)
        )
    plik = _katalog_korpusu(katalog_danych) / Path(nazwa_pliku).name
    if not plik.is_file():
        raise BladWalidacji(f"Nie znaleziono posta '{nazwa_pliku}' w korpusie.")

    naglowek, tresc = _rozdziel_naglowek(plik.read_text(encoding="utf-8"))
    naglowek["typ"] = typ
    tekst_naglowka = yaml.safe_dump(naglowek, allow_unicode=True, sort_keys=False)
    plik.write_text(f"---\n{tekst_naglowka}---\n\n{tresc}\n", encoding="utf-8")


def usun_post(katalog_danych: Path, nazwa_pliku: str) -> None:
    plik = _katalog_korpusu(katalog_danych) / Path(nazwa_pliku).name
    if not plik.is_file():
        raise BladWalidacji(f"Nie znaleziono posta '{nazwa_pliku}' w korpusie.")
    plik.unlink()


# --- Import eksportu LinkedIn (SPEC 8.5) ---


@dataclass
class WierszImportu:
    tresc: str
    data: str
    reakcje: int
    komentarze: int
    url: str


@dataclass
class DiagnostykaImportu:
    """Wynik analizy wgranego pliku, pokazywany PRZED importem (SPEC 8.5)."""

    kolumny: list[str] = field(default_factory=list)
    wykryte: dict[str, str | None] = field(default_factory=dict)
    wierszy_w_pliku: int = 0
    do_zaimportowania: int = 0
    odrzucone_reposty: int = 0
    odrzucone_krotkie: int = 0
    mediana_dlugosci: int = 0
    probki: list[str] = field(default_factory=list)


def _znormalizuj_nazwe_kolumny(nazwa: str) -> str:
    """Nazwa kolumny sprowadzona do porównywalnej postaci.

    Polskie znaki transliterujemy (NFKD), a nie wycinamy: bez tego „Treść"
    zwężało się do „tre" i nie trafiało na listę kandydatów, przez co import
    polskiego eksportu wykrywał złą kolumnę.
    """
    bez_ogonkow = unicodedata.normalize("NFKD", str(nazwa)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", bez_ogonkow.lower())


def _dopasuj_kolumne(
    kolumny: list[str], kandydaci: tuple[str, ...], zajete: set[str] | None = None
) -> str | None:
    """Znajduje kolumnę pełniącą daną rolę. `zajete` to kolumny przypisane już
    do innej roli — jedna kolumna nie może pełnić dwóch (bez tego kandydat
    „post" łapał kolumnę „Repost" jako treść posta)."""
    zajete = zajete or set()
    znormalizowane = {
        _znormalizuj_nazwe_kolumny(k): k for k in kolumny if k not in zajete
    }
    for kandydat in kandydaci:
        if kandydat in znormalizowane:
            return znormalizowane[kandydat]
    # Dopasowanie częściowe — eksporty bywają nazwane np. "Post content (text)".
    for kandydat in kandydaci:
        for znormalizowana, oryginalna in znormalizowane.items():
            if kandydat in znormalizowana:
                return oryginalna
    return None


def wyczysc_tresc(tekst: str) -> str:
    """Usuwa artefakty eksportu (SPEC 8.5)."""
    return WZORZEC_ARTEFAKTU_HASHTAG.sub(r"\1", str(tekst)).strip()


def _wczytaj_tabele(sciezka: Path) -> Any:
    import pandas as pd

    rozszerzenie = sciezka.suffix.lower()
    if rozszerzenie == ".csv":
        return pd.read_csv(sciezka)
    if rozszerzenie in (".xlsx", ".xls"):
        return pd.read_excel(sciezka)
    if rozszerzenie == ".json":
        return pd.read_json(sciezka)
    raise BladWalidacji(
        f"Nie obsługujemy plików '{rozszerzenie}'. Wgraj plik CSV, XLSX albo JSON."
    )


def _czy_repost(wiersz: Any, kolumna_repost: str | None) -> bool:
    if not kolumna_repost:
        return False
    wartosc = str(wiersz.get(kolumna_repost, "")).strip().lower()
    return wartosc in ("true", "1", "tak", "yes", "y")


def _data_z_wartosci(wartosc: Any) -> str:
    import pandas as pd

    if wartosc is None or (isinstance(wartosc, float) and pd.isna(wartosc)):
        return ""
    try:
        return pd.to_datetime(wartosc).date().isoformat()
    except (ValueError, TypeError):
        return ""


def przeanalizuj_plik_importu(sciezka: Path) -> tuple[DiagnostykaImportu, list[WierszImportu]]:
    """Ekran diagnostyczny przed importem (SPEC 8.5): wykryte kolumny,
    próbki, mediana długości i liczba odrzuceń. Nic jeszcze nie zapisuje."""
    import pandas as pd

    tabela = _wczytaj_tabele(sciezka)
    kolumny = [str(k) for k in tabela.columns]

    # Kolejność ma znaczenie: role o charakterystycznych nazwach ustalamy
    # najpierw, a treść — najbardziej ogólną — na końcu, z wykluczeniem
    # kolumn już przypisanych.
    kolumna_repost = _dopasuj_kolumne(kolumny, KOLUMNY_REPOSTA)
    kolumna_daty = _dopasuj_kolumne(kolumny, KOLUMNY_DATY)
    kolumna_reakcji = _dopasuj_kolumne(kolumny, KOLUMNY_REAKCJI)
    kolumna_komentarzy = _dopasuj_kolumne(kolumny, KOLUMNY_KOMENTARZY)
    kolumna_url = _dopasuj_kolumne(kolumny, KOLUMNY_URL)

    zajete = {
        kolumna
        for kolumna in (kolumna_repost, kolumna_daty, kolumna_reakcji, kolumna_komentarzy, kolumna_url)
        if kolumna
    }
    kolumna_tresci = _dopasuj_kolumne(kolumny, KOLUMNY_TRESCI, zajete)
    if not kolumna_tresci:
        raise BladWalidacji(
            "Nie znaleźliśmy w pliku kolumny z treścią postów. Sprawdź, czy to "
            "właściwy plik eksportu — kolumna z treścią powinna nazywać się "
            "np. 'Treść', 'Content' albo 'ShareCommentary'."
        )

    diagnostyka = DiagnostykaImportu(
        kolumny=kolumny,
        wykryte={
            "treść": kolumna_tresci,
            "data": kolumna_daty,
            "reakcje": kolumna_reakcji,
            "komentarze": kolumna_komentarzy,
            "adres posta": kolumna_url,
            "znacznik udostępnienia": kolumna_repost,
        },
        wierszy_w_pliku=int(len(tabela)),
    )

    kandydaci: list[WierszImportu] = []
    dlugosci: list[int] = []
    for _, wiersz in tabela.iterrows():
        surowa_tresc = wiersz.get(kolumna_tresci)
        tresc = "" if pd.isna(surowa_tresc) else wyczysc_tresc(surowa_tresc)

        if _czy_repost(wiersz, kolumna_repost) or not tresc:
            diagnostyka.odrzucone_reposty += 1
            continue
        if len(tresc) < MINIMALNA_DLUGOSC_TRESCI:
            diagnostyka.odrzucone_krotkie += 1
            continue

        dlugosci.append(len(tresc))
        kandydaci.append(
            WierszImportu(
                tresc=tresc,
                data=_data_z_wartosci(wiersz.get(kolumna_daty)) if kolumna_daty else "",
                reakcje=_jako_int(wiersz.get(kolumna_reakcji)) if kolumna_reakcji else 0,
                komentarze=_jako_int(wiersz.get(kolumna_komentarzy)) if kolumna_komentarzy else 0,
                url=str(wiersz.get(kolumna_url, "") or "") if kolumna_url else "",
            )
        )

    # Sortowanie po zaangażowaniu — pozwala zaimportować N najlepszych (SPEC 8.5).
    kandydaci.sort(key=lambda w: (w.reakcje, w.komentarze), reverse=True)

    diagnostyka.do_zaimportowania = len(kandydaci)
    diagnostyka.probki = [w.tresc[:200] for w in kandydaci[:3]]
    if dlugosci:
        posortowane = sorted(dlugosci)
        diagnostyka.mediana_dlugosci = posortowane[len(posortowane) // 2]
    return diagnostyka, kandydaci


def zaimportuj(
    katalog_danych: Path, wiersze: list[WierszImportu], limit: int | None = None
) -> dict[str, int]:
    """Zapisuje wybrane wiersze do korpusu z typem `DO-OZNACZENIA`, żeby
    wymusić ręczną klasyfikację w UI (SPEC 8.5)."""
    katalog = _katalog_korpusu(katalog_danych)
    katalog.mkdir(parents=True, exist_ok=True)

    do_zapisu = wiersze[:limit] if limit else wiersze
    zapisane = 0
    for pozycja in do_zapisu:
        data_posta = pozycja.data or date.today().isoformat()
        plik = katalog / f"{data_posta}_{zbuduj_slug(pozycja.tresc)}.md"
        licznik = 2
        while plik.exists():
            plik = katalog / f"{data_posta}_{zbuduj_slug(pozycja.tresc)}-{licznik}.md"
            licznik += 1

        naglowek = yaml.safe_dump(
            {
                "data": data_posta,
                "typ": TYP_DO_OZNACZENIA,
                "jezyk": "",
                "reakcje": pozycja.reakcje,
                "komentarze": pozycja.komentarze,
                "url": pozycja.url,
            },
            allow_unicode=True,
            sort_keys=False,
        )
        plik.write_text(f"---\n{naglowek}---\n\n{pozycja.tresc}\n", encoding="utf-8")
        zapisane += 1

    return {"zaimportowane": zapisane}
