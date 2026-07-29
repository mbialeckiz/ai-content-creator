# Fakty o firmie — PLACEHOLDER

Co asystent wie o Forces DC i czego nie wolno publikować.

[DO UZUPEŁNIENIA: ten plik ma zostać zastąpiony wersją dostarczoną przez
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
