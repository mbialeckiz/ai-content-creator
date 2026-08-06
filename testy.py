"""Testy aplikacji — uruchom: `.venv/bin/python testy.py`

Sprawdzają kryteria akceptacji z SPEC sekcja 11, które da się zweryfikować
**bez wywołania modelu**. Dlatego uruchomienie tego pliku nic nie kosztuje
i można je powtarzać po każdej zmianie.

Świadomie poza zakresem (wymagają realnego wywołania modelu, płatne):
jakość tekstu, kalibracja na korpusie, faktyczna odmowa modelu.
Tu sprawdzamy, że *mechanizmy* wokół modelu działają.
"""

import asyncio
import inspect
import json
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app import korpus, main, pliki, silnik  # noqa: E402

POST_PELNY = """## Wariant 1
**Podejście:** faktograficzny
Fit-out data center nie wybacza poslizgow w harmonogramie.

## Wariant 2
**Podejście:** przez problem
Najwiecej czasu na budowie zjadaja poprawki, nie sama praca.

## Wariant 3
**Podejście:** przez osobe
Site Manager wchodzi na obiekt razem z zespolem, nie po tygodniu.

## Facebook
Krotsza wersja tego samego, luzniejszym tonem.

## Brief graficzny
**Co ma przedstawiac:** os czasu z dwoma etapami.

## Braki
- [DO UZUPELNIENIA] konkretna liczba dni oszczednosci
"""

_wyniki: list[tuple[str, bool, str]] = []


def sprawdz(nazwa: str, warunek: bool, szczegol: str = "") -> None:
    _wyniki.append((nazwa, bool(warunek), szczegol))


def katalog_testowy() -> Path:
    """Świeży katalog danych o strukturze takiej, jak `dane/`."""
    katalog = Path(tempfile.mkdtemp(prefix="studio-test-"))
    for podkatalog in ("output", "plan", "korpus", "baza-wiedzy", "skille", "input-firmowy"):
        (katalog / podkatalog).mkdir(parents=True)
    return katalog


# --- Bezpieczeństwo (SPEC 11, sekcja twarda) ---


def test_zamknieta_lista_narzedzi() -> None:
    sprawdz(
        "Bash i Edit nieobecne w dozwolonych narzędziach",
        "Bash" not in silnik.DOZWOLONE_NARZEDZIA and "Edit" not in silnik.DOZWOLONE_NARZEDZIA,
        f"lista: {silnik.DOZWOLONE_NARZEDZIA}",
    )
    opcje = silnik.zbuduj_opcje(katalog_testowy(), "test")
    dozwolone = list(getattr(opcje, "allowed_tools", []) or [])
    sprawdz(
        "zbudowane opcje SDK też nie zawierają Bash/Edit",
        "Bash" not in dozwolone and "Edit" not in dozwolone,
        f"allowed_tools: {dozwolone}",
    )
    sprawdz(
        "sufit kosztu jest ustawiony w opcjach SDK",
        getattr(opcje, "max_budget_usd", None),
        f"max_budget_usd={getattr(opcje, 'max_budget_usd', None)}",
    )


def test_zapis_tylko_w_plan_i_output() -> None:
    katalog = katalog_testowy()
    zezwalacz = silnik._zbuduj_zezwalacz(katalog)

    async def zapytaj(sciezka: str):
        return await zezwalacz("Write", {"file_path": sciezka}, None)

    dozwolony = asyncio.run(zapytaj(str(katalog / "output" / "post.md")))
    plan = asyncio.run(zapytaj(str(katalog / "plan" / "2026-08.md")))
    korpus_zapis = asyncio.run(zapytaj(str(katalog / "korpus" / "podmieniony.md")))
    poza = asyncio.run(zapytaj("/etc/passwd"))
    wyjscie_w_gore = asyncio.run(zapytaj(str(katalog / "output" / ".." / ".." / "gdzies.md")))
    inne_narzedzie = asyncio.run(zezwalacz("Bash", {"command": "ls"}, None))

    nazwa_klasy = lambda w: type(w).__name__  # noqa: E731
    sprawdz("zapis do output/ dozwolony", nazwa_klasy(dozwolony) == "PermissionResultAllow")
    sprawdz("zapis do plan/ dozwolony", nazwa_klasy(plan) == "PermissionResultAllow")
    sprawdz("zapis do korpus/ zablokowany", nazwa_klasy(korpus_zapis) == "PermissionResultDeny")
    sprawdz("zapis poza katalog danych zablokowany", nazwa_klasy(poza) == "PermissionResultDeny")
    sprawdz("wyjście przez .. zablokowane", nazwa_klasy(wyjscie_w_gore) == "PermissionResultDeny")
    sprawdz("Bash odrzucony przez zezwalacz", nazwa_klasy(inne_narzedzie) == "PermissionResultDeny")


def test_blokada_nda() -> None:
    katalog = katalog_testowy()
    (katalog / "baza-wiedzy" / "forces-dc-fakty.md").write_text(
        "## Czego NIE wolno publikować\n\n- **Hyperscaler Nordics AS** — przykład\n",
        encoding="utf-8",
    )
    trafienie = pliki.wykryj_fraze_nda(
        "Napisz post o wdrożeniu dla hyperscaler nordics as w Oslo", katalog
    )
    czysty = pliki.wykryj_fraze_nda("Napisz post o przygotowaniu zespołu monterów", katalog)
    sprawdz("brief z nazwą objętą NDA wykryty", trafienie is not None, f"trafienie: {trafienie}")
    sprawdz("wykrywanie ignoruje wielkość liter", trafienie == "Hyperscaler Nordics AS")
    sprawdz("zwykły brief przechodzi", czysty is None)


# --- Odczyt i zapis postów ---


def test_odczyt_posta() -> None:
    katalog = katalog_testowy()
    sciezka = katalog / "output" / "2026-08-04_test.md"
    sciezka.write_text(POST_PELNY, encoding="utf-8")
    post = pliki.wczytaj_wygenerowany_post(sciezka)

    sprawdz("odczytano 3 warianty", len(post.warianty) == 3, f"jest {len(post.warianty)}")
    sprawdz("etykiety podejść odczytane", post.warianty[0].etykieta == "faktograficzny")
    sprawdz("etykieta nie zostaje w treści", "Podejście" not in post.warianty[0].tresc)
    sprawdz("wersja na Facebooka odczytana", post.facebook.startswith("Krotsza"))
    sprawdz("brief graficzny odczytany", "os czasu" in post.brief_graficzny)
    sprawdz("braki odczytane", len(post.braki) == 1, f"braki: {post.braki}")
    sprawdz("plik uznany za kompletny", post.kompletny)
    sprawdz("bez wyboru wariantu na starcie", post.wybrany is None)


def test_niekompletny_post_nie_wysypuje_odczytu() -> None:
    katalog = katalog_testowy()
    sciezka = katalog / "output" / "urwany.md"
    sciezka.write_text("## Wariant 1\nTekst urwany w po", encoding="utf-8")
    post = pliki.wczytaj_wygenerowany_post(sciezka)
    sprawdz("urwany plik daje 1 wariant zamiast wyjątku", len(post.warianty) == 1)
    sprawdz("urwany plik oznaczony jako niekompletny", not post.kompletny)


def test_wybrany_wariant() -> None:
    katalog = katalog_testowy()
    sciezka = katalog / "output" / "2026-08-04_wybor.md"
    sciezka.write_text(POST_PELNY, encoding="utf-8")

    pliki.oznacz_wybrany_wariant(sciezka, 1)
    po_wyborze = pliki.wczytaj_wygenerowany_post(sciezka)
    sprawdz("wybór zapisany i odczytany", po_wyborze.wybrany == 1, f"wybrany={po_wyborze.wybrany}")
    sprawdz("wybór nie psuje pozostałych sekcji", len(po_wyborze.warianty) == 3 and po_wyborze.kompletny)
    sprawdz(
        "wybór widoczny w pliku po polsku",
        "## Wybrany wariant" in sciezka.read_text(encoding="utf-8"),
    )

    pliki.oznacz_wybrany_wariant(sciezka, 2)
    sprawdz("zmiana wyboru nie dubluje sekcji",
            sciezka.read_text(encoding="utf-8").count("## Wybrany wariant") == 1)
    sprawdz("zmiana wyboru odczytana", pliki.wczytaj_wygenerowany_post(sciezka).wybrany == 2)

    pliki.oznacz_wybrany_wariant(sciezka, None)
    sprawdz("odznaczenie kasuje wybór", pliki.wczytaj_wygenerowany_post(sciezka).wybrany is None)
    sprawdz("odznaczenie zostawia post kompletny",
            pliki.wczytaj_wygenerowany_post(sciezka).kompletny)

    # Numer spoza zakresu może wpisać operatorka, edytując plik ręcznie.
    sciezka.write_text(POST_PELNY + "\n## Wybrany wariant\nWariant 9\n", encoding="utf-8")
    sprawdz("zły numer wariantu w pliku jest ignorowany",
            pliki.wczytaj_wygenerowany_post(sciezka).wybrany is None)


def test_poprawka_wariantu_zachowuje_wybor() -> None:
    katalog = katalog_testowy()
    sciezka = katalog / "output" / "2026-08-04_poprawka.md"
    sciezka.write_text(POST_PELNY, encoding="utf-8")
    pliki.oznacz_wybrany_wariant(sciezka, 0)
    pliki.podmien_wariant(sciezka, 0, "Zupelnie nowa tresc pierwszego wariantu.")

    post = pliki.wczytaj_wygenerowany_post(sciezka)
    sprawdz("poprawka podmieniła treść", post.warianty[0].tresc.startswith("Zupelnie nowa"))
    sprawdz("poprawka zostawiła etykietę", post.warianty[0].etykieta == "faktograficzny")
    sprawdz("poprawka nie ruszyła pozostałych wariantów",
            post.warianty[1].tresc.startswith("Najwiecej"))
    sprawdz("poprawka nie skasowała wyboru", post.wybrany == 0)
    sprawdz("poprawka nie skasowała Facebooka i briefu",
            post.facebook and post.brief_graficzny and post.kompletny)


def test_lista_postow() -> None:
    katalog = katalog_testowy()
    (katalog / "output" / "2026-08-01_starszy.md").write_text(POST_PELNY, encoding="utf-8")
    nowszy = katalog / "output" / "2026-08-04_nowszy.md"
    nowszy.write_text(POST_PELNY, encoding="utf-8")
    pliki.oznacz_wybrany_wariant(nowszy, 2)

    lista = pliki.lista_wygenerowanych_postow(katalog)
    sprawdz("lista ma oba posty", len(lista) == 2, f"jest {len(lista)}")
    sprawdz("najnowszy pierwszy", lista[0]["plik"] == "2026-08-04_nowszy.md")
    sprawdz("lista niesie informację o wyborze", lista[0]["wybrany"] == 2)
    sprawdz("podgląd pokazuje wybrany wariant", lista[0]["podglad"].startswith("Site Manager"))
    sprawdz("bez wyboru podgląd pokazuje pierwszy wariant",
            lista[1]["podglad"].startswith("Fit-out"))


# --- Przerwane generowanie nie przepada (zgłoszenie klienta) ---


def test_przerwane_generowanie_zapisuje_czesc() -> None:
    katalog = katalog_testowy()
    urwany = POST_PELNY[: POST_PELNY.index("## Facebook")]

    async def falszywy_redaktor(_katalog, _brief, _material=""):
        for linia in urwany.splitlines():
            yield {"typ": "fragment", "tekst": linia + "\n"}
        yield {"typ": "blad", "tekst": "Przerwano — limit kosztu."}
        yield {"typ": "wynik", "bledny": False, "tury": 1, "koszt_usd": 0.62,
               "uzycie": {}, "sciezka_pliku": None}

    pierwotny_katalog, pierwotny_redaktor = main.katalog_danych, silnik.uruchom_redaktor
    main.katalog_danych = lambda: katalog
    silnik.uruchom_redaktor = falszywy_redaktor
    try:
        zdarzenia = asyncio.run(_zbierz_sse(main._strumien_redaktora("Przygotowanie zespolu")))
    finally:
        main.katalog_danych, silnik.uruchom_redaktor = pierwotny_katalog, pierwotny_redaktor

    wynik = [z for z in zdarzenia if z["typ"] == "wynik"][0]
    zapisane = list((katalog / "output").glob("*.md"))
    sprawdz("przerwanie zgłoszone operatorce", any(z["typ"] == "blad" for z in zdarzenia))
    sprawdz("mimo przerwania plik zapisany", len(zapisane) == 1, f"plików: {len(zapisane)}")
    sprawdz("odczytano to, co zdążyło powstać", wynik.get("post") and len(wynik["post"]["warianty"]) == 3)
    sprawdz("wynik oznaczony jako częściowy", wynik.get("czesciowy") is True)


def test_material_zrodlowy_od_operatora() -> None:
    katalog = katalog_testowy()
    sprawdz("puste pole nie dokłada nic do polecenia",
            pliki.zbuduj_blok_materialu_zrodlowego("   \n  ") == "")

    krotki = pliki.zbuduj_blok_materialu_zrodlowego("Norweskie centra danych rosna o 20% rocznie.")
    sprawdz("wklejony fragment trafia do polecenia", "rosna o 20% rocznie" in krotki)
    sprawdz("fragment jest opisany dla modelu", "Materiał źródłowy od operatora" in krotki)
    sprawdz("model dostaje zakaz dopisywania liczb", "nie dopisuj liczb" in krotki)

    dlugi = pliki.zbuduj_blok_materialu_zrodlowego("slowo " * 5000)
    sprawdz("zbyt długi materiał jest przycięty",
            len(dlugi) < 6000 + pliki.LIMIT_ZNAKOW_MATERIALU,
            f"długość bloku: {len(dlugi)}")
    sprawdz("przycięcie jest zgłoszone modelowi", "został przycięty" in dlugi)

    # Materiał musi trafić do tej samej paczki, co zasady stylu i korpus.
    calosc = pliki.zbuduj_material_dla_redaktora(katalog, material_zrodlowy="Raport NDI 2026.")
    sprawdz("materiał wchodzi do paczki dla redaktora", "Raport NDI 2026." in calosc)
    bez = pliki.zbuduj_material_dla_redaktora(katalog)
    sprawdz("bez wklejonego materiału paczka go nie zawiera",
            "Materiał źródłowy od operatora" not in bez)


PLAN_NOWY = """# Plan na 2026-09

| # | Data | Typ | Temat | Kąt ujęcia | Źródło | Do potwierdzenia | Status |
|---|---|---|---|---|---|---|---|
| 1 | 2026-09-03 | branzowy | Waskie gardlo branzy | Moc rosnie o 18%, ale brakuje ekip — pokazac od strony czasu montazu. | NDI, digi.no | | szkic |
| 2 | 2026-09-12 | realizacja | Odbior w regionie Oslo | Pokazac, ile trwalo od wejscia na plac. | materialy z firmy | liczba dni | szkic |

## Ustalenia z researchu

- Moc zainstalowana: 410 MW, +18% rok do roku (datasenterindustrien.no).
- Konferencja NDI w Trondheim, wrzesien 2026.

## Pytania do firmy

- Ile osob pracowalo przy odbiorze w lipcu i ile to trwalo od wejscia na plac?
- Czy ktos z zespolu jedzie na konferencje NDI we wrzesniu?

## Zapas tematów

- Czym rozni sie fit-out data center od zwyklej budowy — trzy rzeczy.
- Jakie uprawnienia realnie musi miec monter na obiekcie DC.

## Czego zabrakło

- Brak danych o wrzesniowych startach projektow.
"""

PLAN_STARY = """# Plan na 2026-07

| # | Data | Typ | Temat | Źródło | Do potwierdzenia | Status |
|---|---|---|---|---|---|---|
| 1 | 2026-07-03 | branzowy | Stary format planu | NDI | | szkic |

## Czego zabrakło

Brak uwag.
"""


def test_plan_niesie_prace_stratega() -> None:
    katalog = katalog_testowy()
    (katalog / "plan").mkdir(parents=True, exist_ok=True)
    (katalog / "plan" / "2026-09.md").write_text(PLAN_NOWY, encoding="utf-8")

    plan = pliki.wczytaj_plan(katalog, "2026-09")
    sprawdz("plan ma obie pozycje", len(plan.pozycje) == 2, f"jest {len(plan.pozycje)}")
    sprawdz("kąt ujęcia jest odczytany",
            plan.pozycje[0].kat_ujecia.startswith("Moc rosnie o 18%"),
            plan.pozycje[0].kat_ujecia)
    sprawdz("ustalenia z researchu są odczytane", "410 MW" in plan.ustalenia)
    sprawdz("pytania do firmy są odczytane jako lista",
            len(plan.pytania_do_firmy) == 2, f"jest {len(plan.pytania_do_firmy)}")
    sprawdz("zapas tematów jest odczytany", len(plan.zapas_tematow) == 2)
    sprawdz("czego zabrakło nadal działa", len(plan.czego_zabraklo) == 1)
    sprawdz("temat nie wchłonął kąta ujęcia", plan.pozycje[0].temat == "Waskie gardlo branzy")


def test_stary_plan_nadal_sie_wczytuje() -> None:
    """Plany zbudowane przed dodaniem kolumny „Kąt ujęcia" mają dalej działać."""
    katalog = katalog_testowy()
    (katalog / "plan").mkdir(parents=True, exist_ok=True)
    (katalog / "plan" / "2026-07.md").write_text(PLAN_STARY, encoding="utf-8")

    plan = pliki.wczytaj_plan(katalog, "2026-07")
    sprawdz("stary plan się wczytuje", plan.istnieje and len(plan.pozycje) == 1)
    sprawdz("stary plan ma poprawny temat", plan.pozycje[0].temat == "Stary format planu")
    sprawdz("stary plan ma poprawne źródło", plan.pozycje[0].zrodlo == "NDI")
    sprawdz("brakujący kąt ujęcia zostaje pusty", plan.pozycje[0].kat_ujecia == "")
    sprawdz("brak nowych sekcji nie psuje odczytu",
            plan.ustalenia == "" and plan.pytania_do_firmy == [])


def test_zmiana_statusu_nie_gubi_pracy_stratega() -> None:
    """Zmiana statusu przepisuje cały plik — nie może przy tym skasować
    ustaleń, pytań ani kątów ujęcia."""
    katalog = katalog_testowy()
    (katalog / "plan").mkdir(parents=True, exist_ok=True)
    (katalog / "plan" / "2026-09.md").write_text(PLAN_NOWY, encoding="utf-8")

    pliki.zmien_status_pozycji(katalog, "2026-09", 0, "zatwierdzony")
    plan = pliki.wczytaj_plan(katalog, "2026-09")

    sprawdz("status się zmienił", plan.pozycje[0].status == "zatwierdzony")
    sprawdz("ustalenia przetrwały zmianę statusu", "410 MW" in plan.ustalenia)
    sprawdz("pytania przetrwały zmianę statusu", len(plan.pytania_do_firmy) == 2)
    sprawdz("zapas przetrwał zmianę statusu", len(plan.zapas_tematow) == 2)
    sprawdz("kąt ujęcia przetrwał zmianę statusu",
            plan.pozycje[0].kat_ujecia.startswith("Moc rosnie o 18%"))
    sprawdz("czego zabrakło przetrwało zmianę statusu", len(plan.czego_zabraklo) == 1)


def test_reczna_poprawka_wariantu() -> None:
    from fastapi.testclient import TestClient

    katalog = katalog_testowy()
    sciezka = katalog / "output" / "2026-08-04_reczna.md"
    sciezka.write_text(POST_PELNY, encoding="utf-8")
    pliki.oznacz_wybrany_wariant(sciezka, 0)

    pierwotny = main.katalog_danych
    main.katalog_danych = lambda: katalog
    try:
        klient = TestClient(main.app)
        ok = klient.put(
            "/api/posty/wariant",
            json={"plik": sciezka.name, "indeks": 0, "tresc": "Poprawiona recznie tresc."},
        )
        pusta = klient.put(
            "/api/posty/wariant", json={"plik": sciezka.name, "indeks": 0, "tresc": "   "}
        )
        nieznany = klient.put(
            "/api/posty/wariant", json={"plik": "nie-ma.md", "indeks": 0, "tresc": "cokolwiek"}
        )
    finally:
        main.katalog_danych = pierwotny

    post = pliki.wczytaj_wygenerowany_post(sciezka)
    sprawdz("ręczna poprawka się zapisuje", ok.status_code == 200)
    sprawdz("zapisana treść jest w pliku", post.warianty[0].tresc == "Poprawiona recznie tresc.")
    sprawdz("ręczna poprawka zostawia etykietę", post.warianty[0].etykieta == "faktograficzny")
    sprawdz("ręczna poprawka nie kasuje wyboru wariantu", post.wybrany == 0)
    sprawdz("ręczna poprawka nie rusza pozostałych sekcji", post.kompletny)
    sprawdz("pusta treść jest odrzucana", pusta.status_code == 400)
    sprawdz("nieistniejący post daje 404", nieznany.status_code == 404)


def test_wywiad_wycina_propozycje_plikow() -> None:
    from app.silnik import ZNACZNIK_KONCA_PROPOZYCJI, ZNACZNIK_POCZATKU_PROPOZYCJI

    odpowiedz = (
        "Dzięki! To wszystko, o co chciałem zapytać.\n\n"
        f"{ZNACZNIK_POCZATKU_PROPOZYCJI}glos-marki ===\n"
        "---\nname: brand-voice\n---\n\n# Głos marki\nPiszemy rzeczowo.\n"
        f"{ZNACZNIK_KONCA_PROPOZYCJI}\n\n"
        f"{ZNACZNIK_POCZATKU_PROPOZYCJI}rodzaje-postow ===\n"
        "---\nname: schematy-postow\n---\n\n# Rodzaje postów\nrealizacja: 900 znaków.\n"
        f"{ZNACZNIK_KONCA_PROPOZYCJI}\n"
    )
    tekst, propozycje = pliki.wytnij_propozycje_wywiadu(odpowiedz)

    sprawdz("obie propozycje wykryte", len(propozycje) == 2, f"jest {len(propozycje)}")
    sprawdz("propozycje trafiają pod właściwe pliki",
            [p["id"] for p in propozycje] == ["glos-marki", "rodzaje-postow"])
    sprawdz("propozycja niesie polską nazwę pliku", propozycje[0]["nazwa"] == "Głos marki")
    sprawdz("treść propozycji jest kompletna", "Piszemy rzeczowo." in propozycje[0]["tresc"])
    sprawdz("znaczniki nie zostają w tekście do czatu",
            ZNACZNIK_POCZATKU_PROPOZYCJI not in tekst and ZNACZNIK_KONCA_PROPOZYCJI not in tekst)
    sprawdz("tekst rozmowy zostaje", "To wszystko, o co chciałem zapytać." in tekst)

    # Nieznany identyfikator nie może podstawić treści pod dowolny plik.
    podszywka = (
        f"{ZNACZNIK_POCZATKU_PROPOZYCJI}../../../etc/passwd ===\nzlosliwa\n"
        f"{ZNACZNIK_KONCA_PROPOZYCJI}"
    )
    _, puste = pliki.wytnij_propozycje_wywiadu(podszywka)
    sprawdz("propozycja pod nieznany plik jest odrzucana", puste == [], f"wyszło: {puste}")

    sprawdz("zwykła odpowiedź nie niesie propozycji",
            pliki.wytnij_propozycje_wywiadu("A jak zwracacie się do czytelnika?")[1] == [])


def test_material_dla_wywiadu() -> None:
    katalog = katalog_testowy()
    material = pliki.zbuduj_material_dla_wywiadu(katalog)
    sprawdz("przy pustym korpusie wywiad jest o tym uprzedzony",
            "KORPUS JEST PUSTY" in material)
    sprawdz("wywiad dostaje obecną treść obu plików",
            "glos-marki" in material and "rodzaje-postow" in material)

    (katalog / SCIEZKA_PYTAN).parent.mkdir(parents=True, exist_ok=True)
    (katalog / SCIEZKA_PYTAN).write_text(
        "1. Kto mówi w postach?\n2. Do kogo mówicie?\n", encoding="utf-8"
    )
    material = pliki.zbuduj_material_dla_wywiadu(katalog)
    sprawdz("pytania są brane z edytowalnego pliku, nie z kodu",
            "Kto mówi w postach?" in material)


SCIEZKA_PYTAN = pliki.SCIEZKA_PYTAN_WYWIADU


def test_wywiad_nie_ma_prawa_zapisu() -> None:
    """SPEC 8.3: agent proponuje treść, ale nie modyfikuje plików sam."""
    opcje = silnik.zbuduj_opcje(
        katalog_testowy(), silnik.PROMPT_WYWIAD, bez_narzedzi=True, limit_usd=0.6
    )
    dozwolone = list(getattr(opcje, "allowed_tools", []) or [])
    sprawdz("wywiad nie dostaje narzędzia Write", "Write" not in dozwolone, f"{dozwolone}")
    sprawdz("wywiad nie dostaje żadnych narzędzi", not dozwolone, f"{dozwolone}")
    sprawdz("prompt wywiadu mówi wprost, że nic nie zapisuje",
            "NICZEGO NIE ZAPISUJESZ" in silnik.PROMPT_WYWIAD)


def test_grafika_odwzorowuje_wzory_z_canvy() -> None:
    from app import grafika

    katalog = katalog_testowy()
    dane = grafika.zbuduj_dane_grafiki(katalog, haslo="Test", wariant_kolorystyczny="jasny")

    proporcja = dane["format"]["wysokosc"] / dane["format"]["szerokosc"]
    sprawdz("grafika jest pionowa 4:5, nie kwadratowa",
            abs(proporcja - 1.25) < 0.01, f"proporcja {proporcja:.3f}")
    sprawdz("adres strony trafia na grafikę", dane["adres_www"] == "www.forces.no")
    sprawdz("pasek stopki ma swój kolor", dane["kolory"]["pasek_stopki"] == "#111111")

    # Logo leży zawsze na ciemnym: na ciemnym tle albo na czarnym pasku.
    (katalog / "logo").mkdir(parents=True, exist_ok=True)
    (katalog / "logo" / "na-ciemnym.svg").write_text("<svg/>", encoding="utf-8")
    (katalog / "logo" / "na-jasnym.svg").write_text("<svg-jasne/>", encoding="utf-8")
    (katalog / "brand-kit.yaml").write_text(
        'logo:\n  plik: "na-jasnym.svg"\n  plik_na_ciemnym: "na-ciemnym.svg"\n',
        encoding="utf-8",
    )
    import base64

    for wariant in ("ciemny", "jasny"):
        dane = grafika.zbuduj_dane_grafiki(katalog, haslo="Test", wariant_kolorystyczny=wariant)
        odkodowane = base64.b64decode(dane["logo"].split(",", 1)[1]).decode()
        sprawdz(f"wariant {wariant} bierze logo na ciemne tło",
                odkodowane == "<svg/>", odkodowane)


def test_wyciagi_z_dokumentow() -> None:
    katalog = katalog_testowy()
    (katalog / "artykuly").mkdir(parents=True, exist_ok=True)
    (katalog / "artykuly" / "raport.pdf").write_bytes(b"%PDF-1.4 udawany plik")

    lista = pliki.lista_artykulow(katalog)
    sprawdz("wgrany dokument jest na liście", len(lista) == 1, f"jest {len(lista)}")
    sprawdz("dokument bez wyciągu jest tak oznaczony", lista[0]["ma_wyciag"] is False)
    sprawdz("brak wyciągu nie dokłada nic do paczki dla redaktora",
            "Wyciągi z wgranych dokumentów" not in pliki.zbuduj_material_dla_redaktora(katalog))

    pliki.zapisz_wyciag(
        katalog, "raport.pdf",
        "## Fakty i liczby\n- Norweskie centra danych: +18% mocy w 2025.\n",
    )
    lista = pliki.lista_artykulow(katalog)
    sprawdz("po przeczytaniu dokument jest oznaczony jako przeczytany",
            lista[0]["ma_wyciag"] is True)
    sprawdz("wyciąg da się odczytać z powrotem",
            "+18% mocy" in pliki.wczytaj_wyciag(katalog, "raport.pdf"))
    sprawdz("wyciąg trafia do paczki dla redaktora",
            "+18% mocy" in pliki.zbuduj_material_dla_redaktora(katalog))
    sprawdz("podkatalog wyciągów nie pokazuje się jako dokument",
            len(pliki.lista_artykulow(katalog)) == 1)

    # Nazwa pliku przychodzi z przeglądarki — nie może wyprowadzić zapisu.
    zloliwa = pliki.sciezka_wyciagu(katalog, "../../etc/passwd")
    sprawdz("nazwa z ../ nie wychodzi poza katalog wyciągów",
            (katalog / "artykuly" / "wyciagi") in zloliwa.parents, f"wyszło: {zloliwa}")


def test_wyciagi_maja_sufit_dlugosci() -> None:
    katalog = katalog_testowy()
    (katalog / "artykuly").mkdir(parents=True, exist_ok=True)
    for numer in range(6):
        pliki.zapisz_wyciag(katalog, f"raport-{numer}.pdf", "tresc wyciagu. " * 400)

    blok = pliki.zbuduj_blok_wyciagow(katalog)
    sprawdz("wyciągi razem nie przekraczają sufitu",
            len(blok) < pliki.LIMIT_ZNAKOW_WYCIAGOW + 1500, f"długość: {len(blok)}")
    sprawdz("pominięte wyciągi są zgłoszone modelowi", "Pominięto" in blok)


def test_usuniecie_dokumentu_kasuje_wyciag() -> None:
    from fastapi.testclient import TestClient

    katalog = katalog_testowy()
    (katalog / "artykuly").mkdir(parents=True, exist_ok=True)
    (katalog / "artykuly" / "raport.pdf").write_bytes(b"%PDF-1.4 udawany plik")
    pliki.zapisz_wyciag(katalog, "raport.pdf", "## Fakty i liczby\n- cokolwiek\n")

    pierwotny = main.katalog_danych
    main.katalog_danych = lambda: katalog
    try:
        klient = TestClient(main.app)
        odpowiedz = klient.delete("/api/artykuly/raport.pdf")
    finally:
        main.katalog_danych = pierwotny

    sprawdz("usunięcie dokumentu się powiodło", odpowiedz.status_code == 200)
    sprawdz("wyciąg nie zostaje sierotą po usunięciu dokumentu",
            not pliki.sciezka_wyciagu(katalog, "raport.pdf").is_file())
    sprawdz("po usunięciu wyciąg nie trafia już do postów",
            "Wyciągi z wgranych dokumentów" not in pliki.zbuduj_material_dla_redaktora(katalog))


def test_nda_sprawdzane_takze_we_wklejonym_materiale() -> None:
    from fastapi.testclient import TestClient

    katalog = katalog_testowy()
    (katalog / "baza-wiedzy" / "forces-dc-fakty.md").write_text(
        "## Czego NIE wolno publikować\n\n- **Hyperscaler Nordics AS** — przykład\n",
        encoding="utf-8",
    )
    pierwotny = main.katalog_danych
    main.katalog_danych = lambda: katalog
    try:
        klient = TestClient(main.app)
        odpowiedz = klient.post(
            "/api/redaktor",
            json={
                "brief": "Post o przygotowaniu zespolu",
                "material_zrodlowy": "Wedlug raportu Hyperscaler Nordics AS buduje nowy obiekt.",
            },
        )
    finally:
        main.katalog_danych = pierwotny

    sprawdz("nazwa objęta NDA wklejona w materiał jest blokowana",
            odpowiedz.json().get("zablokowane_nda") is True,
            f"odpowiedź: {odpowiedz.status_code} {odpowiedz.text[:120]}")


async def _zbierz_sse(strumien) -> list[dict]:
    zdarzenia = []
    async for kawalek in strumien:
        for linia in kawalek.strip().splitlines():
            if linia.startswith("data: "):
                zdarzenia.append(json.loads(linia[6:]))
    return zdarzenia


# --- Import korpusu (SPEC 8.5) ---


def test_import_odrzuca_reposty_i_krotkie() -> None:
    import pandas as pd

    katalog = katalog_testowy()
    plik = katalog / "eksport.csv"
    dlugi = "Fit-out data center wymaga zespolu, ktory zna procedury. " * 5
    pd.DataFrame(
        [
            {"Data": "2025-08-22", "Tresc posta": dlugi, "Repost": "No", "Reakcje": 40},
            {"Data": "2025-08-23", "Tresc posta": "Za krotki wpis.", "Repost": "No", "Reakcje": 2},
            {"Data": "2025-08-24", "Tresc posta": dlugi, "Repost": "Yes", "Reakcje": 5},
        ]
    ).to_csv(plik, index=False)

    diagnostyka, przyjete = korpus.przeanalizuj_plik_importu(plik)
    sprawdz("import przyjmuje tylko wpis spełniający warunki", len(przyjete) == 1,
            f"przyjęto {len(przyjete)} z 3")
    sprawdz("import odrzucił repost", diagnostyka.odrzucone_reposty == 1,
            f"odrzucone_reposty={diagnostyka.odrzucone_reposty}")
    sprawdz("import odrzucił wpis poniżej 150 znaków", diagnostyka.odrzucone_krotkie == 1,
            f"odrzucone_krotkie={diagnostyka.odrzucone_krotkie}")
    sprawdz("import wykrył kolumnę z treścią", diagnostyka.wykryte.get("treść") == "Tresc posta",
            f"wykryte: {diagnostyka.wykryte}")

    korpus.zaimportuj(katalog, przyjete)
    zapisane = list((katalog / korpus.PODKATALOG_KORPUSU).glob("*.md"))
    sprawdz("zaimportowany post trafił na dysk", len(zapisane) == 1)
    sprawdz("zaimportowany post czeka na oznaczenie typu",
            korpus.TYP_DO_OZNACZENIA in zapisane[0].read_text(encoding="utf-8"))


# --- Konfiguracja ---


def test_katalog_danych_wzgledem_aplikacji(monkey_env=None) -> None:
    import os

    pierwotny = os.environ.get("KATALOG_DANYCH")
    os.environ["KATALOG_DANYCH"] = "dane"
    try:
        sciezka = main.katalog_danych()
    finally:
        if pierwotny is None:
            os.environ.pop("KATALOG_DANYCH", None)
        else:
            os.environ["KATALOG_DANYCH"] = pierwotny

    sprawdz(
        "względny KATALOG_DANYCH liczony od katalogu aplikacji, nie od bieżącego",
        sciezka == main.KATALOG_APLIKACJI / "dane",
        f"wyszło: {sciezka}",
    )


def test_klucz_api_nie_wycieka() -> None:
    """Klucz nie może pojawić się w odpowiedzi diagnostyki (SPEC 11)."""
    import dataclasses
    import os

    from app import diagnostyka

    pierwotny = os.environ.get("ANTHROPIC_API_KEY")
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-api03-TAJNE123" + "x" * 40
    try:
        raport = json.dumps(
            dataclasses.asdict(diagnostyka.uruchom_diagnostyke(katalog_testowy())), default=str
        )
    finally:
        if pierwotny is None:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        else:
            os.environ["ANTHROPIC_API_KEY"] = pierwotny

    sprawdz("klucz API nie pojawia się w raporcie diagnostyki", "TAJNE123" not in raport)
    sprawdz("diagnostyka mimo to potwierdza, że klucz jest ustawiony",
            '"klucz_api"' in raport and '"ok"' in raport)


# --- Uruchomienie ---


def main_testy() -> int:
    testy = [
        wartosc
        for nazwa, wartosc in sorted(globals().items())
        if nazwa.startswith("test_") and inspect.isfunction(wartosc)
    ]
    for test in testy:
        try:
            test()
        except Exception:
            sprawdz(f"{test.__name__} — wyjątek", False, traceback.format_exc().strip().splitlines()[-1])

    nieudane = [w for w in _wyniki if not w[1]]
    for nazwa, ok, szczegol in _wyniki:
        znak = "  ok  " if ok else " NIE  "
        print(f"{znak} {nazwa}" + (f"   [{szczegol}]" if szczegol and not ok else ""))

    print(f"\n{len(_wyniki) - len(nieudane)} / {len(_wyniki)} sprawdzeń przeszło.")
    if nieudane:
        print("Nieudane:", ", ".join(n for n, _, _ in nieudane))
    return 1 if nieudane else 0


if __name__ == "__main__":
    kod = main_testy()
    for katalog in Path(tempfile.gettempdir()).glob("studio-test-*"):
        shutil.rmtree(katalog, ignore_errors=True)
    sys.exit(kod)
