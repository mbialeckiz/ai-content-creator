// Frontend Fazy 1: nawigacja między zakładkami + ekran "Sprawdź środowisko".
// Zero build stepu — czysty JS, bez frameworka (CLAUDE.md).

const OBSZAR = document.getElementById("obszar-glowny");

const NAZWY_ZAKLADEK = {
  asystent: "Asystent",
  plan: "Plan",
  posty: "Posty",
  materialy: "Materiały",
  styl: "Styl",
  korpus: "Korpus",
};

const IKONA_STATUSU = { ok: "✓", ostrzezenie: "!", blad: "✕" };

function escapeHtml(tekst) {
  const nosnik = document.createElement("div");
  nosnik.textContent = tekst ?? "";
  return nosnik.innerHTML;
}

// Licznik zużycia w nagłówku (SPEC-frontend 4). Liczy koszt operacji
// wykonanych od uruchomienia aplikacji — bez tego operatorka dowiaduje się
// o wydatku dopiero z rachunku.
let kosztSesji = 0;

function dopiszKoszt(kosztUsd) {
  if (!kosztUsd) return;
  kosztSesji += kosztUsd;
  const element = document.querySelector(".zuzycie");
  if (element) {
    element.textContent = `Wydano w tej sesji: ${kosztSesji.toFixed(2)} USD`;
    element.classList.toggle("zuzycie-wysokie", kosztSesji >= 2);
  }
}

function ustawAktywnaZakladke(nazwa) {
  document.querySelectorAll("button.zakladka, [data-zakladka]").forEach((el) => {
    el.classList.toggle("aktywna", el.dataset.zakladka === nazwa);
  });
}

function renderujPlaceholder(nazwaZakladki) {
  const etykieta = NAZWY_ZAKLADEK[nazwaZakladki] || nazwaZakladki;
  OBSZAR.innerHTML = `
    <h2>${etykieta}</h2>
    <div class="karta">
      <p class="placeholder">
        Ta funkcja pojawi się w kolejnej fazie budowy narzędzia.
        Na razie sprawdź działanie środowiska w zakładce „Sprawdź środowisko”.
      </p>
    </div>
  `;
}

function elementSprawdzenia(sprawdzenie) {
  // Przy statusie „ok" podpowiedź jest wskazówką, nie usterką — czerwony
  // tekst pod zielonym ptaszkiem czytał się jak błąd.
  const klasaPodpowiedzi = sprawdzenie.status === "ok" ? "szczegoly" : "instrukcja-naprawy";
  const naprawa = sprawdzenie.instrukcja_naprawy
    ? `<div class="${klasaPodpowiedzi}">${sprawdzenie.instrukcja_naprawy}</div>`
    : "";
  return `
    <div class="sprawdzenie status-${sprawdzenie.status}">
      <div class="status-ikona">${IKONA_STATUSU[sprawdzenie.status] || "?"}</div>
      <div class="sprawdzenie-tresc">
        <strong>${sprawdzenie.etykieta}</strong>
        <div class="szczegoly">${sprawdzenie.szczegoly}</div>
        ${naprawa}
      </div>
    </div>
  `;
}

// Klucz API ustawiany z poziomu aplikacji. Plik .env zaczyna się od kropki,
// więc Finder go nie pokazuje, a TextEdit potrafi zapisać kopię w innym
// miejscu — bez tego formularza wymiana klucza zawsze wymagałaby
// administratora. Klucz nigdy nie wraca z serwera do przeglądarki.
function elementUstawienKlucza(ustawienia) {
  const stan = ustawienia.klucz_wypelniony
    ? `<span class="warunek-ok">✓ Klucz jest zapisany w tym pliku</span>`
    : `<span class="warunek-brak">✗ W tym pliku nie ma jeszcze klucza</span>`;

  return `
    <div class="karta">
      <h3 style="margin-top:0">Klucz dostępu do asystenta</h3>
      <p class="szczegoly">Aplikacja czyta ustawienia wyłącznie z tego pliku:</p>
      <p class="monospace" style="font-size:0.82rem;word-break:break-all">${escapeHtml(ustawienia.sciezka || "—")}</p>
      <p style="margin:0.35rem 0">${stan}</p>
      <p class="szczegoly">
        Jeśli wpisywałeś klucz gdzie indziej, trafił do innego pliku niż ten.
        Wklej go poniżej — zapiszemy w odpowiednim miejscu, bez restartu aplikacji.
      </p>
      <div class="pasek-narzedzi" style="margin:0.5rem 0 0">
        <input type="password" id="pole-klucza" style="flex:1;min-width:320px" placeholder="sk-ant-…" autocomplete="off">
        <button class="przycisk-glowny" id="przycisk-zapisz-klucz">Zapisz klucz</button>
        <span id="status-klucza" class="szczegoly"></span>
      </div>
    </div>
  `;
}

async function zapiszKluczApi() {
  const pole = document.getElementById("pole-klucza");
  const status = document.getElementById("status-klucza");
  status.textContent = "Zapisuję…";
  try {
    const odpowiedz = await fetch("/api/klucz-api", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ klucz: pole.value }),
    });
    const dane = await odpowiedz.json();
    if (!odpowiedz.ok) throw new Error(dane.blad || `HTTP ${odpowiedz.status}`);
    pole.value = "";
    renderujDiagnostyke();
  } catch (blad) {
    status.innerHTML = `<span class="instrukcja-naprawy">${escapeHtml(blad.message)}</span>`;
  }
}

async function renderujDiagnostyke() {
  OBSZAR.innerHTML = `<h2>Sprawdź środowisko</h2><div class="karta"><p class="placeholder">Wczytuję…</p></div>`;
  let dane;
  try {
    const odpowiedz = await fetch("/api/diagnostyka");
    if (!odpowiedz.ok) throw new Error(`HTTP ${odpowiedz.status}`);
    dane = await odpowiedz.json();
  } catch (blad) {
    OBSZAR.innerHTML = `
      <h2>Sprawdź środowisko</h2>
      <div class="karta">
        <p class="placeholder">
          Nie udało się pobrać diagnostyki z serwera (${blad.message}).
          Sprawdź, czy serwer aplikacji nadal działa, i odśwież stronę.
        </p>
      </div>
    `;
    return;
  }

  const listaSprawdzen = dane.sprawdzenia.map(elementSprawdzenia).join("");

  OBSZAR.innerHTML = `
    <h2>Sprawdź środowisko</h2>
    <div class="liczniki">
      <div class="licznik">
        <div class="wartosc">${dane.liczniki.postow_w_korpusie}</div>
        <div class="etykieta">postów w korpusie (docelowo min. 20)</div>
      </div>
      <div class="licznik">
        <div class="wartosc">${dane.liczniki.luk_w_bazie_wiedzy}</div>
        <div class="etykieta">luk [DO UZUPEŁNIENIA] w bazie wiedzy</div>
      </div>
      <div class="licznik">
        <div class="wartosc">${dane.liczniki.wgranych_dokumentow ?? 0}</div>
        <div class="etykieta">wgranych artykułów i dokumentów</div>
      </div>
      <div class="licznik">
        <div class="wartosc">${dane.liczniki.miesiecy_z_materialami ?? 0}</div>
        <div class="etykieta">miesięcy z materiałami z firmy</div>
      </div>
    </div>
    <div class="karta">${listaSprawdzen}</div>

    ${elementUstawienKlucza(dane.ustawienia || {})}

    <div class="karta">
      <h3 style="margin-top:0">Testowe wywołanie silnika</h3>
      <div class="ostrzezenie-koszt">
        To sprawdzenie, w przeciwieństwie do listy powyżej, faktycznie woła model
        i zużywa tokeny. Uruchamiaj tylko wtedy, gdy chcesz potwierdzić, że silnik
        agentowy realnie odpowiada (np. po zmianie klucza API).
      </div>
      <button class="przycisk-glowny" id="przycisk-testu">Uruchom testowe wywołanie</button>
      <div class="log-przebiegu" id="log-testu" hidden></div>
    </div>
  `;

  document.getElementById("przycisk-testu").addEventListener("click", uruchomTestSilnika);
  document.getElementById("przycisk-zapisz-klucz").addEventListener("click", zapiszKluczApi);
  document.getElementById("pole-klucza").addEventListener("keydown", (zdarzenie) => {
    if (zdarzenie.key === "Enter") { zdarzenie.preventDefault(); zapiszKluczApi(); }
  });
}

function uruchomTestSilnika() {
  const przycisk = document.getElementById("przycisk-testu");
  const log = document.getElementById("log-testu");
  log.hidden = false;
  log.innerHTML = "";
  przycisk.disabled = true;
  przycisk.textContent = "Trwa wywołanie…";

  const dopiszWpis = (tekst, klasa = "") => {
    const wpis = document.createElement("div");
    wpis.className = `wpis ${klasa}`;
    wpis.textContent = tekst;
    log.appendChild(wpis);
    log.scrollTop = log.scrollHeight;
  };

  const zrodlo = new EventSource("/api/silnik/test");

  const zakoncz = () => {
    zrodlo.close();
    przycisk.disabled = false;
    przycisk.textContent = "Uruchom testowe wywołanie";
  };

  zrodlo.onmessage = (zdarzenie) => {
    const dane = JSON.parse(zdarzenie.data);
    if (dane.typ === "status") {
      dopiszWpis(dane.tekst);
    } else if (dane.typ === "fragment") {
      dopiszWpis(dane.tekst);
    } else if (dane.typ === "wynik") {
      dopiszKoszt(dane.koszt_usd);
      dopiszWpis(
        `Zakończono. Tury: ${dane.tury}, koszt: ${dane.koszt_usd ?? "brak danych"} USD.`
      );
      zakoncz();
    } else if (dane.typ === "blad") {
      dopiszWpis(dane.tekst, "blad");
      zakoncz();
    }
  };

  zrodlo.onerror = () => {
    dopiszWpis("Połączenie przerwane — sprawdź, czy serwer nadal działa.", "blad");
    zakoncz();
  };
}

// --- Ekran "Posty" (tryb Redaktor, SPEC 8.2 / SPEC-frontend 7) ---

// Wyniki trzymane po ID, nie jako pojedyncza zmienna "ostatni wynik" — na
// ekranie Asystenta kilka wygenerowanych postów może współistnieć naraz
// w historii czatu, każdy z własnymi przyciskami "Kopiuj".
let licznikWynikowPostow = 0;
const wynikiPostow = {};

// Ustawiane przez przycisk „Napisz" w planie — ekran Posty otwiera się
// z wypełnionym briefem (SPEC-frontend 6).
let briefZPlanu = "";

function renderujPosty() {
  OBSZAR.innerHTML = `
    <h2>Posty</h2>
    <div class="karta">
      <label for="pole-briefu"><strong>O czym ma być post?</strong></label>
      <p class="szczegoly">
        Przykład: „post o zakończeniu realizacji fit-out w regionie Oslo,
        bez podawania nazwy klienta"
      </p>
      <textarea
        id="pole-briefu"
        class="monospace"
        rows="4"
        style="width:100%;margin-top:0.5rem"
        placeholder="Opisz temat posta…"
      ></textarea>
      <details class="karta karta-zrodla" id="karta-zrodla">
        <summary>
          <strong>Materiał źródłowy</strong>
          <span class="szczegoly">nieobowiązkowe</span>
        </summary>
        <p class="szczegoly">
          Jeśli post ma się opierać na artykule albo raporcie, wklej tutaj sam
          fragment, który ma znaczenie — dwa, trzy akapity. Nie wklejaj całego
          dokumentu: asystent nie napisze przez to lepszego posta, a każdy
          dodatkowy tysiąc znaków podnosi koszt.
        </p>
        <textarea
          id="pole-zrodla"
          rows="6"
          style="width:100%;margin-top:0.5rem"
          placeholder="Wklej fragment artykułu, raportu albo notatki…"
        ></textarea>
        <p class="szczegoly" id="licznik-zrodla">0 znaków</p>
      </details>
      <div style="margin-top:0.75rem">
        <button class="przycisk-glowny" id="przycisk-generuj">Generuj</button>
      </div>
      <div class="log-przebiegu" id="log-redaktora" hidden></div>
    </div>
    <div id="wynik-redaktora"></div>
    <div id="historia-postow"></div>
  `;
  document.getElementById("przycisk-generuj").addEventListener("click", uruchomRedaktora);
  podepnijPoleZrodla();

  if (briefZPlanu) {
    document.getElementById("pole-briefu").value = briefZPlanu;
    briefZPlanu = "";
  }

  wczytajHistoriePostow();
}

// Wklejony materiał przeżywa przełączenie zakładki i odświeżenie strony.
// Bez tego kilka akapitów przepisanych z raportu przepadało przy jednym
// kliknięciu w menu — a to najbardziej pracochłonna rzecz na tym ekranie.
const KLUCZ_ZRODLA = "forces-dc:material-zrodlowy";

function podepnijPoleZrodla() {
  const pole = document.getElementById("pole-zrodla");
  const licznik = document.getElementById("licznik-zrodla");
  const karta = document.getElementById("karta-zrodla");

  const odswiez = () => {
    const znaki = pole.value.trim().length;
    licznik.textContent = znaki
      ? `${znaki.toLocaleString("pl-PL")} znaków — trafi do asystenta razem z tematem`
      : "0 znaków";
    licznik.classList.toggle("licznik-ostrzegawczy", znaki > 12000);
    if (znaki > 12000) {
      licznik.textContent =
        `${znaki.toLocaleString("pl-PL")} znaków — to więcej, niż asystent weźmie ` +
        "pod uwagę (12 000). Zostaw sam fragment, który ma znaczenie.";
    }
  };

  try {
    const zapamietane = localStorage.getItem(KLUCZ_ZRODLA);
    if (zapamietane) {
      pole.value = zapamietane;
      karta.open = true;
    }
  } catch {
    // Prywatne okno przeglądarki blokuje localStorage — pole po prostu
    // startuje puste, nic się nie psuje.
  }

  odswiez();
  pole.addEventListener("input", () => {
    odswiez();
    try {
      localStorage.setItem(KLUCZ_ZRODLA, pole.value);
    } catch {
      /* jak wyżej */
    }
  });
}

// Lista wcześniej wygenerowanych postów, czytana z dysku. Ekran odbudowuje
// się przy każdym wejściu, więc bez tego wynik znikał po przełączeniu
// zakładki — mimo że plik cały czas leżał w output/.
async function wczytajHistoriePostow() {
  const kontener = document.getElementById("historia-postow");
  if (!kontener) return;

  let dane;
  try {
    const odpowiedz = await fetch("/api/posty");
    if (!odpowiedz.ok) throw new Error(`HTTP ${odpowiedz.status}`);
    dane = await odpowiedz.json();
  } catch {
    kontener.innerHTML = "";
    return;
  }

  if (!dane.posty.length) {
    kontener.innerHTML = "";
    return;
  }

  const wiersze = dane.posty
    .map(
      (wpis) => `
      <li>
        <div>
          <button class="link-posta" data-otworz-post="${escapeHtml(wpis.plik)}">
            ${escapeHtml(wpis.data)} — ${escapeHtml(wpis.temat)}
          </button>
          ${wpis.wybrany !== null && wpis.wybrany !== undefined ? `<span class="odznaka-wybrany">Wariant ${wpis.wybrany + 1} wybrany</span>` : ""}
          ${wpis.braki ? `<span class="znacznik-luk">${wpis.braki} braków</span>` : ""}
          <div class="szczegoly">${escapeHtml(wpis.podglad)}…</div>
        </div>
        <button class="przycisk-drugorzedny maly" data-usun-post="${escapeHtml(wpis.plik)}">usuń</button>
      </li>`
    )
    .join("");

  kontener.innerHTML = `
    <div class="karta">
      <strong>Wcześniej wygenerowane posty</strong>
      <p class="szczegoly">Zapisane na dysku w folderze danych. Kliknij, żeby otworzyć.</p>
      <ul class="lista-materialow">${wiersze}</ul>
    </div>
  `;

  kontener.querySelectorAll("[data-otworz-post]").forEach((przycisk) => {
    przycisk.addEventListener("click", () => otworzZapisanyPost(przycisk.dataset.otworzPost));
  });
  kontener.querySelectorAll("[data-usun-post]").forEach((przycisk) => {
    przycisk.addEventListener("click", async () => {
      if (!confirm("Usunąć ten post? Pliku nie da się przywrócić z aplikacji.")) return;
      await fetch(`/api/posty/${encodeURIComponent(przycisk.dataset.usunPost)}`, { method: "DELETE" });
      wczytajHistoriePostow();
    });
  });
}

async function otworzZapisanyPost(nazwaPliku) {
  const wynik = document.getElementById("wynik-redaktora");
  wynik.innerHTML = `<div class="karta"><p class="placeholder">Wczytuję…</p></div>`;
  try {
    const odpowiedz = await fetch(`/api/posty/${encodeURIComponent(nazwaPliku)}`);
    const dane = await odpowiedz.json();
    if (!odpowiedz.ok) throw new Error(dane.blad || `HTTP ${odpowiedz.status}`);
    wynik.innerHTML = elementWynikuPosta(dane.post, dane.plik);
    podepnijPrzyciskiKopiowania();
    wynik.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (blad) {
    wynik.innerHTML = `<div class="karta"><p class="instrukcja-naprawy">${escapeHtml(blad.message)}</p></div>`;
  }
}

function elementBlokadyNda(fraza) {
  return `
    <div class="karta karta-bledu">
      <h3 style="color:var(--blad)">⚠ To polecenie zawiera nazwę objętą NDA</h3>
      <p>Wykryto: „${escapeHtml(fraza)}"</p>
      <p>Nie wysłaliśmy tego do modelu ani do sieci.</p>
      <p><strong>Popraw polecenie albo usuń nazwę klienta.</strong></p>
    </div>
  `;
}

// Ile znaków LinkedIn pokazuje przed „…zobacz więcej". Wartość podana
// w SPEC-frontend 7 z adnotacją [ZWERYFIKUJ aktualny limit] — LinkedIn jej
// nie publikuje i zmienia ją w czasie, więc traktuj jako orientacyjną.
// Linia w podglądzie ma uświadamiać, że początek posta decyduje o zasięgu,
// a nie udawać, że odwzorowuje LinkedIn co do znaku.
const ZNAKOW_PRZED_OBCIECIEM = 200;

// Model pisze briefy zwykłym markdownem. Pokazywanie ich z surowymi
// gwiazdkami czcionką maszynową wyglądało jak kod, a to tekst do przeczytania
// przez grafika. Zamieniamy tylko pogrubienie — kolejność ma znaczenie:
// najpierw ucieczka HTML, potem znaczniki, żeby treść nie mogła wstrzyknąć
// własnego HTML-a.
// Kolejność ma znaczenie: najpierw uciekamy wszystkie znaki specjalne, dopiero
// potem wstawiamy własne znaczniki. Odwrotnie byłaby dziura na wstrzyknięcie
// HTML-a z treści wygenerowanej przez model albo wklejonej przez operatorkę.
function prostyMarkdown(tekst) {
  const wiersze = escapeHtml(tekst || "").split("\n");
  const wynik = [];
  let wLiscie = false;

  const zamknijListe = () => {
    if (wLiscie) {
      wynik.push("</ul>");
      wLiscie = false;
    }
  };

  for (const wiersz of wiersze) {
    const tresc = wiersz.trim();
    const pogrubione = (fragment) => fragment.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

    if (!tresc) {
      zamknijListe();
      continue;
    }
    const naglowek = tresc.match(/^(#{1,4})\s+(.*)$/);
    if (naglowek) {
      zamknijListe();
      const poziom = Math.min(naglowek[1].length + 2, 5);
      wynik.push(`<h${poziom}>${pogrubione(naglowek[2])}</h${poziom}>`);
      continue;
    }
    const punkt = tresc.match(/^[-*]\s+(.*)$/);
    if (punkt) {
      if (!wLiscie) {
        wynik.push("<ul>");
        wLiscie = true;
      }
      wynik.push(`<li>${pogrubione(punkt[1])}</li>`);
      continue;
    }
    zamknijListe();
    wynik.push(`<p>${pogrubione(tresc)}</p>`);
  }
  zamknijListe();
  return wynik.join("");
}

function podgladZLiniaObciecia(tresc) {
  if (tresc.length <= ZNAKOW_PRZED_OBCIECIEM) {
    return `<p class="podglad-tresc">${escapeHtml(tresc)}</p>`;
  }
  // Tniemy na granicy słowa, żeby podgląd nie urywał się w połowie wyrazu.
  const kandydat = tresc.slice(0, ZNAKOW_PRZED_OBCIECIEM);
  const granica = kandydat.lastIndexOf(" ");
  const punkt = granica > ZNAKOW_PRZED_OBCIECIEM - 40 ? granica : ZNAKOW_PRZED_OBCIECIEM;
  return `
    <p class="podglad-tresc">${escapeHtml(tresc.slice(0, punkt))}<span class="podglad-dalej"> …zobacz więcej</span></p>
    <div class="linia-obciecia">tyle widać przed rozwinięciem</div>
    <p class="podglad-tresc">${escapeHtml(tresc.slice(punkt).trimStart())}</p>
  `;
}

// Poprzednie wersje wariantów, na potrzeby „Cofnij". Trzymane w przeglądarce,
// bo cofnięcie to przywrócenie tekstu, który operatorka przed chwilą widziała —
// nie ma powodu budować pod to historii na dysku.
const poprzednieWersje = {};

function elementWynikuPosta(post, sciezkaPliku, czesciowy = false) {
  const idWyniku = ++licznikWynikowPostow;
  wynikiPostow[idWyniku] = post;
  wynikiPostow[idWyniku].plik = post.plik || sciezkaPliku;

  const kartyWariantow = post.warianty
    .map(
      (wariant, indeks) => `
      <div class="karta karta-wariantu${post.wybrany === indeks ? " karta-wybrana" : ""}">
        <div class="wariant-naglowek">
          <strong>Wariant ${indeks + 1}</strong>
          <span class="szczegoly">
            <span class="wariant-etykieta">${escapeHtml(wariant.etykieta)}</span>
            ${wariant.znaki} znaków
            <span class="odznaka-wybrany"${post.wybrany === indeks ? "" : " hidden"}>Wybrany</span>
          </span>
        </div>
        <div class="podglad-posta">
          <div class="podglad-autor">
            <div class="podglad-awatar">FDC</div>
            <div>
              <div class="podglad-nazwa">Forces DC</div>
              <div class="podglad-podpis">Fit-out data center · Norwegia</div>
            </div>
          </div>
          ${podgladZLiniaObciecia(wariant.tresc)}
        </div>
        <div class="wariant-stopka">
          <button class="przycisk-drugorzedny" data-kopiuj-wariant="${indeks}">Kopiuj</button>
          <button class="przycisk-drugorzedny" data-popraw="${indeks}">Popraw</button>
          <button class="przycisk-drugorzedny" data-edytuj="${indeks}">Popraw ręcznie</button>
          <button class="przycisk-drugorzedny" data-cofnij="${indeks}" hidden>Cofnij</button>
          <button class="przycisk-wybierz" data-wybierz="${indeks}">
            ${post.wybrany === indeks ? "Odznacz wybrany" : "Zapisz jako wybrany"}
          </button>
        </div>
        <div class="pole-poprawki" data-poprawka-dla="${indeks}" hidden></div>
      </div>`
    )
    .join("");

  // Każdy brak da się przenieść wprost na ekran Materiały. Bez tego Magda
  // musiałaby przepisywać go ręcznie, a wtedy po prostu tego nie zrobi —
  // a brak materiałów z firmy to zdiagnozowany rdzeń problemu tego klienta.
  const brakiHtml = post.braki.length
    ? `<ul class="lista-brakow">${post.braki
        .map(
          (brak) => `<li>
            <span>${escapeHtml(brak)}</span>
            <button class="przycisk-drugorzedny maly" data-dopisz-brak="${escapeHtml(brak)}">Dopisz do materiałów</button>
          </li>`
        )
        .join("")}</ul>`
    : "<p>Brak braków.</p>";

  const niekompletnyHtml = post.kompletny
    ? ""
    : `<p class="instrukcja-naprawy">
        Zapisany plik nie ma wszystkich oczekiwanych sekcji — pokazujemy to, co się dało odczytać.
        Sprawdź surowy plik: ${escapeHtml(sciezkaPliku || "")}
      </p>`;

  // Przerwany przebieg nie znika — backend zapisuje to, co model zdążył
  // napisać. Operatorka musi wiedzieć, że patrzy na urwany tekst.
  const czesciowyHtml = czesciowy
    ? `<div class="karta karta-ostrzegawcza">
        <p class="instrukcja-naprawy" style="margin:0">
          Pisanie zostało przerwane, ale to, co powstało, jest już zapisane —
          nic nie przepadło. Poniżej może brakować końcówki albo całych sekcji.
          Kliknij „Popraw” przy wybranym wariancie, żeby dokończyć,
          albo wygeneruj jeszcze raz.
        </p>
      </div>`
    : "";

  return `
    <div data-post-id="${idWyniku}">
      ${czesciowyHtml}
      <h3>Warianty</h3>
      ${kartyWariantow}
      <details class="karta">
        <summary><strong>Wersja na Facebooka</strong> <span class="szczegoly">(${post.facebook.length} znaków)</span></summary>
        <p class="podglad-tresc" style="margin:0.5rem 0">${escapeHtml(post.facebook)}</p>
        <button class="przycisk-drugorzedny" data-kopiuj-facebook>Kopiuj</button>
      </details>
      <div class="karta">
        <strong>Brief graficzny</strong>
        <p class="podglad-tresc" style="margin:0.5rem 0">${prostyMarkdown(post.brief_graficzny)}</p>
        <button class="przycisk-drugorzedny" data-kopiuj-brief>Kopiuj dla Sikory</button>
      </div>
      <div class="karta">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:1rem">
          <strong>Grafika do posta</strong>
          <button class="przycisk-glowny" data-zrob-grafike="${idWyniku}">Zrób grafikę</button>
        </div>
        <p class="szczegoly">
          Powstaje z Waszej identyfikacji wizualnej. Hasło dobiera asystent —
          możesz je poprawić przed pobraniem.
        </p>
        <div class="obszar-grafiki" data-grafika-dla="${idWyniku}" hidden></div>
      </div>
      <div class="karta karta-ostrzegawcza">
        <h3 style="color:var(--ostrzezenie)">Braki</h3>
        ${brakiHtml}
      </div>
      ${niekompletnyHtml}
    </div>
  `;
}

async function kopiujDoSchowka(tekst, przycisk) {
  const oryginalnyTekst = przycisk.textContent;
  try {
    await navigator.clipboard.writeText(tekst);
    przycisk.textContent = "Skopiowano";
  } catch {
    przycisk.textContent = "Nie udało się skopiować";
  }
  setTimeout(() => {
    przycisk.textContent = oryginalnyTekst;
  }, 1500);
}

// `zakres`: element, w którym szukamy nowych przycisków — wywoływane też
// wielokrotnie w historii czatu, więc `dataset.podpieto` chroni przed
// podwójnym podpięciem tego samego przycisku (podwójne kopiowanie po kliku).
function podepnijPrzyciskiKopiowania(zakres = document) {
  const wynikDlaPrzycisku = (przycisk) => {
    const kontener = przycisk.closest("[data-post-id]");
    return wynikiPostow[kontener?.dataset.postId];
  };

  zakres.querySelectorAll("[data-kopiuj-wariant]").forEach((przycisk) => {
    if (przycisk.dataset.podpieto) return;
    przycisk.dataset.podpieto = "1";
    przycisk.addEventListener("click", () => {
      const indeks = Number(przycisk.dataset.kopiujWariant);
      kopiujDoSchowka(wynikDlaPrzycisku(przycisk).warianty[indeks].tresc, przycisk);
    });
  });
  zakres.querySelectorAll("[data-kopiuj-facebook]").forEach((przycisk) => {
    if (przycisk.dataset.podpieto) return;
    przycisk.dataset.podpieto = "1";
    przycisk.addEventListener("click", () => kopiujDoSchowka(wynikDlaPrzycisku(przycisk).facebook, przycisk));
  });
  zakres.querySelectorAll("[data-kopiuj-brief]").forEach((przycisk) => {
    if (przycisk.dataset.podpieto) return;
    przycisk.dataset.podpieto = "1";
    przycisk.addEventListener("click", () =>
      kopiujDoSchowka(wynikDlaPrzycisku(przycisk).brief_graficzny, przycisk)
    );
  });

  zakres.querySelectorAll("[data-zrob-grafike]").forEach((przycisk) => {
    if (przycisk.dataset.podpieto) return;
    przycisk.dataset.podpieto = "1";
    przycisk.addEventListener("click", () => zrobGrafike(przycisk));
  });

  zakres.querySelectorAll("[data-popraw]").forEach((przycisk) => {
    if (przycisk.dataset.podpieto) return;
    przycisk.dataset.podpieto = "1";
    przycisk.addEventListener("click", () => otworzPolePoprawki(przycisk));
  });

  zakres.querySelectorAll("[data-cofnij]").forEach((przycisk) => {
    if (przycisk.dataset.podpieto) return;
    przycisk.dataset.podpieto = "1";
    przycisk.addEventListener("click", () => cofnijPoprawke(przycisk));
  });

  zakres.querySelectorAll("[data-edytuj]").forEach((przycisk) => {
    if (przycisk.dataset.podpieto) return;
    przycisk.dataset.podpieto = "1";
    przycisk.addEventListener("click", () => przelaczTrybEdycji(przycisk));
  });

  zakres.querySelectorAll("[data-dopisz-brak]").forEach((przycisk) => {
    if (przycisk.dataset.podpieto) return;
    przycisk.dataset.podpieto = "1";
    przycisk.addEventListener("click", () => przeniesBrakDoMaterialow(przycisk.dataset.dopiszBrak));
  });

  zakres.querySelectorAll("[data-wybierz]").forEach((przycisk) => {
    if (przycisk.dataset.podpieto) return;
    przycisk.dataset.podpieto = "1";
    przycisk.addEventListener("click", () =>
      zapiszWybranyWariant(przycisk, wynikDlaPrzycisku(przycisk))
    );
  });
}

// Przeniesienie braku na ekran Materiały (SPEC-frontend 7). Nie zapisujemy
// go od razu do żadnej sekcji — asystent nie wie, do której pasuje, a zły
// wpis w materiałach jest gorszy niż jego brak. Przenosimy tekst do pola
// i zostawiamy operatorce wybór sekcji.
let brakDoPrzeniesienia = "";

function przeniesBrakDoMaterialow(brak) {
  brakDoPrzeniesienia = brak;
  przejdzDoZakladki("materialy");
}

function wstawPrzeniesionyBrak(sekcje) {
  const kontener = document.getElementById("przeniesiony-brak");
  if (!kontener) return;
  if (!brakDoPrzeniesienia) {
    kontener.innerHTML = "";
    return;
  }

  const tekst = brakDoPrzeniesienia;
  brakDoPrzeniesienia = "";
  const opcje = sekcje
    .map((sekcja, indeks) => `<option value="${indeks}">${escapeHtml(sekcja)}</option>`)
    .join("");

  kontener.innerHTML = `
    <div class="karta karta-propozycja">
      <strong>Brak przeniesiony z posta</strong>
      <p class="szczegoly">
        Asystent zgłosił, że tego mu zabrakło. Przepisz to na zdanie o tym, co
        realnie się wydarzyło, i wskaż sekcję — wtedy następny post nie będzie
        już miał tej dziury.
      </p>
      <label class="szczegoly" style="display:block;margin-top:0.5rem">
        Sekcja: <select id="sekcja-braku">${opcje}</select>
      </label>
      <textarea id="tresc-braku" rows="3" style="width:100%;margin-top:0.5rem">${escapeHtml(tekst)}</textarea>
      <div class="pasek-narzedzi" style="margin-top:0.5rem">
        <button class="przycisk-glowny" id="zapisz-brak">Dodaj do materiałów</button>
        <button class="przycisk-drugorzedny" id="odrzuc-brak">Nie teraz</button>
      </div>
    </div>
  `;
  kontener.scrollIntoView({ behavior: "smooth", block: "nearest" });

  document.getElementById("odrzuc-brak").addEventListener("click", () => {
    kontener.innerHTML = "";
  });
  document.getElementById("zapisz-brak").addEventListener("click", () => {
    const nowaTresc = document.getElementById("tresc-braku").value.trim();
    if (!nowaTresc) return;
    const sekcja = sekcje[Number(document.getElementById("sekcja-braku").value)];
    stanMaterialow[sekcja] = [...(stanMaterialow[sekcja] || []), nowaTresc];
    zapiszMaterialy();
  });
}

// Wybór jednego wariantu do publikacji (SPEC-frontend 7). Zapisujemy go
// w pliku posta, żeby przetrwał odświeżenie strony i restart aplikacji.
async function zapiszWybranyWariant(przycisk, wynik) {
  const indeks = Number(przycisk.dataset.wybierz);
  // Drugi klik w ten sam wariant odznacza wybór — inaczej pomyłki nie da się
  // cofnąć bez wchodzenia w plik.
  const nowyWybor = wynik.wybrany === indeks ? null : indeks;
  const kontener = przycisk.closest("[data-post-id]");
  const oryginalnyTekst = przycisk.textContent.trim();

  przycisk.disabled = true;
  let odpowiedz;
  try {
    odpowiedz = await fetch("/api/posty/wybrany", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plik: wynik.plik, indeks: nowyWybor }),
    });
  } catch (blad) {
    przycisk.disabled = false;
    przycisk.textContent = "Nie udało się połączyć z serwerem";
    setTimeout(() => (przycisk.textContent = oryginalnyTekst), 2500);
    return;
  }

  const dane = await odpowiedz.json();
  przycisk.disabled = false;
  if (!odpowiedz.ok) {
    przycisk.textContent = dane.blad || "Nie udało się zapisać wyboru";
    setTimeout(() => (przycisk.textContent = oryginalnyTekst), 2500);
    return;
  }

  wynik.wybrany = nowyWybor;
  odswiezOznaczenieWybranego(kontener, nowyWybor);
  wczytajHistoriePostow();
}

function odswiezOznaczenieWybranego(kontener, wybrany) {
  if (!kontener) return;
  kontener.querySelectorAll("[data-wybierz]").forEach((przycisk) => {
    const indeks = Number(przycisk.dataset.wybierz);
    const karta = kartaWariantuDla(przycisk);
    const jestWybrany = indeks === wybrany;
    karta.classList.toggle("karta-wybrana", jestWybrany);
    przycisk.textContent = jestWybrany ? "Odznacz wybrany" : "Zapisz jako wybrany";
    const odznaka = karta.querySelector(".odznaka-wybrany");
    if (odznaka) odznaka.hidden = !jestWybrany;
  });
}

function kartaWariantuDla(przycisk) {
  return przycisk.closest(".karta-wariantu");
}

// --- Grafika do posta ---

const daneGrafiki = {};

async function zrobGrafike(przycisk) {
  const id = przycisk.dataset.zrobGrafike;
  const wynik = wynikiPostow[id];
  const obszar = document.querySelector(`[data-grafika-dla="${id}"]`);
  obszar.hidden = false;
  obszar.innerHTML = `<div class="log-przebiegu"><div class="wpis">Dobieram hasło…</div></div>`;
  przycisk.disabled = true;

  let odpowiedz;
  try {
    odpowiedz = await fetch("/api/grafika", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // Grafika powstaje na podstawie wariantu wskazanego do publikacji;
      // dopóki operatorka nie wybrała, bierzemy pierwszy.
      body: JSON.stringify({ plik: wynik.plik, indeks: wynik.wybrany ?? 0 }),
    });
  } catch (blad) {
    obszar.innerHTML = `<p class="instrukcja-naprawy">Nie udało się połączyć z serwerem (${escapeHtml(blad.message)}).</p>`;
    przycisk.disabled = false;
    return;
  }

  if ((odpowiedz.headers.get("content-type") || "").includes("application/json")) {
    const dane = await odpowiedz.json();
    obszar.innerHTML = `<p class="instrukcja-naprawy">${escapeHtml(dane.blad || "Nie udało się przygotować grafiki.")}</p>`;
    przycisk.disabled = false;
    return;
  }

  await strumieniujSSE(odpowiedz, (zdarzenie) => {
    if (zdarzenie.typ === "status") {
      obszar.innerHTML = `<div class="log-przebiegu"><div class="wpis">${escapeHtml(zdarzenie.tekst)}</div></div>`;
    } else if (zdarzenie.typ === "blad") {
      obszar.innerHTML = `<p class="instrukcja-naprawy">${escapeHtml(zdarzenie.tekst)}</p>`;
      przycisk.disabled = false;
    } else if (zdarzenie.typ === "wynik") {
      dopiszKoszt(zdarzenie.koszt_usd);
      przycisk.disabled = false;
      przycisk.textContent = "Zrób od nowa";
      if (zdarzenie.blad_grafiki) {
        obszar.innerHTML = `<p class="instrukcja-naprawy">${escapeHtml(zdarzenie.blad_grafiki)}</p>`;
      } else if (zdarzenie.grafika) {
        daneGrafiki[id] = zdarzenie.grafika;
        pokazGrafike(id);
      }
    }
  });
}

function pokazGrafike(id) {
  const dane = daneGrafiki[id];
  const obszar = document.querySelector(`[data-grafika-dla="${id}"]`);
  const ciemny = dane.wariant_kolorystyczny === "ciemny";

  const ostrzezenia = (dane.ostrzezenia || []).length
    ? `<div class="ostrzezenie-koszt">${dane.ostrzezenia.map(escapeHtml).join("<br>")}</div>`
    : "";

  obszar.innerHTML = `
    ${ostrzezenia}
    <div class="uklad-grafiki">
      <canvas class="podglad-grafiki" data-canvas="${id}"></canvas>
      <div class="ustawienia-grafiki">
        <label>Hasło na grafice
          <textarea class="pole-hasla" rows="3">${escapeHtml(dane.haslo)}</textarea>
        </label>
        <label>Podtytuł (opcjonalny)
          <textarea class="pole-podtytulu" rows="2">${escapeHtml(dane.podtytul || "")}</textarea>
        </label>
        <label>Wersja kolorystyczna
          <select class="wybor-wariantu">
            <option value="ciemny"${ciemny ? " selected" : ""}>ciemna</option>
            <option value="jasny"${ciemny ? "" : " selected"}>jasna</option>
          </select>
        </label>
        <div class="przyciski-grafiki">
          <button class="przycisk-drugorzedny" data-odswiez-grafike="${id}">Odśwież podgląd</button>
          <button class="przycisk-glowny" data-pobierz-grafike="${id}">Pobierz PNG</button>
        </div>
        ${dane.alt ? `<p class="szczegoly"><strong>Tekst alternatywny:</strong> ${escapeHtml(dane.alt)}</p>` : ""}
      </div>
    </div>
  `;

  const canvas = obszar.querySelector(`[data-canvas="${id}"]`);
  narysujGrafike(canvas, dane);

  obszar.querySelector(`[data-odswiez-grafike="${id}"]`).addEventListener("click", () => odswiezGrafike(id));
  obszar.querySelector(`[data-pobierz-grafike="${id}"]`).addEventListener("click", () => {
    const nazwa = (wynikiPostow[id].plik || "grafika").replace(/\.md$/, "") + ".png";
    pobierzGrafike(canvas, nazwa);
  });
}

async function odswiezGrafike(id) {
  const obszar = document.querySelector(`[data-grafika-dla="${id}"]`);
  const haslo = obszar.querySelector(".pole-hasla").value;
  const podtytul = obszar.querySelector(".pole-podtytulu").value;
  const wariant = obszar.querySelector(".wybor-wariantu").value;

  const odpowiedz = await fetch("/api/grafika/podglad", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ haslo, podtytul, wariant_kolorystyczny: wariant }),
  });
  const dane = await odpowiedz.json();
  if (!odpowiedz.ok) {
    alert(dane.blad || "Nie udało się odświeżyć podglądu.");
    return;
  }
  // Tekst alternatywny pochodzi od asystenta i nie zmienia się przy ręcznej
  // korekcie hasła — przenosimy go do nowych danych.
  dane.grafika.alt = daneGrafiki[id].alt;
  daneGrafiki[id] = dane.grafika;
  pokazGrafike(id);
}

function otworzPolePoprawki(przycisk) {
  const indeks = przycisk.dataset.popraw;
  const karta = kartaWariantuDla(przycisk);
  const pole = karta.querySelector(`[data-poprawka-dla="${indeks}"]`);

  if (!pole.hidden) {
    pole.hidden = true;
    return;
  }

  pole.hidden = false;
  pole.innerHTML = `
    <div class="poprawka-wiersz">
      <input type="text" class="pole-polecenia" placeholder="Napisz, co zmienić — np. „skróć o połowę” albo „mniej formalnie”">
      <button class="przycisk-glowny przycisk-wyslij-poprawke">Popraw</button>
    </div>
    <div class="status-poprawki szczegoly"></div>
  `;

  const wejscie = pole.querySelector(".pole-polecenia");
  const wyslij = () => wyslijPoprawke(przycisk, wejscie.value);
  pole.querySelector(".przycisk-wyslij-poprawke").addEventListener("click", wyslij);
  wejscie.addEventListener("keydown", (zdarzenie) => {
    if (zdarzenie.key === "Enter") {
      zdarzenie.preventDefault();
      wyslij();
    }
  });
  wejscie.focus();
}

async function wyslijPoprawke(przycisk, polecenie) {
  const indeks = Number(przycisk.dataset.popraw);
  const karta = kartaWariantuDla(przycisk);
  const kontener = karta.closest("[data-post-id]");
  const wynik = wynikiPostow[kontener.dataset.postId];
  const pole = karta.querySelector(`[data-poprawka-dla="${indeks}"]`);
  const status = pole.querySelector(".status-poprawki");
  const przyciskWyslij = pole.querySelector(".przycisk-wyslij-poprawke");

  if (!polecenie.trim()) {
    status.innerHTML = `<span class="instrukcja-naprawy">Napisz, co zmienić.</span>`;
    return;
  }

  przyciskWyslij.disabled = true;
  status.textContent = "Poprawiam…";

  let odpowiedz;
  try {
    odpowiedz = await fetch("/api/popraw", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plik: wynik.plik, indeks, polecenie }),
    });
  } catch (blad) {
    status.innerHTML = `<span class="instrukcja-naprawy">Nie udało się połączyć z serwerem (${escapeHtml(blad.message)}).</span>`;
    przyciskWyslij.disabled = false;
    return;
  }

  if ((odpowiedz.headers.get("content-type") || "").includes("application/json")) {
    const dane = await odpowiedz.json();
    status.innerHTML = dane.zablokowane_nda
      ? `<span class="instrukcja-naprawy">Polecenie zawiera nazwę objętą NDA: „${escapeHtml(dane.fraza)}". Popraw je.</span>`
      : `<span class="instrukcja-naprawy">${escapeHtml(dane.blad || "Nie udało się poprawić.")}</span>`;
    przyciskWyslij.disabled = false;
    return;
  }

  await strumieniujSSE(odpowiedz, (zdarzenie) => {
    if (zdarzenie.typ === "status") {
      status.textContent = zdarzenie.tekst;
    } else if (zdarzenie.typ === "blad") {
      status.innerHTML = `<span class="instrukcja-naprawy">${escapeHtml(zdarzenie.tekst)}</span>`;
      przyciskWyslij.disabled = false;
    } else if (zdarzenie.typ === "wynik") {
      dopiszKoszt(zdarzenie.koszt_usd);
      if (zdarzenie.blad_poprawki) {
        status.innerHTML = `<span class="instrukcja-naprawy">${escapeHtml(zdarzenie.blad_poprawki)}</span>`;
        przyciskWyslij.disabled = false;
        return;
      }
      if (zdarzenie.nowa_tresc) {
        poprzednieWersje[`${kontener.dataset.postId}:${indeks}`] = wynik.warianty[indeks].tresc;
        wynik.warianty[indeks].tresc = zdarzenie.nowa_tresc;
        wynik.warianty[indeks].znaki = zdarzenie.znaki;
        odswiezWariant(karta, zdarzenie.nowa_tresc, zdarzenie.znaki);
        karta.querySelector(`[data-cofnij="${indeks}"]`).hidden = false;
        pole.hidden = true;
      }
    }
  });
}

function odswiezWariant(karta, tresc, znaki) {
  // Celujemy w kontener, nie w `.podglad-tresc` — w trybie ręcznej edycji
  // podglądu nie ma, jest pole tekstowe.
  karta.querySelector(".podglad-posta").innerHTML = `
    <div class="podglad-autor">
      <div class="podglad-awatar">FDC</div>
      <div>
        <div class="podglad-nazwa">Forces DC</div>
        <div class="podglad-podpis">Fit-out data center · Norwegia</div>
      </div>
    </div>
    ${podgladZLiniaObciecia(tresc)}
  `;
  // Odbudowując nagłówek, przenosimy też odznakę wyboru — bez tego poprawka
  // wariantu kasowała informację, że to on idzie do publikacji.
  const licznikZnakow = karta.querySelector(".wariant-naglowek .szczegoly");
  const etykieta = licznikZnakow.querySelector(".wariant-etykieta").outerHTML;
  const odznaka = licznikZnakow.querySelector(".odznaka-wybrany")?.outerHTML || "";
  licznikZnakow.innerHTML = `${etykieta} ${znaki} znaków ${odznaka}`;
}

async function cofnijPoprawke(przycisk) {
  const indeks = Number(przycisk.dataset.cofnij);
  const karta = kartaWariantuDla(przycisk);
  const kontener = karta.closest("[data-post-id]");
  const wynik = wynikiPostow[kontener.dataset.postId];
  const klucz = `${kontener.dataset.postId}:${indeks}`;
  const poprzednia = poprzednieWersje[klucz];
  if (!poprzednia) return;

  przycisk.disabled = true;
  const odpowiedz = await fetch("/api/popraw/cofnij", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plik: wynik.plik, indeks, tresc: poprzednia }),
  });
  przycisk.disabled = false;
  if (!odpowiedz.ok) {
    const dane = await odpowiedz.json();
    alert(dane.blad || "Nie udało się przywrócić poprzedniej wersji.");
    return;
  }

  wynik.warianty[indeks].tresc = poprzednia;
  wynik.warianty[indeks].znaki = poprzednia.length;
  odswiezWariant(karta, poprzednia, poprzednia.length);
  delete poprzednieWersje[klucz];
  przycisk.hidden = true;
}

// Ręczna edycja wariantu (SPEC-frontend 7: „z możliwością przejścia w tryb
// edycji tekstu dla drobnych korekt"). Literówki nie warto poprawiać przez
// model — ani czekać na odpowiedź, ani za nią płacić.
function przelaczTrybEdycji(przycisk) {
  const indeks = Number(przycisk.dataset.edytuj);
  const karta = kartaWariantuDla(przycisk);
  const kontener = karta.closest("[data-post-id]");
  const wynik = wynikiPostow[kontener.dataset.postId];
  const podglad = karta.querySelector(".podglad-posta");

  if (karta.dataset.wEdycji) {
    odswiezWariant(karta, wynik.warianty[indeks].tresc, wynik.warianty[indeks].znaki);
    delete karta.dataset.wEdycji;
    przycisk.textContent = "Popraw ręcznie";
    return;
  }

  karta.dataset.wEdycji = "1";
  przycisk.textContent = "Anuluj edycję";
  podglad.innerHTML = `
    <textarea class="pole-edycji-wariantu" rows="12" style="width:100%">${escapeHtml(wynik.warianty[indeks].tresc)}</textarea>
    <div class="pasek-narzedzi" style="margin-top:0.5rem">
      <button class="przycisk-glowny przycisk-zapisz-edycje">Zapisz zmiany</button>
      <span class="szczegoly status-edycji"></span>
    </div>
  `;

  const pole = podglad.querySelector(".pole-edycji-wariantu");
  const status = podglad.querySelector(".status-edycji");
  const odswiezLicznik = () => (status.textContent = `${pole.value.trim().length} znaków`);
  odswiezLicznik();
  pole.addEventListener("input", odswiezLicznik);
  pole.focus();

  podglad.querySelector(".przycisk-zapisz-edycje").addEventListener("click", async (zdarzenie) => {
    const nowa = pole.value.trim();
    if (!nowa) {
      status.innerHTML = `<span class="instrukcja-naprawy">Treść nie może być pusta.</span>`;
      return;
    }
    zdarzenie.target.disabled = true;
    status.textContent = "Zapisuję…";

    let odpowiedz;
    try {
      odpowiedz = await fetch("/api/posty/wariant", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plik: wynik.plik, indeks, tresc: nowa }),
      });
    } catch (blad) {
      // Wąskie `try` tylko wokół sieci: obejmując też odświeżenie karty,
      // zamieniało błąd w kodzie na mylący komunikat „brak połączenia".
      status.innerHTML = `<span class="instrukcja-naprawy">Nie udało się połączyć z serwerem (${escapeHtml(blad.message)}).</span>`;
      zdarzenie.target.disabled = false;
      return;
    }

    const dane = await odpowiedz.json();
    if (!odpowiedz.ok) {
      status.innerHTML = `<span class="instrukcja-naprawy">${escapeHtml(dane.blad || "Nie udało się zapisać.")}</span>`;
      zdarzenie.target.disabled = false;
      return;
    }
    wynik.warianty[indeks].tresc = nowa;
    wynik.warianty[indeks].znaki = dane.znaki;
    odswiezWariant(karta, nowa, dane.znaki);
    delete karta.dataset.wEdycji;
    przycisk.textContent = "Popraw ręcznie";
  });
}

async function strumieniujSSE(odpowiedz, obslugaZdarzenia) {
  const czytnik = odpowiedz.body.getReader();
  const dekoder = new TextDecoder();
  let bufor = "";
  for (;;) {
    const { value, done } = await czytnik.read();
    if (done) break;
    bufor += dekoder.decode(value, { stream: true });
    let indeksKonca;
    while ((indeksKonca = bufor.indexOf("\n\n")) !== -1) {
      const blok = bufor.slice(0, indeksKonca);
      bufor = bufor.slice(indeksKonca + 2);
      const liniaDanych = blok.split("\n").find((linia) => linia.startsWith("data: "));
      if (liniaDanych) {
        obslugaZdarzenia(JSON.parse(liniaDanych.slice("data: ".length)));
      }
    }
  }
}

async function uruchomRedaktora() {
  const brief = document.getElementById("pole-briefu").value.trim();
  const materialZrodlowy = document.getElementById("pole-zrodla")?.value.trim() || "";
  const przycisk = document.getElementById("przycisk-generuj");
  const log = document.getElementById("log-redaktora");
  const wynik = document.getElementById("wynik-redaktora");
  wynik.innerHTML = "";
  log.hidden = true;
  log.innerHTML = "";

  if (!brief) {
    wynik.innerHTML = `<div class="karta"><p class="instrukcja-naprawy">Opisz, o czym ma być post, zanim klikniesz „Generuj".</p></div>`;
    return;
  }

  przycisk.disabled = true;
  przycisk.textContent = "Generuję…";

  // Log pojawia się dopiero, gdy faktycznie zaczynamy strumieniować odpowiedź —
  // blokada NDA i błędy walidacji kończą się przed wywołaniem SDK i nie
  // powinny zostawiać pustego paska logu nad kartą komunikatu.
  const dopiszWpis = (tekst, klasa = "") => {
    log.hidden = false;
    const wpis = document.createElement("div");
    wpis.className = `wpis ${klasa}`;
    wpis.textContent = tekst;
    log.appendChild(wpis);
    log.scrollTop = log.scrollHeight;
  };
  const zakoncz = () => {
    przycisk.disabled = false;
    przycisk.textContent = "Generuj";
  };

  let odpowiedz;
  try {
    odpowiedz = await fetch("/api/redaktor", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ brief, material_zrodlowy: materialZrodlowy }),
    });
  } catch (blad) {
    wynik.innerHTML = `<div class="karta"><p class="instrukcja-naprawy">Nie udało się połączyć z serwerem (${escapeHtml(blad.message)}).</p></div>`;
    zakoncz();
    return;
  }

  const typTresci = odpowiedz.headers.get("content-type") || "";

  if (typTresci.includes("application/json")) {
    const dane = await odpowiedz.json();
    if (dane.zablokowane_nda) {
      wynik.innerHTML = elementBlokadyNda(dane.fraza);
    } else {
      wynik.innerHTML = `<div class="karta"><p class="instrukcja-naprawy">${escapeHtml(dane.blad || "Nie udało się uruchomić generowania.")}</p></div>`;
    }
    zakoncz();
    return;
  }

  log.hidden = false;
  await strumieniujSSE(odpowiedz, (dane) => {
    if (dane.typ === "status" || dane.typ === "fragment") {
      dopiszWpis(dane.tekst);
    } else if (dane.typ === "wynik") {
      dopiszKoszt(dane.koszt_usd);
      if (dane.bledny) {
        dopiszWpis("Generowanie zakończyło się błędem.", "blad");
      } else if (dane.post) {
        wynik.innerHTML = elementWynikuPosta(dane.post, dane.sciezka_pliku, dane.czesciowy);
        podepnijPrzyciskiKopiowania();
        wczytajHistoriePostow();
      } else {
        dopiszWpis(
          dane.blad_zapisu || "Asystent nie zwrócił żadnego tekstu — spróbuj jeszcze raz.",
          "blad"
        );
      }
      zakoncz();
    } else if (dane.typ === "blad") {
      dopiszWpis(dane.tekst, "blad");
      zakoncz();
    }
  });
}

// --- Ekran "Asystent" (czat, SPEC-frontend 5) ---

const propozycje = {};
let licznikPropozycji = 0;

// Asystent jest ekranem startowym, więc pusty prostokąt to pierwsze, co widzi
// operatorka. Zamiast niego dajemy gotowe zdania do kliknięcia — pokazują,
// co aplikacja w ogóle potrafi, bez czytania instrukcji.
const PRZYKLADY_CZATU = [
  "Jaki jest plan na ten miesiąc?",
  "Napisz post o przygotowaniu zespołu przed startem fit-outu",
  "Czego brakuje w materiałach na ten miesiąc?",
  "Pokaż posty, które już wygenerowaliśmy",
];

function elementPustegoCzatu() {
  const przyciski = PRZYKLADY_CZATU.map(
    (tekst) =>
      `<button class="przycisk-drugorzedny" data-przyklad-czatu="${escapeHtml(tekst)}">${escapeHtml(tekst)}</button>`
  ).join("");
  return `
    <div class="pusty-czat">
      <p class="placeholder">Napisz, czego potrzebujesz — normalnym zdaniem, tak jak do człowieka.</p>
      <div class="przyklady-czatu">${przyciski}</div>
    </div>`;
}

function podepnijPrzykladyCzatu() {
  document.querySelectorAll("[data-przyklad-czatu]").forEach((przycisk) => {
    przycisk.addEventListener("click", () => {
      const pole = document.getElementById("czat-pole");
      pole.value = przycisk.dataset.przykladCzatu;
      pole.focus();
      wyslijWiadomoscAsystenta();
    });
  });
}

function renderujAsystenta() {
  OBSZAR.innerHTML = `
    <h2>Asystent</h2>
    <div class="karta" id="czat-historia" style="min-height:320px;max-height:60vh;overflow-y:auto">
      ${elementPustegoCzatu()}
    </div>
    <form id="czat-formularz" style="display:flex;gap:0.5rem;margin-top:0.75rem">
      <textarea
        id="czat-pole"
        rows="2"
        style="flex:1"
        placeholder="Napisz, czego potrzebujesz — Enter wysyła, Shift+Enter robi nową linię"
      ></textarea>
      <button class="przycisk-glowny" type="submit">Wyślij</button>
    </form>
  `;
  podepnijPrzykladyCzatu();
  document.getElementById("czat-formularz").addEventListener("submit", (zdarzenie) => {
    zdarzenie.preventDefault();
    wyslijWiadomoscAsystenta();
  });

  // Enter wysyła, Shift+Enter robi nową linię — jak w każdym komunikatorze.
  // Bez tego trzeba było sięgać myszą po przycisk przy każdej wiadomości.
  const pole = document.getElementById("czat-pole");
  pole.addEventListener("keydown", (zdarzenie) => {
    if (zdarzenie.key === "Enter" && !zdarzenie.shiftKey && !zdarzenie.isComposing) {
      zdarzenie.preventDefault();
      wyslijWiadomoscAsystenta();
    }
  });
  pole.focus();
}

function dodajWiadomoscUzytkownikaDoCzatu(historia, tekst) {
  const div = document.createElement("div");
  div.className = "wiadomosc-czatu uzytkownik";
  div.textContent = tekst;
  historia.appendChild(div);
  historia.scrollTop = historia.scrollHeight;
}

function utworzTureAsystentaWCzacie(historia) {
  const kontener = document.createElement("div");
  kontener.className = "wiadomosc-czatu asystent";

  const kroki = document.createElement("details");
  kroki.className = "kroki-agenta";
  kroki.hidden = true;
  const podsumowanie = document.createElement("summary");
  podsumowanie.textContent = "Kroki agenta";
  const listaKrokow = document.createElement("ul");
  kroki.appendChild(podsumowanie);
  kroki.appendChild(listaKrokow);

  const tresc = document.createElement("div");
  tresc.className = "czat-tresc";

  kontener.appendChild(kroki);
  kontener.appendChild(tresc);
  historia.appendChild(kontener);
  historia.scrollTop = historia.scrollHeight;

  return { historia, kontener, kroki, listaKrokow, tresc, liczbaKrokow: 0 };
}

function elementPropozycji(dane, id) {
  const tokeny = Number(dane.szacowane_tokeny);
  const tokenyTekst = Number.isFinite(tokeny) ? `~${tokeny.toLocaleString("pl-PL")}` : "nieznane";
  return `
    <div class="karta karta-propozycja" data-propozycja-id="${id}" style="margin-top:0.5rem">
      <p style="margin-top:0"><strong>Napiszę post:</strong> ${escapeHtml(dane.brief || "")}</p>
      <p class="szczegoly">Użyję: ${escapeHtml(dane.zasoby || "zasad stylu, korpusu")}</p>
      <p class="szczegoly">Szacowane zużycie: ${tokenyTekst} tokenów (orientacyjnie)</p>
      <div style="margin-top:0.5rem;display:flex;gap:0.5rem">
        <button class="przycisk-glowny" data-uruchom-propozycje="${id}">Uruchom</button>
        <button class="przycisk-drugorzedny" data-anuluj-propozycje="${id}">Anuluj</button>
      </div>
    </div>
  `;
}

function podepnijPrzyciskiPropozycji(zakres = document) {
  zakres.querySelectorAll("[data-uruchom-propozycje]").forEach((przycisk) => {
    if (przycisk.dataset.podpieto) return;
    przycisk.dataset.podpieto = "1";
    przycisk.addEventListener("click", () => uruchomPropozycje(przycisk));
  });
  zakres.querySelectorAll("[data-anuluj-propozycje]").forEach((przycisk) => {
    if (przycisk.dataset.podpieto) return;
    przycisk.dataset.podpieto = "1";
    przycisk.addEventListener("click", () => {
      przycisk.closest(".karta-propozycja").innerHTML = `<p class="szczegoly" style="margin:0">Anulowano.</p>`;
    });
  });
}

async function uruchomPropozycje(przycisk) {
  const karta = przycisk.closest(".karta-propozycja");
  const dane = propozycje[przycisk.dataset.uruchomPropozycje];
  karta.innerHTML = `<p class="szczegoly" style="margin-top:0">Generuję…</p><div class="log-przebiegu" style="display:block"></div>`;
  const log = karta.querySelector(".log-przebiegu");

  const dopiszWpis = (tekst, klasa = "") => {
    const wpis = document.createElement("div");
    wpis.className = `wpis ${klasa}`;
    wpis.textContent = tekst;
    log.appendChild(wpis);
    log.scrollTop = log.scrollHeight;
  };

  let odpowiedz;
  try {
    odpowiedz = await fetch("/api/redaktor", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ brief: dane.brief || "" }),
    });
  } catch (blad) {
    dopiszWpis(`Nie udało się połączyć z serwerem (${blad.message}).`, "blad");
    return;
  }

  const typTresci = odpowiedz.headers.get("content-type") || "";
  if (typTresci.includes("application/json")) {
    const wynik = await odpowiedz.json();
    karta.innerHTML = wynik.zablokowane_nda
      ? elementBlokadyNda(wynik.fraza)
      : `<p class="instrukcja-naprawy" style="margin:0">${escapeHtml(wynik.blad || "Nie udało się uruchomić generowania.")}</p>`;
    return;
  }

  await strumieniujSSE(odpowiedz, (zdarzenie) => {
    if (zdarzenie.typ === "status" || zdarzenie.typ === "fragment") {
      dopiszWpis(zdarzenie.tekst);
    } else if (zdarzenie.typ === "wynik") {
      dopiszKoszt(zdarzenie.koszt_usd);
      if (zdarzenie.bledny) {
        dopiszWpis("Generowanie zakończyło się błędem.", "blad");
      } else if (zdarzenie.post) {
        karta.outerHTML = elementWynikuPosta(
          zdarzenie.post,
          zdarzenie.sciezka_pliku,
          zdarzenie.czesciowy
        );
        podepnijPrzyciskiKopiowania();
      } else {
        dopiszWpis(
          zdarzenie.blad_zapisu || "Asystent nie zwrócił żadnego tekstu — spróbuj jeszcze raz.",
          "blad"
        );
      }
    } else if (zdarzenie.typ === "blad") {
      dopiszWpis(zdarzenie.tekst, "blad");
    }
  });
}

function obslugaZdarzeniaCzatu(dane, tura) {
  if (dane.typ === "status") {
    tura.kroki.hidden = false;
    tura.liczbaKrokow += 1;
    tura.kroki.querySelector("summary").textContent = `Kroki agenta (${tura.liczbaKrokow})`;
    const wpis = document.createElement("li");
    wpis.textContent = dane.tekst;
    tura.listaKrokow.appendChild(wpis);
  } else if (dane.typ === "fragment") {
    tura.tresc.textContent += dane.tekst;
  } else if (dane.typ === "propozycja") {
    licznikPropozycji += 1;
    propozycje[licznikPropozycji] = dane.dane || {};
    const nosnik = document.createElement("div");
    nosnik.innerHTML = elementPropozycji(dane.dane || {}, licznikPropozycji);
    tura.kontener.appendChild(nosnik.firstElementChild);
    podepnijPrzyciskiPropozycji(tura.kontener);
  } else if (dane.typ === "blad") {
    const blad = document.createElement("p");
    blad.className = "instrukcja-naprawy";
    blad.textContent = dane.tekst;
    tura.kontener.appendChild(blad);
  } else if (dane.typ === "wynik" && dane.koszt_usd != null) {
    dopiszKoszt(dane.koszt_usd);
    const stopka = document.createElement("div");
    stopka.className = "szczegoly";
    stopka.style.marginTop = "0.35rem";
    stopka.textContent = `Zużycie: $${dane.koszt_usd.toFixed(3)}`;
    tura.kontener.appendChild(stopka);
  }
  tura.historia.scrollTop = tura.historia.scrollHeight;
}

async function wyslijWiadomoscAsystenta() {
  const pole = document.getElementById("czat-pole");
  const tresc = pole.value.trim();
  if (!tresc) return;
  pole.value = "";

  const historia = document.getElementById("czat-historia");
  historia.querySelector(".pusty-czat")?.remove();
  dodajWiadomoscUzytkownikaDoCzatu(historia, tresc);
  const tura = utworzTureAsystentaWCzacie(historia);

  let odpowiedz;
  try {
    odpowiedz = await fetch("/api/asystent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ wiadomosc: tresc }),
    });
  } catch (blad) {
    obslugaZdarzeniaCzatu({ typ: "blad", tekst: `Nie udało się połączyć z serwerem (${blad.message}).` }, tura);
    return;
  }

  const typTresci = odpowiedz.headers.get("content-type") || "";
  if (typTresci.includes("application/json")) {
    const dane = await odpowiedz.json();
    if (dane.zablokowane_nda) {
      const nosnik = document.createElement("div");
      nosnik.innerHTML = elementBlokadyNda(dane.fraza);
      tura.kontener.appendChild(nosnik.firstElementChild);
      tura.historia.scrollTop = tura.historia.scrollHeight;
    } else {
      obslugaZdarzeniaCzatu({ typ: "blad", tekst: dane.blad || "Nie udało się wysłać wiadomości." }, tura);
    }
    return;
  }

  await strumieniujSSE(odpowiedz, (dane) => obslugaZdarzeniaCzatu(dane, tura));
}

// --- Ekran "Styl" (pliki sterujące, SPEC 8.4 / SPEC-frontend 9) ---

let aktywnyPlikStylu = null;
let trescNaDysku = "";

async function renderujStyl() {
  OBSZAR.innerHTML = `<h2>Styl</h2><div class="karta"><p class="placeholder">Wczytuję…</p></div>`;
  let dane;
  try {
    const odpowiedz = await fetch("/api/pliki");
    if (!odpowiedz.ok) throw new Error(`HTTP ${odpowiedz.status}`);
    dane = await odpowiedz.json();
  } catch (blad) {
    OBSZAR.innerHTML = `<h2>Styl</h2><div class="karta"><p class="instrukcja-naprawy">Nie udało się wczytać listy ustawień (${escapeHtml(blad.message)}). Sprawdź, czy serwer aplikacji nadal działa, i odśwież stronę.</p></div>`;
    return;
  }

  // Identyfikacja wizualna nie jest plikiem warstwy jakości (ma inny format
  // i osobne endpointy), ale operatorka szuka jej w tym samym miejscu.
  dane.pliki = [...dane.pliki, { id: "brand-kit", nazwa: "Identyfikacja wizualna", opis: "Kolory, kroje i logo używane przy tworzeniu grafik", luki: 0 }];

  const zakladki = dane.pliki
    .map((plik) => {
      const luki = plik.luki > 0 ? ` <span class="znacznik-luk">${plik.luki}</span>` : "";
      return `<button class="zakladka-pliku" data-plik="${plik.id}">${escapeHtml(plik.nazwa)}${luki}</button>`;
    })
    .join("");

  OBSZAR.innerHTML = `
    <h2>Styl</h2>
    <p class="szczegoly">
      Tu zmieniasz sposób, w jaki asystent pisze. Zmiany działają od następnej
      rozmowy — nie trzeba nic restartować.
    </p>
    <div class="karta karta-wywiad">
      <div>
        <strong>Nie wiesz, co tu wpisać?</strong>
        <p class="szczegoly" style="margin:0.3rem 0 0">
          Asystent przejrzy Wasze opublikowane posty, powie, co z nich odczytał,
          i dopyta tylko o to, czego nie da się z nich wyczytać. Na koniec
          zaproponuje gotową treść „Głosu marki" i „Rodzajów postów"
          — zapisujesz jednym kliknięciem albo odrzucasz.
        </p>
      </div>
      <button class="przycisk-glowny" id="przycisk-wywiad">Porozmawiaj o stylu</button>
    </div>
    <div class="zakladki-plikow">${zakladki}</div>
    <div id="edytor-stylu"></div>
  `;

  document.getElementById("przycisk-wywiad").addEventListener("click", renderujWywiad);

  OBSZAR.querySelectorAll(".zakladka-pliku").forEach((przycisk) => {
    przycisk.addEventListener("click", () => otworzPlikStylu(przycisk.dataset.plik, dane.pliki));
  });

  if (dane.pliki.length) otworzPlikStylu(dane.pliki[0].id, dane.pliki);
}

// --- Wywiad o stylu (SPEC 8.3, SPEC-frontend 9) ---
//
// Rozmowa żyje w przeglądarce i wraca do serwera przy każdej turze: pojedyncze
// wywołanie asystenta nie pamięta poprzednich. Na końcu asystent proponuje
// treść plików, ale ich nie zapisuje — zapis to osobne kliknięcie operatorki.

let rozmowaWywiadu = [];

function renderujWywiad() {
  rozmowaWywiadu = [];
  OBSZAR.innerHTML = `
    <h2>Rozmowa o stylu</h2>
    <p class="szczegoly">
      Odpowiadaj własnymi słowami — asystent pyta o jedną rzecz naraz.
      Możesz przerwać w dowolnym momencie i wrócić do tego później;
      nic nie zapisze się bez Twojej zgody.
    </p>
    <div class="karta" id="wywiad-historia" style="min-height:300px;max-height:58vh;overflow-y:auto"></div>
    <form id="wywiad-formularz" style="display:flex;gap:0.5rem;margin-top:0.75rem">
      <textarea id="wywiad-pole" rows="2" style="flex:1"
        placeholder="Twoja odpowiedź — Enter wysyła, Shift+Enter robi nową linię"></textarea>
      <button class="przycisk-glowny" type="submit">Wyślij</button>
    </form>
    <div class="pasek-narzedzi" style="margin-top:0.75rem">
      <button class="przycisk-drugorzedny" id="wywiad-zakoncz">Zakończ i pokaż propozycję</button>
      <button class="przycisk-drugorzedny" id="wywiad-wroc">Wróć do ustawień</button>
    </div>
  `;

  document.getElementById("wywiad-formularz").addEventListener("submit", (zdarzenie) => {
    zdarzenie.preventDefault();
    wyslijTureWywiadu();
  });
  const pole = document.getElementById("wywiad-pole");
  pole.addEventListener("keydown", (zdarzenie) => {
    if (zdarzenie.key === "Enter" && !zdarzenie.shiftKey && !zdarzenie.isComposing) {
      zdarzenie.preventDefault();
      wyslijTureWywiadu();
    }
  });
  document.getElementById("wywiad-zakoncz").addEventListener("click", () => {
    if (!rozmowaWywiadu.some((wpis) => wpis.rola === "operator")) {
      dodajWpisWywiadu(
        "asystent",
        "Najpierw odpowiedz choć na jedno pytanie — bez tego nie ma z czego zbudować zasad."
      );
      return;
    }
    wyslijTureWywiadu({ zakoncz: true });
  });
  document.getElementById("wywiad-wroc").addEventListener("click", renderujStyl);

  // Pierwszą turę wywołujemy sami — rozmowę zaczyna asystent, nie operatorka.
  wyslijTureWywiadu({ pierwsza: true });
}

function dodajWpisWywiadu(rola, tresc) {
  const historia = document.getElementById("wywiad-historia");
  const wpis = document.createElement("div");
  wpis.className = `wiadomosc-czatu ${rola === "operator" ? "uzytkownik" : "asystent"}`;
  if (rola === "operator") {
    wpis.textContent = tresc;
  } else {
    wpis.classList.add("tresc-wywiadu");
    wpis.innerHTML = prostyMarkdown(tresc);
  }
  historia.appendChild(wpis);
  historia.scrollTop = historia.scrollHeight;
  return wpis;
}

async function wyslijTureWywiadu({ pierwsza = false, zakoncz = false } = {}) {
  const pole = document.getElementById("wywiad-pole");
  const tresc = pierwsza || zakoncz ? "" : pole.value.trim();
  if (!pierwsza && !zakoncz && !tresc) return;

  if (tresc) {
    rozmowaWywiadu.push({ rola: "operator", tresc });
    dodajWpisWywiadu("operator", tresc);
    pole.value = "";
  }

  const czekacz = dodajWpisWywiadu(
    "asystent",
    pierwsza ? "Przeglądam Wasze posty…" : zakoncz ? "Spisuję ustalenia…" : "Myślę…"
  );
  pole.disabled = true;

  let odpowiedz;
  try {
    odpowiedz = await fetch("/api/wywiad", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ historia: rozmowaWywiadu, zakoncz }),
    });
  } catch (blad) {
    czekacz.innerHTML = `<p class="instrukcja-naprawy">Nie udało się połączyć z serwerem (${escapeHtml(blad.message)}).</p>`;
    pole.disabled = false;
    return;
  }

  if ((odpowiedz.headers.get("content-type") || "").includes("application/json")) {
    const dane = await odpowiedz.json();
    czekacz.outerHTML = dane.zablokowane_nda
      ? elementBlokadyNda(dane.fraza)
      : `<p class="instrukcja-naprawy">${escapeHtml(dane.blad || "Nie udało się uruchomić rozmowy.")}</p>`;
    pole.disabled = false;
    return;
  }

  await strumieniujSSE(odpowiedz, (zdarzenie) => {
    if (zdarzenie.typ === "status") {
      czekacz.innerHTML = `<p class="placeholder">${escapeHtml(zdarzenie.tekst)}</p>`;
    } else if (zdarzenie.typ === "blad") {
      czekacz.innerHTML = `<p class="instrukcja-naprawy">${escapeHtml(zdarzenie.tekst)}</p>`;
      pole.disabled = false;
    } else if (zdarzenie.typ === "wynik") {
      dopiszKoszt(zdarzenie.koszt_usd);
      pole.disabled = false;
      const tekst = zdarzenie.odpowiedz || "";
      czekacz.innerHTML = prostyMarkdown(tekst || "(brak odpowiedzi — spróbuj jeszcze raz)");
      if (tekst) rozmowaWywiadu.push({ rola: "asystent", tresc: tekst });
      (zdarzenie.propozycje_plikow || []).forEach(pokazPropozycjePliku);
      if (zdarzenie.blad_propozycji) {
        dodajWpisWywiadu("asystent", zdarzenie.blad_propozycji);
      }
      pole.focus();
    }
  });
}

const propozycjeStylu = {};
let licznikPropozycjiStylu = 0;

function pokazPropozycjePliku(propozycja) {
  const id = ++licznikPropozycjiStylu;
  propozycjeStylu[id] = propozycja;

  const historia = document.getElementById("wywiad-historia");
  const karta = document.createElement("div");
  karta.className = "karta karta-propozycja";
  karta.innerHTML = `
    <strong>Propozycja: ${escapeHtml(propozycja.nazwa)}</strong>
    <p class="szczegoly">
      Przeczytaj i zdecyduj. Zapis nadpisze obecną treść — poprzednia wersja
      zniknie, więc jeśli nie masz pewności, skopiuj ją najpierw.
    </p>
    <textarea class="monospace" rows="14" style="width:100%;margin-top:0.5rem" data-tresc-propozycji="${id}">${escapeHtml(propozycja.tresc)}</textarea>
    <div class="pasek-narzedzi" style="margin-top:0.5rem">
      <button class="przycisk-glowny" data-zapisz-propozycje="${id}">Zapisz jako „${escapeHtml(propozycja.nazwa)}"</button>
      <button class="przycisk-drugorzedny" data-odrzuc-propozycje="${id}">Odrzuć</button>
      <span class="szczegoly" data-status-propozycji="${id}"></span>
    </div>
  `;
  historia.appendChild(karta);
  historia.scrollTop = historia.scrollHeight;

  karta.querySelector("[data-zapisz-propozycje]").addEventListener("click", (zdarzenie) =>
    zapiszPropozycjeStylu(id, zdarzenie.target)
  );
  karta.querySelector("[data-odrzuc-propozycje]").addEventListener("click", () => karta.remove());
}

async function zapiszPropozycjeStylu(id, przycisk) {
  const propozycja = propozycjeStylu[id];
  const pole = document.querySelector(`[data-tresc-propozycji="${id}"]`);
  const status = document.querySelector(`[data-status-propozycji="${id}"]`);
  przycisk.disabled = true;
  status.textContent = "Zapisuję…";

  try {
    const odpowiedz = await fetch(`/api/pliki/${encodeURIComponent(propozycja.id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tresc: pole.value }),
    });
    const dane = await odpowiedz.json();
    if (!odpowiedz.ok) {
      status.innerHTML = `<span class="instrukcja-naprawy">${escapeHtml(dane.blad || "Nie udało się zapisać.")}</span>`;
      przycisk.disabled = false;
      return;
    }
    status.textContent = dane.luki
      ? `Zapisane. Zostało ${dane.luki} miejsc do uzupełnienia.`
      : "Zapisane.";
    przycisk.textContent = "Zapisano";
  } catch (blad) {
    status.innerHTML = `<span class="instrukcja-naprawy">Nie udało się połączyć z serwerem (${escapeHtml(blad.message)}).</span>`;
    przycisk.disabled = false;
  }
}

async function otworzPlikStylu(identyfikator, listaPlikow) {
  aktywnyPlikStylu = identyfikator;
  if (identyfikator === "brand-kit") {
    OBSZAR.querySelectorAll(".zakladka-pliku").forEach((p) => {
      p.classList.toggle("aktywna", p.dataset.plik === identyfikator);
    });
    return otworzIdentyfikacjeWizualna();
  }
  const opisPliku = listaPlikow.find((plik) => plik.id === identyfikator) || {};
  OBSZAR.querySelectorAll(".zakladka-pliku").forEach((przycisk) => {
    przycisk.classList.toggle("aktywna", przycisk.dataset.plik === identyfikator);
  });

  const edytor = document.getElementById("edytor-stylu");
  edytor.innerHTML = `<div class="karta"><p class="placeholder">Wczytuję…</p></div>`;

  let dane;
  try {
    const odpowiedz = await fetch(`/api/pliki/${identyfikator}`);
    dane = await odpowiedz.json();
    if (!odpowiedz.ok) throw new Error(dane.blad || `HTTP ${odpowiedz.status}`);
  } catch (blad) {
    edytor.innerHTML = `<div class="karta"><p class="instrukcja-naprawy">${escapeHtml(blad.message)}</p></div>`;
    return;
  }

  trescNaDysku = dane.tresc;
  const ostrzezenieLuk =
    dane.luki > 0
      ? `<div class="ostrzezenie-koszt">W tym pliku jest ${dane.luki} ${dane.luki === 1 ? "miejsce" : "miejsc"} do uzupełnienia — poszukaj „[DO UZUPEŁNIENIA” i „[DO POTWIERDZENIA”.</div>`
      : "";

  edytor.innerHTML = `
    <div class="karta">
      <strong>${escapeHtml(opisPliku.nazwa || "")}</strong>
      <p class="szczegoly">${escapeHtml(opisPliku.opis || "")}</p>
      ${ostrzezenieLuk}
      <textarea id="pole-stylu" class="monospace" rows="22" style="width:100%;margin-top:0.5rem"></textarea>
      <div style="margin-top:0.75rem;display:flex;gap:0.5rem;align-items:center">
        <button class="przycisk-glowny" id="przycisk-zapisz-styl">Zapisz zmiany</button>
        <button class="przycisk-drugorzedny" id="przycisk-przywroc-styl">Przywróć</button>
        <span id="status-stylu" class="szczegoly"></span>
      </div>
      <div id="podglad-roznicy"></div>
    </div>
  `;
  document.getElementById("pole-stylu").value = dane.tresc;
  document.getElementById("przycisk-zapisz-styl").addEventListener("click", () => pokazRoznicePrzedZapisem(listaPlikow));
  document.getElementById("przycisk-przywroc-styl").addEventListener("click", () => {
    document.getElementById("pole-stylu").value = trescNaDysku;
    document.getElementById("podglad-roznicy").innerHTML = "";
    document.getElementById("status-stylu").textContent = "Przywrócono zapisaną wersję.";
  });
}

async function otworzIdentyfikacjeWizualna() {
  const edytor = document.getElementById("edytor-stylu");
  edytor.innerHTML = `<div class="karta"><p class="placeholder">Wczytuję…</p></div>`;

  let dane;
  try {
    const odpowiedz = await fetch("/api/brand-kit");
    dane = await odpowiedz.json();
    if (!odpowiedz.ok) throw new Error(dane.blad || `HTTP ${odpowiedz.status}`);
  } catch (blad) {
    edytor.innerHTML = `<div class="karta"><p class="instrukcja-naprawy">${escapeHtml(blad.message)}</p></div>`;
    return;
  }

  const ostrzezenia = dane.ostrzezenia.length
    ? `<div class="ostrzezenie-koszt">${dane.ostrzezenia.map(escapeHtml).join("<br>")}</div>`
    : "";
  const listaLogo = dane.logo.length
    ? `<ul class="lista-materialow">${dane.logo.map((n) => `<li>${escapeHtml(n)}</li>`).join("")}</ul>`
    : `<p class="szczegoly">Nie wgrano jeszcze logo — grafika użyje nazwy firmy zapisanej tekstem.</p>`;

  edytor.innerHTML = `
    <div class="karta">
      <strong>Identyfikacja wizualna</strong>
      <p class="szczegoly">Kolory, kroje i logo, z których powstają grafiki do postów.</p>
      ${ostrzezenia}
      <textarea id="pole-brand-kitu" class="monospace" rows="20" style="width:100%;margin-top:0.5rem"></textarea>
      <div style="margin-top:0.75rem;display:flex;gap:0.5rem;align-items:center">
        <button class="przycisk-glowny" id="zapisz-brand-kit">Zapisz zmiany</button>
        <span id="status-brand-kitu" class="szczegoly"></span>
      </div>
    </div>
    <div class="karta">
      <strong>Logo</strong>
      <p class="szczegoly">
        Po wgraniu wpisz nazwę pliku w polu <code>logo → plik</code> powyżej.
        Jeśli macie osobną wersję na ciemne tło, wgraj obie.
      </p>
      ${listaLogo}
      <div class="pasek-narzedzi" style="margin:0.75rem 0 0">
        <input type="file" id="plik-logo" accept=".png,.svg,.jpg,.jpeg,.webp">
        <button class="przycisk-drugorzedny" id="wgraj-logo">Wgraj logo</button>
        <span id="status-logo" class="szczegoly"></span>
      </div>
    </div>
  `;
  document.getElementById("pole-brand-kitu").value = dane.tresc;

  document.getElementById("zapisz-brand-kit").addEventListener("click", async () => {
    const status = document.getElementById("status-brand-kitu");
    status.textContent = "Zapisuję…";
    const odpowiedz = await fetch("/api/brand-kit", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tresc: document.getElementById("pole-brand-kitu").value }),
    });
    const wynik = await odpowiedz.json();
    status.innerHTML = odpowiedz.ok
      ? "Zapisano."
      : `<span class="instrukcja-naprawy">${escapeHtml(wynik.blad)}</span>`;
    if (odpowiedz.ok) otworzIdentyfikacjeWizualna();
  });

  document.getElementById("wgraj-logo").addEventListener("click", async () => {
    const wejscie = document.getElementById("plik-logo");
    const status = document.getElementById("status-logo");
    if (!wejscie.files.length) {
      status.innerHTML = `<span class="instrukcja-naprawy">Najpierw wybierz plik.</span>`;
      return;
    }
    status.textContent = "Wgrywam…";
    const formularz = new FormData();
    formularz.append("plik", wejscie.files[0]);
    const odpowiedz = await fetch("/api/brand-kit/logo", { method: "POST", body: formularz });
    const wynik = await odpowiedz.json();
    if (!odpowiedz.ok) {
      status.innerHTML = `<span class="instrukcja-naprawy">${escapeHtml(wynik.blad)}</span>`;
      return;
    }
    otworzIdentyfikacjeWizualna();
  });
}

function zbudujRoznice(stara, nowa) {
  const stareLinie = stara.split("\n");
  const noweLinie = nowa.split("\n");
  const usuniete = stareLinie.filter((linia) => !noweLinie.includes(linia));
  const dodane = noweLinie.filter((linia) => !stareLinie.includes(linia));
  if (!usuniete.length && !dodane.length) return null;
  return (
    usuniete.map((l) => `<div class="linia-usunieta">- ${escapeHtml(l)}</div>`).join("") +
    dodane.map((l) => `<div class="linia-dodana">+ ${escapeHtml(l)}</div>`).join("")
  );
}

function pokazRoznicePrzedZapisem(listaPlikow) {
  const nowaTresc = document.getElementById("pole-stylu").value;
  const podglad = document.getElementById("podglad-roznicy");
  const roznica = zbudujRoznice(trescNaDysku, nowaTresc);

  if (!roznica) {
    document.getElementById("status-stylu").textContent = "Nie ma żadnych zmian do zapisania.";
    podglad.innerHTML = "";
    return;
  }

  podglad.innerHTML = `
    <div class="karta" style="margin-top:0.75rem">
      <strong>Co się zmieni</strong>
      <div class="roznica monospace">${roznica}</div>
      <div style="margin-top:0.5rem;display:flex;gap:0.5rem">
        <button class="przycisk-glowny" id="potwierdz-zapis">Potwierdź zapis</button>
        <button class="przycisk-drugorzedny" id="anuluj-zapis">Anuluj</button>
      </div>
    </div>
  `;
  document.getElementById("anuluj-zapis").addEventListener("click", () => {
    podglad.innerHTML = "";
  });
  document.getElementById("potwierdz-zapis").addEventListener("click", () => zapiszPlikStylu(listaPlikow));
}

async function zapiszPlikStylu(listaPlikow) {
  const nowaTresc = document.getElementById("pole-stylu").value;
  const status = document.getElementById("status-stylu");
  try {
    const odpowiedz = await fetch(`/api/pliki/${aktywnyPlikStylu}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tresc: nowaTresc }),
    });
    const dane = await odpowiedz.json();
    if (!odpowiedz.ok) throw new Error(dane.blad || `HTTP ${odpowiedz.status}`);
    trescNaDysku = nowaTresc;
    document.getElementById("podglad-roznicy").innerHTML = "";
    status.textContent = "Zapisano.";
    const wpis = listaPlikow.find((plik) => plik.id === aktywnyPlikStylu);
    if (wpis) wpis.luki = dane.luki;
  } catch (blad) {
    status.textContent = "";
    document.getElementById("podglad-roznicy").innerHTML = `<p class="instrukcja-naprawy">${escapeHtml(blad.message)}</p>`;
  }
}

// --- Ekran "Korpus" (SPEC 8.5 / SPEC-frontend 10) ---

let stanKorpusu = { posty: [], dozwolone_typy: [], docelowo: 20, ostrzezenia: [] };
let filtrTypu = "";
let sortujPoReakcjach = false;

async function renderujKorpus() {
  OBSZAR.innerHTML = `<h2>Korpus</h2><div class="karta"><p class="placeholder">Wczytuję…</p></div>`;
  try {
    const odpowiedz = await fetch("/api/korpus");
    if (!odpowiedz.ok) throw new Error(`HTTP ${odpowiedz.status}`);
    stanKorpusu = await odpowiedz.json();
  } catch (blad) {
    OBSZAR.innerHTML = `<h2>Korpus</h2><div class="karta"><p class="instrukcja-naprawy">Nie udało się wczytać korpusu (${escapeHtml(blad.message)}). Sprawdź, czy serwer aplikacji nadal działa, i odśwież stronę.</p></div>`;
    return;
  }
  rysujKorpus();
}

function opcjeTypow(wybrany = "") {
  return stanKorpusu.dozwolone_typy
    .map((typ) => `<option value="${typ}"${typ === wybrany ? " selected" : ""}>${typ}</option>`)
    .join("");
}

function rysujKorpus() {
  const liczba = stanKorpusu.posty.length;
  const docelowo = stanKorpusu.docelowo;
  const procent = Math.min(100, Math.round((liczba / docelowo) * 100));
  const bezTypu = stanKorpusu.posty.filter((post) => post.wymaga_oznaczenia).length;

  const ostrzezeniaHtml = stanKorpusu.ostrzezenia.length
    ? `<div class="karta karta-ostrzegawcza">
        <strong>Pliki, których nie udało się odczytać</strong>
        <ul>${stanKorpusu.ostrzezenia.map((o) => `<li>${escapeHtml(o)}</li>`).join("")}</ul>
       </div>`
    : "";

  const bezTypuHtml = bezTypu
    ? `<div class="ostrzezenie-koszt">${bezTypu} ${bezTypu === 1 ? "post wymaga" : "postów wymaga"} oznaczenia rodzaju — wybierz rodzaj w tabeli poniżej.</div>`
    : "";

  OBSZAR.innerHTML = `
    <h2>Korpus</h2>
    <div class="karta">
      <strong>Opublikowane posty: ${liczba} / ${docelowo} zalecanych</strong>
      <div class="pasek-postepu"><div class="pasek-wypelnienie" style="width:${procent}%"></div></div>
      <p class="szczegoly">
        Im więcej postów tu wgrasz, tym lepiej asystent pisze w Waszym głosie.
        Dopisuj każdy opublikowany post.
      </p>
      ${bezTypuHtml}
    </div>
    ${ostrzezeniaHtml}
    <div class="karta">
      <div class="pasek-narzedzi" style="margin-bottom:0">
        <label>Rodzaj:
          <select id="filtr-typu"><option value="">wszystkie</option>${opcjeTypow(filtrTypu)}</select>
        </label>
        <label><input type="checkbox" id="sortuj-reakcje"${sortujPoReakcjach ? " checked" : ""}> sortuj po reakcjach</label>
      </div>
      <div id="tabela-korpusu"></div>
    </div>
    <details class="karta">
      <summary><strong>Dodaj opublikowany post</strong></summary>
      <div style="margin-top:0.75rem">
        <textarea id="nowy-tresc" class="monospace" rows="6" style="width:100%" placeholder="Wklej treść opublikowanego posta…"></textarea>
        <div class="pola-formularza">
          <label>Data<input type="date" id="nowy-data" value="${new Date().toISOString().slice(0, 10)}"></label>
          <label>Rodzaj<select id="nowy-typ">${opcjeTypow()}</select></label>
          <label>Język<select id="nowy-jezyk"><option value="pl">pl</option><option value="en">en</option><option value="no">no</option></select></label>
          <label>Reakcje<input type="number" id="nowy-reakcje" value="0" min="0"></label>
          <label>Komentarze<input type="number" id="nowy-komentarze" value="0" min="0"></label>
          <label>Adres posta<input type="text" id="nowy-url" placeholder="https://linkedin.com/…"></label>
        </div>
        <div style="margin-top:0.75rem;display:flex;gap:0.5rem;align-items:center">
          <button class="przycisk-glowny" id="przycisk-dodaj-post">Dodaj do korpusu</button>
          <span id="status-dodawania" class="szczegoly"></span>
        </div>
      </div>
    </details>
    <details class="karta">
      <summary><strong>Import z pliku</strong></summary>
      <p class="szczegoly" style="margin-top:0.5rem">
        Wgraj eksport z LinkedIna (CSV, XLSX albo JSON). Najpierw pokażemy, co
        zostanie zaimportowane — nic nie zapisze się bez Twojego potwierdzenia.
      </p>
      <input type="file" id="plik-importu" accept=".csv,.xlsx,.xls,.json">
      <button class="przycisk-drugorzedny" id="przycisk-analizuj">Sprawdź plik</button>
      <div id="wynik-importu"></div>
    </details>
  `;

  document.getElementById("filtr-typu").addEventListener("change", (zdarzenie) => {
    filtrTypu = zdarzenie.target.value;
    rysujTabeleKorpusu();
  });
  document.getElementById("sortuj-reakcje").addEventListener("change", (zdarzenie) => {
    sortujPoReakcjach = zdarzenie.target.checked;
    rysujTabeleKorpusu();
  });
  document.getElementById("przycisk-dodaj-post").addEventListener("click", dodajPostDoKorpusu);
  document.getElementById("przycisk-analizuj").addEventListener("click", analizujPlikImportu);
  rysujTabeleKorpusu();
}

function rysujTabeleKorpusu() {
  const kontener = document.getElementById("tabela-korpusu");
  let posty = [...stanKorpusu.posty];
  if (filtrTypu) posty = posty.filter((post) => post.typ === filtrTypu);
  if (sortujPoReakcjach) posty.sort((a, b) => b.reakcje - a.reakcje);

  if (!posty.length) {
    kontener.innerHTML = `<p class="placeholder">
      ${stanKorpusu.posty.length ? "Żaden post nie pasuje do wybranego rodzaju." : "Korpus jest pusty. Dodaj pierwszy opublikowany post formularzem poniżej albo zaimportuj eksport z LinkedIna."}
    </p>`;
    return;
  }

  const wiersze = posty
    .map(
      (post) => `
      <tr class="${post.wymaga_oznaczenia ? "wymaga-oznaczenia" : ""}">
        <td>${escapeHtml(post.data)}</td>
        <td>
          <select data-typ-dla="${escapeHtml(post.plik)}">
            ${post.wymaga_oznaczenia ? `<option value="">${escapeHtml(post.typ)}</option>` : ""}
            ${opcjeTypow(post.typ)}
          </select>
        </td>
        <td>${escapeHtml(post.jezyk)}</td>
        <td>${post.reakcje}</td>
        <td><details><summary>${escapeHtml(post.tresc.slice(0, 80))}…</summary><pre class="monospace" style="white-space:pre-wrap">${escapeHtml(post.tresc)}</pre></details></td>
        <td><button class="przycisk-drugorzedny" data-usun="${escapeHtml(post.plik)}">Usuń</button></td>
      </tr>`
    )
    .join("");

  kontener.innerHTML = `
    <table class="tabela-korpusu">
      <thead><tr><th>Data</th><th>Rodzaj</th><th>Język</th><th>Reakcje</th><th>Treść</th><th></th></tr></thead>
      <tbody>${wiersze}</tbody>
    </table>
  `;

  kontener.querySelectorAll("[data-typ-dla]").forEach((wybor) => {
    wybor.addEventListener("change", () => zmienTypPosta(wybor.dataset.typDla, wybor.value));
  });
  kontener.querySelectorAll("[data-usun]").forEach((przycisk) => {
    przycisk.addEventListener("click", () => usunPostZKorpusu(przycisk.dataset.usun));
  });
}

async function zmienTypPosta(nazwaPliku, typ) {
  if (!typ) return;
  const odpowiedz = await fetch(`/api/korpus/${encodeURIComponent(nazwaPliku)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ typ }),
  });
  if (!odpowiedz.ok) {
    const dane = await odpowiedz.json();
    alert(dane.blad || "Nie udało się zapisać rodzaju posta.");
    return;
  }
  await renderujKorpus();
}

async function usunPostZKorpusu(nazwaPliku) {
  if (!confirm("Usunąć ten post z korpusu? Pliku nie da się przywrócić z aplikacji.")) return;
  const odpowiedz = await fetch(`/api/korpus/${encodeURIComponent(nazwaPliku)}`, { method: "DELETE" });
  if (!odpowiedz.ok) {
    const dane = await odpowiedz.json();
    alert(dane.blad || "Nie udało się usunąć posta.");
    return;
  }
  await renderujKorpus();
}

async function dodajPostDoKorpusu() {
  const status = document.getElementById("status-dodawania");
  status.textContent = "";
  const nowy = {
    tresc: document.getElementById("nowy-tresc").value,
    data: document.getElementById("nowy-data").value,
    typ: document.getElementById("nowy-typ").value,
    jezyk: document.getElementById("nowy-jezyk").value,
    reakcje: Number(document.getElementById("nowy-reakcje").value || 0),
    komentarze: Number(document.getElementById("nowy-komentarze").value || 0),
    url: document.getElementById("nowy-url").value,
  };

  const odpowiedz = await fetch("/api/korpus", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(nowy),
  });
  const dane = await odpowiedz.json();
  if (!odpowiedz.ok) {
    status.innerHTML = `<span class="instrukcja-naprawy">${escapeHtml(dane.blad || "Nie udało się dodać posta.")}</span>`;
    return;
  }
  await renderujKorpus();
}

async function analizujPlikImportu() {
  const wejscie = document.getElementById("plik-importu");
  const wynik = document.getElementById("wynik-importu");
  if (!wejscie.files.length) {
    wynik.innerHTML = `<p class="instrukcja-naprawy">Najpierw wybierz plik z dysku.</p>`;
    return;
  }

  wynik.innerHTML = `<p class="placeholder">Sprawdzam plik…</p>`;
  const formularz = new FormData();
  formularz.append("plik", wejscie.files[0]);

  let dane;
  try {
    const odpowiedz = await fetch("/api/korpus/import/analiza", { method: "POST", body: formularz });
    dane = await odpowiedz.json();
    if (!odpowiedz.ok) throw new Error(dane.blad || `HTTP ${odpowiedz.status}`);
  } catch (blad) {
    wynik.innerHTML = `<p class="instrukcja-naprawy">${escapeHtml(blad.message)}</p>`;
    return;
  }

  const d = dane.diagnostyka;
  const wykryte = Object.entries(d.wykryte)
    .map(([rola, kolumna]) => `<li>${escapeHtml(rola)}: ${kolumna ? `<code>${escapeHtml(kolumna)}</code>` : "<em>nie znaleziono</em>"}</li>`)
    .join("");
  const probki = d.probki.map((p) => `<li>${escapeHtml(p)}…</li>`).join("");

  wynik.innerHTML = `
    <div class="karta" style="margin-top:0.75rem">
      <strong>Co znaleźliśmy w pliku</strong>
      <p class="szczegoly">Wierszy w pliku: ${d.wierszy_w_pliku}</p>
      <ul>${wykryte}</ul>
      <p><strong>Do zaimportowania: ${d.do_zaimportowania}</strong> ·
        odrzucone: ${d.odrzucone_reposty} (udostępnienia/puste), ${d.odrzucone_krotkie} (krótsze niż 150 znaków)</p>
      <p class="szczegoly">Mediana długości treści: ${d.mediana_dlugosci} znaków</p>
      ${probki ? `<strong>Próbki treści</strong><ul class="szczegoly">${probki}</ul>` : ""}
      <label>Zaimportuj tylko najlepsze:
        <input type="number" id="limit-importu" min="1" max="${d.do_zaimportowania}" value="${d.do_zaimportowania}">
      </label>
      <div style="margin-top:0.75rem">
        <button class="przycisk-glowny" id="potwierdz-import" data-identyfikator="${escapeHtml(dane.identyfikator)}">Importuj</button>
      </div>
    </div>
  `;
  document.getElementById("potwierdz-import").addEventListener("click", wykonajImport);
}

async function wykonajImport() {
  const przycisk = document.getElementById("potwierdz-import");
  const limit = Number(document.getElementById("limit-importu").value) || null;
  przycisk.disabled = true;
  przycisk.textContent = "Importuję…";

  const odpowiedz = await fetch("/api/korpus/import/wykonaj", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identyfikator: przycisk.dataset.identyfikator, limit }),
  });
  const dane = await odpowiedz.json();
  if (!odpowiedz.ok) {
    document.getElementById("wynik-importu").innerHTML = `<p class="instrukcja-naprawy">${escapeHtml(dane.blad || "Nie udało się zaimportować.")}</p>`;
    return;
  }

  await renderujKorpus();
  const wynik = document.getElementById("wynik-importu");
  if (wynik) {
    wynik.innerHTML = `<p>Zaimportowano ${dane.zaimportowane}, odrzucono ${dane.odrzucone_reposty + dane.odrzucone_krotkie} (${dane.odrzucone_reposty} udostępnień, ${dane.odrzucone_krotkie} zbyt krótkich). Oznacz rodzaj u nowych postów w tabeli powyżej.</p>`;
  }
}

// --- Wspólne: wybór miesiąca ---

function biezacyMiesiac() {
  return new Date().toISOString().slice(0, 7);
}

function nastepnyMiesiac() {
  const teraz = new Date();
  return new Date(teraz.getFullYear(), teraz.getMonth() + 1, 1).toISOString().slice(0, 7);
}

const NAZWY_MIESIECY = [
  "styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec",
  "lipiec", "sierpień", "wrzesień", "październik", "listopad", "grudzień",
];

function nazwaMiesiaca(miesiac) {
  const [rok, numer] = miesiac.split("-");
  return `${NAZWY_MIESIECY[Number(numer) - 1]} ${rok}`;
}

// --- Ekran "Plan" (tryb Strateg, SPEC 8.1 / SPEC-frontend 6) ---

let miesiacPlanu = nastepnyMiesiac();

async function renderujPlan() {
  OBSZAR.innerHTML = `<h2>Plan</h2><div class="karta"><p class="placeholder">Wczytuję…</p></div>`;
  let dane;
  try {
    const odpowiedz = await fetch(`/api/plan/${miesiacPlanu}`);
    if (!odpowiedz.ok) throw new Error(`HTTP ${odpowiedz.status}`);
    dane = await odpowiedz.json();
  } catch (blad) {
    OBSZAR.innerHTML = `<h2>Plan</h2><div class="karta"><p class="instrukcja-naprawy">Nie udało się wczytać planu (${escapeHtml(blad.message)}). Sprawdź, czy serwer aplikacji nadal działa, i odśwież stronę.</p></div>`;
    return;
  }

  const wyborMiesiaca = `
    <div class="pasek-narzedzi">
      <label>Miesiąc: <input type="month" id="miesiac-planu" value="${miesiacPlanu}"></label>
    </div>
  `;

  OBSZAR.innerHTML = `<h2>Plan</h2>${wyborMiesiaca}<div id="tresc-planu"></div>`;
  document.getElementById("miesiac-planu").addEventListener("change", (zdarzenie) => {
    miesiacPlanu = zdarzenie.target.value;
    renderujPlan();
  });

  const kontener = document.getElementById("tresc-planu");
  kontener.innerHTML = dane.plan.istnieje ? widokPlanu(dane) : widokPustegoPlanu(dane);
  podepnijAkcjePlanu(dane);
}

function widokPustegoPlanu(dane) {
  const w = dane.warunki;
  const znacznik = (spelniony) => (spelniony ? "✓" : "✗");
  const klasa = (spelniony) => (spelniony ? "warunek-ok" : "warunek-brak");

  const zrodlaOk = w.zrodla_luki === 0;
  const korpusOk = w.korpus > 0;
  const materialyOk = !w.materialy_puste;

  return `
    <div class="karta">
      <p>Nie ma jeszcze planu na <strong>${escapeHtml(nazwaMiesiaca(miesiacPlanu))}</strong>.</p>
      <button class="przycisk-glowny" id="przycisk-zbuduj-plan">Zbuduj plan na ${escapeHtml(nazwaMiesiaca(miesiacPlanu))}</button>
      <div style="margin-top:1rem">
        <strong>Przed zbudowaniem planu:</strong>
        <ul class="lista-warunkow">
          <li class="${klasa(korpusOk)}">${znacznik(korpusOk)} Korpus — ${w.korpus} ${w.korpus === 1 ? "post" : "postów"} (docelowo ${w.korpus_docelowo})</li>
          <li class="${klasa(zrodlaOk)}">${znacznik(zrodlaOk)} Źródła branżowe — ${zrodlaOk ? "gotowe" : `${w.zrodla_luki} do uzupełnienia`}</li>
          <li class="${klasa(materialyOk)}">${znacznik(materialyOk)} Materiały z firmy na ${escapeHtml(nazwaMiesiaca(miesiacPlanu))} — ${materialyOk ? "są" : "puste"}</li>
        </ul>
        ${
          materialyOk
            ? ""
            : `<div class="ostrzezenie-koszt">
                 Bez materiałów z firmy plan będzie krótszy — asystent nie dopycha go
                 newsami z branży, bo taki content nie odróżnia Was od konkurencji.
                 <button class="przycisk-drugorzedny" id="przejdz-do-materialow" style="margin-left:0.5rem">Uzupełnij materiały</button>
               </div>`
        }
      </div>
      <label style="display:block;margin-top:0.75rem">
        Uwagi dla asystenta (opcjonalne)
        <textarea id="uwagi-planu" class="monospace" rows="2" style="width:100%;margin-top:0.25rem" placeholder="np. w tym miesiącu kładziemy nacisk na rekrutację"></textarea>
      </label>
      <div class="log-przebiegu" id="log-planu" hidden></div>
    </div>
  `;
}

function widokPlanu(dane) {
  const plan = dane.plan;
  const brakiHtml = plan.czego_zabraklo.length
    ? `<div class="karta karta-ostrzegawcza">
         <h3 style="color:var(--ostrzezenie)">Czego zabrakło</h3>
         <ul>${plan.czego_zabraklo.map((b) => `<li>${escapeHtml(b)}</li>`).join("")}</ul>
         <button class="przycisk-drugorzedny" id="przejdz-do-materialow">Uzupełnij materiały</button>
       </div>`
    : "";

  const wiersze = plan.pozycje
    .map(
      (pozycja, indeks) => `
      <tr class="${pozycja.do_potwierdzenia ? "wymaga-oznaczenia" : ""}">
        <td>${escapeHtml(pozycja.data)}</td>
        <td>${escapeHtml(pozycja.typ)}</td>
        <td>${escapeHtml(pozycja.temat)}</td>
        <td class="szczegoly">${escapeHtml(pozycja.zrodlo)}</td>
        <td class="szczegoly">${escapeHtml(pozycja.do_potwierdzenia)}</td>
        <td>
          <select data-status-dla="${indeks}" class="status-${escapeHtml(pozycja.status)}">
            ${dane.statusy.map((s) => `<option value="${s}"${s === pozycja.status ? " selected" : ""}>${s}</option>`).join("")}
          </select>
        </td>
        <td><button class="przycisk-drugorzedny" data-napisz="${indeks}">Napisz</button></td>
      </tr>`
    )
    .join("");

  return `
    ${brakiHtml}
    <div class="karta">
      <table class="tabela-korpusu">
        <thead><tr><th>Data</th><th>Typ</th><th>Temat</th><th>Źródło</th><th>Do potwierdzenia</th><th>Status</th><th></th></tr></thead>
        <tbody>${wiersze}</tbody>
      </table>
      <div style="margin-top:0.75rem">
        <button class="przycisk-drugorzedny" id="przycisk-zbuduj-plan">Zbuduj plan od nowa</button>
        <span class="szczegoly">Nadpisze obecny plan na ten miesiąc.</span>
      </div>
      <textarea id="uwagi-planu" hidden></textarea>
      <div class="log-przebiegu" id="log-planu" hidden></div>
    </div>
  `;
}

function podepnijAkcjePlanu(dane) {
  const przejdz = document.getElementById("przejdz-do-materialow");
  if (przejdz) {
    przejdz.addEventListener("click", () => {
      miesiacMaterialow = miesiacPlanu;
      przejdzDoZakladki("materialy");
    });
  }

  const zbuduj = document.getElementById("przycisk-zbuduj-plan");
  if (zbuduj) zbuduj.addEventListener("click", zbudujPlan);

  document.querySelectorAll("[data-status-dla]").forEach((wybor) => {
    wybor.addEventListener("change", async () => {
      const odpowiedz = await fetch(`/api/plan/${miesiacPlanu}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ numer_wiersza: Number(wybor.dataset.statusDla), status: wybor.value }),
      });
      if (!odpowiedz.ok) {
        const blad = await odpowiedz.json();
        alert(blad.blad || "Nie udało się zapisać statusu.");
      }
      renderujPlan();
    });
  });

  document.querySelectorAll("[data-napisz]").forEach((przycisk) => {
    przycisk.addEventListener("click", () => {
      const pozycja = dane.plan.pozycje[Number(przycisk.dataset.napisz)];
      briefZPlanu = [
        `Temat: ${pozycja.temat}`,
        pozycja.typ ? `Rodzaj posta: ${pozycja.typ}` : "",
        pozycja.zrodlo ? `Źródło: ${pozycja.zrodlo}` : "",
        pozycja.do_potwierdzenia ? `Do potwierdzenia: ${pozycja.do_potwierdzenia}` : "",
      ]
        .filter(Boolean)
        .join("\n");
      przejdzDoZakladki("posty");
    });
  });
}

async function zbudujPlan() {
  const przycisk = document.getElementById("przycisk-zbuduj-plan");
  const log = document.getElementById("log-planu");
  const uwagi = document.getElementById("uwagi-planu").value;
  przycisk.disabled = true;
  przycisk.textContent = "Buduję plan…";
  log.hidden = false;
  log.innerHTML = "";

  const dopiszWpis = (tekst, klasa = "") => {
    const wpis = document.createElement("div");
    wpis.className = `wpis ${klasa}`;
    wpis.textContent = tekst;
    log.appendChild(wpis);
    log.scrollTop = log.scrollHeight;
  };

  let odpowiedz;
  try {
    odpowiedz = await fetch("/api/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ miesiac: miesiacPlanu, uwagi }),
    });
  } catch (blad) {
    dopiszWpis(`Nie udało się połączyć z serwerem (${blad.message}).`, "blad");
    przycisk.disabled = false;
    return;
  }

  if ((odpowiedz.headers.get("content-type") || "").includes("application/json")) {
    const dane = await odpowiedz.json();
    document.getElementById("tresc-planu").innerHTML = dane.zablokowane_nda
      ? elementBlokadyNda(dane.fraza)
      : `<div class="karta"><p class="instrukcja-naprawy">${escapeHtml(dane.blad || "Nie udało się zbudować planu.")}</p></div>`;
    return;
  }

  await strumieniujSSE(odpowiedz, (zdarzenie) => {
    if (zdarzenie.typ === "status" || zdarzenie.typ === "fragment") {
      dopiszWpis(zdarzenie.tekst);
    } else if (zdarzenie.typ === "wynik") {
      dopiszKoszt(zdarzenie.koszt_usd);
      if (zdarzenie.bledny) {
        dopiszWpis("Budowanie planu zakończyło się błędem.", "blad");
        przycisk.disabled = false;
      } else {
        renderujPlan();
      }
    } else if (zdarzenie.typ === "blad") {
      dopiszWpis(zdarzenie.tekst, "blad");
      przycisk.disabled = false;
    }
  });
}

// --- Ekran "Materiały" (input firmowy, SPEC-frontend 8) ---

let miesiacMaterialow = biezacyMiesiac();
let stanMaterialow = {};

async function renderujMaterialy() {
  OBSZAR.innerHTML = `<h2>Materiały</h2><div class="karta"><p class="placeholder">Wczytuję…</p></div>`;
  let dane;
  try {
    const odpowiedz = await fetch(`/api/materialy/${miesiacMaterialow}`);
    if (!odpowiedz.ok) throw new Error(`HTTP ${odpowiedz.status}`);
    dane = await odpowiedz.json();
  } catch (blad) {
    OBSZAR.innerHTML = `<h2>Materiały</h2><div class="karta"><p class="instrukcja-naprawy">Nie udało się wczytać materiałów (${escapeHtml(blad.message)}). Sprawdź, czy serwer aplikacji nadal działa, i odśwież stronę.</p></div>`;
    return;
  }

  stanMaterialow = dane.materialy;

  const blokPusty = dane.puste
    ? `<div class="karta karta-ostrzegawcza">
         <h3 style="color:var(--ostrzezenie)">Ten miesiąc jest pusty</h3>
         <p>
           Plan contentu oparty wyłącznie na newsach z branży będzie nieodróżnialny
           od konkurencji. Wyróżnia Was to, co realnie dzieje się na budowach.
         </p>
         <p><strong>Jedno zdanie wystarczy.</strong></p>
       </div>`
    : "";

  const bloki = dane.sekcje
    .map((sekcja, indeks) => {
      const wpisy = stanMaterialow[sekcja] || [];
      const listaWpisow = wpisy.length
        ? wpisy
            .map(
              (wpis, i) => `
              <li>
                <span>${escapeHtml(wpis)}</span>
                <button class="przycisk-drugorzedny maly" data-usun-wpis="${indeks}:${i}">usuń</button>
              </li>`
            )
            .join("")
        : `<li class="placeholder">(pusto)</li>`;
      return `
        <div class="karta">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <strong>${escapeHtml(sekcja)}</strong>
            <button class="przycisk-drugorzedny" data-dodaj-wpis="${indeks}">+ Dodaj</button>
          </div>
          <ul class="lista-materialow">${listaWpisow}</ul>
          <div data-formularz-dla="${indeks}" hidden style="margin-top:0.5rem">
            <input type="text" class="pole-wpisu" style="width:100%" placeholder="Jedno zdanie wystarczy…">
            <div style="margin-top:0.35rem">
              <button class="przycisk-glowny" data-zapisz-wpis="${indeks}">Dodaj</button>
              <button class="przycisk-drugorzedny" data-anuluj-wpis="${indeks}">Anuluj</button>
            </div>
          </div>
        </div>`;
    })
    .join("");

  OBSZAR.innerHTML = `
    <h2>Materiały</h2>
    <div class="pasek-narzedzi">
      <label>Miesiąc: <input type="month" id="miesiac-materialow" value="${miesiacMaterialow}"></label>
      <button class="przycisk-drugorzedny" id="przycisk-prosba">Wyślij prośbę o materiały</button>
    </div>
    ${blokPusty}
    <div id="przeniesiony-brak"></div>
    <div id="prosba-o-materialy"></div>
    ${bloki}
    <div id="sekcja-artykulow"></div>
  `;

  wstawPrzeniesionyBrak(dane.sekcje);

  document.getElementById("miesiac-materialow").addEventListener("change", (zdarzenie) => {
    miesiacMaterialow = zdarzenie.target.value;
    renderujMaterialy();
  });
  document.getElementById("przycisk-prosba").addEventListener("click", pokazProsbeOMaterialy);

  OBSZAR.querySelectorAll("[data-dodaj-wpis]").forEach((przycisk) => {
    przycisk.addEventListener("click", () => {
      const formularz = OBSZAR.querySelector(`[data-formularz-dla="${przycisk.dataset.dodajWpis}"]`);
      formularz.hidden = false;
      formularz.querySelector(".pole-wpisu").focus();
    });
  });
  OBSZAR.querySelectorAll("[data-anuluj-wpis]").forEach((przycisk) => {
    przycisk.addEventListener("click", () => {
      OBSZAR.querySelector(`[data-formularz-dla="${przycisk.dataset.anulujWpis}"]`).hidden = true;
    });
  });
  OBSZAR.querySelectorAll("[data-zapisz-wpis]").forEach((przycisk) => {
    przycisk.addEventListener("click", () => dodajWpisMaterialow(przycisk.dataset.zapiszWpis, dane.sekcje));
  });
  OBSZAR.querySelectorAll("[data-usun-wpis]").forEach((przycisk) => {
    przycisk.addEventListener("click", () => {
      const [indeksSekcji, indeksWpisu] = przycisk.dataset.usunWpis.split(":").map(Number);
      const sekcja = dane.sekcje[indeksSekcji];
      stanMaterialow[sekcja].splice(indeksWpisu, 1);
      zapiszMaterialy();
    });
  });

  wczytajArtykuly();
}

// Wgrane artykuły i dokumenty źródłowe. Leżą w katalogu danych, więc
// przeżywają restart aplikacji i jadą razem z folderem na inny komputer.
// Nie są przypisane do miesiąca — asystent korzysta z nich niezależnie
// od tego, który miesiąc jest wybrany.
async function wczytajArtykuly() {
  const kontener = document.getElementById("sekcja-artykulow");
  if (!kontener) return;

  let dane;
  try {
    const odpowiedz = await fetch("/api/artykuly");
    if (!odpowiedz.ok) throw new Error(`HTTP ${odpowiedz.status}`);
    dane = await odpowiedz.json();
  } catch {
    kontener.innerHTML = "";
    return;
  }

  const lista = dane.artykuly.length
    ? dane.artykuly
        .map(
          (wpis) => `
          <li>
            <div>
              ${escapeHtml(wpis.plik)}
              <span class="szczegoly">${wpis.rozmiar_kb} KB${wpis.czytelny ? "" : " · asystent tego nie odczyta"}</span>
              ${wpis.ma_wyciag ? `<span class="odznaka-wybrany">przeczytany</span>` : ""}
              <div class="szczegoly">${
                wpis.ma_wyciag
                  ? "Asystent korzysta z tego dokumentu przy planowaniu i pisaniu."
                  : "Asystent jeszcze go nie przeczytał — kliknij „Przeczytaj”."
              }</div>
              <div class="wyciag-dokumentu" data-wyciag-dla="${escapeHtml(wpis.plik)}" hidden></div>
            </div>
            <div class="pasek-narzedzi" style="margin:0">
              ${
                wpis.czytelny
                  ? `<button class="przycisk-drugorzedny maly" data-przeczytaj-artykul="${escapeHtml(wpis.plik)}">${wpis.ma_wyciag ? "Przeczytaj od nowa" : "Przeczytaj"}</button>`
                  : ""
              }
              ${
                wpis.ma_wyciag
                  ? `<button class="przycisk-drugorzedny maly" data-pokaz-wyciag="${escapeHtml(wpis.plik)}">Co z tego wynika</button>`
                  : ""
              }
              <button class="przycisk-drugorzedny maly" data-usun-artykul="${escapeHtml(wpis.plik)}">usuń</button>
            </div>
          </li>`
        )
        .join("")
    : `<li class="placeholder">Nie wgrano jeszcze żadnych dokumentów.</li>`;

  kontener.innerHTML = `
    <div class="karta">
      <strong>Artykuły i dokumenty</strong>
      <p class="szczegoly">
        Wgraj artykuły, raporty albo notatki. Zostają na stałe — nie trzeba
        wgrywać ich ponownie po zamknięciu aplikacji. Obsługiwane: PDF, TXT,
        MD, CSV, HTML (plik z Worda zapisz najpierw jako PDF).
      </p>
      <p class="szczegoly">
        <strong>Jak to działa:</strong> po wgraniu kliknij „Przeczytaj”.
        Asystent przechodzi dokument raz i wypisuje z niego fakty, liczby
        i tematy na posty. Od tej pory korzysta z tego przy planowaniu miesiąca
        i przy pisaniu — bez wracania do całego pliku. Czytanie jest płatne,
        dlatego dzieje się na kliknięcie, a nie samo z siebie; wielostronicowy
        raport to zwykle kilkadziesiąt centów, jednorazowo.
      </p>
      <ul class="lista-materialow">${lista}</ul>
      <div class="pasek-narzedzi" style="margin:0.75rem 0 0">
        <input type="file" id="plik-artykulu" accept=".pdf,.txt,.md,.csv,.html,.htm">
        <button class="przycisk-drugorzedny" id="przycisk-wgraj-artykul">Wgraj dokument</button>
        <span id="status-artykulu" class="szczegoly"></span>
      </div>
    </div>
  `;

  document.getElementById("przycisk-wgraj-artykul").addEventListener("click", wgrajArtykul);
  kontener.querySelectorAll("[data-usun-artykul]").forEach((przycisk) => {
    przycisk.addEventListener("click", async () => {
      if (!confirm(`Usunąć „${przycisk.dataset.usunArtykul}"?`)) return;
      await fetch(`/api/artykuly/${encodeURIComponent(przycisk.dataset.usunArtykul)}`, { method: "DELETE" });
      wczytajArtykuly();
    });
  });
  kontener.querySelectorAll("[data-przeczytaj-artykul]").forEach((przycisk) => {
    przycisk.addEventListener("click", () => przeczytajArtykul(przycisk));
  });
  kontener.querySelectorAll("[data-pokaz-wyciag]").forEach((przycisk) => {
    przycisk.addEventListener("click", () => pokazWyciag(przycisk));
  });
}

// Jednorazowe przeczytanie dokumentu. Wyciąg zapisuje backend, więc przerwane
// czytanie nie zostawia operatorki z niczym poza komunikatem.
async function przeczytajArtykul(przycisk) {
  const nazwa = przycisk.dataset.przeczytajArtykul;
  const obszar = document.querySelector(`[data-wyciag-dla="${CSS.escape(nazwa)}"]`);
  const oryginalnyTekst = przycisk.textContent;
  przycisk.disabled = true;
  przycisk.textContent = "Czytam…";
  obszar.hidden = false;
  obszar.innerHTML = `<div class="log-przebiegu"><div class="wpis">Czytam dokument…</div></div>`;

  let odpowiedz;
  try {
    odpowiedz = await fetch(`/api/artykuly/${encodeURIComponent(nazwa)}/wyciag`, { method: "POST" });
  } catch (blad) {
    obszar.innerHTML = `<p class="instrukcja-naprawy">Nie udało się połączyć z serwerem (${escapeHtml(blad.message)}).</p>`;
    przycisk.disabled = false;
    przycisk.textContent = oryginalnyTekst;
    return;
  }

  if ((odpowiedz.headers.get("content-type") || "").includes("application/json")) {
    const dane = await odpowiedz.json();
    obszar.innerHTML = `<p class="instrukcja-naprawy">${escapeHtml(dane.blad || "Nie udało się przeczytać dokumentu.")}</p>`;
    przycisk.disabled = false;
    przycisk.textContent = oryginalnyTekst;
    return;
  }

  await strumieniujSSE(odpowiedz, (zdarzenie) => {
    if (zdarzenie.typ === "status") {
      obszar.innerHTML = `<div class="log-przebiegu"><div class="wpis">${escapeHtml(zdarzenie.tekst)}</div></div>`;
    } else if (zdarzenie.typ === "blad") {
      obszar.innerHTML = `<p class="instrukcja-naprawy">${escapeHtml(zdarzenie.tekst)}</p>`;
    } else if (zdarzenie.typ === "wynik") {
      dopiszKoszt(zdarzenie.koszt_usd);
      przycisk.disabled = false;
      przycisk.textContent = oryginalnyTekst;
      if (zdarzenie.blad_wyciagu) {
        obszar.innerHTML = `<p class="instrukcja-naprawy">${escapeHtml(zdarzenie.blad_wyciagu)}</p>`;
      } else {
        obszar.innerHTML = `<div class="karta">${prostyMarkdown(zdarzenie.wyciag)}</div>`;
        wczytajArtykuly();
      }
    }
  });
}

async function pokazWyciag(przycisk) {
  const nazwa = przycisk.dataset.pokazWyciag;
  const obszar = document.querySelector(`[data-wyciag-dla="${CSS.escape(nazwa)}"]`);
  if (!obszar.hidden) {
    obszar.hidden = true;
    return;
  }
  obszar.hidden = false;
  obszar.innerHTML = `<p class="placeholder">Wczytuję…</p>`;
  try {
    const odpowiedz = await fetch(`/api/artykuly/${encodeURIComponent(nazwa)}/wyciag`);
    const dane = await odpowiedz.json();
    obszar.innerHTML = odpowiedz.ok
      ? `<div class="karta">${prostyMarkdown(dane.wyciag)}</div>`
      : `<p class="instrukcja-naprawy">${escapeHtml(dane.blad)}</p>`;
  } catch (blad) {
    obszar.innerHTML = `<p class="instrukcja-naprawy">Nie udało się wczytać (${escapeHtml(blad.message)}).</p>`;
  }
}

async function wgrajArtykul() {
  const wejscie = document.getElementById("plik-artykulu");
  const status = document.getElementById("status-artykulu");
  if (!wejscie.files.length) {
    status.innerHTML = `<span class="instrukcja-naprawy">Najpierw wybierz plik z dysku.</span>`;
    return;
  }

  status.textContent = "Wgrywam…";
  const formularz = new FormData();
  formularz.append("plik", wejscie.files[0]);

  try {
    const odpowiedz = await fetch("/api/artykuly", { method: "POST", body: formularz });
    const dane = await odpowiedz.json();
    if (!odpowiedz.ok) throw new Error(dane.blad || `HTTP ${odpowiedz.status}`);
    wczytajArtykuly();
  } catch (blad) {
    status.innerHTML = `<span class="instrukcja-naprawy">${escapeHtml(blad.message)}</span>`;
  }
}

function dodajWpisMaterialow(indeksSekcji, sekcje) {
  const formularz = OBSZAR.querySelector(`[data-formularz-dla="${indeksSekcji}"]`);
  const tekst = formularz.querySelector(".pole-wpisu").value.trim();
  if (!tekst) return;
  const sekcja = sekcje[Number(indeksSekcji)];
  stanMaterialow[sekcja] = [...(stanMaterialow[sekcja] || []), tekst];
  zapiszMaterialy();
}

async function zapiszMaterialy() {
  const odpowiedz = await fetch(`/api/materialy/${miesiacMaterialow}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ materialy: stanMaterialow }),
  });
  if (!odpowiedz.ok) {
    const dane = await odpowiedz.json();
    alert(dane.blad || "Nie udało się zapisać materiałów.");
    return;
  }
  renderujMaterialy();
}

function pokazProsbeOMaterialy() {
  const tekst =
    `Cześć! Zbieram materiały do postów na ${nazwaMiesiaca(miesiacMaterialow)}.\n\n` +
    "Dajcie znać, czy w tym miesiącu było coś z tych rzeczy:\n" +
    "- start nowego projektu\n" +
    "- zakończenie albo odbiór realizacji\n" +
    "- kamień milowy, certyfikat, szkolenie\n" +
    "- ktoś nowy w zespole albo awans\n" +
    "- udział w wydarzeniu branżowym\n\n" +
    "Jedno zdanie na punkt w zupełności wystarczy — resztę dopiszę sama. Dzięki!";

  const kontener = document.getElementById("prosba-o-materialy");
  kontener.innerHTML = `
    <div class="karta">
      <strong>Gotowa wiadomość do wysłania</strong>
      <p class="szczegoly">Skopiuj i wyślij na WhatsAppie. Aplikacja niczego nie wysyła sama.</p>
      <pre class="monospace" style="white-space:pre-wrap;margin:0.5rem 0">${escapeHtml(tekst)}</pre>
      <button class="przycisk-drugorzedny" id="kopiuj-prosbe">Kopiuj</button>
    </div>
  `;
  document.getElementById("kopiuj-prosbe").addEventListener("click", (zdarzenie) =>
    kopiujDoSchowka(tekst, zdarzenie.target)
  );
}

function przejdzDoZakladki(nazwa) {
  ustawAktywnaZakladke(nazwa);
  window.location.hash = nazwa;
  if (nazwa === "diagnostyka") {
    renderujDiagnostyke();
  } else if (nazwa === "posty") {
    renderujPosty();
  } else if (nazwa === "asystent") {
    renderujAsystenta();
  } else if (nazwa === "styl") {
    renderujStyl();
  } else if (nazwa === "korpus") {
    renderujKorpus();
  } else if (nazwa === "plan") {
    renderujPlan();
  } else if (nazwa === "materialy") {
    renderujMaterialy();
  } else {
    renderujPlaceholder(nazwa);
  }
}

document.querySelectorAll("[data-zakladka]").forEach((el) => {
  el.addEventListener("click", () => przejdzDoZakladki(el.dataset.zakladka));
});

// Bez tego przycisk „wstecz" w przeglądarce zmieniał adres, ale ekran
// zostawał poprzedni — wyglądało to jak zawieszenie aplikacji.
window.addEventListener("hashchange", () => {
  const zZadresu = window.location.hash.replace("#", "") || "asystent";
  const aktywna = document.querySelector("[data-zakladka].aktywna");
  if (aktywna?.dataset.zakladka !== zZadresu) przejdzDoZakladki(zZadresu);
});

const poczatkowaZakladka = window.location.hash.replace("#", "") || "asystent";
przejdzDoZakladki(poczatkowaZakladka);
