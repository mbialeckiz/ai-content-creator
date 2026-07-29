#!/bin/bash
# Uruchamia Forces DC Content Studio: instaluje zależności (jeśli trzeba),
# startuje serwer i otwiera przeglądarkę. Dwuklik w Finderze wystarczy.
set -e

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "Pierwsze uruchomienie — przygotowuję środowisko (chwilę to potrwa)..."
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

if [ ! -f ".env" ]; then
    echo ""
    echo "Brakuje pliku .env — skopiuj .env.example do .env i uzupełnij klucz API."
    echo "Otwieram szablon do edycji..."
    cp .env.example .env
    open -e .env
    echo "Uzupełnij plik .env, zapisz go, zamknij edytor i uruchom start.command ponownie."
    read -n 1 -s -r -p "Naciśnij dowolny klawisz, aby zamknąć to okno..."
    exit 1
fi

PORT="${PORT:-8420}"
(sleep 2 && open "http://localhost:${PORT}") &

python3 -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT}"
