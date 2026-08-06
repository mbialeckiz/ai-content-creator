@echo off
rem Uruchamia Forces DC Content Studio na Windows: sprawdza wersję Pythona,
rem buduje środowisko, instaluje zależności, startuje serwer i otwiera
rem przeglądarkę. Dwuklik w Eksplorerze wystarczy.
rem
rem Odpowiednik start.command dla macOS — zmiany rób w obu plikach.

rem Strona kodowa UTF-8: bez tego polskie znaki w komunikatach wychodzą krzakami.
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo.
echo Forces DC Content Studio
echo.

rem --- Python 3.10 lub nowszy -------------------------------------------------
rem Instalator z python.org dodaje launcher "py"; sam "python" bywa zajęty
rem przez zaślepkę ze Sklepu Microsoft, która niczego nie uruchamia.
set "PYTHON="

py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 set "PYTHON=py -3"

if not defined PYTHON (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON=python"
)

if not defined PYTHON (
    echo Aplikacja wymaga Pythona w wersji 3.10 lub nowszej.
    echo Nie znalazlem go na tym komputerze albo wersja jest za stara.
    echo.
    echo Jak to naprawic:
    echo   1. Wejdz na https://www.python.org/downloads/
    echo   2. Pobierz i zainstaluj najnowsza wersje dla Windows
    echo   3. WAZNE: w pierwszym oknie instalatora zaznacz
    echo      "Add python.exe to PATH", zanim klikniesz Install
    echo   4. Uruchom start.bat ponownie
    echo.
    pause
    exit /b 1
)

rem --- Srodowisko wirtualne ---------------------------------------------------
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if errorlevel 1 (
        echo Srodowisko bylo zbudowane starsza wersja Pythona - buduje je od nowa...
        rmdir /s /q .venv
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo Pierwsze uruchomienie - przygotowuje srodowisko ^(chwile to potrwa^)...
    %PYTHON% -m venv .venv
    if errorlevel 1 (
        echo.
        echo Nie udalo sie przygotowac srodowiska. Pokaz to okno administratorowi.
        pause
        exit /b 1
    )
)

echo Sprawdzam skladniki aplikacji...
.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
.venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo.
    echo Nie udalo sie zainstalowac skladnikow aplikacji.
    echo Najczestsza przyczyna to brak polaczenia z internetem - sprawdz je
    echo i uruchom start.bat ponownie.
    echo.
    echo Jesli problem wraca, pokaz to okno administratorowi.
    pause
    exit /b 1
)

rem --- Klucz dostepu ----------------------------------------------------------
rem Brak klucza nie zatrzymuje uruchomienia: aplikacja przyjmie go na ekranie
rem "Sprawdz srodowisko", bez restartu.
if not exist ".env" (
    copy /y ".env.example" ".env" >nul
    echo.
    echo Pierwsze uruchomienie: brakuje jeszcze klucza dostepu do asystenta.
    echo Wklej go w aplikacji - zakladka "Sprawdz srodowisko" na dole menu.
    echo Klucz dostaniesz od administratora.
)

if not defined PORT set "PORT=8420"

echo.
echo Uruchamiam aplikacje. Otworzy sie w przegladarce pod adresem:
echo    http://localhost:%PORT%
echo.
echo To okno musi pozostac otwarte, dopoki pracujesz z aplikacja.
echo Zeby zakonczyc - zamknij to okno albo nacisnij Ctrl+C.
echo.

rem Przegladarke otwiera Python, a nie "start" z opoznieniem: unika to
rem zagniezdzonych cudzyslowow w batchu, ktore latwo psuja sie na sciezkach
rem ze spacjami.
start "" /b .venv\Scripts\python.exe -c "import time, webbrowser; time.sleep(4); webbrowser.open('http://localhost:%PORT%')"

.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%

rem Serwer sie zatrzymal - zostawiamy okno, zeby dalo sie odczytac przyczyne.
echo.
echo Aplikacja zostala zatrzymana.
pause
