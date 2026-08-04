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
