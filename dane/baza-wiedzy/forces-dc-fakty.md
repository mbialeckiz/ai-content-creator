# Fakty o firmie — PLACEHOLDER

Co asystent wie o Forces DC i czego nie wolno publikować.

## Czym zajmuje się firma

Ustalone ze strony forces.no (lipiec 2026) — **do potwierdzenia u klienta**:

- Forces DC dostarcza wyspecjalizowane zespoły do prac fit-out przy budowie
  data center **w całym regionie nordyckim**, nie tylko w Norwegii.
- Zespół: monterzy, elektrycy, stolarze i malarze z doświadczeniem
  w obiektach data center.
- Zaplecze ok. 300 gotowych do pracy specjalistów.
- Wyróżnik komunikowany na stronie: **własni Site Managerowie i Project
  Managerowie na budowie**, w bezpośrednim kontakcie z kierownictwem klienta
  — nie samo „użyczanie ludzi".
- Zakres wykracza poza dostarczenie rąk do pracy: doradztwo, obsługa HR,
  rekrutacja, wdrożenie i bieżące zarządzanie zespołem.
- Druga usługa obok fit-outu: logistyka placu budowy (site logistics).
- Deklaracja ze strony głównej: „Experts in all fit-out tasks in DC
  construction".

[DO UZUPEŁNIENIA: powyższe pochodzi ze strony internetowej, nie od klienta —
potwierdź z Magdą i uzupełnij o rzeczy, których na stronie nie ma.

Reszta tego pliku ma zostać zastąpiona wersją dostarczoną przez
administratora. Musi zawierać sekcję „Czego NIE wolno publikować" z listą
nazw klientów/hyperscalerów objętych NDA (SPEC 10.2–10.3) — bez niej
blokada NDA w aplikacji nie ma czego wykrywać.]

## Czego NIE wolno publikować

Backend wykrywa frazy z listy poniżej w poleceniu **przed** wysłaniem
czegokolwiek do modelu czy do sieci (SPEC 10.2–10.3, `app/pliki.py`
funkcja `wykryj_fraze_nda`). Format pozycji: pogrubiona część linii to
dokładna fraza do wykrycia (dopasowanie bez rozróżniania wielkości liter).
Dopisz każdą nazwę klienta/hyperscalera objętego NDA jako osobną pozycję.

- **Hyperscaler Nordics AS** — przykład formatu, nazwa fikcyjna wyłącznie
  do testów mechanizmu blokady. [DO UZUPEŁNIENIA: zastąp prawdziwą listą
  klientów Forces DC objętych NDA przed uruchomieniem produkcyjnym —
  bez tego test NDA z SPEC 10.2 nie ma czego wykrywać.]
