"""FastAPI: routing i SSE. Logikę agenta trzymaj w silnik.py (CLAUDE.md)."""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import shutil
import tempfile
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import yaml
from pydantic import BaseModel

# Musi wykonać się przed jakimkolwiek importem, który buduje ClaudeAgentOptions:
# CLI Claude Code czyta ANTHROPIC_API_KEY ze środowiska procesu nadrzędnego
# (SPEC sekcja 5), więc zmienna musi tam być, zanim padnie pierwsze zapytanie.
load_dotenv()

from app import diagnostyka, grafika, korpus, pliki, silnik  # noqa: E402 — patrz komentarz wyżej

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("forces_content_studio")

KATALOG_APLIKACJI = Path(__file__).resolve().parent.parent


def katalog_danych() -> Path:
    """Katalog roboczy z danymi operatorki.

    Czytany przy każdym żądaniu, nie raz przy starcie — SPEC wymaga, żeby
    zmiana KATALOG_DANYCH w .env działała bez zmian w kodzie (sekcja 11).

    Ścieżkę względną liczymy od katalogu aplikacji, NIE od katalogu, z
    którego uruchomiono serwer. Wcześniej było odwrotnie i wystarczyło
    uruchomić aplikację z innego miejsca, żeby `./dane` wskazało inny —
    pusty — folder: korpus, materiały i plany „znikały", choć leżały
    nietknięte w poprzednim katalogu. Ścieżka bezwzględna (np. folder
    na Dysku Google) działa jak wcześniej.
    """
    wskazana = Path(os.environ.get("KATALOG_DANYCH", "").strip() or "./dane")
    if wskazana.is_absolute():
        return wskazana.resolve()
    return (KATALOG_APLIKACJI / wskazana).resolve()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # SPEC sekcja 5: przy pierwszym uruchomieniu wypisz do logu faktyczną
    # wersję SDK i dostępne pola ClaudeAgentOptions, żeby rozbieżności API
    # były widoczne od razu.
    import claude_agent_sdk

    wersja = getattr(claude_agent_sdk, "__version__", "nieznana")
    zgodnosc = silnik.sprawdz_zgodnosc_parametrow()
    logger.info("claude-agent-sdk: wersja %s", wersja)
    logger.info("ClaudeAgentOptions — pola dostępne w SDK: %s", zgodnosc["wszystkie_pola_sdk"])
    if not zgodnosc["zgodne"]:
        logger.error(
            "Rozjazd API SDK — kod używa pól, których nie ma w zainstalowanej "
            "wersji: %s",
            zgodnosc["brakujace_w_sdk"],
        )
    yield


app = FastAPI(title="Forces DC Content Studio", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=KATALOG_APLIKACJI / "app" / "static"), name="static")


@app.get("/")
async def strona_glowna() -> FileResponse:
    return FileResponse(KATALOG_APLIKACJI / "app" / "static" / "index.html")


@app.get("/api/diagnostyka")
async def api_diagnostyka() -> JSONResponse:
    raport = diagnostyka.uruchom_diagnostyke(katalog_danych())
    return JSONResponse(
        {
            "sprawdzenia": [dataclasses.asdict(s) for s in raport.sprawdzenia],
            "liczniki": raport.liczniki,
            "ustawienia": pliki.stan_pliku_env(KATALOG_APLIKACJI),
        }
    )


class NowyKluczApi(BaseModel):
    klucz: str


@app.post("/api/klucz-api", response_model=None)
async def api_zapisz_klucz(dane: NowyKluczApi) -> JSONResponse:
    """Zapisuje klucz do .env i od razu udostępnia go bieżącemu procesowi,
    więc nie trzeba restartować aplikacji.

    Klucz nigdy nie jest zwracany do przeglądarki (SPEC 10.5) — endpoint
    potwierdza tylko zapis. Aplikacja słucha wyłącznie na localhost.
    """
    klucz = dane.klucz.strip().strip("\"'")
    if not klucz:
        return JSONResponse({"blad": "Wklej klucz, zanim zapiszesz."}, status_code=400)
    if not klucz.startswith("sk-ant-") or len(klucz) < 40:
        return JSONResponse(
            {
                "blad": (
                    "To nie wygląda na klucz API — powinien zaczynać się od "
                    "sk-ant- i być znacznie dłuższy. Skopiuj go ponownie "
                    "z console.anthropic.com (sekcja API Keys)."
                )
            },
            status_code=400,
        )

    try:
        pliki.zapisz_klucz_api(KATALOG_APLIKACJI, klucz)
    except OSError as blad:
        logger.error("Nie udało się zapisać klucza do .env: %s", blad)
        return JSONResponse(
            {"blad": "Nie udało się zapisać ustawień — sprawdź uprawnienia do katalogu aplikacji."},
            status_code=500,
        )

    # Bieżący proces dostaje klucz od razu; CLI dziedziczy go przy następnym
    # wywołaniu, więc restart nie jest potrzebny.
    os.environ["ANTHROPIC_API_KEY"] = klucz
    logger.info("Zapisano nowy klucz API (wartość nie jest logowana).")
    return JSONResponse({"zapisano": True})


def _jako_sse(dane: dict) -> str:
    return f"data: {json.dumps(dane, ensure_ascii=False)}\n\n"


async def _strumien_testu_silnika() -> AsyncIterator[str]:
    async for zdarzenie in silnik.testowe_wywolanie(katalog_danych()):
        yield _jako_sse(zdarzenie)


@app.get("/api/silnik/test")
async def api_silnik_test() -> StreamingResponse:
    """Jedyny tryb agenta w Fazie 1 — potwierdza, że SDK faktycznie działa
    (SPEC sekcja 12, Faza 1). Tryby Strateg/Redaktor/Wywiad przychodzą później."""
    return StreamingResponse(_strumien_testu_silnika(), media_type="text/event-stream")


def _blokada_nda_lub_none(tekst: str) -> JSONResponse | None:
    """Blokada NDA (SPEC 10.2–10.3), sprawdzana synchronicznie przed
    jakimkolwiek wywołaniem SDK — nie tylko instrukcją w prompcie modelu
    (SPEC 10.1, kryterium akceptacji frontendu)."""
    fraza_nda = pliki.wykryj_fraze_nda(tekst, katalog_danych())
    if not fraza_nda:
        return None
    logger.warning("Zablokowano polecenie zawierające frazę objętą NDA.")
    return JSONResponse({"zablokowane_nda": True, "fraza": fraza_nda})


class PolecenieRedaktora(BaseModel):
    brief: str
    # Fragment artykułu lub raportu wklejony ręcznie przez operatorkę.
    material_zrodlowy: str = ""


async def _strumien_redaktora(brief: str, material_zrodlowy: str = "") -> AsyncIterator[str]:
    """Zbiera treść od redaktora i to backend zapisuje plik, nie agent.

    Dzięki temu przerwany przebieg (np. po przekroczeniu limitu kosztu) nie
    przepada w całości: zapisujemy to, co model zdążył napisać, a operatorka
    dostaje gotowe warianty zamiast samego komunikatu o błędzie.
    """
    katalog = katalog_danych()
    material = pliki.zbuduj_material_dla_redaktora(katalog, material_zrodlowy=material_zrodlowy)
    zebrane: list[str] = []
    przerwane = False

    async for zdarzenie in silnik.uruchom_redaktor(katalog, brief, material):
        if zdarzenie["typ"] == "fragment":
            zebrane.append(zdarzenie["tekst"])
            continue
        if zdarzenie["typ"] == "blad":
            przerwane = True
            yield _jako_sse(zdarzenie)
            continue
        if zdarzenie["typ"] == "wynik":
            zdarzenie["post"] = None
            tresc = "".join(zebrane).strip()
            if tresc:
                try:
                    nazwa = pliki.zapisz_wygenerowany_post(katalog, brief, tresc)
                    zdarzenie["sciezka_pliku"] = nazwa
                    zdarzenie["post"] = dataclasses.asdict(
                        pliki.wczytaj_wygenerowany_post(
                            pliki.sciezka_wygenerowanego_posta(katalog, nazwa)
                        )
                    )
                    zdarzenie["czesciowy"] = przerwane or not zdarzenie["post"]["kompletny"]
                except OSError as blad:
                    logger.error("Nie udało się zapisać wygenerowanego posta: %s", blad)
                    zdarzenie["blad_zapisu"] = (
                        "Tekst powstał, ale nie udało się go zapisać — sprawdź, "
                        "czy folder danych jest dostępny."
                    )
        yield _jako_sse(zdarzenie)


@app.post("/api/redaktor", response_model=None)
async def api_redaktor(polecenie: PolecenieRedaktora) -> JSONResponse | StreamingResponse:
    """Tryb Redaktor (SPEC 8.2): brief albo pozycja z planu -> 3 warianty."""
    brief = polecenie.brief.strip()
    if not brief:
        return JSONResponse({"blad": "Brief nie może być pusty — opisz, o czym ma być post."}, status_code=400)

    # Wklejony materiał źródłowy sprawdzamy tak samo jak brief — nazwa objęta
    # NDA równie łatwo trafi tu przez wklejenie, co przez wpisanie.
    blokada = _blokada_nda_lub_none(f"{brief}\n{polecenie.material_zrodlowy}")
    if blokada:
        return blokada

    return StreamingResponse(
        _strumien_redaktora(brief, polecenie.material_zrodlowy),
        media_type="text/event-stream",
    )


class WiadomoscAsystenta(BaseModel):
    wiadomosc: str


async def _strumien_asystenta(wiadomosc: str) -> AsyncIterator[str]:
    async for zdarzenie in silnik.uruchom_asystenta(katalog_danych(), wiadomosc):
        yield _jako_sse(zdarzenie)


@app.post("/api/asystent", response_model=None)
async def api_asystent(polecenie: WiadomoscAsystenta) -> JSONResponse | StreamingResponse:
    """Tryb Asystent (SPEC-frontend 5) — główny czat. Kosztowne operacje nie
    uruchamiają się same: model zgłasza zdarzenie "propozycja", a operator
    zatwierdza ją osobnym wywołaniem /api/redaktor (patrz app.js)."""
    wiadomosc = polecenie.wiadomosc.strip()
    if not wiadomosc:
        return JSONResponse({"blad": "Napisz coś, zanim wyślesz wiadomość."}, status_code=400)

    blokada = _blokada_nda_lub_none(wiadomosc)
    if blokada:
        return blokada

    return StreamingResponse(_strumien_asystenta(wiadomosc), media_type="text/event-stream")


# --- Ekran „Styl": pliki sterujące zachowaniem asystenta (SPEC 8.4) ---


@app.get("/api/pliki")
async def api_pliki() -> JSONResponse:
    return JSONResponse({"pliki": pliki.lista_plikow_jakosci(katalog_danych())})


@app.get("/api/pliki/{identyfikator}", response_model=None)
async def api_plik(identyfikator: str) -> JSONResponse:
    try:
        tresc = pliki.czytaj_plik_jakosci(katalog_danych(), identyfikator)
    except KeyError:
        return JSONResponse({"blad": "Nie znamy takiego pliku ustawień."}, status_code=404)
    except OSError as blad:
        logger.error("Nie udało się odczytać pliku %s: %s", identyfikator, blad)
        return JSONResponse(
            {"blad": "Nie udało się odczytać pliku — sprawdź, czy folder danych jest dostępny."},
            status_code=500,
        )
    return JSONResponse({"tresc": tresc, "luki": pliki.policz_luki(tresc)})


class TrescPliku(BaseModel):
    tresc: str


@app.put("/api/pliki/{identyfikator}", response_model=None)
async def api_zapisz_plik(identyfikator: str, dane: TrescPliku) -> JSONResponse:
    try:
        pliki.zapisz_plik_jakosci(katalog_danych(), identyfikator, dane.tresc)
    except KeyError:
        return JSONResponse({"blad": "Nie znamy takiego pliku ustawień."}, status_code=404)
    except OSError as blad:
        logger.error("Nie udało się zapisać pliku %s: %s", identyfikator, blad)
        return JSONResponse(
            {"blad": "Nie udało się zapisać pliku — sprawdź, czy folder danych jest dostępny."},
            status_code=500,
        )
    return JSONResponse({"zapisano": True, "luki": pliki.policz_luki(dane.tresc)})


# --- Ekran „Korpus" (SPEC 8.5, SPEC-frontend 10) ---


@app.get("/api/korpus")
async def api_korpus() -> JSONResponse:
    posty, ostrzezenia = korpus.wczytaj_korpus(katalog_danych())
    return JSONResponse(
        {
            "posty": [dataclasses.asdict(post) | {"wymaga_oznaczenia": post.wymaga_oznaczenia} for post in posty],
            "ostrzezenia": ostrzezenia,
            "docelowo": korpus.DOCELOWA_LICZBA_POSTOW,
            "dozwolone_typy": list(korpus.DOZWOLONE_TYPY),
        }
    )


class NowyPost(BaseModel):
    data: str
    typ: str
    jezyk: str = "pl"
    reakcje: int = 0
    komentarze: int = 0
    url: str = ""
    tresc: str


@app.post("/api/korpus", response_model=None)
async def api_dodaj_post(post: NowyPost) -> JSONResponse:
    try:
        nazwa = korpus.zapisz_post(
            katalog_danych(),
            data=post.data,
            typ=post.typ,
            jezyk=post.jezyk,
            reakcje=post.reakcje,
            komentarze=post.komentarze,
            url=post.url,
            tresc=post.tresc,
        )
    except korpus.BladWalidacji as blad:
        return JSONResponse({"blad": str(blad)}, status_code=400)
    except OSError as blad:
        logger.error("Nie udało się zapisać posta korpusu: %s", blad)
        return JSONResponse(
            {"blad": "Nie udało się zapisać posta — sprawdź, czy folder danych jest dostępny."},
            status_code=500,
        )
    return JSONResponse({"zapisano": True, "plik": nazwa})


class OznaczenieTypu(BaseModel):
    typ: str


@app.patch("/api/korpus/{nazwa_pliku}", response_model=None)
async def api_oznacz_typ(nazwa_pliku: str, dane: OznaczenieTypu) -> JSONResponse:
    try:
        korpus.oznacz_typ(katalog_danych(), nazwa_pliku, dane.typ)
    except korpus.BladWalidacji as blad:
        return JSONResponse({"blad": str(blad)}, status_code=400)
    except OSError as blad:
        logger.error("Nie udało się zmienić typu posta %s: %s", nazwa_pliku, blad)
        return JSONResponse(
            {"blad": "Nie udało się zapisać zmiany — sprawdź, czy folder danych jest dostępny."},
            status_code=500,
        )
    return JSONResponse({"zapisano": True})


@app.delete("/api/korpus/{nazwa_pliku}", response_model=None)
async def api_usun_post(nazwa_pliku: str) -> JSONResponse:
    try:
        korpus.usun_post(katalog_danych(), nazwa_pliku)
    except korpus.BladWalidacji as blad:
        return JSONResponse({"blad": str(blad)}, status_code=404)
    except OSError as blad:
        logger.error("Nie udało się usunąć posta %s: %s", nazwa_pliku, blad)
        return JSONResponse(
            {"blad": "Nie udało się usunąć posta — sprawdź, czy folder danych jest dostępny."},
            status_code=500,
        )
    return JSONResponse({"usunieto": True})


# Wgrane pliki czekające na potwierdzenie importu. Trzymane w katalogu
# tymczasowym systemu, nie w katalogu danych: to stan przejściowy jednego
# kliknięcia, a nie dane aplikacji (te są w plikach .md — CLAUDE.md #2).
KATALOG_WGRANYCH = Path(tempfile.gettempdir()) / "forces-content-studio-import"


@app.post("/api/korpus/import/analiza", response_model=None)
async def api_import_analiza(plik: UploadFile = File(...)) -> JSONResponse:
    """Krok 1 importu: analiza wgranego pliku. Nic jeszcze nie zapisuje do
    korpusu — operatorka najpierw widzi, co zostanie zaimportowane (SPEC 8.5)."""
    KATALOG_WGRANYCH.mkdir(parents=True, exist_ok=True)
    rozszerzenie = Path(plik.filename or "").suffix.lower()
    identyfikator = uuid.uuid4().hex
    sciezka = KATALOG_WGRANYCH / f"{identyfikator}{rozszerzenie}"

    try:
        with sciezka.open("wb") as docelowy:
            shutil.copyfileobj(plik.file, docelowy)
        diagnostyka_importu, _ = korpus.przeanalizuj_plik_importu(sciezka)
    except korpus.BladWalidacji as blad:
        sciezka.unlink(missing_ok=True)
        return JSONResponse({"blad": str(blad)}, status_code=400)
    except Exception as blad:  # noqa: BLE001 — pandas rzuca różnymi typami
        logger.error("Nie udało się przeanalizować wgranego pliku: %s", blad)
        sciezka.unlink(missing_ok=True)
        return JSONResponse(
            {
                "blad": (
                    "Nie udało się odczytać tego pliku. Sprawdź, czy to poprawny "
                    "plik CSV, XLSX albo JSON z eksportu LinkedIn."
                )
            },
            status_code=400,
        )

    return JSONResponse(
        {"identyfikator": sciezka.name, "diagnostyka": dataclasses.asdict(diagnostyka_importu)}
    )


class PotwierdzenieImportu(BaseModel):
    identyfikator: str
    limit: int | None = None


@app.post("/api/korpus/import/wykonaj", response_model=None)
async def api_import_wykonaj(dane: PotwierdzenieImportu) -> JSONResponse:
    """Krok 2 importu: zapis do korpusu po potwierdzeniu przez operatorkę."""
    sciezka = KATALOG_WGRANYCH / Path(dane.identyfikator).name
    if not sciezka.is_file():
        return JSONResponse(
            {"blad": "Wgrany plik wygasł — wgraj go jeszcze raz i potwierdź import."},
            status_code=404,
        )

    try:
        diagnostyka_importu, wiersze = korpus.przeanalizuj_plik_importu(sciezka)
        wynik = korpus.zaimportuj(katalog_danych(), wiersze, dane.limit)
    except korpus.BladWalidacji as blad:
        return JSONResponse({"blad": str(blad)}, status_code=400)
    except OSError as blad:
        logger.error("Nie udało się zaimportować korpusu: %s", blad)
        return JSONResponse(
            {"blad": "Nie udało się zapisać postów — sprawdź, czy folder danych jest dostępny."},
            status_code=500,
        )
    finally:
        sciezka.unlink(missing_ok=True)

    return JSONResponse(
        {
            "zaimportowane": wynik["zaimportowane"],
            "odrzucone_reposty": diagnostyka_importu.odrzucone_reposty,
            "odrzucone_krotkie": diagnostyka_importu.odrzucone_krotkie,
        }
    )


@app.get("/api/posty")
async def api_lista_postow() -> JSONResponse:
    """Wcześniej wygenerowane posty — czytane z dysku, żeby przetrwały
    przełączenie zakładki, odświeżenie strony i restart aplikacji."""
    return JSONResponse({"posty": pliki.lista_wygenerowanych_postow(katalog_danych())})


@app.get("/api/posty/{nazwa_pliku}", response_model=None)
async def api_wczytaj_post(nazwa_pliku: str) -> JSONResponse:
    sciezka = pliki.sciezka_wygenerowanego_posta(katalog_danych(), nazwa_pliku)
    if not sciezka.is_file():
        return JSONResponse({"blad": "Nie znaleźliśmy tego posta."}, status_code=404)
    try:
        post = pliki.wczytaj_wygenerowany_post(sciezka)
    except OSError as blad:
        logger.error("Nie udało się odczytać posta %s: %s", sciezka, blad)
        return JSONResponse(
            {"blad": "Nie udało się odczytać posta — sprawdź, czy folder danych jest dostępny."},
            status_code=500,
        )
    return JSONResponse({"post": dataclasses.asdict(post), "plik": sciezka.name})


class PoleceniePoprawki(BaseModel):
    plik: str
    indeks: int
    polecenie: str


async def _strumien_poprawki(plik: str, indeks: int, polecenie: str) -> AsyncIterator[str]:
    katalog = katalog_danych()
    sciezka = pliki.sciezka_wygenerowanego_posta(katalog, plik)
    post = pliki.wczytaj_wygenerowany_post(sciezka)
    obecna = post.warianty[indeks].tresc

    zebrane: list[str] = []
    async for zdarzenie in silnik.popraw_wariant(
        katalog, obecna, polecenie, pliki.wczytaj_zasady_stylu(katalog)
    ):
        if zdarzenie["typ"] == "fragment":
            # Fragmenty poprawki zbieramy, zamiast wysyłać na bieżąco: dopóki
            # nie znamy całości, nie da się jej ani zapisać, ani policzyć znaków.
            zebrane.append(zdarzenie["tekst"])
            continue
        if zdarzenie["typ"] == "wynik" and not zdarzenie["bledny"]:
            nowa = "".join(zebrane).strip()
            if not nowa:
                zdarzenie["blad_poprawki"] = "Asystent nie zwrócił poprawionej treści."
            else:
                try:
                    pliki.podmien_wariant(sciezka, indeks, nowa)
                    zdarzenie["nowa_tresc"] = nowa
                    zdarzenie["znaki"] = len(nowa)
                except (KeyError, OSError) as blad:
                    logger.error("Nie udało się zapisać poprawki w %s: %s", sciezka, blad)
                    zdarzenie["blad_poprawki"] = (
                        "Poprawka powstała, ale nie udało się jej zapisać — "
                        "sprawdź, czy folder danych jest dostępny."
                    )
        yield _jako_sse(zdarzenie)


@app.post("/api/popraw", response_model=None)
async def api_popraw(dane: PoleceniePoprawki) -> JSONResponse | StreamingResponse:
    """Poprawianie wariantu jednym poleceniem (SPEC-frontend 7)."""
    polecenie = dane.polecenie.strip()
    if not polecenie:
        return JSONResponse({"blad": "Napisz, co zmienić w tym poście."}, status_code=400)

    blokada = _blokada_nda_lub_none(polecenie)
    if blokada:
        return blokada

    sciezka = pliki.sciezka_wygenerowanego_posta(katalog_danych(), dane.plik)
    if not sciezka.is_file():
        return JSONResponse({"blad": "Nie znaleźliśmy tego posta."}, status_code=404)
    try:
        post = pliki.wczytaj_wygenerowany_post(sciezka)
    except OSError as blad:
        logger.error("Nie udało się odczytać posta %s: %s", sciezka, blad)
        return JSONResponse({"blad": "Nie udało się odczytać posta."}, status_code=500)
    if not 0 <= dane.indeks < len(post.warianty):
        return JSONResponse({"blad": "Ten wariant nie istnieje w zapisanym poście."}, status_code=400)

    return StreamingResponse(
        _strumien_poprawki(dane.plik, dane.indeks, polecenie),
        media_type="text/event-stream",
    )


class ZapotrzebowanieNaGrafike(BaseModel):
    plik: str
    indeks: int = 0


async def _strumien_grafiki(plik: str, indeks: int) -> AsyncIterator[str]:
    katalog = katalog_danych()
    sciezka = pliki.sciezka_wygenerowanego_posta(katalog, plik)
    post = pliki.wczytaj_wygenerowany_post(sciezka)
    tresc = post.warianty[indeks].tresc

    zebrane: list[str] = []
    async for zdarzenie in silnik.zaproponuj_haslo_grafiki(katalog, tresc, post.brief_graficzny):
        if zdarzenie["typ"] == "fragment":
            zebrane.append(zdarzenie["tekst"])
            continue
        if zdarzenie["typ"] == "wynik" and not zdarzenie["bledny"]:
            rozebrane = silnik.rozbierz_odpowiedz_o_grafice("".join(zebrane))
            if not rozebrane["haslo"]:
                zdarzenie["blad_grafiki"] = (
                    "Asystent nie zaproponował hasła. Wpisz je ręcznie w polu poniżej."
                )
            else:
                zdarzenie["grafika"] = grafika.zbuduj_dane_grafiki(
                    katalog, haslo=rozebrane["haslo"], podtytul=rozebrane["podtytul"]
                )
                zdarzenie["grafika"]["alt"] = rozebrane["alt"]
        yield _jako_sse(zdarzenie)


@app.post("/api/grafika", response_model=None)
async def api_grafika(dane: ZapotrzebowanieNaGrafike) -> JSONResponse | StreamingResponse:
    """Dobiera hasło na grafikę do wybranego wariantu posta."""
    sciezka = pliki.sciezka_wygenerowanego_posta(katalog_danych(), dane.plik)
    if not sciezka.is_file():
        return JSONResponse({"blad": "Nie znaleźliśmy tego posta."}, status_code=404)
    try:
        post = pliki.wczytaj_wygenerowany_post(sciezka)
    except OSError as blad:
        logger.error("Nie udało się odczytać posta %s: %s", sciezka, blad)
        return JSONResponse({"blad": "Nie udało się odczytać posta."}, status_code=500)
    if not 0 <= dane.indeks < len(post.warianty):
        return JSONResponse({"blad": "Ten wariant nie istnieje."}, status_code=400)

    return StreamingResponse(_strumien_grafiki(dane.plik, dane.indeks), media_type="text/event-stream")


class RecznaGrafika(BaseModel):
    haslo: str
    podtytul: str = ""
    wariant_kolorystyczny: str = "ciemny"


@app.post("/api/grafika/podglad", response_model=None)
async def api_grafika_podglad(dane: RecznaGrafika) -> JSONResponse:
    """Przelicza dane grafiki po ręcznej zmianie hasła albo wariantu kolorów.
    Nie woła modelu — jest darmowe i natychmiastowe."""
    if not dane.haslo.strip():
        return JSONResponse({"blad": "Wpisz hasło, które ma być na grafice."}, status_code=400)
    return JSONResponse(
        {
            "grafika": grafika.zbuduj_dane_grafiki(
                katalog_danych(),
                haslo=dane.haslo.strip(),
                podtytul=dane.podtytul.strip(),
                wariant_kolorystyczny=dane.wariant_kolorystyczny,
            )
        }
    )


@app.get("/api/brand-kit")
async def api_brand_kit() -> JSONResponse:
    katalog = katalog_danych()
    kit, ostrzezenia = grafika.wczytaj_brand_kit(katalog)
    plik = grafika.sciezka_brand_kitu(katalog)
    return JSONResponse(
        {
            "tresc": plik.read_text(encoding="utf-8") if plik.is_file() else "",
            "ostrzezenia": ostrzezenia,
            "logo": grafika.lista_logo(katalog),
            "nazwa_firmy": kit["nazwa_firmy"],
        }
    )


@app.put("/api/brand-kit", response_model=None)
async def api_zapisz_brand_kit(dane: TrescPliku) -> JSONResponse:
    try:
        yaml.safe_load(dane.tresc)
    except yaml.YAMLError as blad:
        return JSONResponse(
            {"blad": f"Plik ma błąd formatu i nie został zapisany: {blad}"}, status_code=400
        )
    try:
        grafika.sciezka_brand_kitu(katalog_danych()).write_text(dane.tresc, encoding="utf-8")
    except OSError as blad:
        logger.error("Nie udało się zapisać identyfikacji wizualnej: %s", blad)
        return JSONResponse(
            {"blad": "Nie udało się zapisać — sprawdź, czy folder danych jest dostępny."},
            status_code=500,
        )
    _, ostrzezenia = grafika.wczytaj_brand_kit(katalog_danych())
    return JSONResponse({"zapisano": True, "ostrzezenia": ostrzezenia})


@app.post("/api/brand-kit/logo", response_model=None)
async def api_wgraj_logo(plik: UploadFile = File(...)) -> JSONResponse:
    nazwa = plik.filename or "logo.png"
    if Path(nazwa).suffix.lower() not in grafika.ROZSZERZENIA_LOGO:
        return JSONResponse(
            {"blad": "Logo wgraj jako PNG, SVG, JPG albo WEBP."}, status_code=400
        )
    cel = grafika.przygotuj_miejsce_na_logo(katalog_danych(), nazwa)
    try:
        with cel.open("wb") as docelowy:
            shutil.copyfileobj(plik.file, docelowy)
    except OSError as blad:
        logger.error("Nie udało się zapisać logo %s: %s", cel, blad)
        return JSONResponse({"blad": "Nie udało się zapisać logo."}, status_code=500)
    return JSONResponse({"zapisano": True, "plik": cel.name})


class PrzywroceniePoprzedniej(BaseModel):
    plik: str
    indeks: int
    tresc: str


@app.post("/api/popraw/cofnij", response_model=None)
async def api_cofnij_poprawke(dane: PrzywroceniePoprzedniej) -> JSONResponse:
    """Przywraca poprzednią treść wariantu. Wersje trzyma przeglądarka, więc
    cofanie nie wymaga wywołania modelu ani osobnej historii na dysku."""
    sciezka = pliki.sciezka_wygenerowanego_posta(katalog_danych(), dane.plik)
    if not sciezka.is_file():
        return JSONResponse({"blad": "Nie znaleźliśmy tego posta."}, status_code=404)
    try:
        pliki.podmien_wariant(sciezka, dane.indeks, dane.tresc)
    except (KeyError, OSError) as blad:
        logger.error("Nie udało się cofnąć poprawki w %s: %s", sciezka, blad)
        return JSONResponse({"blad": "Nie udało się przywrócić poprzedniej wersji."}, status_code=500)
    return JSONResponse({"przywrocono": True})


class WyborWariantu(BaseModel):
    plik: str
    # None = odznaczenie wyboru (operatorka klika drugi raz w ten sam wariant).
    indeks: int | None = None


@app.post("/api/posty/wybrany", response_model=None)
async def api_oznacz_wybrany(dane: WyborWariantu) -> JSONResponse:
    """Zapisuje, który wariant idzie do publikacji (SPEC-frontend 7).

    Bez wywołania modelu — to zwykły zapis do pliku, więc nic nie kosztuje.
    """
    sciezka = pliki.sciezka_wygenerowanego_posta(katalog_danych(), dane.plik)
    if not sciezka.is_file():
        return JSONResponse({"blad": "Nie znaleźliśmy tego posta."}, status_code=404)
    try:
        pliki.oznacz_wybrany_wariant(sciezka, dane.indeks)
    except OSError as blad:
        logger.error("Nie udało się zapisać wyboru wariantu w %s: %s", sciezka, blad)
        return JSONResponse(
            {"blad": "Nie udało się zapisać wyboru — sprawdź, czy folder danych jest dostępny."},
            status_code=500,
        )
    return JSONResponse({"wybrany": dane.indeks})


@app.delete("/api/posty/{nazwa_pliku}", response_model=None)
async def api_usun_wygenerowany_post(nazwa_pliku: str) -> JSONResponse:
    sciezka = pliki.sciezka_wygenerowanego_posta(katalog_danych(), nazwa_pliku)
    if not sciezka.is_file():
        return JSONResponse({"blad": "Nie znaleźliśmy tego posta."}, status_code=404)
    try:
        sciezka.unlink()
    except OSError as blad:
        logger.error("Nie udało się usunąć posta %s: %s", sciezka, blad)
        return JSONResponse(
            {"blad": "Nie udało się usunąć posta — sprawdź, czy folder danych jest dostępny."},
            status_code=500,
        )
    return JSONResponse({"usunieto": True})


# --- Ekran „Plan" (tryb Strateg, SPEC 8.1 / SPEC-frontend 6) ---


def _poprzedni_miesiac(miesiac: str) -> str:
    rok, numer = (int(czesc) for czesc in miesiac.split("-"))
    return f"{rok - 1}-12" if numer == 1 else f"{rok}-{numer - 1:02d}"


@app.get("/api/plan/{miesiac}")
async def api_plan(miesiac: str) -> JSONResponse:
    katalog = katalog_danych()
    plan = pliki.wczytaj_plan(katalog, miesiac)
    materialy = pliki.wczytaj_materialy(katalog, miesiac)
    posty_korpusu, _ = korpus.wczytaj_korpus(katalog)

    # Warunki wstępne pokazywane na pustym ekranie planu (SPEC-frontend 6):
    # operator ma z góry widzieć konsekwencje braków, zanim kliknie „Zbuduj".
    pliki_jakosci = {plik["id"]: plik for plik in pliki.lista_plikow_jakosci(katalog)}
    zrodla = pliki_jakosci.get("zrodla-branzowe", {})
    return JSONResponse(
        {
            "plan": dataclasses.asdict(plan),
            "warunki": {
                "korpus": len(posty_korpusu),
                "korpus_docelowo": korpus.DOCELOWA_LICZBA_POSTOW,
                "zrodla_luki": zrodla.get("luki", 0),
                "materialy_puste": pliki.czy_materialy_puste(materialy),
                "materialy_poprzedni_puste": pliki.czy_materialy_puste(
                    pliki.wczytaj_materialy(katalog, _poprzedni_miesiac(miesiac))
                ),
            },
            "statusy": list(pliki.STATUSY_PLANU),
        }
    )


class PolecenieStratega(BaseModel):
    miesiac: str
    uwagi: str = ""


async def _strumien_stratega(miesiac: str, uwagi: str) -> AsyncIterator[str]:
    async for zdarzenie in silnik.uruchom_stratega(katalog_danych(), miesiac, uwagi):
        if zdarzenie["typ"] == "wynik" and not zdarzenie["bledny"]:
            zdarzenie["plan"] = dataclasses.asdict(
                pliki.wczytaj_plan(katalog_danych(), miesiac)
            )
        yield _jako_sse(zdarzenie)


@app.post("/api/plan", response_model=None)
async def api_zbuduj_plan(polecenie: PolecenieStratega) -> JSONResponse | StreamingResponse:
    blokada = _blokada_nda_lub_none(polecenie.uwagi)
    if blokada:
        return blokada
    return StreamingResponse(
        _strumien_stratega(polecenie.miesiac, polecenie.uwagi),
        media_type="text/event-stream",
    )


class ZmianaStatusu(BaseModel):
    numer_wiersza: int
    status: str


@app.patch("/api/plan/{miesiac}", response_model=None)
async def api_zmien_status(miesiac: str, dane: ZmianaStatusu) -> JSONResponse:
    try:
        pliki.zmien_status_pozycji(katalog_danych(), miesiac, dane.numer_wiersza, dane.status)
    except (ValueError, IndexError) as blad:
        return JSONResponse({"blad": str(blad)}, status_code=400)
    except FileNotFoundError as blad:
        return JSONResponse({"blad": str(blad)}, status_code=404)
    except OSError as blad:
        logger.error("Nie udało się zapisać statusu w planie %s: %s", miesiac, blad)
        return JSONResponse(
            {"blad": "Nie udało się zapisać zmiany — sprawdź, czy folder danych jest dostępny."},
            status_code=500,
        )
    return JSONResponse({"zapisano": True})


# --- Ekran „Materiały" (input firmowy, SPEC-frontend 8) ---


@app.get("/api/materialy/{miesiac}")
async def api_materialy(miesiac: str) -> JSONResponse:
    materialy = pliki.wczytaj_materialy(katalog_danych(), miesiac)
    return JSONResponse(
        {
            "materialy": materialy,
            "sekcje": list(pliki.SEKCJE_MATERIALOW),
            "puste": pliki.czy_materialy_puste(materialy),
        }
    )


@app.get("/api/artykuly")
async def api_lista_artykulow() -> JSONResponse:
    return JSONResponse(
        {
            "artykuly": pliki.lista_artykulow(katalog_danych()),
            "obslugiwane": list(pliki.ROZSZERZENIA_ARTYKULOW),
        }
    )


@app.post("/api/artykuly", response_model=None)
async def api_wgraj_artykul(plik: UploadFile = File(...)) -> JSONResponse:
    """Wgranie dokumentu źródłowego (artykuł, notatka, raport), z którego
    asystent może korzystać przy pisaniu. Zapis do katalogu danych, więc
    dokument przeżywa restart aplikacji i jedzie razem z folderem danych."""
    nazwa = plik.filename or "dokument"
    if Path(nazwa).suffix.lower() not in pliki.ROZSZERZENIA_ARTYKULOW:
        return JSONResponse(
            {
                "blad": (
                    f"Nie obsługujemy plików „{Path(nazwa).suffix or 'bez rozszerzenia'}”. "
                    "Wgraj dokument w formacie PDF, TXT, MD, CSV albo HTML. "
                    "Plik z Worda zapisz najpierw jako PDF."
                )
            },
            status_code=400,
        )

    cel = pliki.przygotuj_miejsce_na_artykul(katalog_danych(), nazwa)
    try:
        with cel.open("wb") as docelowy:
            shutil.copyfileobj(plik.file, docelowy)
    except OSError as blad:
        logger.error("Nie udało się zapisać dokumentu %s: %s", cel, blad)
        return JSONResponse(
            {"blad": "Nie udało się zapisać dokumentu — sprawdź, czy folder danych jest dostępny."},
            status_code=500,
        )
    return JSONResponse({"zapisano": True, "plik": cel.name})


@app.delete("/api/artykuly/{nazwa_pliku}", response_model=None)
async def api_usun_artykul(nazwa_pliku: str) -> JSONResponse:
    katalog = katalog_danych()
    sciezka = pliki.sciezka_artykulu(katalog, nazwa_pliku)
    if not sciezka.is_file():
        return JSONResponse({"blad": "Nie znaleźliśmy tego dokumentu."}, status_code=404)
    try:
        sciezka.unlink()
        # Wyciąg bez dokumentu byłby sierotą — i dalej trafiałby do postów.
        pliki.sciezka_wyciagu(katalog, nazwa_pliku).unlink(missing_ok=True)
    except OSError as blad:
        logger.error("Nie udało się usunąć dokumentu %s: %s", sciezka, blad)
        return JSONResponse(
            {"blad": "Nie udało się usunąć dokumentu — sprawdź, czy folder danych jest dostępny."},
            status_code=500,
        )
    return JSONResponse({"usunieto": True})


@app.get("/api/artykuly/{nazwa_pliku}/wyciag", response_model=None)
async def api_wczytaj_wyciag(nazwa_pliku: str) -> JSONResponse:
    tresc = pliki.wczytaj_wyciag(katalog_danych(), nazwa_pliku)
    if not tresc:
        return JSONResponse(
            {"blad": "Ten dokument nie został jeszcze przeczytany."}, status_code=404
        )
    return JSONResponse({"wyciag": tresc})


async def _strumien_wyciagu(nazwa_pliku: str) -> AsyncIterator[str]:
    katalog = katalog_danych()
    sciezka = pliki.sciezka_artykulu(katalog, nazwa_pliku)
    wzgledna = str(sciezka.relative_to(katalog))

    zebrane: list[str] = []
    async for zdarzenie in silnik.zrob_wyciag_z_dokumentu(katalog, wzgledna):
        if zdarzenie["typ"] == "fragment":
            zebrane.append(zdarzenie["tekst"])
            continue
        if zdarzenie["typ"] == "wynik":
            tresc = "".join(zebrane).strip()
            if not tresc:
                zdarzenie["blad_wyciagu"] = (
                    "Asystent nie zwrócił nic z tego dokumentu. Sprawdź, czy plik "
                    "nie jest skanem bez warstwy tekstowej — z takiego nie da się "
                    "nic odczytać."
                )
            else:
                try:
                    pliki.zapisz_wyciag(katalog, nazwa_pliku, tresc)
                    zdarzenie["wyciag"] = tresc
                except OSError as blad:
                    logger.error("Nie udało się zapisać wyciągu z %s: %s", nazwa_pliku, blad)
                    zdarzenie["blad_wyciagu"] = (
                        "Wyciąg powstał, ale nie udało się go zapisać — sprawdź, "
                        "czy folder danych jest dostępny."
                    )
        yield _jako_sse(zdarzenie)


@app.post("/api/artykuly/{nazwa_pliku}/wyciag", response_model=None)
async def api_zrob_wyciag(nazwa_pliku: str) -> JSONResponse | StreamingResponse:
    """Jednorazowe przeczytanie dokumentu: fakty, liczby i tematy na posty.

    Osobny krok, a nie automat przy wgrywaniu — wielostronicowy raport
    kosztuje realne pieniądze i operatorka ma o tym zdecydować świadomie.
    """
    sciezka = pliki.sciezka_artykulu(katalog_danych(), nazwa_pliku)
    if not sciezka.is_file():
        return JSONResponse({"blad": "Nie znaleźliśmy tego dokumentu."}, status_code=404)
    if sciezka.suffix.lower() not in pliki.ROZSZERZENIA_ARTYKULOW:
        return JSONResponse(
            {"blad": "Tego formatu asystent nie odczyta — wgraj PDF, TXT, MD, CSV albo HTML."},
            status_code=400,
        )
    return StreamingResponse(_strumien_wyciagu(nazwa_pliku), media_type="text/event-stream")


class ZapisMaterialow(BaseModel):
    materialy: dict[str, list[str]]


@app.put("/api/materialy/{miesiac}", response_model=None)
async def api_zapisz_materialy(miesiac: str, dane: ZapisMaterialow) -> JSONResponse:
    try:
        pliki.zapisz_materialy(katalog_danych(), miesiac, dane.materialy)
    except OSError as blad:
        logger.error("Nie udało się zapisać materiałów na %s: %s", miesiac, blad)
        return JSONResponse(
            {"blad": "Nie udało się zapisać materiałów — sprawdź, czy folder danych jest dostępny."},
            status_code=500,
        )
    return JSONResponse({"zapisano": True})
