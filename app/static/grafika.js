// Rysowanie grafiki do posta. Obraz powstaje w przeglądarce na elemencie
// canvas — podgląd i pobrany plik PNG pochodzą z tego samego kodu, więc nie
// mogą się rozjechać. Nie ma tu żadnej biblioteki: kroje pism biorą się
// z systemu operatorki, a logo przychodzi z serwera jako data URI, żeby
// zapis PNG nie był blokowany przez zabezpieczenia przeglądarki.
//
// Układ odwzorowuje stałe elementy z projektów, które operatorka robi
// w Canvie (paczka wzorów z sierpnia 2026): format pionowy 4:5, adres strony
// u góry, tekst wyśrodkowany, a na dole czarny pasek z wyśrodkowanym logo.
// Na ciemnym tle paska nie ma — logo leży wtedy wprost na tle, tak jak
// w ich infografikach.

const MARGINES = 96;

function zawinTekst(kontekst, tekst, maksSzerokosc) {
  const linie = [];
  // Ręczne łamanie w haśle jest świadomą decyzją operatorki, więc je szanujemy
  // i zawijamy każdy akapit osobno.
  for (const akapit of tekst.split("\n")) {
    if (!akapit.trim()) continue;
    let biezaca = "";
    for (const slowo of akapit.trim().split(/\s+/)) {
      const kandydat = biezaca ? `${biezaca} ${slowo}` : slowo;
      if (kontekst.measureText(kandydat).width > maksSzerokosc && biezaca) {
        linie.push(biezaca);
        biezaca = slowo;
      } else {
        biezaca = kandydat;
      }
    }
    if (biezaca) linie.push(biezaca);
  }
  return linie;
}

// Hasło ma wypełnić kadr niezależnie od długości: zaczynamy od dużego
// stopnia i schodzimy, aż tekst zmieści się w wyznaczonym polu.
function dopasujStopienPisma(kontekst, tekst, krój, maksSzerokosc, maksWysokosc) {
  for (let stopien = 104; stopien >= 34; stopien -= 2) {
    kontekst.font = `700 ${stopien}px ${krój}`;
    const linie = zawinTekst(kontekst, tekst, maksSzerokosc);
    if (linie.length * stopien * 1.22 <= maksWysokosc) return { stopien, linie };
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
  const naCiemnym = dane.wariant_kolorystyczny !== "jasny";
  k.fillStyle = dane.kolory.tlo;
  k.fillRect(0, 0, szerokosc, wysokosc);

  const logo = await wczytajObraz(dane.logo);
  const wysokoscPaska = Math.round(wysokosc * 0.088);

  // Czarny pasek ze znakiem u dołu — element powtarzający się we wszystkich
  // jasnych projektach. Na ciemnym tle byłby niewidoczny, więc go pomijamy.
  const zPaskiem = !naCiemnym && Boolean(logo);
  if (zPaskiem) {
    k.fillStyle = dane.kolory.pasek_stopki || "#111111";
    k.fillRect(0, wysokosc - wysokoscPaska, szerokosc, wysokoscPaska);
  }

  // Adres strony u góry — jest na większości ich projektów i pełni rolę
  // podpisu nadawcy, gdy grafika krąży wyrwana z kontekstu posta.
  let gornaKrawedz = MARGINES;
  if (dane.adres_www) {
    const stopienAdresu = Math.round(wysokosc * 0.026);
    k.font = `400 ${stopienAdresu}px ${dane.kroje.podpis}`;
    k.fillStyle = dane.kolory.tekst;
    k.textAlign = "center";
    k.textBaseline = "top";
    k.globalAlpha = 0.75;
    k.fillText(dane.adres_www, szerokosc / 2, MARGINES * 0.62);
    k.globalAlpha = 1;
    gornaKrawedz = MARGINES * 0.62 + stopienAdresu * 2.4;
  }

  const polePola = szerokosc - MARGINES * 2;
  const dolnaKrawedz = wysokosc - (zPaskiem ? wysokoscPaska : 0) - MARGINES * 1.5;
  const { stopien, linie } = dopasujStopienPisma(
    k, dane.haslo, dane.kroje.naglowek, polePola, (dolnaKrawedz - gornaKrawedz) * 0.7
  );

  const wysokoscLinii = stopien * 1.22;
  const stopienPodtytulu = Math.max(26, Math.round(stopien * 0.36));
  k.font = `400 ${stopienPodtytulu}px ${dane.kroje.podpis}`;
  const liniePodtytulu = dane.podtytul ? zawinTekst(k, dane.podtytul, polePola) : [];
  const wysokoscBloku =
    linie.length * wysokoscLinii +
    (liniePodtytulu.length ? wysokoscLinii * 0.5 + liniePodtytulu.length * stopienPodtytulu * 1.35 : 0);

  // Tekst wyśrodkowany w pionie i w poziomie — tak jak na ich kartach
  // z cytatem i zapowiedzią wydarzenia.
  let y = (gornaKrawedz + dolnaKrawedz) / 2 - wysokoscBloku / 2 + wysokoscLinii / 2;
  k.textAlign = "center";
  k.textBaseline = "middle";
  k.fillStyle = dane.kolory.tekst;
  k.font = `700 ${stopien}px ${dane.kroje.naglowek}`;
  for (const linia of linie) {
    k.fillText(linia, szerokosc / 2, y);
    y += wysokoscLinii;
  }

  if (liniePodtytulu.length) {
    y += wysokoscLinii * 0.5;
    // Podkreślenie akcentem pod hasłem — odpowiednik złotej belki, której
    // używają przy nagłówkach.
    k.strokeStyle = dane.kolory.akcent;
    k.lineWidth = 4;
    k.beginPath();
    k.moveTo(szerokosc / 2 - 54, y - wysokoscLinii * 0.32);
    k.lineTo(szerokosc / 2 + 54, y - wysokoscLinii * 0.32);
    k.stroke();

    k.font = `400 ${stopienPodtytulu}px ${dane.kroje.podpis}`;
    k.globalAlpha = 0.85;
    for (const linia of liniePodtytulu) {
      k.fillText(linia, szerokosc / 2, y);
      y += stopienPodtytulu * 1.35;
    }
    k.globalAlpha = 1;
  }

  if (logo) {
    const wysokoscLogo = zPaskiem
      ? Math.round(wysokoscPaska * 0.42)
      : Math.round(wysokosc * 0.042);
    const szerokoscLogo = (logo.width / logo.height) * wysokoscLogo;
    const xLogo = zPaskiem ? (szerokosc - szerokoscLogo) / 2 : MARGINES;
    const yLogo = zPaskiem
      ? wysokosc - wysokoscPaska / 2 - wysokoscLogo / 2
      : wysokosc - MARGINES * 0.8 - wysokoscLogo;
    k.drawImage(logo, xLogo, yLogo, szerokoscLogo, wysokoscLogo);
  } else {
    // Bez pliku logo zostaje sam napis — grafika ma być podpisana zawsze.
    k.textAlign = "center";
    k.fillStyle = dane.kolory.tekst;
    k.font = `700 ${Math.round(wysokosc * 0.034)}px ${dane.kroje.naglowek}`;
    k.fillText(dane.nazwa_firmy, szerokosc / 2, wysokosc - MARGINES * 0.9);
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
