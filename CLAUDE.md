# CLAUDE.md — Forces DC Content Studio

Konwencje obowiązujące w tym repozytorium. Specyfikacja funkcjonalna:
`SPEC-forces-content-studio.md`. Specyfikacja frontendu: `SPEC-frontend.md`
(zastępuje sekcję 9 dokumentu głównego).

---

## Kontekst w jednym akapicie

Narzędzie contentowe dla Forces DC (fit-out data center, Norwegia). Główną
użytkowniczką jest asystentka nietechniczna — nie otworzy terminala i nie
zmieni linii kodu. Administrator jest dostępny jeden dzień w tygodniu.
Te dwa fakty rozstrzygają większość decyzji projektowych.

---

## Zasady twarde

1. **Zero build stepu.** Frontend to HTML + vanilla JS + CSS. Bez Reacta,
   bez npm, bez bundlerów. Uzasadnienie: nikt tego nie będzie utrzymywał.

2. **Pliki są bazą danych.** Stan aplikacji to pliki `.md` na dysku.
   Nie wprowadzaj SQLite ani żadnej bazy — operatorka musi móc edytować
   wszystko ręcznie, a Drive daje wersjonowanie.

3. **Agent nie ma `Bash` ani `Edit`.** Lista `allowed_tools` jest zamknięta:
   `Read`, `Grep`, `Glob`, `Write`, `Skill`, `Agent`, `WebSearch`, `WebFetch`.
   Zapis ograniczony do `plan/` i `output/` — wymuszony w backendzie,
   nie tylko w prompcie.

4. **Granica NDA jest nienegocjowalna.** Agent nie nazywa klientów Forces DC.
   Test: brief z nazwą hyperscalera musi skutkować odmową. Blocker wydania.

5. **Nie zgaduj API SDK.** Jeśli parametr z SPEC nie istnieje w zainstalowanej
   wersji — sprawdź dokumentację i zgłoś rozbieżność w komentarzu.
   Nie obchodź problemu cichą zmianą zachowania.

---

## Język

- **Kod:** angielski (nazwy zmiennych, funkcji, klas)
- **Komentarze w kodzie:** polski, tylko tam, gdzie wyjaśniają decyzję
  („dlaczego"), nie działanie („co")
- **Interfejs użytkownika:** polski, bez żargonu technicznego
  — nie „prompt", nie „agent", nie „skill"; pisz „zasady stylu", „asystent",
  „plan miesiąca"
- **Komunikaty błędów:** polski + konkretna instrukcja naprawy.
  Nie „Error 500", a „Nie udało się zapisać pliku — sprawdź, czy folder
  danych jest dostępny"
- **Dokumentacja i README:** polski

---

## Struktura

Trzymaj się układu z SPEC sekcja 6. Nie twórz dodatkowych warstw abstrakcji
„na przyszłość" — projekt ma jednego administratora i jeden przypadek użycia.

```
app/main.py         → routing, SSE, nic więcej
app/silnik.py       → cała styczność z SDK, izolowana w jednym miejscu
app/pliki.py        → CRUD + walidacja YAML
app/korpus.py       → import i klasyfikacja
app/diagnostyka.py  → sprawdzenia bez wywołania modelu
```

Cała styczność z SDK w `silnik.py`. Gdy API się zmieni, poprawka ma być
w jednym pliku.

---

## Styl kodu

- Python: typowanie na sygnaturach funkcji publicznych, `pathlib` zamiast
  `os.path`, f-stringi
- Bez klas tam, gdzie wystarczy funkcja
- Bez `try/except` łykających wyjątki bez logowania
- Długość funkcji: jeśli nie mieści się na ekranie, podziel

---

## Czego nie robić

- nie dodawaj automatycznej publikacji na LinkedIn (poza zakresem v1,
  brak oficjalnego konektora, ryzyko regulaminowe)
- nie generuj grafik (wymaga brand templates od grafika)
- nie dodawaj triggerów ani harmonogramów
- nie wprowadzaj uwierzytelniania użytkowników
- nie generuj treści prawnych — oznaczaj jako wymagające weryfikacji
- nie przypinaj konkretnego modelu w kodzie; jeśli musisz, wynieś do `.env`
- nie commituj `.env` ani klucza API

---

## Dane początkowe

Katalog `dane/` (skille, baza wiedzy, 10 postów korpusu) jest **dostarczony**.
Nie generuj tych plików od nowa — zaimportuj paczkę. Zawierają wnioski
z analizy realnego profilu klienta, których nie da się odtworzyć.

W tym repozytorium katalog `dane/` zawiera na razie wyłącznie **rusztowanie**
(puste katalogi + pliki-placeholdery jawnie oznaczone jako takie). Prawdziwa
zawartość ma zostać zaimportowana osobno przez administratora — zobacz
`dane/README.md`.

---

## Definicja gotowości

Faza jest skończona, gdy przechodzą jej testy z SPEC sekcja 11 i gdy
osoba nietechniczna wykonałaby główną operację tej fazy bez instrukcji.
