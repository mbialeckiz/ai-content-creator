# Forces DC Content Studio

Lokalne narzędzie contentowe dla Forces DC (fit-out data center, Norwegia,
grupa Maya Holding). Pełny kontekst biznesowy i wymagania: zobacz
`SPEC-forces-content-studio.md` (dokument główny) i `SPEC-frontend.md`
(warstwa interfejsu — zastępuje sekcję 9 dokumentu głównego). Konwencje
projektu: `CLAUDE.md`.

**Status: fazy 1–3 gotowe** z kolejności implementacji w SPEC sekcja 12.

| Faza | Zakres | Stan |
|---|---|---|
| 1 | szkielet FastAPI, `start.command`, ekran „Sprawdź środowisko", opakowanie SDK | gotowe |
| 2 | Asystent (czat) + Posty (tryb Redaktor) | gotowe |
| 3 | Korpus + Styl | gotowe |
| 4 | Plan + Materiały (tryb Strateg) | do zrobienia |
| 5 | Wywiad o stylu w czacie | do zrobienia |

Od fazy 3 narzędzie jest samowystarczalne dla operatorki: dopisywanie
i import korpusu oraz zmiana zasad stylu nie wymagają administratora.
Zakładki „Plan" i „Materiały" są jeszcze puste.

## Uruchomienie

**macOS:** dwuklik na `start.command`. Przy pierwszym uruchomieniu skrypt
utworzy środowisko wirtualne, poprosi o uzupełnienie `.env` i otworzy go
do edycji.

**Ręcznie (dowolny system):**

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # uzupełnij ANTHROPIC_API_KEY
python -m uvicorn app.main:app --host 127.0.0.1 --port 8420
```

Otwórz `http://localhost:8420`. Zakładka „Sprawdź środowisko" (dolna część
nawigacji) działa od razu i nie wywołuje modelu — pokazuje, czy brakuje
klucza API, czy struktura katalogu danych jest kompletna itd.

## Katalog danych

Ścieżka konfigurowalna przez `KATALOG_DANYCH` w `.env` (domyślnie `./dane`).
Docelowo powinna wskazywać na folder zsynchronizowany z Google Drive —
tak, żeby operatorka mogła edytować pliki `.md` również spoza aplikacji.

**Zawartość `dane/` w tym repozytorium to rusztowanie**, nie prawdziwe dane
Forces DC — szczegóły w `dane/README.md`. Skille, bazę wiedzy i korpus
10 postów dostarcza administrator jako osobną paczkę do zaimportowania
(CLAUDE.md, SPEC sekcja 6).

## Rozbieżności od specyfikacji — zweryfikowane w Fazie 1

SPEC sekcja 13 wymienia niepewności do sprawdzenia przed implementacją,
zamiast zgadywania. Zweryfikowano względem `claude-agent-sdk==0.2.128`
(Python 3.11):

- **Nazwy parametrów `ClaudeAgentOptions`** (SPEC 13.1) — `cwd`,
  `setting_sources`, `skills`, `allowed_tools`, `agents`, `system_prompt`
  istnieją i działają jak opisano. Zgodność jest też sprawdzana
  automatycznie przy każdym starcie serwera i na ekranie diagnostyki
  (`app/silnik.py::sprawdz_zgodnosc_parametrow`).
- **`"Skill"` w `allowed_tools` jest przestarzałe** — w tej wersji SDK
  trzeba użyć parametru `skills=` (np. `skills="all"`), który sam dopisuje
  narzędzie `Skill` do efektywnej listy. SPEC tego nie przewidywał;
  `app/silnik.py` używa `skills=`, nie literału `"Skill"`.
- **Subagenci przez `AgentDefinition`** (SPEC 13.2) — potwierdzone, klasa
  istnieje z polami `description`, `prompt`, `tools`, `model`, `skills`
  i in., przekazywana przez `ClaudeAgentOptions.agents`.
- **Nazwy narzędzi** (SPEC 13.3) — `WebSearch`, `WebFetch`, `Agent`
  potwierdzone. `Skill` — patrz punkt wyżej.
- **Zapis ograniczony do `plan/` i `output/` (SPEC 10.1)** — nie
  zaimplementowano tego przez scoped-owe wpisy w `allowed_tools`
  (np. `Write(plan/**)`), bo udokumentowana jest taka składnia tylko dla
  `Bash`. Zamiast zgadywać, `Write` **nie jest wpisany jako cały tool**
  w `allowed_tools` — każde jego wywołanie trafia do `can_use_tool`
  (SDK: "the SDK replacement for the interactive permission prompt"),
  gdzie `app/silnik.py::_zezwol_na_narzedzie` sprawdza ścieżkę względem
  katalogu danych i odrzuca wszystko poza `plan/` i `output/` (w tym próby
  z `..`). Przetestowane ręcznie, patrz historia commitów Fazy 1.
- **`can_use_tool` wymaga trybu strumieniowego** — nieudokumentowane w
  SPEC: ta wersja SDK rzuca `ValueError`, jeśli `can_use_tool` jest
  ustawione, a `prompt` do `query()` jest zwykłym `str`. `app/silnik.py`
  opakowuje prompt jako `AsyncIterable` (`_jako_strumien_wejscia`).
- **`query()` a event loop** (SPEC 13.6) — `query()` jest w pełni
  asynchroniczne (`async def`, zwraca `AsyncIterator`); iterowanie po nim
  wewnątrz generatora `StreamingResponse` FastAPI nie blokuje event loopa,
  osobny wątek/task nie jest potrzebny.

## Wgrane dokumenty — jak trafiają do treści

Artykuły i raporty wgrane na ekranie „Materiały" leżą w `dane/artykuly/`.
Sam plik nie jest jeszcze używany — dopiero przycisk **„Przeczytaj"**
przepuszcza go raz przez asystenta i zapisuje wyciąg w
`dane/artykuly/wyciagi/<nazwa>.md`: fakty, liczby, tematy na posty i lista
tego, czego w dokumencie zabrakło.

Od tego momentu wyciąg — kilka kilobajtów zamiast kilkuset — trafia
automatycznie do planu miesiąca i do każdego pisanego posta. Dokumentu nikt
już nie czyta po raz drugi, więc koszt jest jednorazowy (zmierzone: 0,20 USD
za notatkę branżową, 3 tury).

Osobno, na ekranie „Posty", jest pole **„Materiał źródłowy"**: miejsce na
wklejenie konkretnego fragmentu, na którym ma się opierać dany post.
Przycinane do 12 tys. znaków. To ścieżka dla sytuacji „mam dokładnie ten
akapit", niezależna od wyciągów.

Wyciąg jest zwykłym plikiem `.md` — można go poprawić ręcznie, a asystent
będzie korzystał z poprawionej wersji. Usunięcie dokumentu kasuje też jego
wyciąg.

## Testy

```bash
.venv/bin/python testy.py
```

Sprawdzenia z SPEC sekcja 11, które da się wykonać **bez wywołania modelu**:
blokada NDA, zamknięta lista narzędzi, zapis tylko do `plan/` i `output/`,
odczyt i zapis postów, wybór wariantu, import korpusu, brak wycieku klucza
API do diagnostyki. Uruchomienie nic nie kosztuje, więc warto po każdej
zmianie. Jakość samych tekstów sprawdza się tylko ręcznie — tego żaden
test automatyczny nie zastąpi.

## Koszty — do potwierdzenia przed produkcją

SPEC sekcja 13.4 prosi o zweryfikowanie rozliczenia SDK dla planu Team,
bo klient o to zapyta. Stan na dzień pisania tego README (koniec lipca
2026): Anthropic ogłosił, że korzystanie z Agent SDK (w tym `claude -p`
i aplikacje trzecich firm oparte o SDK) przestaje być liczone z puli
subskrypcji, a zamiast tego korzysta z osobnej, comiesięcznej puli
kredytów rozliczanej po cenach API — dla planu Team ma to być $20/mies.
(Standard) lub $100/mies. (Premium) na użytkownika, bez łączenia
i przenoszenia między osobami. Ta zmiana miała wejść w życie 15 czerwca
2026, ale pojawiły się też doniesienia o jej wstrzymaniu/przełożeniu —
**stan na dziś jest niejednoznaczny w źródłach dostępnych z tej sesji**,
więc **przed uruchomieniem produkcyjnym administrator musi to sprawdzić
bezpośrednio na https://support.claude.com (artykuł „Use the Claude Agent
SDK with your Claude plan") i w panelu rozliczeń organizacji**, a nie
polegać na tym README. Niezależnie od modelu rozliczeń: ta aplikacja nie
ma własnego licznika kosztów w Fazie 1 — pojawi się w kolejnej fazie
razem z resztą interfejsu Asystenta (SPEC-frontend sekcja 5).

## Dane osobowe i treści prawne

Tryb Strateg wykonuje research o wydarzeniach i osobach (prelegenci,
partnerzy) — to dotyka danych osobowych i wymaga weryfikacji zgodności
z RODO / norweską personvernloven przed użyciem produkcyjnym. Narzędzie
nie generuje treści prawnych — braki tego typu są oznaczane jako wymagające
weryfikacji, nie uzupełniane domysłem.

## Bezpieczeństwo

- `allowed_tools` jest zamkniętą listą: `Read`, `Grep`, `Glob`, `Agent`,
  `WebSearch`, `WebFetch`, plus narzędzie `Skill` dodawane automatycznie
  przez parametr `skills=`. `Bash` i `Edit` są jawnie na liście
  `disallowed_tools`.
- Zapis jest możliwy wyłącznie do `plan/` i `output/`, wymuszone w
  `app/silnik.py` (patrz wyżej), nie tylko instrukcją w prompcie.
- Klucz API czytany jest wyłącznie ze zmiennej środowiskowej / `.env`
  (w `.gitignore`). Nigdy nie jest logowany ani zwracany w odpowiedziach
  API — diagnostyka zgłasza tylko jego obecność, nie wartość.
