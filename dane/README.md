# Katalog danych — rusztowanie do zastąpienia

Ten katalog jest katalogiem roboczym agenta (`cwd` dla SDK, SPEC sekcja 5–6).
W tym repozytorium zawiera **wyłącznie szkielet struktury** — puste katalogi
i pliki jawnie oznaczone jako placeholdery.

**Zgodnie z `CLAUDE.md` i SPEC sekcja 6: prawdziwa zawartość (zasady stylu
wypracowane z klientem, baza wiedzy o Forces DC, 10 realnych postów korpusu)
ma zostać dostarczona osobno jako gotowa paczka i zaimportowana tutaj —
nie generuj tej treści od nowa.** Te pliki kodują wnioski z analizy realnego
profilu LinkedIn klienta, których nie da się odtworzyć bez tamtych danych.

## Co zrobić przed użyciem produkcyjnym

1. Zastąp pliki w `.claude/skills/*/SKILL.md` dostarczoną wersją.
2. Zastąp pliki w `baza-wiedzy/*.md` dostarczoną wersją — w szczególności
   `forces-dc-fakty.md`, sekcja „Czego NIE wolno publikować" (granica NDA,
   SPEC 10.2–10.3).
3. Zaimportuj 10 postów korpusu do `korpus/linkedin/` (przez ekran „Korpus"
   od Fazy 3, albo ręcznie w formacie z SPEC sekcja 7).
4. Sprawdź wynik na ekranie „Sprawdź środowisko" — liczniki postów i luk
   w bazie wiedzy powinny odzwierciedlać prawdziwą zawartość.
