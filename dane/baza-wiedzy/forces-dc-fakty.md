# Fakty o firmie — PLACEHOLDER

Co asystent wie o Forces DC i czego nie wolno publikować.

## Czym zajmuje się firma

Odczytane ze strony forces.no (lipiec 2026) — **do potwierdzenia u klienta**.

**Pozycjonowanie i hasła własne firmy:**
- „Special Forces For Nordic Data Center Industry" — hasło ze strony głównej
- „Providing skilled teams to support all fit-out tasks and site logistic
  in data center construction"
- Zasięg: **cały region nordycki**, nie sama Norwegia

**Czym się różnią (ich własne sformułowanie, sekcja „What makes us different"):**
własne wsparcie na miejscu — Site Managerowie i Project Managerowie
nadzorują zespoły i pozostają w bezpośrednim kontakcie z kierownictwem
klienta. To nie jest samo użyczanie ludzi. Do tego pełna obsługa HR:
rekrutacja, wdrożenie i bieżące zarządzanie zespołem.

**Liczby podawane publicznie na stronie** (sekcja „Our Impact in Numbers"):
- +269 342 godzin w data center **bez wypadków (HSE)**
- +193 000 metrów ułożonych kabli
- +30 zespołów, +15 liderów, +300 wykwalifikowanych pracowników
- +30% wzrost efektywności

**Zespół:** monterzy, elektrycy, stolarze, malarze, monterzy paneli
warstwowych. Certyfikaty wymieniane na stronie: FSE, podnośniki nożycowe,
praca na wysokości.

**Odbiorcy:** generalni wykonawcy (pełny pakiet HR) oraz podwykonawcy
(elastyczne zwiększanie mocy przerobowych).

**Przynależność branżowa:** członek Norsk Datasenter Industri, producent
NDC TV. To jest gotowy temat pod typ posta „obecnosc-branzowa".

**Projekty wymienione publicznie na własnej stronie** (sekcja „Projects We
Power"): Lefdal Mine, VLB1A Skien, Hamar, Fetsund, Enebakk.

**Firmy pokazane publicznie na stronie jako referencje** (sekcja „Trusted by
Industry Leaders"): Schneider Electric, CTS Nordics, Stengel IT-Infrastruktur,
Oslo Bilutleie, est-G.T Nordics AS.

> **Uwaga do rozstrzygnięcia z klientem.** Powyższe nazwy projektów i firm
> Forces DC publikuje samodzielnie na własnej stronie, więc nie są objęte
> tajemnicą. Nie znaczy to jednak, że wolno je swobodnie łączyć z detalami
> realizacji w postach — ustal z Maćkiem, co konkretnie wolno napisać
> o tych lokalizacjach. Do czasu ustalenia asystent ich nie używa.

[DO UZUPEŁNIENIA: powyższe pochodzi ze strony internetowej, nie od klienta —
potwierdź z Magdą i uzupełnij o rzeczy, których na stronie nie ma.]

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
