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

function przejdzDoZakladki(nazwa) {
  ustawAktywnaZakladke(nazwa);
  window.location.hash = nazwa;
  if (nazwa === "diagnostyka") {
    renderujDiagnostyke();
  } else {
    renderujPlaceholder(nazwa);
  }
}

document.querySelectorAll("[data-zakladka]").forEach((el) => {
  el.addEventListener("click", () => przejdzDoZakladki(el.dataset.zakladka));
});

const poczatkowaZakladka = window.location.hash.replace("#", "") || "asystent";
przejdzDoZakladki(poczatkowaZakladka);
