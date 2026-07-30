"""FastAPI: routing i SSE. Logikę agenta trzymaj w silnik.py (CLAUDE.md)."""

from __future__ import annotations

import dataclasses
import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Musi wykonać się przed jakimkolwiek importem, który buduje ClaudeAgentOptions:
# CLI Claude Code czyta ANTHROPIC_API_KEY ze środowiska procesu nadrzędnego
# (SPEC sekcja 5), więc zmienna musi tam być, zanim padnie pierwsze zapytanie.
load_dotenv()

from app import diagnostyka, pliki, silnik  # noqa: E402 — patrz komentarz wyżej

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("forces_content_studio")

KATALOG_APLIKACJI = Path(__file__).resolve().parent.parent


def katalog_danych() -> Path:
    """Czytana przy każdym żądaniu, nie raz przy starcie — SPEC wymaga, żeby
    zmiana KATALOG_DANYCH w .env działała bez zmian w kodzie (sekcja 11)."""
    return Path(os.environ.get("KATALOG_DANYCH", "./dane")).resolve()


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
