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
  const naprawa = sprawdzenie.instrukcja_naprawy
    ? `<div class="instrukcja-naprawy">${sprawdzenie.instrukcja_naprawy}</div>`
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
    </div>
    <div class="karta">${listaSprawdzen}</div>

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

let ostatniWynikRedaktora = null;

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
      <div style="margin-top:0.75rem">
        <button class="przycisk-glowny" id="przycisk-generuj">Generuj</button>
      </div>
      <div class="log-przebiegu" id="log-redaktora" hidden></div>
    </div>
    <div id="wynik-redaktora"></div>
  `;
  document.getElementById("przycisk-generuj").addEventListener("click", uruchomRedaktora);
}

function elementBlokadyNda(fraza) {
  return `
    <div class="karta" style="border-color:var(--blad)">
      <h3 style="margin-top:0;color:var(--blad)">⚠ To polecenie zawiera nazwę objętą NDA</h3>
      <p>Wykryto: „${escapeHtml(fraza)}"</p>
      <p>Nie wysłaliśmy tego do modelu ani do sieci.</p>
      <p><strong>Popraw polecenie albo usuń nazwę klienta.</strong></p>
    </div>
  `;
}

function elementWynikuPosta(post, sciezkaPliku) {
  ostatniWynikRedaktora = post;

  const kartyWariantow = post.warianty
    .map(
      (wariant, indeks) => `
      <div class="karta">
        <div style="display:flex;justify-content:space-between;align-items:baseline">
          <strong>Wariant ${indeks + 1}</strong>
          <span class="szczegoly">${escapeHtml(wariant.etykieta)} · ${wariant.znaki} znaków</span>
        </div>
        <pre class="monospace" style="white-space:pre-wrap;margin:0.5rem 0">${escapeHtml(wariant.tresc)}</pre>
        <button class="przycisk-drugorzedny" data-kopiuj-wariant="${indeks}">Kopiuj</button>
      </div>`
    )
    .join("");

  const brakiHtml = post.braki.length
    ? `<ul>${post.braki.map((brak) => `<li>${escapeHtml(brak)}</li>`).join("")}</ul>`
    : "<p>Brak braków.</p>";

  const niekompletnyHtml = post.kompletny
    ? ""
    : `<p class="instrukcja-naprawy">
        Zapisany plik nie ma wszystkich oczekiwanych sekcji — pokazujemy to, co się dało odczytać.
        Sprawdź surowy plik: ${escapeHtml(sciezkaPliku || "")}
      </p>`;

  return `
    <h3>Warianty</h3>
    ${kartyWariantow}
    <details class="karta">
      <summary><strong>Wersja na Facebooka</strong> <span class="szczegoly">(${post.facebook.length} znaków)</span></summary>
      <pre class="monospace" style="white-space:pre-wrap">${escapeHtml(post.facebook)}</pre>
      <button class="przycisk-drugorzedny" data-kopiuj-facebook>Kopiuj</button>
    </details>
    <div class="karta">
      <strong>Brief graficzny</strong>
      <pre class="monospace" style="white-space:pre-wrap;margin:0.5rem 0">${escapeHtml(post.brief_graficzny)}</pre>
      <button class="przycisk-drugorzedny" data-kopiuj-brief>Kopiuj dla Sikory</button>
    </div>
    <div class="karta" style="border-color:var(--ostrzezenie)">
      <h3 style="margin-top:0;color:var(--ostrzezenie)">Braki</h3>
      ${brakiHtml}
    </div>
    ${niekompletnyHtml}
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

function podepnijPrzyciskiKopiowania() {
  document.querySelectorAll("[data-kopiuj-wariant]").forEach((przycisk) => {
    przycisk.addEventListener("click", () => {
      const indeks = Number(przycisk.dataset.kopiujWariant);
      kopiujDoSchowka(ostatniWynikRedaktora.warianty[indeks].tresc, przycisk);
    });
  });
  const przyciskFb = document.querySelector("[data-kopiuj-facebook]");
  if (przyciskFb) {
    przyciskFb.addEventListener("click", () => kopiujDoSchowka(ostatniWynikRedaktora.facebook, przyciskFb));
  }
  const przyciskBrief = document.querySelector("[data-kopiuj-brief]");
  if (przyciskBrief) {
    przyciskBrief.addEventListener("click", () =>
      kopiujDoSchowka(ostatniWynikRedaktora.brief_graficzny, przyciskBrief)
    );
  }
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
  const przycisk = document.getElementById("przycisk-generuj");
  const log = document.getElementById("log-redaktora");
  const wynik = document.getElementById("wynik-redaktora");
  wynik.innerHTML = "";

  if (!brief) {
    wynik.innerHTML = `<div class="karta"><p class="instrukcja-naprawy">Opisz, o czym ma być post, zanim klikniesz „Generuj".</p></div>`;
    return;
  }

  log.hidden = false;
  log.innerHTML = "";
  przycisk.disabled = true;
  przycisk.textContent = "Generuję…";

  const dopiszWpis = (tekst, klasa = "") => {
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
      body: JSON.stringify({ brief }),
    });
  } catch (blad) {
    dopiszWpis(`Nie udało się połączyć z serwerem (${blad.message}).`, "blad");
    zakoncz();
    return;
  }

  const typTresci = odpowiedz.headers.get("content-type") || "";

  if (typTresci.includes("application/json")) {
    const dane = await odpowiedz.json();
    if (dane.zablokowane_nda) {
      wynik.innerHTML = elementBlokadyNda(dane.fraza);
    } else {
      dopiszWpis(dane.blad || "Nie udało się uruchomić generowania.", "blad");
    }
    zakoncz();
    return;
  }

  await strumieniujSSE(odpowiedz, (dane) => {
    if (dane.typ === "status" || dane.typ === "fragment") {
      dopiszWpis(dane.tekst);
    } else if (dane.typ === "wynik") {
      if (dane.bledny) {
        dopiszWpis("Generowanie zakończyło się błędem.", "blad");
      } else if (dane.post) {
        wynik.innerHTML = elementWynikuPosta(dane.post, dane.sciezka_pliku);
        podepnijPrzyciskiKopiowania();
      } else {
        dopiszWpis("Brak zapisanego pliku wynikowego — sprawdź log powyżej.", "blad");
      }
      zakoncz();
    } else if (dane.typ === "blad") {
      dopiszWpis(dane.tekst, "blad");
      zakoncz();
    }
  });
}

function przejdzDoZakladki(nazwa) {
  ustawAktywnaZakladke(nazwa);
  window.location.hash = nazwa;
  if (nazwa === "diagnostyka") {
    renderujDiagnostyke();
  } else if (nazwa === "posty") {
    renderujPosty();
  } else {
    renderujPlaceholder(nazwa);
  }
}

document.querySelectorAll("[data-zakladka]").forEach((el) => {
  el.addEventListener("click", () => przejdzDoZakladki(el.dataset.zakladka));
});

const poczatkowaZakladka = window.location.hash.replace("#", "") || "asystent";
przejdzDoZakladki(poczatkowaZakladka);
