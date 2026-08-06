// Rysowanie grafiki do posta. Obraz powstaje w przeglądarce na elemencie
// canvas — podgląd i pobrany plik PNG pochodzą z tego samego kodu, więc nie
// mogą się rozjechać. Nie ma tu żadnej biblioteki: kroje pism biorą się
// z systemu operatorki, a logo przychodzi z serwera jako data URI, żeby
// zapis PNG nie był blokowany przez zabezpieczenia przeglądarki.

const MARGINES = 90;

function zawinTekst(kontekst, tekst, maksSzerokosc) {
  const slowa = tekst.split(/\s+/);
  const linie = [];
  let biezaca = "";
  for (const slowo of slowa) {
    const kandydat = biezaca ? `${biezaca} ${slowo}` : slowo;
    if (kontekst.measureText(kandydat).width > maksSzerokosc && biezaca) {
      linie.push(biezaca);
      biezaca = slowo;
    } else {
      biezaca = kandydat;
    }
  }
  if (biezaca) linie.push(biezaca);
  return linie;
}

// Hasło ma wypełnić kadr niezależnie od długości: zaczynamy od dużego
// stopnia i schodzimy, aż tekst zmieści się w wyznaczonym polu.
function dopasujStopienPisma(kontekst, tekst, krój, maksSzerokosc, maksWysokosc) {
  for (let stopien = 96; stopien >= 34; stopien -= 2) {
    kontekst.font = `700 ${stopien}px ${krój}`;
    const linie = zawinTekst(kontekst, tekst, maksSzerokosc);
    const wysokosc = linie.length * stopien * 1.18;
    if (wysokosc <= maksWysokosc) return { stopien, linie };
  }
  kontekst.font = `700 34px ${krój}`;
  return { stopien: 34, linie: zawinTekst(kontekst, tekst, maksSzerokosc) };
}

async function wczytajObraz(zrodlo) {
  if (!zrodlo) return null;
  return new Promise((gotowe) => {
    const obraz = new Image();
    obraz.onload = () => gotowe(obraz);
    obraz.onerror = () => gotowe(null);
    obraz.src = zrodlo;
  });
}

async function narysujGrafike(canvas, dane) {
  const szerokosc = dane.format.szerokosc;
  const wysokosc = dane.format.wysokosc;
  canvas.width = szerokosc;
  canvas.height = wysokosc;

  const k = canvas.getContext("2d");
  k.fillStyle = dane.kolory.tlo;
  k.fillRect(0, 0, szerokosc, wysokosc);

  // Pasek akcentu przy lewej krawędzi — jedyny element dekoracyjny,
  // pozwala rozpoznać grafikę jako Waszą bez czytania.
  k.fillStyle = dane.kolory.akcent;
  k.fillRect(0, 0, 14, wysokosc);

  const polePola = szerokosc - MARGINES * 2 - 14;
  const gornaKrawedz = MARGINES;
  const dolnaKrawedz = wysokosc - MARGINES - 110; // nad stopką z logo
  const { stopien, linie } = dopasujStopienPisma(
    k, dane.haslo, dane.kroje.naglowek, polePola, (dolnaKrawedz - gornaKrawedz) * 0.72
  );

  // Blok hasła i podtytułu wyśrodkowany optycznie między górną krawędzią
  // a stopką — inaczej przy krótkim haśle w środku kadru zostawała dziura.
  const wysokoscLinii = stopien * 1.18;
  const stopienPodtytulu = Math.max(24, Math.round(stopien * 0.38));
  const liniePodtytulu = dane.podtytul
    ? (k.font = `400 ${stopienPodtytulu}px ${dane.kroje.podpis}`, zawinTekst(k, dane.podtytul, polePola))
    : [];
  const wysokoscBloku =
    linie.length * wysokoscLinii +
    (liniePodtytulu.length ? wysokoscLinii * 0.35 + liniePodtytulu.length * stopienPodtytulu * 1.3 : 0);

  let y = (gornaKrawedz + dolnaKrawedz) / 2 - wysokoscBloku / 2 + wysokoscLinii / 2;

  k.fillStyle = dane.kolory.tekst;
  k.textBaseline = "middle";
  k.font = `700 ${stopien}px ${dane.kroje.naglowek}`;
  for (const linia of linie) {
    k.fillText(linia, MARGINES + 14, y);
    y += wysokoscLinii;
  }

  if (liniePodtytulu.length) {
    k.font = `400 ${stopienPodtytulu}px ${dane.kroje.podpis}`;
    k.globalAlpha = 0.82;
    y += wysokoscLinii * 0.35;
    for (const linia of liniePodtytulu) {
      k.fillText(linia, MARGINES + 14, y);
      y += stopienPodtytulu * 1.3;
    }
    k.globalAlpha = 1;
  }

  const yStopki = wysokosc - MARGINES;
  const logo = await wczytajObraz(dane.logo);

  // Kreska nad stopką oddziela hasło od identyfikacji nadawcy. Rysujemy ją
  // dopiero po wczytaniu logo, bo jej wysokość zależy od wysokości znaku —
  // wcześniej stała na sztywno i przy szerokim logotypie na niego nachodziła.
  const wysokoscLogo = logo ? dane.wysokosc_logo : 56;
  k.strokeStyle = dane.kolory.akcent;
  k.lineWidth = 3;
  k.beginPath();
  k.moveTo(MARGINES + 14, yStopki - wysokoscLogo - 34);
  k.lineTo(MARGINES + 14 + 96, yStopki - wysokoscLogo - 34);
  k.stroke();

  if (logo) {
    const szerokoscLogo = (logo.width / logo.height) * wysokoscLogo;
    k.drawImage(logo, MARGINES + 14, yStopki - wysokoscLogo, szerokoscLogo, wysokoscLogo);
  } else {
    k.fillStyle = dane.kolory.tekst;
    k.font = `700 34px ${dane.kroje.naglowek}`;
    k.fillText(dane.nazwa_firmy, MARGINES + 14, yStopki - 22);
    if (dane.podpis) {
      k.globalAlpha = 0.7;
      k.font = `400 22px ${dane.kroje.podpis}`;
      k.fillText(dane.podpis, MARGINES + 14, yStopki + 12);
      k.globalAlpha = 1;
    }
  }
}

function pobierzGrafike(canvas, nazwa) {
  canvas.toBlob((blob) => {
    const adres = URL.createObjectURL(blob);
    const odnosnik = document.createElement("a");
    odnosnik.href = adres;
    odnosnik.download = nazwa;
    odnosnik.click();
    URL.revokeObjectURL(adres);
  }, "image/png");
}
