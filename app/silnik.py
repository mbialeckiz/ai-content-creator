"""Cała styczność z Claude Agent SDK żyje w tym module (patrz CLAUDE.md).

Gdy API SDK się zmieni, poprawka ma być w jednym pliku — dlatego nawet
tryb testowy z Fazy 1 buduje `ClaudeAgentOptions` w ten sam sposób, w jaki
będą to robić tryby Strateg/Redaktor/Wywiad w kolejnych fazach.
"""

from __future__ import annotations

import dataclasses
import logging
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
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
    query,
)

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
) -> ClaudeAgentOptions:
    """Buduje `ClaudeAgentOptions` wspólne dla wszystkich trybów agenta."""
    return ClaudeAgentOptions(
        cwd=katalog_danych,
        setting_sources=["project"],
        skills="all",
        allowed_tools=DOZWOLONE_NARZEDZIA,
        disallowed_tools=ZABRONIONE_NARZEDZIA,
        system_prompt=system_prompt,
        can_use_tool=_zbuduj_zezwalacz(katalog_danych),
        model=model or os.environ.get("MODEL") or None,
        agents=agents,
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


async def _jako_strumien_wejscia(tekst: str) -> AsyncIterator[dict[str, Any]]:
    """Opakowuje pojedynczy prompt jako AsyncIterable.

    Wymagane przez zainstalowaną wersję SDK (0.2.128): `can_use_tool`
    działa tylko w trybie strumieniowym wejścia — zwykły `str` jako prompt
    rzuca `ValueError("can_use_tool callback requires streaming mode")`.
    To nie jest udokumentowane w SPEC (sekcja 13 tego nie przewidywała),
    więc odnotowujemy to tutaj zamiast gdzie indziej zgadywać.
    """
    yield {
        "type": "user",
        "session_id": "",
        "message": {"role": "user", "content": tekst},
        "parent_tool_use_id": None,
    }


async def testowe_wywolanie(katalog_danych: Path) -> AsyncIterator[dict[str, Any]]:
    """Jeden pełny przelot przez SDK: potwierdza, że CLI startuje, czyta klucz
    API ze środowiska i zwraca odpowiedź. Używane przez ekran diagnostyki
    (Faza 1) — jedyne miejsce w tej fazie, które faktycznie woła model.
    """
    opcje = zbuduj_opcje(katalog_danych, PROMPT_TESTOWY)
    yield {"typ": "status", "tekst": "Uruchamiam CLI Claude Code…"}

    try:
        prompt = _jako_strumien_wejscia("Testowe wywołanie startowe.")
        async for wiadomosc in query(prompt=prompt, options=opcje):
            if isinstance(wiadomosc, SystemMessage) and wiadomosc.subtype == "init":
                yield {"typ": "status", "tekst": "Sesja zainicjowana, model odpowiada…"}
            elif isinstance(wiadomosc, AssistantMessage):
                for blok in wiadomosc.content:
                    if isinstance(blok, TextBlock):
                        yield {"typ": "fragment", "tekst": blok.text}
                    elif isinstance(blok, ToolUseBlock):
                        yield {"typ": "status", "tekst": f"Wywołuję narzędzie: {blok.name}…"}
            elif isinstance(wiadomosc, ResultMessage):
                yield {
                    "typ": "wynik",
                    "bledny": wiadomosc.is_error,
                    "tury": wiadomosc.num_turns,
                    "koszt_usd": wiadomosc.total_cost_usd,
                    "uzycie": wiadomosc.usage,
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
