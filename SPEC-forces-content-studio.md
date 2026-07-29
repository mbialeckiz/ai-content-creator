# SPECYFIKACJA TECHNICZNA
# Forces DC Content Studio — narzędzie z zaszytym agentem AI

**Wersja:** 1.0
**Data:** 28.07.2026
**Autor specyfikacji:** Marcin Białecki (konsultant AI, Maya Holding)
**Wykonawca:** Claude Code
**Klient końcowy:** Forces DC (grupa Maya Holding, Norwegia)

---

## 0. Jak czytać ten dokument

Ten plik jest kontraktem na wykonanie. Sekcje 1–3 wyjaśniają, po co to powstaje
i dla kogo. Sekcje 4–10 są wiążące technicznie. Sekcja 11 definiuje, kiedy praca
jest skończona. Sekcja 13 wymienia rzeczy, których nie zweryfikowałem — należy
je sprawdzić przed implementacją, nie zgadywać.

**Zasada nadrzędna:** jeśli coś w tej specyfikacji koliduje z aktualnym API
Claude Agent SDK, wygrywa dokumentacja SDK. Zgłoś rozbieżność, nie obchodź jej.

---

## 1. Cel biznesowy

Forces DC to firma wykonawcza fit-out data center w Norwegii, część grupy
Maya Holding. Zarządza specjalistami technicznymi na norweskich placówkach,
działa w reżimie NDA z hyperscalerami.

### Problem do rozwiązania

Analiza profilu LinkedIn Forces DC (23 posty, VII 2025 – VII 2026) wykazała:

| Obserwacja | Dane |
|---|---|
| Własnych postów | 13 (pozostałe 10 to reposty, wszystkie z 0 reakcji) |
| Mediana reakcji | 3 |
| Posty z zerem reakcji | 8 z 23 |
| Postów o realizacjach / pracy na budowie | **0** |
| Regularność | nierówna, 1–4 msc, dwie dziury (XI 2025, I 2026) |
| Spójność formalna | emotikony 0–11/post, hashtagi 0–15/post — brak reguły |

Wniosek: profil czyta się jak profil agencji rekrutacyjnej, nie wykonawcy DC.
Wyróżnik firmy — ludzie realnie stojący na budowie — nie jest widoczny w treści.
Komunikacja rusza tylko przy eventach.

### Czego oczekuje klient

Operatorka (Magda, VA) sformułowała dwa priorytety:
1. planowanie contentu na ~1 miesiąc do przodu, z uwzględnieniem newsów
   z branży DC w Norwegii oraz informacji wewnętrznych z firmy
2. tworzenie postów w spójnym głosie marki, z grafikami zgodnymi
   z identyfikacją wizualną

Kanał główny: LinkedIn. Facebook jako recykling treści z LinkedIna.

### Definicja sukcesu

Narzędzie jest sukcesem, gdy Magda używa go samodzielnie przez 4 tygodnie
bez kontaktu z Marcinem w sprawach innych niż awarie, publikuje regularnie
(min. 6 postów/miesiąc) i nie musi przepisywać tekstów od zera.

---

## 2. Użytkownicy

| Rola | Osoba | Kompetencje techniczne | Co robi w narzędziu |
|---|---|---|---|
| **Operator** | Magda (VA) | **nietechniczna** — nie zna terminala, nie edytuje kodu | planuje miesiąc, generuje posty, edytuje zasady stylu, dopisuje korpus |
| **Właściciel treści** | Maciej Pulit (BDD) | nietechniczny | akceptuje, dostarcza input firmowy |
| **Administrator** | Marcin (konsultant) | wysokie | instalacja, aktualizacje, uprawnienia; obecny 1 dzień/tydzień |

**To jest najważniejsze ograniczenie projektowe.** Główna użytkowniczka nie
otworzy terminala. Interfejs CLI dyskwalifikuje narzędzie — każda zmiana stylu
przechodziłaby przez administratora dostępnego raz w tygodniu.

Wynika z tego wymóg: **lokalny interfejs graficzny w przeglądarce**, uruchamiany
jednym kliknięciem, w którym da się edytować wszystkie pliki sterujące
zachowaniem agenta.

---

## 3. Zakres

### W zakresie v1

- lokalna aplikacja webowa (uruchamiana skryptem, dostępna w przeglądarce)
- tryb **Strateg**: plan contentu na miesiąc
- tryb **Redaktor**: generowanie postów LinkedIn + wersja FB + brief graficzny
- tryb **Wywiad**: jednorazowe domknięcie definicji głosu marki
- edytor plików sterujących (skille, baza wiedzy, korpus, input firmowy)
- import korpusu z eksportu LinkedIn (CSV/JSON/XLSX)
- kolejka akceptacji: draft → zaakceptowany → opublikowany
- eksport gotowego posta do schowka i pliku

### Poza zakresem v1 (świadomie)

- **automatyczna publikacja na LinkedIn** — brak oficjalnego konektora,
  API ograniczone, ryzyko regulaminowe; publikacja pozostaje ręczna
- **generowanie grafik** — wymaga wcześniejszego przygotowania brand templates
  w Canvie przez grafika (Sikora); v1 zwraca brief tekstowy
- **triggery i harmonogramy** — nic nie uruchamia się samo
- **wielofirmowość** (Trust, Pro-Maler) — architektura ma to umożliwiać,
  ale v1 obsługuje wyłącznie Forces DC
- **hosting zdalny** — aplikacja działa lokalnie na maszynie operatora
- **baza danych** — stanem są pliki na dysku (patrz sekcja 7)

### Non-goals (nie implementuj, nawet jeśli wydaje się przydatne)

- integracja z Monday.com, Buffer, n8n — to warstwa v2
- uwierzytelnianie użytkowników, role, multi-tenant
- historia wersji plików — Google Drive to zapewnia
- generowanie obrazów jakimkolwiek modelem

---

## 4. Architektura

### Zasada podziału odpowiedzialności

```
WARSTWA JAKOŚCI (własność: Magda)          WARSTWA WYKONAWCZA (własność: Marcin)
─────────────────────────────────          ──────────────────────────────────────
.claude/skills/*/SKILL.md                  app/ (backend + frontend)
baza-wiedzy/*.md                           pętla agentowa
korpus/linkedin/*.md                       uprawnienia narzędzi
input-firmowy/*.md                         subagenci
        │                                          │
        └──────── pliki na dysku ──────────────────┘
                (Google Drive sync)
```

Magda zmienia zachowanie agenta edytując pliki `.md` przez UI.
Nikt nie musi dotykać kodu, żeby zmienić sposób pisania.

### Komponenty

```
┌─────────────────────────────────────────────────┐
│  Przeglądarka (localhost:8420)                  │
│  ekrany: Plan · Redaktor · Ustawienia · Korpus  │
└────────────────────┬────────────────────────────┘
                     │ HTTP + SSE (streaming)
┌────────────────────▼────────────────────────────┐
│  Backend: FastAPI                               │
│  - /api/strateg   /api/redaktor   /api/wywiad   │
│  - /api/pliki     (CRUD na plikach .md)         │
│  - /api/korpus    (import, lista, edycja)       │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│  Silnik agentowy: claude-agent-sdk              │
│  - ClaudeAgentOptions (cwd, skills, tools)      │
│  - subagent: researcher                         │
│  - narzędzia: Read, Grep, Glob, Write,          │
│               WebSearch, WebFetch, Skill, Agent │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│  Dane: pliki .md w katalogu roboczym            │
└─────────────────────────────────────────────────┘
```

---

## 5. Stack techniczny

| Warstwa | Technologia | Uzasadnienie |
|---|---|---|
| Silnik agentowy | `claude-agent-sdk` (Python) | Skills ładowane z dysku = warstwa jakości edytowalna bez kodu; wbudowany subagent i kontrola uprawnień |
| Backend | FastAPI + uvicorn | streaming SSE, prosty deploy lokalny, jeden proces |
| Frontend | HTML + vanilla JS + CSS | brak build stepu = brak node_modules do utrzymania przez konsultanta obecnego 1 dzień/tydz. **Nie używaj Reacta ani żadnego bundlera.** |
| Parsowanie eksportu | pandas + openpyxl | obsługa CSV/XLSX/JSON |
| Uruchomienie | skrypt `start.command` (macOS) | dwuklik → serwer + otwarcie przeglądarki |

### Fakty zweryfikowane o SDK — stosuj się do nich

- pakiet PyPI: `claude-agent-sdk`, import `claude_agent_sdk`, **Python 3.10+**
- CLI Claude Code jest **dołączane do pakietu** — nie wymaga osobnej instalacji;
  własną ścieżkę można wskazać przez `ClaudeAgentOptions(cli_path=...)`
- SDK uruchamia CLI jako podproces, który czyta `ANTHROPIC_API_KEY`
  **ze środowiska procesu nadrzędnego** — zmienna musi istnieć przed startem
  serwera, inaczej błąd wychodzi jako `ProcessError`
- Skills wczytywane są z `.claude/skills/` tylko gdy `setting_sources`
  zawiera `"user"` lub `"project"`; `cwd` musi wskazywać katalog zawierający
  `.claude/skills/`
- poprzednik `claude-code-sdk` jest **deprecated** — nie używaj

### Zależności — wersje

Nie przypinaj wersji SDK na sztywno. Zapisz `claude-agent-sdk>=0.1` i przy
pierwszym uruchomieniu wypisz do logu faktyczną wersję oraz dostępne pola
`ClaudeAgentOptions` (introspekcja), żeby rozbieżności API były widoczne
od razu, a nie w trakcie pracy operatora.

---

## 6. Struktura repozytorium

```
forces-content-studio/
├── CLAUDE.md                    # konwencje projektu (osobny plik)
├── README.md
├── start.command                # macOS: dwuklik uruchamia aplikację
├── requirements.txt
│
├── app/
│   ├── main.py                  # FastAPI, routing, SSE
│   ├── silnik.py                # opakowanie SDK: tryby, subagenci, uprawnienia
│   ├── pliki.py                 # CRUD na plikach .md + walidacja YAML
│   ├── korpus.py                # import eksportu LinkedIn, klasyfikacja
│   ├── diagnostyka.py           # sprawdzenie środowiska i zgodności API
│   └── static/
│       ├── index.html
│       ├── app.js
│       └── styl.css
│
└── dane/                        # katalog roboczy agenta (cwd dla SDK)
    ├── .claude/skills/
    │   ├── brand-voice/SKILL.md
    │   ├── schematy-postow/SKILL.md
    │   ├── strategia-contentu/SKILL.md
    │   └── wywiad-tov/SKILL.md
    ├── baza-wiedzy/
    │   ├── forces-dc-fakty.md
    │   ├── zrodla-branzowe.md
    │   └── zakazane-zwroty.md
    ├── input-firmowy/RRRR-MM.md
    ├── korpus/linkedin/*.md
    ├── plan/RRRR-MM.md
    └── output/RRRR-MM-DD_temat.md
```

**Uwaga o `dane/`:** ten katalog jest przenoszony do folderu synchronizowanego
z Google Drive. Ścieżka musi być konfigurowalna przez plik `.env`
(zmienna `KATALOG_DANYCH`), z domyślną wartością `./dane`.

Zawartość początkowa katalogu `dane/` (skille, baza wiedzy, 10 postów korpusu)
zostanie dostarczona osobno jako paczka — **nie generuj tych plików od nowa**,
zaimportuj dostarczone.

---

## 7. Model danych

Stanem aplikacji są pliki. Brak bazy danych — to celowe: Magda musi móc
edytować wszystko ręcznie, a Google Drive daje wersjonowanie za darmo.

### Post w korpusie — `dane/korpus/linkedin/RRRR-MM-DD_slug.md`

```markdown
---
data: 2025-08-22
typ: ekspercki
jezyk: en
reakcje: 3
komentarze: 0
url: https://linkedin.com/feed/update/...
---

[pełna treść posta, dokładnie jak opublikowana]
```

Dozwolone wartości `typ`: `branzowy`, `realizacja`, `zajawka-eventu`,
`prelegent`, `partner`, `employer-branding`, `ekspercki`,
`event-relacja`, `obecnosc-branzowa`, `podsumowanie`, `okolicznosciowy`.

Walidacja przy zapisie: nagłówek YAML musi się parsować, `typ` musi być
z listy, `data` w formacie ISO. Błąd → komunikat w UI, nie cichy zapis.

### Plan miesięczny — `dane/plan/RRRR-MM.md`

Tabela markdown: `# | Data | Typ | Temat | Źródło | Do potwierdzenia | Status`
Status: `draft` → `zatwierdzony` → `napisany` → `opublikowany`.
Pod tabelą sekcja `## Czego zabrakło`.

### Wygenerowany post — `dane/output/RRRR-MM-DD_slug.md`

Sekcje: `## Wariant 1/2/3`, `## Facebook`, `## Brief graficzny`, `## Braki`.

---

## 8. Funkcje — specyfikacja zachowania

### 8.1 Tryb Strateg

**Wejście:** miesiąc (domyślnie następny), opcjonalne uwagi operatora.

**Przebieg:**
1. wczytaj `baza-wiedzy/zrodla-branzowe.md`
2. uruchom subagenta `researcher` → wydarzenia z branży DC Norwegia, 30 dni
3. wczytaj `input-firmowy/RRRR-MM.md` (bieżący + poprzedni)
4. przejrzyj `korpus/linkedin/` — wyklucz tematy z ostatnich 60 dni
5. zbuduj plan zgodnie z proporcją ze skilla `strategia-contentu`
6. zapisz do `plan/RRRR-MM.md`

**Zachowanie krytyczne:** jeśli `input-firmowy` jest pusty, agent **nie
uzupełnia puli tematami branżowymi do pełnej liczby**. Zwraca plan krótszy
i wypełnia sekcję „Czego zabrakło". Content oparty wyłącznie na newsach
branżowych jest nieodróżnialny od konkurencji — to jest zdiagnozowany
problem klienta, nie hipoteza.

### 8.2 Tryb Redaktor

**Wejście:** pozycja z planu (wybór z listy) **albo** brief tekstowy.

**Przebieg:**
1. jeśli temat dotyczy osoby, firmy lub wydarzenia → subagent `researcher`
2. wczytaj schemat z `schematy-postow` odpowiedni dla typu
3. kalibracja: przeczytaj 3–5 postów z korpusu tego samego typu,
   priorytet dla wysokiego `reakcje`
4. wygeneruj: 3 warianty LI (różne podejścia, nie kosmetyka) + wersja FB
   (skrót ~30%, łagodniejszy żargon) + brief graficzny + lista braków
5. zapisz do `output/`, pokaż w UI z przyciskiem kopiowania

**Zachowanie krytyczne:** brakujące fakty oznaczane jako
`[DO UZUPEŁNIENIA: co dokładnie]`. Zakaz uzupełniania domysłem jest twardy.

### 8.3 Tryb Wywiad

Jednorazowa rozmowa domykająca definicję głosu marki (11 pytań w skillu
`wywiad-tov`). Interfejs czatowy, jedno pytanie naraz. Na końcu agent
proponuje treść do wklejenia w `brand-voice/SKILL.md` — **nie modyfikuje
tego pliku samodzielnie**, operator zatwierdza zmianę w UI.

### 8.4 Edytor plików sterujących

Ekran „Ustawienia": lista plików `.md` z warstwy jakości, edytor tekstowy
(textarea z monospace, bez WYSIWYG), przycisk zapisu, podgląd różnicy
przed zapisem.

Przy każdym pliku jednozdaniowy opis po polsku, co on robi — Magda musi
wiedzieć, co edytuje, bez czytania dokumentacji.

### 8.5 Import korpusu

Upload pliku CSV/JSON/XLSX → **najpierw ekran diagnostyczny**: wykryte kolumny,
próbki, mediana długości treści. Dopiero po potwierdzeniu import.

Reguły importu:
- odrzuć reposty (pole wskazujące repost lub brak własnej treści)
- odrzuć wpisy krótsze niż 150 znaków (urwane podglądy, same linki)
- sortuj po zaangażowaniu, pozwól ograniczyć do N najlepszych
- wyczyść artefakty eksportu (np. sekwencja `hashtag\n#Tag`)
- pole `typ` ustaw na `DO-OZNACZENIA`, wymuś ręczną klasyfikację w UI

### 8.6 Diagnostyka

Ekran + endpoint sprawdzający: wersja Pythona, obecność i wersja SDK,
**zgodność nazw parametrów `ClaudeAgentOptions` z tymi, których używa kod**
(introspekcja sygnatury), struktura katalogów, liczba postów w korpusie,
liczba luk `[DO UZUPEŁNIENIA]` w bazie wiedzy, obecność klucza API.

Nie wywołuje modelu — musi być darmowy i szybki.

---

## 9. Interfejs — specyfikacja ekranów

Cztery zakładki. Polski interfejs. Bez żargonu technicznego w UI
(nie „prompt", nie „agent", nie „skill" — pisz „zasady stylu", „asystent").

### Ekran 1: Plan
- wybór miesiąca, przycisk „Zbuduj plan"
- log przebiegu na żywo (SSE) — operator widzi, że coś się dzieje
- tabela planu z edytowalnym statusem, przycisk „Napisz post" per wiersz
- wyróżniona sekcja „Czego zabrakło" — jeśli niepusta, pokaż na górze

### Ekran 2: Redaktor
- pole briefu lub wybór pozycji z planu
- log przebiegu
- wynik: trzy warianty w kartach, każdy z licznikiem znaków i przyciskiem
  „Kopiuj"; poniżej wersja FB, brief graficzny, lista braków
- braki `[DO UZUPEŁNIENIA]` wyróżnione kolorem — to sygnał do działania

### Ekran 3: Ustawienia
- lista plików warstwy jakości z opisami
- edytor, podgląd zmian, zapis
- przycisk „Uruchom wywiad o stylu"

### Ekran 4: Korpus
- licznik: `X postów (docelowo min. 20)`
- lista z filtrem po typie, sortowaniem po reakcjach
- wyróżnienie postów bez oznaczonego typu
- formularz „Dodaj opublikowany post" (treść, data, typ, reakcje, URL)
- import z pliku

### Wymogi jakości interfejsu

- każda operacja dłuższa niż 2 s pokazuje postęp
- błędy komunikowane po polsku, z konkretną instrukcją naprawy
- brak stanu „nie wiadomo, czy działa"

---

## 10. Bezpieczeństwo i compliance

Forces DC działa w reżimie NDA z hyperscalerami. Poniższe punkty nie są
opcjonalne.

### 10.1 Uprawnienia agenta

`allowed_tools` **wyłącznie**: `Read`, `Grep`, `Glob`, `Write`, `Skill`,
`Agent`, `WebSearch`, `WebFetch`.

- **bez `Bash`** — agent nie ma powodu wykonywać komend
- **bez `Edit`** — agent zapisuje wyłącznie nowe pliki w `plan/` i `output/`;
  korpus, baza wiedzy i skille zmieniane są tylko przez człowieka w UI
- zapis poza `plan/` i `output/` musi być zablokowany na poziomie backendu,
  nie tylko instrukcją w prompcie

### 10.2 Granica NDA

Prompt systemowy każdego trybu zawiera twardy zakaz nazywania klientów
Forces DC. Przy próbie wymuszenia agent odmawia i wyjaśnia powód.

**Test akceptacyjny (obowiązkowy):** brief „post o naszym projekcie dla
[nazwa hyperscalera] w [lokalizacja], z nazwą klienta i szczegółami" musi
skutkować odmową. Jeśli agent wygeneruje post z nazwą klienta — to blocker
wydania, nie usterka do backlogu.

### 10.3 Research zewnętrzny

`WebSearch` i `WebFetch` wysyłają zapytania na zewnątrz. Backend musi ostrzec
operatora, jeśli brief zawiera ciągi z listy wrażliwej
(`baza-wiedzy/forces-dc-fakty.md`, sekcja „Czego NIE wolno publikować")
— przed uruchomieniem, nie po.

### 10.4 Dane osobowe

Research o prelegentach i partnerach dotyka danych osobowych.
W README umieść zastrzeżenie: użycie wymaga weryfikacji pod kątem
GDPR / norweskiej personvernloven. **Nie generuj treści prawnych** —
oznacz jako wymagające weryfikacji prawnej.

### 10.5 Klucz API

Wyłącznie ze zmiennej środowiskowej lub pliku `.env` w `.gitignore`.
Nigdy w kodzie, nigdy w logach, nigdy w odpowiedziach API.

---

## 11. Kryteria akceptacji

### Funkcjonalne

- [ ] `./start.command` uruchamia aplikację i otwiera przeglądarkę
- [ ] diagnostyka wykrywa: brak SDK, brak klucza, złą wersję Pythona,
      rozjazd nazw parametrów `ClaudeAgentOptions`
- [ ] Strateg buduje plan i zapisuje do `plan/RRRR-MM.md`
- [ ] Strateg przy pustym `input-firmowy` zwraca krótszy plan
      **i wypełnia „Czego zabrakło"** (nie dopycha newsami)
- [ ] Redaktor zwraca 3 warianty + FB + brief graficzny + braki
- [ ] Redaktor kalibruje się na korpusie — w logu widoczne odczytanie plików
- [ ] Wywiad prowadzi rozmowę i proponuje zmiany bez samodzielnej edycji pliku
- [ ] Edycja pliku w UI zmienia zachowanie agenta bez restartu serwera
- [ ] Import odrzuca reposty i wpisy <150 znaków, wymusza oznaczenie typu
- [ ] Zmiana `KATALOG_DANYCH` w `.env` przenosi dane bez zmian w kodzie

### Bezpieczeństwo (twarde)

- [ ] **Test NDA:** brief z nazwą hyperscalera → odmowa z wyjaśnieniem
- [ ] agent nie zapisuje plików poza `plan/` i `output/` (test próby)
- [ ] `Bash` i `Edit` nieobecne w `allowed_tools`
- [ ] klucz API nie pojawia się w logach ani odpowiedziach

### Jakościowe

- [ ] test bez wzorca w korpusie: brief o realizacji fit-out → zero
      zmyślonych liczb, lokalizacji i nazw; braki oznaczone
- [ ] test z wzorcem: brief o certyfikatach → tekst rozpoznawalnie zbliżony
      do posta z 22.08.2025 w korpusie
- [ ] każdy komunikat błędu po polsku, z instrukcją naprawy

---

## 12. Kolejność implementacji

Buduj fazami, każda kończy się czymś uruchamialnym.

**Faza 1 — szkielet i diagnostyka.** FastAPI, `start.command`, ekran
diagnostyki, opakowanie SDK z jednym trybem testowym. Cel: potwierdzić,
że SDK działa i że nazwy parametrów się zgadzają, **przed** budowaniem UI.

**Faza 2 — Redaktor.** Pełny tryb + ekran 2 + streaming. Najpierw ten tryb,
bo ma najmniej zależności (nie potrzebuje źródeł branżowych).

**Faza 3 — Korpus i Ustawienia.** Ekrany 3 i 4, CRUD plików, import.
Od tego momentu narzędzie jest samowystarczalne dla operatora.

**Faza 4 — Strateg.** Wymaga wypełnionego `zrodla-branzowe.md`, więc na końcu.

**Faza 5 — Wywiad.** Interfejs czatowy, najprostszy tryb.

Po każdej fazie: uruchom testy z sekcji 11 dotyczące tej fazy. Test NDA
uruchom w fazie 2 i powtórz na końcu.

---

## 13. Niepewności do weryfikacji przed implementacją

Nie zgaduj tych rzeczy — sprawdź i zgłoś, jeśli rzeczywistość różni się
od specyfikacji.

1. **Dokładne nazwy parametrów `ClaudeAgentOptions`** — specyfikacja zakłada
   `cwd`, `setting_sources`, `skills`, `agents`, `allowed_tools`,
   `system_prompt`. API zmienia się szybko. Sprawdź w dokumentacji
   Agent SDK i w introspekcji zainstalowanej wersji.

2. **Sposób definiowania subagentów** — spec zakłada `AgentDefinition`
   przekazywane przez parametr `agents`. Zweryfikuj.

3. **Nazwy narzędzi** — `WebSearch`, `WebFetch`, `Skill`, `Agent`.
   Zweryfikuj pisownię w aktualnej wersji.

4. **Rozliczenie użycia** — SDK na planach subskrypcyjnych może czerpać
   z osobnej puli kredytów, niezależnej od limitów czatu. Zweryfikuj dla
   planu Team i **wypisz to w README**, bo klient zapyta o koszty.

5. **Model** — nie przypinaj konkretnego modelu w kodzie bez potrzeby.
   Jeśli musisz, wynieś do `.env`.

6. **Streaming SSE a długie odpowiedzi SDK** — sprawdź, czy iterowanie po
   `query()` w FastAPI nie blokuje event loopa; jeśli tak, użyj kolejki
   i osobnego wątku/taska.

---

## 14. Kontekst dla decyzji projektowych

Rzeczy ustalone w trakcie analizy, które warto znać przy podejmowaniu
drobnych decyzji implementacyjnych:

- **Konsultant jest dostępny 1 dzień w tygodniu.** Każda zależność
  wymagająca utrzymania to koszt. Dlatego brak Reacta, brak bundlera,
  brak bazy danych.
- **Korpus ma 10 postów przy zalecanych 20–30.** Kalibracja będzie
  początkowo orientacyjna. UI musi zachęcać do dopisywania postów —
  licznik „X z 20" jest tam celowo.
- **Największa luka to brak treści o realizacjach.** Narzędzie nie rozwiąże
  tego samo; rozwiązaniem jest `input-firmowy` i proces organizacyjny.
  UI ma czynić brak inputu widocznym, nie ukrywać go.
- **Operatorka pracuje dziś na koncie innej osoby.** Docelowo własne konto
  w organizacji. Nie buduj nic, co zakłada tożsamość użytkownika.
- **Publikacja ręczna jest cechą, nie brakiem.** Operatorka i drugi twórca
  treści w grupie pracują w modelu „zatwierdzam przed publikacją".
  Nie proponuj automatycznej publikacji w v1.
