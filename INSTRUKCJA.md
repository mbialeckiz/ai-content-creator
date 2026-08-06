# Forces DC Content Studio — instrukcja

Dla osoby, która będzie korzystać z narzędzia na co dzień. Nie trzeba nic
umieć programować.

Instrukcja obejmuje **Windows** i **Maca**. Kroki są takie same, różnią się
tylko nazwy plików i sposób ich uruchamiania — przy każdym kroku, w którym
to ma znaczenie, znajdziesz obie wersje.

| | Windows | Mac |
|---|---|---|
| Plik do uruchamiania | `start.bat` | `start.command` |
| Terminal / wiersz poleceń | **Wiersz polecenia** (`Win + R`, wpisz `cmd`) | **Terminal** (`Cmd + Spacja`, wpisz `terminal`) |

Jeśli coś nie zadziała, przejdź na koniec — jest tam lista typowych problemów.

---

# Część 1. Instalacja (robisz raz)

## Krok 1. Sprawdź, czy masz Pythona

Aplikacja potrzebuje programu o nazwie Python, w wersji 3.10 lub nowszej.
Na Macu zwykle jest, ale często w za starej wersji. Na Windowsie najczęściej
trzeba go doinstalować.

**Windows:**

1. Naciśnij `Win + R`, wpisz `cmd`, `Enter`.
2. Wklej i naciśnij `Enter`:

   ```
   py --version
   ```

**Mac:**

1. Naciśnij `Cmd + Spacja`, wpisz `terminal`, `Enter`.
2. Wklej i naciśnij `Enter`:

   ```
   python3 --version
   ```

**Odczytanie wyniku (tak samo na obu):** zobaczysz coś w rodzaju
`Python 3.9.6` albo `Python 3.12.4`.

- **Druga liczba to 10 lub więcej** (3.10, 3.11, 3.12…) — masz wszystko,
  przejdź do kroku 2.
- **Druga liczba mniejsza niż 10** albo dostajesz błąd — zainstaluj Pythona:

1. Wejdź na <https://www.python.org/downloads/>
2. Kliknij duży żółty przycisk na górze strony
3. Otwórz pobrany plik i przeklikaj instalator

   > **Windows — to jest ważne:** w pierwszym oknie instalatora, na samym
   > dole, zaznacz **„Add python.exe to PATH"**, zanim klikniesz *Install Now*.
   > Bez tego aplikacja nie znajdzie Pythona.

4. Zamknij wiersz poleceń / Terminal i otwórz go od nowa

Instalacja niczego nie zepsuje — nowy Python stanie obok starego.

## Krok 2. Pobierz aplikację

Marcin przysyła Ci link do repozytorium na GitHubie albo gotowy plik ZIP.

**Jeśli dostałaś link do GitHuba:**

1. Otwórz link w przeglądarce (może być potrzebne zalogowanie na GitHub —
   Marcin wcześniej doda Cię do projektu)
2. Kliknij zielony przycisk **Code**
3. Wybierz **Download ZIP**

**Jeśli dostałaś plik ZIP** — po prostu go pobierz.

Dalej tak samo:

4. Rozpakuj pobrany plik ZIP:
   - **Windows:** prawy przycisk na pliku → **Wyodrębnij wszystkie** → *Wyodrębnij*
   - **Mac:** dwuklik na pliku
5. **Przenieś powstały folder do katalogu Dokumenty** i nazwij go krótko,
   np. `Forces-DC-Studio`

> **Ważne:** nie zostawiaj folderu w Pobranych. Aplikacja zapisuje w nim
> Twoje posty i plany — w Pobranych łatwo go przypadkiem usunąć.
>
> **Windows:** nie zostawiaj go też w folderze zsynchronizowanym z OneDrive,
> jeśli masz włączone „pliki na żądanie" — potrafi to zablokować zapis.

## Krok 3. Poproś Marcina o klucz dostępu

Klucz to długi ciąg znaków zaczynający się od `sk-ant-`. Bez niego asystent
nie zadziała. Wpiszesz go za chwilę, w kroku 5.

> Klucz jest jak hasło do firmowej karty — nie wysyłaj go dalej i nie wklejaj
> w losowe strony. Aplikacja trzyma go tylko na Twoim komputerze.

## Krok 4. Uruchom aplikację

**Windows:**

1. Otwórz folder `Forces-DC-Studio`
2. Kliknij dwukrotnie plik **`start.bat`**
3. Jeśli pojawi się niebieskie okno *„System Windows ochronił Twój komputer"*
   — kliknij **Więcej informacji**, a potem **Uruchom mimo to**

**Mac:**

1. Otwórz folder `Forces-DC-Studio`
2. Znajdź plik **`start.command`**
3. **Kliknij go prawym przyciskiem** → **Otwórz** → w okienku, które wyskoczy,
   kliknij jeszcze raz **Otwórz**

> Za pierwszym razem koniecznie prawym przyciskiem — zwykły dwuklik macOS
> zablokuje. Przy kolejnych uruchomieniach dwuklik wystarczy.

**Dalej tak samo na obu systemach:**

Otworzy się czarne okno i zacznie wypisywać tekst. **To normalne.**
Pierwsze uruchomienie trwa 2–3 minuty, bo aplikacja dociąga swoje składniki
(ok. 300 MB, więc potrzebny jest internet).

Po chwili sama otworzy przeglądarkę pod adresem `http://localhost:8420`.

> **Czarne okno musi zostać otwarte, dopóki pracujesz.** Zamknięcie go
> wyłącza aplikację. Możesz je zminimalizować.
>
> Windows może przy pierwszym uruchomieniu zapytać o dostęp do sieci dla
> Pythona — wystarczy **sieć prywatna**. Aplikacja i tak działa tylko na
> Twoim komputerze.

## Krok 5. Wpisz klucz

Za pierwszym razem aplikacja poprosi o klucz.

1. W menu po lewej, na samym dole, kliknij **Sprawdź środowisko**
2. Znajdź sekcję **Klucz dostępu do asystenta**
3. Wklej klucz od Marcina w pole i kliknij **Zapisz klucz**
4. Strona odświeży się sama; przy pozycji „Klucz API" powinien pojawić się
   zielony znaczek

Nie trzeba nic restartować. Klucz zapisuje się na stałe — przy kolejnych
uruchomieniach nie będziesz o niego pytana.

## Krok 6. Sprawdź, czy wszystko gra

Zostań na ekranie **Sprawdź środowisko**. Powinnaś zobaczyć listę
z zielonymi znaczkami. Żółte ostrzeżenia są w porządku. **Czerwone krzyżyki
oznaczają problem** — przy każdym jest napisane, co zrobić.

---

# Część 2. Codzienne uruchamianie

Otwórz folder `Forces-DC-Studio` i kliknij dwukrotnie:

- **Windows:** `start.bat`
- **Mac:** `start.command`

To wszystko. Przeglądarka otworzy się sama.

Żeby skończyć pracę: zamknij czarne okno.

> Wygodniej? Kliknij ten plik prawym przyciskiem i wybierz
> **Przypnij do paska zadań** (Windows) albo przeciągnij go do Docka (Mac).

---

# Część 3. Jak korzystać

Menu po lewej ma sześć zakładek. Poniżej każda z nich, w kolejności,
w jakiej najsensowniej z nich korzystać przez miesiąc.

## Korpus — najpierw to

**Po co:** asystent uczy się pisać tak jak Wy, czytając Wasze opublikowane
posty. Bez nich pisze ogólnie i bezbarwnie.

**Co zrobić:**

- Przy każdym poście na liście jest lista rozwijana z **typem** posta
  (realizacja, ekspercki, wydarzenie…). Zaimportowane posty mają wpisane
  `DO-OZNACZENIA` — poprzestawiaj je na właściwe. To pięć minut, a bardzo
  poprawia jakość planu.
- Po każdej publikacji na LinkedInie dopisz tu nowy post. Im ich więcej,
  tym lepiej asystent pisze.

## Styl — powiedz asystentowi, jak piszecie

**Po co:** tu ustawiasz ton, rodzaje postów i to, czego nigdy nie pisać.

**Najprostsza droga:** kliknij **Porozmawiaj o stylu**. Asystent przejrzy
Wasze posty, powie, co z nich odczytał, i dopyta tylko o to, czego nie da
się z nich wyczytać. Odpowiadasz normalnymi zdaniami, jedno pytanie naraz.

Na końcu kliknij **Zakończ i pokaż propozycję** — dostaniesz gotową treść
do zatwierdzenia. Przeczytaj i kliknij **Zapisz**, albo **Odrzuć**, jeśli
się nie zgadzasz. **Nic nie zapisze się bez Twojej zgody.**

Możesz przerwać w połowie i wrócić później — rozmowa nie przepada.

## Materiały — to, co realnie dzieje się w firmie

**Po co:** to jest najważniejsza zakładka i jednocześnie ta, o której
najłatwiej zapomnieć. Bez niej plan opiera się na samych newsach z branży,
a taki content jest nieodróżnialny od konkurencji.

**Co zrobić:**

- Wybierz miesiąc i dopisuj jednym zdaniem, co się wydarzyło: start
  projektu, odbiór, certyfikat, nowa osoba w zespole, udział w konferencji.
  **Jedno zdanie wystarczy** — nie ma formularza z dziesięcioma polami.
- Przycisk **Wyślij prośbę o materiały** przygotowuje gotową wiadomość
  do skopiowania i wysłania na WhatsAppie. Aplikacja niczego nie wysyła sama.

**Artykuły i dokumenty** (na dole ekranu): wgraj raporty branżowe i artykuły
w PDF. Po wgraniu kliknij przy pliku **Przeczytaj** — asystent przejdzie
dokument raz i wypisze z niego fakty, liczby i pomysły na posty. Od tej pory
korzysta z tego przy planowaniu i pisaniu.

> Czytanie dokumentu kosztuje ok. **0,20 USD**, jednorazowo. Dlatego jest
> osobnym przyciskiem, a nie dzieje się samo.

## Plan — co publikujemy w tym miesiącu

**Po co:** rozpisuje tematy na cały miesiąc.

**Kolejność:**

1. **Zrób przegląd branży** (przycisk u góry) — asystent sprawdza, co się
   dzieje w branży, i zapisuje fakty z adresami źródeł.
   **To kosztuje ok. 1,30 USD i trwa kilka minut.** Rób to raz na kilka
   tygodni, nie przed każdym postem.
2. **Zbuduj plan** — powstaje tabela z tematami i datami.

**Co dostajesz w planie:**

- **Kąt ujęcia** przy każdym temacie: od czego zacząć i dlaczego akurat
  Forces DC ma tu coś do powiedzenia
- **Pytania do firmy** — gotowe do wysłania, przycisk **Kopiuj wszystkie**
- **Ustalenia z researchu** — fakty i liczby, które trafią potem do postów
- **Zapas tematów** — rezerwa na chudy miesiąc

Przy każdej pozycji jest przycisk **Napisz**, który przenosi temat prosto
do pisania posta.

> Jeśli plan wyjdzie krótszy, niż się spodziewasz — to nie błąd. Asystent
> celowo nie dopycha planu newsami, kiedy brakuje materiałów z firmy.
> Uzupełnij Materiały i zbuduj plan od nowa.

## Posty — pisanie

**Po co:** tu powstają treści.

**Jak:**

1. Opisz temat w polu **O czym ma być post?** — normalnym zdaniem, po polsku
2. Jeśli post ma się opierać na artykule, rozwiń **Materiał źródłowy**
   i wklej ten fragment, który ma znaczenie. Nie wklejaj całego dokumentu.
3. Kliknij **Generuj**

**Posty powstają po angielsku** — tak, jak Forces DC publikuje. Temat możesz
opisywać po polsku.

Dostajesz **trzy warianty** w podglądzie wyglądającym jak LinkedIn, z linią
pokazującą, ile widać przed kliknięciem „zobacz więcej".

Przy każdym wariancie:

| Przycisk | Co robi |
|---|---|
| **Kopiuj** | kopiuje treść do schowka |
| **Popraw** | zmiana jednym poleceniem, np. „skróć o połowę" |
| **Popraw ręcznie** | wchodzisz w tekst i poprawiasz sama — za darmo |
| **Zapisz jako wybrany** | oznacza wariant, który idzie do publikacji |

Niżej: **wersja na Facebooka**, **brief graficzny** i sekcja **Braki**.

**Braki** to lista rzeczy, których asystentowi zabrakło. Przy każdej jest
przycisk **Dopisz do materiałów** — przenosi ją do Materiałów, żeby następny
post nie miał już tej dziury.

Wszystkie posty zapisują się same i są na dole ekranu w sekcji
**Wcześniej wygenerowane posty**.

## Grafika — przez Canvę

Pod briefem graficznym jest przycisk **Zrób grafikę w Canvie**.

1. Kliknij go — pojawi się gotowe polecenie
2. Kliknij **Kopiuj polecenie**
3. Otwórz **claude.ai** (jest odnośnik obok) i upewnij się, że masz włączony
   konektor Canva — ikona spinacza pod polem wiadomości
4. Wklej polecenie i wyślij
5. Claude założy projekt w Canvie i przyśle link
6. **Otwórz projekt w Canvie i popraw, co trzeba** — to szkic, nie wersja
   gotowa do publikacji bez oglądania

Sekcja **Podgląd hasła** rysuje prostą planszę. To tylko sposób, żeby
zobaczyć, czy hasło działa w kadrze — nie jest to grafika do publikacji.

## Asystent — czat

Zwykła rozmowa. Możesz zapytać „jaki jest plan na sierpień", „czego brakuje
w materiałach", „pokaż wygenerowane posty". Asystent czyta pliki, więc
odpowiada na podstawie tego, co faktycznie jest, a nie zgaduje.

`Enter` wysyła wiadomość, `Shift + Enter` robi nową linię.

---

# Część 4. Rzeczy, które warto wiedzieć

## Ile to kosztuje

W prawym górnym rogu widać, ile wydano od uruchomienia aplikacji.
Orientacyjnie:

| Operacja | Koszt |
|---|---|
| Napisanie posta (3 warianty) | ok. 0,15 USD |
| Poprawka jednym poleceniem | ok. 0,03 USD |
| Poprawka ręczna | 0 |
| Przeczytanie dokumentu | ok. 0,20 USD, raz na dokument |
| Przegląd branży | **ok. 1,30 USD**, raz na kilka tygodni |
| Plan miesiąca | ok. 0,50–1,00 USD |

Jest twardy limit na jedną operację — nie da się przypadkiem wydać
kilkudziesięciu dolarów.

## Czy mogę przełączyć okno w trakcie

**Tak.** Pisanie posta czy budowanie planu trwa nawet kilka minut — możesz
w tym czasie przełączać zakładki w aplikacji i przechodzić do innych
programów. W nagłówku widać pasek, np. „Pisanie posta…", a po zakończeniu
„gotowe". Kliknięcie w niego wraca tam, gdzie leży wynik.

**Czego nie robić w trakcie:** nie zamykaj karty przeglądarki i nie odświeżaj
strony (`F5` na Windowsie, `Cmd + R` na Macu). To naprawdę przerywa pracę,
za którą i tak zapłacisz. Aplikacja ostrzeże pytaniem.

## Gdzie są moje pliki

Wszystko leży w folderze `Forces-DC-Studio/dane`:

| Folder | Co w nim jest |
|---|---|
| `output/` | wygenerowane posty |
| `plan/` | plany miesięczne |
| `input-firmowy/` | materiały z firmy |
| `korpus/linkedin/` | opublikowane posty |
| `artykuly/` | wgrane dokumenty |
| `logo/` | pliki logo do grafik |

To zwykłe pliki tekstowe — możesz je otworzyć i poprawić poza aplikacją.
**Warto ten folder regularnie kopiować** albo trzymać na Dysku Google.

---

# Część 5. Gdy coś nie działa

**Mac: dwuklik na `start.command` nic nie robi albo pokazuje ostrzeżenie**
→ Za pierwszym razem kliknij **prawym przyciskiem** → **Otwórz** → **Otwórz**.

**Windows: „System Windows ochronił Twój komputer"**
→ **Więcej informacji** → **Uruchom mimo to**. To standardowe ostrzeżenie
dla plików pobranych z internetu.

**Windows: okno mignęło i zniknęło**
→ Otwórz wiersz poleceń (`Win + R` → `cmd`), przeciągnij do niego plik
`start.bat` i naciśnij `Enter`. Okno zostanie otwarte i zobaczysz komunikat.

**Windows: otwiera się Microsoft Store zamiast aplikacji**
→ To zaślepka Pythona ze Sklepu. Zainstaluj Pythona z python.org
(krok 1 instalacji) i zaznacz **„Add python.exe to PATH"**.

**„Aplikacja wymaga Pythona w wersji 3.10 lub nowszej"**
→ Wróć do kroku 1 instalacji.

**Przeglądarka pokazuje „Nie można połączyć się z serwerem"**
→ Czarne okno Terminala zostało zamknięte. Uruchom `start.command` od nowa.

**„Nie udało się zainstalować składników aplikacji"**
→ Najczęściej brak internetu. Sprawdź połączenie i spróbuj ponownie.

**Asystent odpowiada, że nie jest zalogowany**
→ Klucz jest zły albo wygasł. Sprawdź środowisko → wklej klucz od nowa.

**Zmiany nie działają po aktualizacji od Marcina**
→ Zamknij czarne okno **do końca** i uruchom aplikację ponownie.
Stary proces potrafi zostać w tle i podawać poprzednią wersję.

**Posty „zniknęły"**
→ Sprawdź środowisko → pozycja „Ścieżka katalogu danych" pokazuje, z którego
folderu aplikacja czyta. Jeśli to nie ten, w którym pracowałaś, powiedz
administratorowi.

**Coś innego**
→ Zrób zrzut ekranu czarnego okna i wyślij Marcinowi. Tam widać, co się stało.

---

> **Uwaga administratora:** wersja dla Windows (`start.bat`) została napisana
> i sprawdzona pod kątem logiki, ale nie była uruchomiona na prawdziwym
> Windowsie — w środowisku, w którym powstawała, nie było takiej maszyny.
> Sam kod aplikacji jest przenośny i nie zawiera niczego uniksowego.
> Pierwsze uruchomienie u operatorki warto zrobić razem, przez telefon.
