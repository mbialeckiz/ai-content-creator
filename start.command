#!/bin/bash
# Uruchamia Forces DC Content Studio: sprawdza środowisko, instaluje
# zależności (jeśli trzeba), startuje serwer i otwiera przeglądarkę.
# Dwuklik w Finderze wystarczy.
set -e

cd "$(dirname "$0")"

MINIMALNY_PYTHON="3.10"

zakoncz_z_komunikatem() {
    echo ""
    echo "$1"
    echo ""
    read -n 1 -s -r -p "Naciśnij dowolny klawisz, aby zamknąć to okno..."
    exit 1
}

# Czy dany interpreter spełnia minimum wersji.
wersja_wystarczy() {
    "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null
}

# macOS dostarcza systemowego Pythona 3.9, który jest za stary dla silnika
# agentowego. Zanim cokolwiek zainstalujemy, szukamy nowszego — użytkownik
# często ma go już obok systemowego (Homebrew, python.org).
znajdz_pythona() {
    for kandydat in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$kandydat" >/dev/null 2>&1 && wersja_wystarczy "$kandydat"; then
            command -v "$kandydat"
            return 0
        fi
    done
    return 1
}

if ! PYTHON=$(znajdz_pythona); then
    ZNALEZIONA="brak"
    if command -v python3 >/dev/null 2>&1; then
        ZNALEZIONA=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "nieznana")
    fi
    zakoncz_z_komunikatem "Aplikacja wymaga Pythona w wersji ${MINIMALNY_PYTHON} lub nowszej.
Na tym komputerze znaleziono wersję: ${ZNALEZIONA}.

Jak to naprawić:
  1. Wejdź na https://www.python.org/downloads/
  2. Pobierz i zainstaluj najnowszą wersję dla macOS (przycisk na górze strony)
  3. Uruchom start.command ponownie

Instalacja niczego nie zepsuje — nowy Python stanie obok tego,
który jest już w systemie."
fi

# Środowisko zbudowane starym Pythonem trzeba postawić od nowa, inaczej
# instalacja zależności będzie się wywalać przy każdym uruchomieniu.
if [ -d ".venv" ] && ! wersja_wystarczy ".venv/bin/python"; then
    echo "Środowisko było zbudowane starszą wersją Pythona — buduję je od nowa..."
    rm -rf .venv
fi

if [ ! -d ".venv" ]; then
    echo "Pierwsze uruchomienie — przygotowuję środowisko (chwilę to potrwa)..."
    "$PYTHON" -m venv .venv
fi

echo "Sprawdzam zależności..."
.venv/bin/python -m pip install --quiet --upgrade pip
if ! .venv/bin/python -m pip install --quiet -r requirements.txt; then
    zakoncz_z_komunikatem "Nie udało się zainstalować składników aplikacji.
Najczęstsza przyczyna to brak połączenia z internetem — sprawdź je
i uruchom start.command ponownie.

Jeśli problem wraca, pokaż to okno administratorowi."
fi

# Brak klucza nie zatrzymuje uruchomienia: aplikacja przyjmie go na ekranie
# „Sprawdź środowisko". Wcześniej skrypt kończył pracę i otwierał plik .env
# w edytorze, co dla osoby nietechnicznej jest ślepą uliczką — plik zaczyna
# się od kropki, więc Finder go nie pokazuje, a TextEdit potrafi zapisać
# kopię w innym miejscu.
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "Pierwsze uruchomienie: brakuje jeszcze klucza dostępu do asystenta."
    echo "Wklej go w aplikacji — zakładka „Sprawdź środowisko” na dole menu."
    echo "Klucz dostaniesz od administratora."
    echo ""
fi

PORT="${PORT:-8420}"
echo ""
echo "Uruchamiam aplikację. Otworzy się w przeglądarce pod adresem:"
echo "   http://localhost:${PORT}"
echo ""
echo "To okno musi pozostać otwarte, dopóki pracujesz z aplikacją."
echo "Żeby zakończyć — zamknij to okno albo naciśnij Ctrl+C."
echo ""

(sleep 2 && open "http://localhost:${PORT}") &

.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT}"
