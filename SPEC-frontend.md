# SPECYFIKACJA FRONTENDU
# Forces DC Content Studio — warstwa interfejsu

**Wersja:** 1.0
**Data:** 28.07.2026
**Status:** rozszerzenie `SPEC-forces-content-studio.md` — sekcja 9 tego
dokumentu zostaje zastąpiona treścią poniżej

---

## CZĘŚĆ I — ANALIZA REFERENCJI

## 1. Co to za produkt

`juliuszdrojecki.pl` to polski SaaS do automatyzacji social media dla małych
firm lokalnych. Model: abonament <cite index="15-1">od 199 zł netto miesięcznie za pełną obsługę AI, z tańszą linią Plan AI od 69 zł, gdzie AI pisze teksty i daje prompty do grafik, ale obrazy generuje użytkownik</cite>.

Grupa docelowa to <cite index="15-1">salony fryzjerskie i kosmetyczne, trenerzy personalni, warsztaty samochodowe, restauracje, biura rachunkowe i lokalne firmy usługowe</cite> — czyli zupełnie inny segment niż Forces DC.

### Dlaczego to nie jest alternatywa dla naszego projektu

Zanim przejdę do UX, jedna rzecz, którą trzeba postawić jasno, bo oszczędza
rozmowę z Kamilem o „może kupmy gotowe":

1. **LinkedIn — kanał główny Forces DC — u nich nie działa.** Strona podaje wprost, że <cite index="15-1">na razie publikują na Facebooku i Instagramie, a LinkedIn, Google i TikTok czekają na weryfikację po stronie tych platform</cite>. Produkt nie obsługuje dziś jedynego kanału, który ma dla Was znaczenie.
2. **Brak warstwy compliance.** Nic w produkcie nie adresuje NDA z hyperscalerami ani zakazu nazywania klientów.
3. **Brak researchu branżowego.** Model generuje treści z profilu firmy, nie z monitoringu wydarzeń w sektorze DC w Norwegii.
4. **Podmiot przetwarzający.** Wysyłanie treści Forces DC do zewnętrznego dostawcy wymaga umowy powierzenia — <cite index="15-1">mają DPA na stronie</cite>, ale to nadal dodatkowa zależność prawna do przejścia z Kamilem.
5. **Kalibracja na własnym korpusie.** Ich profil marki powstaje z opisu firmy w kreatorze, nie z analizy 10 realnych postów z historią zaangażowania.

To dobry produkt dla fryzjera w Poznaniu. Nie dla wykonawcy DC pod NDA.

**Wniosek uboczny, ale ważny:** fakt, że komercyjny produkt z zespołem i budżetem
nie ma jeszcze zgody na publikację na LinkedIn, potwierdza wcześniejszą decyzję —
v1 nie próbuje publikować automatycznie. To nie ostrożność, to stan rynku.

---

## 2. Wzorce UX warte przeniesienia

Tu strona jest naprawdę dobra i warto się uczyć. Osiem wzorców, każdy
z uzasadnieniem, dlaczego pasuje do Magdy.

### 2.1 Czat jako główny sposób pracy, nie formularz

Najmocniejszy wzorzec. <cite index="15-1">Użytkownik opisuje post jednym zdaniem, a asystent tworzy treść, generuje zdjęcie i planuje publikację</cite>. Asystent <cite index="15-1">zna cały panel, nie tylko posty — można zapytać o kredyty, najbliższą publikację czy ustawienia</cite>.

**Dlaczego to pasuje:** Magda pracuje dziś w czacie Claude'a. Formularz z ośmioma
polami to regres wobec tego, co już umie. Czat jest interfejsem, którego nie
trzeba jej tłumaczyć.

### 2.2 Potwierdzenie kosztu przed akcją

Wzorzec z ich demo: asystent zapowiada operację, pokazuje szacowany koszt
i czeka na „Akceptuję" albo „Anuluj". Licznik zużycia widoczny na stałe.
<cite index="15-1">Nie da się przekroczyć limitu — to bezpieczny sufit kosztów</cite>.

**Dlaczego to pasuje:** to bezpośrednia odpowiedź na otwartą kwestię z sekcji 13
głównej specyfikacji — rozliczenie Agent SDK. Kamil zapyta o koszty.
Licznik w interfejsie zamienia niepewność w liczbę.

### 2.3 Podgląd w formie docelowego posta

Wygenerowana treść pokazana jako makieta posta z platformy — avatar, nazwa
firmy, obcięcie tekstu przez „…więcej".

**Dlaczego to pasuje:** Magda ocenia, czy post nadaje się do publikacji.
Surowy markdown w textarea utrudnia tę ocenę. Na LinkedIn kluczowe jest,
co widać przed rozwinięciem — podgląd musi to pokazywać.

### 2.4 Przełącznik „Ty zatwierdzasz, nie AI"

<cite index="15-1">Użytkownik wybiera: publikacja automatyczna albo nic nie wychodzi bez jego zgody, a każdy post można edytować lub poprawić jednym poleceniem do AI</cite>.

**Co przenosimy:** samą jawność. W naszym v1 akceptacja jest zawsze wymagana
i publikacja jest ręczna — ale interfejs ma to komunikować jako świadomą
cechę, nie jako brak funkcji.

### 2.5 Wgrywanie własnych materiałów jako priorytet

<cite index="15-1">Użytkownik wrzuca zdjęcie z realizacji, pomysł na temat lub szkic posta, a AI układa to w treść; można też zaznaczać ulubione zdjęcia jako priorytet</cite>. <cite index="15-1">Jeśli nic nie wrzuci, AI przygotuje posty samodzielnie na podstawie konfiguracji firmy</cite>.

**Dlaczego to kluczowe:** to dokładnie mechanizm `input-firmowy`. U nas ma jednak
działać odwrotnie w jednym punkcie — brak inputu **nie** ma być cicho zastąpiony
treścią generyczną. To zdiagnozowany problem Forces DC: zero postów
o realizacjach. Interfejs musi brak inputu uwypuklać, nie maskować.

### 2.6 Poprawianie treści polem tekstowym, nie ręczną edycją

<cite index="15-1">Poprawia zaplanowane posty — jedno zdanie z uwagami wystarczy</cite>.

**Dlaczego to pasuje:** szybsza pętla niż edycja ręczna, a przy okazji uczy
Magdę formułowania uwag — co bezpośrednio przenosi się na doskonalenie zasad
stylu.

### 2.7 Kreator startowy budujący profil marki

<cite index="15-1">Użytkownik opisuje firmę własnymi słowami, a AI w kilka minut buduje profil: opis, ton, kolory marki i hashtagi</cite>.

**Co przenosimy:** to nasz tryb Wywiad. Różnica: u nas kreator ma najpierw
pokazać, co już wiadomo z analizy 10 postów, i dopytać tylko o luki —
nie budować od zera.

### 2.8 Pomoc w formie krótkich filmów

<cite index="15-1">16 krótkich filmów z panelu w sekcji Pomoc</cite>.

**Dlaczego to pasuje:** administrator jest na miejscu jeden dzień w tygodniu.
Trzy nagrania ekranu po minucie zastępują połowę pytań. To nie jest część
kodu, ale należy do zakresu wdrożenia.

### Czego świadomie NIE przenosimy

| Wzorzec | Dlaczego nie |
|---|---|
| Automatyczna publikacja | brak dostępu do API LinkedIn; nawet oni jeszcze go nie mają |
| Generowanie grafik AI | wymaga brand templates; identyfikacja wizualna Forces DC nie jest generatywna |
| Model kredytowy | płacicie API bezpośrednio; licznik pokazuje zużycie, nie sprzedaje pakietów |
| Rejestracja, OAuth, multi-tenant | aplikacja lokalna, jeden operator |
| Integracje e-commerce | brak zastosowania |
| Statystyki z API platform | v1 nie łączy się z LinkedIn; reakcje wpisywane ręcznie przy dopisywaniu do korpusu |

---

## CZĘŚĆ II — SPECYFIKACJA FRONTENDU

## 3. Zasady projektowe

1. **Czat jest interfejsem podstawowym.** Ekrany strukturalne (plan, korpus,
   ustawienia) uzupełniają go, nie zastępują.
2. **Zero żargonu technicznego.** Nie „prompt", „agent", „skill", „SKILL.md".
   Piszemy: „asystent", „zasady stylu", „plan miesiąca", „materiały z firmy".
3. **Każda operacja ma widoczny stan.** Nigdy „nie wiadomo, czy działa".
4. **Koszt zawsze widoczny.** Przed operacją szacunek, po niej rzeczywiste zużycie.
5. **Brak danych jest komunikatem, nie pustym miejscem.** Pusty input firmowy
   pokazuje się jako wyróżniony blok z instrukcją, nie jako biała plama.
6. **Zero build stepu.** HTML + vanilla JS + CSS, bez Reacta i bundlerów
   (uzasadnienie w `CLAUDE.md`).

---

## 4. Układ aplikacji

```
┌──────────────────────────────────────────────────────────────┐
│  Forces DC Content Studio          Zużycie dziś: 12 300 tok. │
├────────────┬─────────────────────────────────────────────────┤
│            │                                                 │
│  ● Asystent│   OBSZAR GŁÓWNY                                 │
│  ○ Plan    │   (zawartość zależna od zakładki)               │
│  ○ Posty   │                                                 │
│  ○ Materiały│                                                │
│  ○ Styl    │                                                 │
│  ○ Korpus  │                                                 │
│            │                                                 │
│  ─────────  │                                                │
│  Sprawdź    │                                                │
│  środowisko │                                                │
└────────────┴─────────────────────────────────────────────────┘
```

Sześć zakładek. Nawigacja pionowa po lewej, stała. Nagłówek z licznikiem zużycia.

---

## 5. Ekran 1 — Asystent (domyślny)

Główne miejsce pracy. Interfejs czatu.

### Zachowanie

- pole tekstowe na dole, historia rozmowy powyżej
- odpowiedzi strumieniowane (SSE) — tekst pojawia się w miarę generowania
- **kroki agenta widoczne jako zwijane wiersze statusu**, nie surowy log:
  `Czytam zasady stylu…` · `Szukam w branży (3 źródła)…` · `Sprawdzam korpus…`
- asystent zna kontekst całej aplikacji: potrafi odpowiedzieć „ile mam postów
  w korpusie", „co jest w planie na sierpień", „czego brakuje w materiałach"

### Potwierdzanie operacji kosztownych

Przed uruchomieniem trybu Strateg lub Redaktor asystent pokazuje kartę:

```
┌────────────────────────────────────────────┐
│  Napiszę post: zakończenie realizacji      │
│  fit-out, LinkedIn, EN                     │
│                                            │
│  Użyję: zasad stylu, korpusu (3 posty),    │
│         wyszukiwania w sieci               │
│  Szacowane zużycie: ~15 000 tokenów        │
│                                            │
│         [ Uruchom ]    [ Anuluj ]          │
└────────────────────────────────────────────┘
```

Po zakończeniu: rzeczywiste zużycie w stopce odpowiedzi.

### Ostrzeżenie NDA — przed wywołaniem, nie po

Jeśli treść polecenia zawiera ciąg z listy wrażliwej
(`baza-wiedzy/forces-dc-fakty.md`, sekcja „Czego NIE wolno publikować"),
zamiast karty potwierdzenia pokazuje się blokada:

```
┌────────────────────────────────────────────┐
│  ⚠ To polecenie zawiera nazwę objętą NDA   │
│                                            │
│  Wykryto: "[nazwa]"                        │
│  Nie wyślemy tego do modelu ani do sieci.  │
│                                            │
│  Popraw polecenie albo usuń nazwę klienta. │
│                                            │
│         [ Wróć do edycji ]                 │
└────────────────────────────────────────────┘
```

Blokada działa **po stronie backendu, przed wywołaniem SDK**. Wykrycie
w interfejsie to tylko warstwa informacyjna.

---

## 6. Ekran 2 — Plan

### Stan pusty (brak planu na wybrany miesiąc)

Duży przycisk „Zbuduj plan na sierpień" plus lista warunków wstępnych ze
statusem:

```
Przed zbudowaniem planu:
  ✓ Zasady stylu — gotowe
  ✓ Korpus — 10 postów (docelowo 20)
  ✗ Źródła branżowe — nieuzupełnione        [Uzupełnij]
  ✗ Materiały z firmy na sierpień — puste   [Uzupełnij]

Bez materiałów z firmy plan będzie zawierał tylko tematy branżowe.
```

To nie jest blokada — plan da się zbudować. Ale operator widzi konsekwencję
z góry.

### Stan z planem

Tabela: `Data · Typ · Temat · Źródło · Do potwierdzenia · Status · Akcja`

- status jako rozwijana lista (`szkic` → `zatwierdzony` → `napisany` → `opublikowany`),
  z kolorem
- kolumna „Do potwierdzenia" — jeśli niepusta, wiersz oznaczony
- akcja: przycisk „Napisz" → przenosi do ekranu Posty z wypełnionym kontekstem
- sekcja **„Czego zabrakło"** nad tabelą, wyróżniona, jeśli niepusta

---

## 7. Ekran 3 — Posty (Redaktor)

### Wejście

Pole briefu albo wybór pozycji z planu. Pod polem podpowiedź z realnym
przykładem, żeby operator wiedział, jak formułować.

### Wynik — trzy warianty jako karty

Każda karta zawiera:

- **podgląd w formie posta LinkedIn**: awatar Forces DC, nazwa firmy, treść
  z zaznaczoną linią obcięcia „…zobacz więcej" (LinkedIn skraca po ~200 znakach —
  `[ZWERYFIKUJ aktualny limit]`)
- licznik znaków
- etykieta podejścia (`faktograficzny` / `przez problem` / `przez osobę`)
- przyciski: `Kopiuj` · `Popraw` · `Zapisz jako wybrany`

### Poprawianie

Przycisk `Popraw` otwiera jednolinijkowe pole: „Napisz, co zmienić".
Wynik zastępuje treść karty, poprzednia wersja dostępna przez `Cofnij`.
Bez ręcznej edycji jako podstawowej ścieżki — ale z możliwością przejścia
w tryb edycji tekstu dla drobnych korekt.

### Pozostałe sekcje pod kartami

- **Wersja na Facebooka** — zwinięta domyślnie, z licznikiem znaków
- **Brief graficzny** — czego potrzebuje grafik: opis, format, tekst na obrazie,
  sugerowany szablon; przycisk „Kopiuj dla Sikory"
- **Braki** — lista `[DO UZUPEŁNIENIA]` wyróżniona kolorem ostrzegawczym,
  z przyciskiem „Dopisz do materiałów" przenoszącym do ekranu Materiały

Sekcja braków nie może być zwinięta domyślnie. To najważniejszy sygnał
na tym ekranie.

---

## 8. Ekran 4 — Materiały (input firmowy)

Ekran, którego nie ma w referencji, a który u nas jest krytyczny — bo brak
treści o realizacjach to zdiagnozowany rdzeń problemu.

### Układ

Wybór miesiąca + pięć bloków odpowiadających sekcjom pliku:

```
Projekty — start                                    [+ Dodaj]
  (pusto)

Projekty — zakończenie / odbiór                     [+ Dodaj]
  • Odbiór fit-out, region Oslo, 3 tygodnie    [edytuj] [usuń]

Kamienie milowe, certyfikaty                        [+ Dodaj]
  (pusto)

Ludzie — zatrudnienia, awanse                       [+ Dodaj]
  (pusto)

Obecność branżowa                                   [+ Dodaj]
  (pusto)
```

`+ Dodaj` otwiera jedno pole tekstowe. Jedno zdanie wystarczy — bez formularza
z ośmioma polami, bo wtedy nikt tego nie wypełni.

### Blok informacyjny na górze, gdy miesiąc jest pusty

```
Ten miesiąc jest pusty.

Plan contentu oparty wyłącznie na newsach z branży będzie
nieodróżnialny od konkurencji. Wyróżnia Was to, co realnie
dzieje się na budowach.

Jedno zdanie wystarczy.
```

### Funkcja pomocnicza

Przycisk „Wyślij prośbę o materiały" generuje gotowy tekst wiadomości
(do skopiowania na WhatsAppa) z pytaniem o wydarzenia z miesiąca —
adresowany do Maćka i Kaktusa. Nie wysyła sam.

---

## 9. Ekran 5 — Styl (zasady)

Edycja warstwy jakości. Zakładki wewnętrzne odpowiadające plikom, z opisem
po polsku — bez ujawniania nazw plików:

| Nazwa w UI | Plik | Opis w UI |
|---|---|---|
| Głos marki | `brand-voice/SKILL.md` | Jak Forces DC pisze: ton, zasady, czego unikać |
| Rodzaje postów | `schematy-postow/SKILL.md` | Struktura i długość każdego typu posta |
| Zasady planowania | `strategia-contentu/SKILL.md` | Jak asystent buduje plan miesiąca |
| Zakazane zwroty | `zakazane-zwroty.md` | Lista zwrotów, które nie mają wyjść |
| Fakty o firmie | `forces-dc-fakty.md` | Co asystent wie o Forces DC i czego nie wolno publikować |
| Źródła branżowe | `zrodla-branzowe.md` | Skąd asystent bierze newsy z branży |

### Elementy

- edytor: textarea monospace, bez WYSIWYG (pliki są w Markdown)
- licznik miejsc `[DO POTWIERDZENIA]` i `[DO UZUPEŁNIENIA]` w każdym pliku,
  z podświetleniem
- przed zapisem podgląd różnicy
- przycisk **„Porozmawiaj o stylu"** → uruchamia tryb Wywiad w czacie

### Wywiad — zachowanie

Kreator zaczyna od pokazania, co już wiadomo z analizy korpusu (11 pytań
w skillu `wywiad-tov`), i pyta tylko o luki. Na końcu proponuje gotową treść
do wklejenia — **operator zatwierdza, agent nie zapisuje sam**.

---

## 10. Ekran 6 — Korpus

### Nagłówek

```
Opublikowane posty: 10 / 20 zalecanych
[████████░░░░░░░░]

Im więcej postów tu wgrasz, tym lepiej asystent pisze
w Waszym głosie. Dopisuj każdy opublikowany post.
```

### Lista

Tabela: `Data · Typ · Język · Reakcje · Początek treści · Akcje`

- filtr po typie, sortowanie po reakcjach
- wiersze bez oznaczonego typu wyróżnione — wymagają uzupełnienia
- rozwinięcie wiersza pokazuje pełną treść

### Dodawanie

Dwie ścieżki:

1. **Formularz** „Dodaj opublikowany post": treść, data, typ (lista), język,
   reakcje, URL. To główna ścieżka — używana po każdej publikacji.
2. **Import z pliku** (CSV/JSON/XLSX): upload → **ekran diagnostyczny**
   z wykrytymi kolumnami, próbkami i medianą długości treści → dopiero potem
   import. Reguły odrzucania (reposty, wpisy <150 znaków) pokazane jako wynik:
   „zaimportowano 10, odrzucono 13 (10 repostów, 3 zbyt krótkie)".

---

## 11. Ekran pomocniczy — Sprawdź środowisko

Dostępny z dolnej części nawigacji. Wynik diagnostyki w formie listy
z ikonami statusu. Nie wywołuje modelu — musi być darmowy i natychmiastowy.

Sprawdza: wersja Pythona, obecność i wersja SDK, **zgodność nazw parametrów
`ClaudeAgentOptions` z tymi używanymi w kodzie** (introspekcja), struktura
katalogów, liczba postów w korpusie, liczba luk w bazie wiedzy, obecność
klucza API, ścieżka katalogu danych.

Każdy problem z konkretną instrukcją naprawy po polsku.

---

## 12. Warstwa wizualna

Nie kopiuj estetyki referencji — to strona sprzedażowa dla firm lokalnych.
Narzędzie wewnętrzne ma być spokojne i czytelne.

- **Typografia:** jeden krój bezszeryfowy systemowy, dwa rozmiary nagłówków,
  monospace w edytorach i podglądach kodu
- **Kolor:** neutralne tło, jeden kolor akcentu na akcje główne;
  kolory funkcyjne wyłącznie dla znaczeń: ostrzeżenie (braki), błąd (NDA),
  potwierdzenie (zapisano)
- **Bez animacji dekoracyjnych.** Animacja tylko jako wskaźnik postępu.
- **Gęstość informacji wysoka** — to narzędzie pracy, nie landing page.
  Tabele zwarte, mało pustej przestrzeni.
- **Responsywność:** desktop pierwszorzędnie (Magda pracuje na laptopie).
  Układ nie może się psuć poniżej 1280 px, ale mobile nie jest wymagane.
- **Dostępność:** kontrast tekstu min. 4.5:1, obsługa klawiaturą,
  focus widoczny.

---

## 13. Kryteria akceptacji frontendu

### Funkcjonalne

- [ ] czat strumieniuje odpowiedź, kroki agenta widoczne jako statusy
- [ ] karta potwierdzenia przed każdą operacją kosztowną, z szacunkiem zużycia
- [ ] licznik zużycia w nagłówku aktualizuje się po operacji
- [ ] **blokada NDA zadziała przed wywołaniem SDK** (test: brief z nazwą
      hyperscalera nie wychodzi z backendu)
- [ ] podgląd posta pokazuje linię obcięcia LinkedIna i licznik znaków
- [ ] `Popraw` działa jako polecenie tekstowe, `Cofnij` przywraca wersję
- [ ] sekcja braków nie jest zwinięta i prowadzi do ekranu Materiały
- [ ] pusty miesiąc w Materiałach pokazuje blok informacyjny, nie białą plamę
- [ ] edycja pliku na ekranie Styl zmienia zachowanie asystenta bez restartu
- [ ] import pokazuje diagnostykę przed importem i raport po
- [ ] licznik korpusu `X / 20` z paskiem postępu
- [ ] diagnostyka wykrywa rozjazd nazw parametrów SDK

### Użyteczność — test na osobie nietechnicznej

Osoba, która nigdy nie widziała narzędzia, wykonuje bez instrukcji:

- [ ] generuje post z briefu
- [ ] kopiuje wybrany wariant
- [ ] dopisuje opublikowany post do korpusu
- [ ] znajduje, gdzie zmienić zasady stylu
- [ ] rozumie, czego brakuje, gdy plan wyjdzie krótki

Jeśli którykolwiek punkt wymaga tłumaczenia — interfejs wymaga poprawy,
nie użytkownik szkolenia.

### Techniczne

- [ ] brak `node_modules`, brak build stepu — pliki statyczne serwowane
      przez FastAPI
- [ ] wszystkie komunikaty po polsku, każdy błąd z instrukcją naprawy
- [ ] brak `localStorage` jako źródła prawdy — stanem są pliki na dysku
- [ ] działa w Safari i Chrome na macOS

---

## 14. Kolejność implementacji frontendu

Wpisuje się w fazy z głównej specyfikacji:

| Faza | Ekrany | Uzasadnienie |
|---|---|---|
| 1 | Sprawdź środowisko | potwierdza zgodność SDK przed budową UI |
| 2 | Asystent + Posty | najkrótsza droga do wartości; test NDA tutaj |
| 3 | Korpus + Styl | narzędzie staje się samowystarczalne dla operatora |
| 4 | Plan + Materiały | wymagają uzupełnionych źródeł branżowych |
| 5 | Wywiad w czacie | najprostszy tryb, na końcu |

---

## 15. Poza kodem — do zakresu wdrożenia

Trzy nagrania ekranu po ~60 sekund, wzorem sekcji Pomoc w referencji:

1. jak wygenerować post i skopiować wariant
2. jak dopisać opublikowany post do korpusu
3. jak zmienić zasady stylu

To nie jest część aplikacji, ale bez tego administrator obecny jeden dzień
w tygodniu zostanie zasypany pytaniami. Nagrania robi Marcin po odbiorze fazy 3.
