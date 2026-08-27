#!/usr/bin/env python3
"""Hangoskönyv-modul készítése egy egyszerű szövegfájlból.
Build an audiobook meditation module from a plain text list.

MAGYARUL
--------
Egy hangoskönyv (vagy bármilyen többrészes felvétel-sorozat) linkjeiből
`module.json`-t ír: minden szám kap egy **csoportot** (a szekció neve), egy
**sorszámot** (a sorrend a csoporton belül) és `folytatolagos: true`-t, hogy az
appban a szekció végigjátsszon.

A bemenet soronként egy szám, két alakban — a kettő keverhető egy fájlon belül:

    12<TAB>A tizenkettedik rész<TAB>https://...
    https://...            # csak URL: a sorszám és a név a névből/URL-ből jön

Üres sorok és a `#`-kel kezdődők kimaradnak.

**Miért van sorszám?** Mert a név szerinti rendezés a „11. rész”-t a „2. rész”
ELÉ teszi. A sorszám ezt oldja meg — a szkript ezért ellenőrzi is, hogy a kapott
sorszámok hézagmentesek-e és nincs-e köztük duplikátum. Ha a számot nem oszlopból
kapja, hanem a névből vonja ki, és a találat bizonytalan (pl. „Holotope 432 Hz”
esetén a 432-t találná), azt külön kiírja.

    # először MINDIG így nézd meg, ez nem ír semmit:
    python3 tools/make-audiobook-module.py lista.txt \
        --id ryokah-alchemy-audio \
        --group hu="Az alkímia hangoskönyv" --group en="The Alchemy audiobook" \
        --dry-run

    # ha a táblázat rendben van, akkor írd ki:
    python3 tools/make-audiobook-module.py lista.txt \
        --id ryokah-alchemy-audio \
        --group hu="Az alkímia hangoskönyv" --group en="The Alchemy audiobook" \
        --nev hu="Ryokah — alkímia (hang)" --nev en="Ryokah — alchemy (audio)" \
        --out ryokah.alchemy/module.json

Ha a `--out` fájl már létezik, a szkript **beleszerkeszt**: az `items` és a többi
mező marad, csak a `meditaciok` frissül (URL alapján párosítva). Teljesen új
manifesztet a `--overwrite` ír.

Csak azokat a nyelveket írja ki, amiket megadtál — az app a hiányzókra
angolra/magyarra esik vissza, így nem kerül a fájlba kitalált fordítás. A
többit a `tools/translate.py` tudja utólag megcsinálni.

IN ENGLISH
----------
Turns a list of links into a `module.json` where every track carries a
**group** (the section title), a **sorszam** (its order inside that section)
and `folytatolagos: true`, so the app plays the section straight through.

One track per line, in either form — the two may be mixed in one file:

    12<TAB>The twelfth part<TAB>https://...
    https://...            # URL only: order and name are derived

Blank lines and lines starting with `#` are ignored.

**Why an explicit number?** Sorting by name puts "Part 11" BEFORE "Part 2".
The number fixes that, so the script also checks the numbers it ends up with
for gaps and duplicates, and flags any it had to guess out of a title.

    python3 tools/make-audiobook-module.py list.txt \
        --id my-audiobook --group en="The audiobook" --dry-run
    python3 tools/make-audiobook-module.py list.txt \
        --id my-audiobook --group en="The audiobook" --out my.module/module.json

An existing `--out` file is merged into, never clobbered: `items` and the other
fields stay, only `meditaciok` is refreshed (matched on URL). Use `--overwrite`
for a fresh manifest. Only the languages you pass are written; the app falls
back to English/Hungarian for the rest.

EXIT CODES
----------
    0  ok (warnings may still have been printed)
    1  usage / input error, or a check failed (duplicates, or any warning
       under --strict)
"""

import argparse
import json
import re
import sys
import unicodedata
import urllib.parse
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# The 15 the app ships; used only to reject typo'd language codes.
LANGS = {"hu", "en", "de", "es", "fr", "it", "pt", "ro", "pl", "cs", "sk",
         "ja", "zh", "ru", "ar"}

# Ordinals that are unambiguously an ordinal: a word or marker in front of the
# number. Tried in order, before the bare first-number fallback, so that
# "Holotope 432 Hz — Part 2" yields 2 and not 432.
JELOLT_MINTAK = [
    r"(?:^|[^\w])#\s*(\d{1,4})\b",
    r"\b(?:part|pt|chapter|chap|ch|track|trk|episode|ep|disc|cd|no|nr|num)\b"
    r"[\s._:#-]*(\d{1,4})\b",
    r"\b(?:resz|rész|fejezet|szam|szám|lecke|nap)\b[\s._:#-]*(\d{1,4})\b",
    r"\b(\d{1,4})\s*[.)]?\s*(?:resz|rész|fejezet|lecke|nap)\b",
    r"^\s*(\d{1,4})\s*[.)_:-]\s+",     # "07 - Title", "7. Title", "07_Title"
    r"^\s*(\d{1,4})\s*$",
]

# A bare number anywhere. The spec's fallback — correct often enough to be
# worth having, wrong often enough to always be reported as a guess.
CSUPASZ_MINTA = r"(\d{1,4})"


def figyelmeztet(uzenet):
    print(f"figyelem / warning: {uzenet}", file=sys.stderr)


def hiba(uzenet):
    print(f"HIBA / ERROR: {uzenet}", file=sys.stderr)
    sys.exit(1)


def nyelvi_par(szoveg):
    """`--group hu=Első rész` → ("hu", "Első rész")."""
    if "=" not in szoveg:
        raise argparse.ArgumentTypeError(
            f"'{szoveg}': LANG=SZÖVEG alakban várom / expected LANG=TEXT")
    kod, _, ertek = szoveg.partition("=")
    kod = kod.strip().lower()
    ertek = ertek.strip()
    if kod not in LANGS:
        raise argparse.ArgumentTypeError(
            f"'{kod}': ismeretlen nyelv / unknown language "
            f"({', '.join(sorted(LANGS))})")
    if not ertek:
        raise argparse.ArgumentTypeError(f"'{kod}': üres érték / empty value")
    return kod, ertek


def szotarra(parok):
    """[("hu", "a"), ("en", "b")] → {"hu": "a", "en": "b"}"""
    return {kod: ertek for kod, ertek in parok or []}


def kivon_sorszam(szoveg):
    """(szám, biztos-e) — a második tag False, ha csak tippeltünk.

    Returns (number, confident). `confident` is False when the number came
    from the bare-first-digits fallback, which is the one that mistakes a
    sample rate, a year or a running time for a track number.
    """
    if not szoveg:
        return None, False
    normalt = unicodedata.normalize("NFC", szoveg)
    for minta in JELOLT_MINTAK:
        talalat = re.search(minta, normalt, re.IGNORECASE)
        if talalat:
            return int(talalat.group(1)), True
    talalat = re.search(CSUPASZ_MINTA, normalt)
    if talalat:
        return int(talalat.group(1)), False
    return None, False


def nev_urlbol(url):
    """A link utolsó szegmenséből olvasható név, ha van benne ilyen."""
    try:
        eleresi_ut = urllib.parse.urlparse(url).path
    except ValueError:
        return ""
    utolso = urllib.parse.unquote(eleresi_ut.rstrip("/").split("/")[-1])
    if not utolso:
        return ""
    utolso = re.sub(r"\.(mp3|m4a|m4b|aac|wav|ogg|opus|flac|mp4|mov|m4v)$", "",
                    utolso, flags=re.IGNORECASE)
    utolso = utolso.replace("_", " ").replace("+", " ")
    return re.sub(r"\s+", " ", utolso).strip()


def beolvas(ut):
    """A bemeneti fájl → [(sorszám|None, név|None, url, sor-szám-a-fájlban)]"""
    try:
        nyers = Path(ut).read_text(encoding="utf-8")
    except OSError as e:
        hiba(f"a bemenet nem olvasható / cannot read input: {e}")
    sorok = []
    for sorszamozott, sor in enumerate(nyers.splitlines(), start=1):
        sor = sor.strip()
        if not sor or sor.startswith("#"):
            continue
        mezok = [m.strip() for m in sor.split("\t") if m.strip()]
        if len(mezok) >= 3:
            elso, nev, url = mezok[0], mezok[1], mezok[2]
            if not elso.isdigit():
                hiba(f"{sorszamozott}. sor: három oszlopnál az első a sorszám, "
                     f"de '{elso}' nem szám / first column must be a number")
            sorok.append((int(elso), nev, url, sorszamozott))
        elif len(mezok) == 2:
            elso, masodik = mezok
            if elso.isdigit():
                sorok.append((int(elso), None, masodik, sorszamozott))
            else:
                sorok.append((None, elso, masodik, sorszamozott))
        else:
            sorok.append((None, None, mezok[0], sorszamozott))
    return sorok


def ellenoriz(tetelek, kezdet, strict):
    """Duplikátum / hézag / tippelt szám — ezek miatt lett 1 után 11.

    Returns True when everything is clean. Duplicates always fail the run;
    the rest are warnings unless --strict.
    """
    rendben = True
    tippeltek = [t for t in tetelek if not t["biztos"]]
    if tippeltek:
        figyelmeztet(
            f"{len(tippeltek)} sorszám a névből/URL-ből lett kitalálva, nem "
            f"jelölt helyről — ellenőrizd / guessed from a bare number in the "
            f"title, please check:")
        for t in tippeltek:
            print(f"    {t['sorszam']:>4}  <- {t['forras']!r}", file=sys.stderr)
        rendben = rendben and not strict

    szamok = [t["sorszam"] for t in tetelek]
    duplak = sorted({s for s in szamok if szamok.count(s) > 1})
    if duplak:
        hiba(f"duplikált sorszámok / duplicate numbers: {duplak} — "
             f"add meg őket kézzel az első oszlopban / set them explicitly "
             f"in the first column")

    if szamok:
        legkisebb, legnagyobb = min(szamok), max(szamok)
        if legkisebb != kezdet:
            figyelmeztet(
                f"a sorozat {legkisebb}-vel kezdődik, nem {kezdet}-vel / "
                f"starts at {legkisebb}, not {kezdet}")
            rendben = rendben and not strict
        # A tartomány egyetlen elhibázott tipptől (432 Hz) elszállhat, ezért a
        # hiánylistát vágjuk — különben a képernyőt tölti meg. One bad guess
        # can blow the range up, so the missing list is capped.
        hianyzo = sorted(set(range(legkisebb, legnagyobb + 1)) - set(szamok))
        if hianyzo:
            mutat = ", ".join(str(h) for h in hianyzo[:15])
            ha_tobb = (f" … és még {len(hianyzo) - 15} / and "
                       f"{len(hianyzo) - 15} more") if len(hianyzo) > 15 else ""
            figyelmeztet(
                f"hézagos a számozás, {len(hianyzo)} hiányzik / gaps in the "
                f"numbering, {len(hianyzo)} missing: {mutat}{ha_tobb}")
            rendben = rendben and not strict
    return rendben


def epit_meditaciok(tetelek, csoport, folytatolagos):
    ki = []
    for t in tetelek:
        bejegyzes = {
            # A szám címe nyelvenként ugyanaz — a felvétel neve nem fordítás
            # kérdése. The track title repeats across languages on purpose.
            "nevek": {kod: t["nev"] for kod in sorted(csoport)},
            "url": t["url"],
            "csoport": dict(csoport),
            "sorszam": t["sorszam"],
        }
        if folytatolagos:
            bejegyzes["folytatolagos"] = True
        ki.append(bejegyzes)
    return ki


def main():
    p = argparse.ArgumentParser(
        description="Hangoskönyv-modul egy linklistából / audiobook module "
                    "from a list of links.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Részletes súgó a fájl tetején / full usage at the top of "
               "this file.")
    p.add_argument("input", help="szövegfájl / text file: "
                                 "'sorszám<TAB>név<TAB>url' vagy csak url")
    p.add_argument("--id", help="a modul azonosítója / module id")
    p.add_argument("--out", help="hova írjuk / where to write module.json")
    p.add_argument("--group", "--csoport", dest="group", action="append",
                   type=nyelvi_par, metavar="LANG=TEXT",
                   help="a szekció neve, nyelvenként / section name per "
                        "language (ismételhető / repeatable)")
    p.add_argument("--nev", "--name", dest="nev", action="append",
                   type=nyelvi_par, metavar="LANG=TEXT",
                   help="a modul címe / module title (alapból a csoportnév / "
                        "defaults to the group name)")
    p.add_argument("--leiras", "--description", dest="leiras", action="append",
                   type=nyelvi_par, metavar="LANG=TEXT",
                   help="a modul leírása / module description")
    p.add_argument("--version", default="1.0.0",
                   help="tartalomverzió / content version (default 1.0.0)")
    p.add_argument("--start", type=int, default=1,
                   help="a várt első sorszám / expected first number "
                        "(default 1)")
    p.add_argument("--no-folytatolagos", dest="folytatolagos",
                   action="store_false",
                   help="ne játssza végig a szekciót / do not play the "
                        "section through")
    p.add_argument("--overwrite", action="store_true",
                   help="teljesen új manifeszt a meglévő helyére / replace "
                        "an existing manifest instead of merging into it")
    p.add_argument("--strict", action="store_true",
                   help="a figyelmeztetés is hiba / treat warnings as errors")
    p.add_argument("--dry-run", action="store_true",
                   help="csak mutasd, ne írj / show the plan, write nothing")
    a = p.parse_args()

    if not a.dry_run and not a.out:
        hiba("--out kell, vagy használd a --dry-run-t / --out is required "
             "unless --dry-run")

    csoport = szotarra(a.group)
    if not csoport:
        hiba("legalább egy --group LANG=SZÖVEG kell / at least one "
             "--group LANG=TEXT is required")

    sorok = beolvas(a.input)
    if not sorok:
        hiba("a bemenet egyetlen használható sort sem tartalmaz / no usable "
             "lines in the input")

    tetelek = []
    for explicit, nev, url, fajlsor in sorok:
        if not re.match(r"https?://", url, re.IGNORECASE):
            figyelmeztet(f"{fajlsor}. sor: ez nem http(s) link / not an "
                         f"http(s) link: {url!r}")
        cim = nev or nev_urlbol(url)
        if explicit is not None:
            szam, biztos, forras, honnan = explicit, True, cim, "oszlop"
        else:
            szam, biztos = kivon_sorszam(cim)
            forras, honnan = cim, "név"
            if szam is None:
                szam, biztos = kivon_sorszam(nev_urlbol(url))
                forras, honnan = nev_urlbol(url), "URL"
            if szam is None:
                hiba(f"{fajlsor}. sor: nincs kinyerhető sorszám, add meg az "
                     f"első oszlopban / no number found, put it in the first "
                     f"column: {url!r}")
            if not biztos:
                honnan = "TIPP / GUESS"
        if not cim:
            cim = f"{szam}"
            figyelmeztet(f"{fajlsor}. sor: nincs név, a sorszám lesz az / no "
                         f"name, using the number: {url!r}")
        tetelek.append({"sorszam": szam, "nev": cim, "url": url,
                        "biztos": biztos, "forras": forras, "honnan": honnan})

    latott = {}
    for t in tetelek:
        if t["url"] in latott:
            figyelmeztet(f"ugyanaz a link kétszer / duplicate link: "
                         f"{t['url']!r}")
        latott[t["url"]] = True

    tetelek.sort(key=lambda t: t["sorszam"])
    rendben = ellenoriz(tetelek, a.start, a.strict)

    print(f"\n{len(tetelek)} szám / tracks — csoport / group: "
          f"{csoport.get('hu') or next(iter(csoport.values()))}")
    print(f"{'sorszám':>7}  {'név / name':<52}  honnan / from")
    for t in tetelek:
        print(f"{t['sorszam']:>7}  {t['nev'][:52]:<52}  {t['honnan']}")
    print()

    # A --strict a KIÍRÁS ELŐTT áll meg, különben a hibás fájl már a lemezen
    # lenne. --strict stops before writing, not after.
    if not rendben:
        hiba("--strict: a fenti figyelmeztetések miatt állok meg, nem írok / "
             "stopping on the warnings above, nothing written")

    meditaciok = epit_meditaciok(tetelek, csoport, a.folytatolagos)

    kimeneti_ut = Path(a.out) if a.out else None
    if kimeneti_ut and not kimeneti_ut.is_absolute():
        kimeneti_ut = REPO / kimeneti_ut

    manifeszt = None
    if kimeneti_ut and kimeneti_ut.exists() and not a.overwrite:
        try:
            manifeszt = json.loads(kimeneti_ut.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            hiba(f"a meglévő manifeszt nem olvasható / existing manifest "
                 f"unreadable ({e}) — --overwrite írja felül")
        print(f"beleszerkesztés / merging into: {kimeneti_ut}")
        regi = {m.get("url"): m for m in manifeszt.get("meditaciok") or []}
        for m in meditaciok:
            regi[m["url"]] = m
        manifeszt["meditaciok"] = list(regi.values())
        if a.id and manifeszt.get("id") not in (None, a.id):
            figyelmeztet(f"a meglévő id ({manifeszt.get('id')!r}) marad, a "
                         f"--id ({a.id!r}) nem írja felül / keeping the "
                         f"existing id")
    else:
        if not a.id:
            hiba("--id kell új manifeszthez / --id is required for a new "
                 "manifest")
        manifeszt = {
            "formatVersion": 1,
            "id": a.id,
            "version": a.version,
            "nevek": szotarra(a.nev) or dict(csoport),
            "items": [],
            "meditaciok": meditaciok,
        }
        leiras = szotarra(a.leiras)
        if leiras:
            manifeszt["description"] = leiras

    szoveg = json.dumps(manifeszt, ensure_ascii=False, indent=2) + "\n"

    if a.dry_run:
        print("--- dry-run: nem írok semmit / nothing written ---")
        print(szoveg if len(szoveg) < 4000 else szoveg[:4000] + "\n… (levágva "
              "/ truncated)")
    else:
        kimeneti_ut.parent.mkdir(parents=True, exist_ok=True)
        kimeneti_ut.write_text(szoveg, encoding="utf-8")
        print(f"kiírva / written: {kimeneti_ut}")


if __name__ == "__main__":
    main()
