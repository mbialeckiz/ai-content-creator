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
from pydantic import BaseModel

# Musi wykonać się przed jakimkolwiek importem, który buduje ClaudeAgentOptions:
# CLI Claude Code czyta ANTHROPIC_API_KEY ze środowiska procesu nadrzędnego
# (SPEC sekcja 5), więc zmienna musi tam być, zanim padnie pierwsze zapytanie.
load_dotenv()

from app import diagnostyka, korpus, pliki, silnik  # noqa: E402 — patrz komentarz wyżej

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
        }
    )


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


async def _strumien_redaktora(brief: str) -> AsyncIterator[str]:
    async for zdarzenie in silnik.uruchom_redaktor(katalog_danych(), brief):
        if zdarzenie["typ"] == "wynik" and not zdarzenie["bledny"] and zdarzenie.get("sciezka_pliku"):
            sciezka_pelna = katalog_danych() / zdarzenie["sciezka_pliku"]
            try:
                zdarzenie["post"] = dataclasses.asdict(pliki.wczytaj_wygenerowany_post(sciezka_pelna))
            except OSError as blad:
                logger.error("Nie udało się odczytać zapisanego posta %s: %s", sciezka_pelna, blad)
                zdarzenie["post"] = None
        yield _jako_sse(zdarzenie)


@app.post("/api/redaktor", response_model=None)
async def api_redaktor(polecenie: PolecenieRedaktora) -> JSONResponse | StreamingResponse:
    """Tryb Redaktor (SPEC 8.2): brief albo pozycja z planu -> 3 warianty."""
    brief = polecenie.brief.strip()
    if not brief:
        return JSONResponse({"blad": "Brief nie może być pusty — opisz, o czym ma być post."}, status_code=400)

    blokada = _blokada_nda_lub_none(brief)
    if blokada:
        return blokada

    return StreamingResponse(_strumien_redaktora(brief), media_type="text/event-stream")


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
    sciezka = pliki.sciezka_artykulu(katalog_danych(), nazwa_pliku)
    if not sciezka.is_file():
        return JSONResponse({"blad": "Nie znaleźliśmy tego dokumentu."}, status_code=404)
    try:
        sciezka.unlink()
    except OSError as blad:
        logger.error("Nie udało się usunąć dokumentu %s: %s", sciezka, blad)
        return JSONResponse(
            {"blad": "Nie udało się usunąć dokumentu — sprawdź, czy folder danych jest dostępny."},
            status_code=500,
        )
    return JSONResponse({"usunieto": True})


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
