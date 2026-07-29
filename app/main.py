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

# Musi wykonać się przed jakimkolwiek importem, który buduje ClaudeAgentOptions:
# CLI Claude Code czyta ANTHROPIC_API_KEY ze środowiska procesu nadrzędnego
# (SPEC sekcja 5), więc zmienna musi tam być, zanim padnie pierwsze zapytanie.
load_dotenv()

from app import diagnostyka, silnik  # noqa: E402 — patrz komentarz wyżej

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
