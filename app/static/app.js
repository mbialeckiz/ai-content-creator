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

// Wyniki trzymane po ID, nie jako pojedyncza zmienna "ostatni wynik" — na
// ekranie Asystenta kilka wygenerowanych postów może współistnieć naraz
// w historii czatu, każdy z własnymi przyciskami "Kopiuj".
let licznikWynikowPostow = 0;
const wynikiPostow = {};

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
  const idWyniku = ++licznikWynikowPostow;
  wynikiPostow[idWyniku] = post;

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
    <div data-post-id="${idWyniku}">
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
      body: JSON.stringify({ brief }),
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

// --- Ekran "Asystent" (czat, SPEC-frontend 5) ---

const propozycje = {};
let licznikPropozycji = 0;

function renderujAsystenta() {
  OBSZAR.innerHTML = `
    <h2>Asystent</h2>
    <div class="karta" id="czat-historia" style="min-height:320px;max-height:60vh;overflow-y:auto"></div>
    <form id="czat-formularz" style="display:flex;gap:0.5rem;margin-top:0.75rem">
      <textarea
        id="czat-pole"
        class="monospace"
        rows="2"
        style="flex:1"
        placeholder="Napisz do asystenta, np. „ile mam postów w korpusie" albo „napisz post o…"
      ></textarea>
      <button class="przycisk-glowny" type="submit">Wyślij</button>
    </form>
  `;
  document.getElementById("czat-formularz").addEventListener("submit", (zdarzenie) => {
    zdarzenie.preventDefault();
    wyslijWiadomoscAsystenta();
  });
  document.getElementById("czat-pole").focus();
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
      if (zdarzenie.bledny) {
        dopiszWpis("Generowanie zakończyło się błędem.", "blad");
      } else if (zdarzenie.post) {
        karta.outerHTML = elementWynikuPosta(zdarzenie.post, zdarzenie.sciezka_pliku);
        podepnijPrzyciskiKopiowania();
      } else {
        dopiszWpis("Brak zapisanego pliku wynikowego — sprawdź log powyżej.", "blad");
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

function przejdzDoZakladki(nazwa) {
  ustawAktywnaZakladke(nazwa);
  window.location.hash = nazwa;
  if (nazwa === "diagnostyka") {
    renderujDiagnostyke();
  } else if (nazwa === "posty") {
    renderujPosty();
  } else if (nazwa === "asystent") {
    renderujAsystenta();
  } else {
    renderujPlaceholder(nazwa);
  }
}

document.querySelectorAll("[data-zakladka]").forEach((el) => {
  el.addEventListener("click", () => przejdzDoZakladki(el.dataset.zakladka));
});

const poczatkowaZakladka = window.location.hash.replace("#", "") || "asystent";
przejdzDoZakladki(poczatkowaZakladka);
