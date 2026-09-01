#!/usr/bin/env python3
"""A vezetett meditacio szovegebol kesz hangfajlt epit.

Amit a regi pipeline nem tudott:
  - .txt-bol olvas, nem kezzel irt JSON-bol
  - kiszuri a ── fejleceket es a cimblokkot (Ara kulonben felolvasna oket)
  - a szamolast szambankbol rakja ki, masodpercre kiosztva, mert a TTS
    prozodiaja nem kepes lelegzesre alkalmas tempot tartani
  - a klipek VALODI hosszat meri, es abbol szamolja az idozitest
  - a csendet ugy osztja el, hogy az utolso szegmens pontosan a kivant
    hossznal erjen veget — igy nincs lezaro csend, amit az export levagna

    python3 epit.py --dry-run     # csak a szamok
    python3 epit.py               # gyartas

A kulcs a kornyezetbol vagy ~/.xai_key-bol jon, es soha nem kerul kiirasra.
"""
import argparse, json, os, pathlib, re, shutil, subprocess, sys, time, urllib.error, urllib.request

API, MODEL, VOICE, LANG = "https://api.x.ai/v1/tts", "grok-tts", "ara", "hu"
ITT = pathlib.Path(__file__).resolve().parent
GYOKER = ITT.parent.parent
SZOVEG = ITT / "bashar-hoppanalas.txt"
MUNKA = ITT / ".epites"
AZONOSITO = "bashar-shifting-timer-hoppban-allas"
TELJES = 2400                      # 40 perc

# Kisbetuvel: a mondatkezdo nagy kezdobetu nehol elrontja a hangzast
# (a "Hét." roviden jott ki). A szamokat egyszer gyartjuk, sokszor hasznaljuk.
SZAMOK = ["egy.", "kettő.", "három.", "négy.", "öt.", "hat.", "hét.", "nyolc."]
SZAM_KOZ = 1.5                     # masodperc ket szam kezdete kozott
MANTRA = "Óm. Namah. Krisna."

# Csend az egyes szakaszok UTAN, masodpercben. A MARADAS nincs benne:
# az nyeli el a maradekot, hogy a vegosszeg pontosan TELJES legyen.
SZAKASZ_CSEND = {
    "ELŐKÉSZÜLET": 10, "BELÉPÉS": 20, "1.": 30, "2.": 15, "3.": 20, "4.": 20,
    "5.": 15, "6.": 90, "7.": 20, "8.": 40, "9.": 30, "10.": 70, "11.": 10,
    "12.": 90, "13.": 20, "14.": 5, "15.": 12, "16.": 70, "17.": 30,
    "18.": 20, "19.": 10, "20.": 8, "21.": 0,
}
ALAP_KOZ = 2.5                     # szegmensek kozott egy szakaszon belul
MANTRA_KOZ = 5.0                   # a mantra lassabban lelegzik


def kulcs():
    k = os.environ.get("XAI_API_KEY", "").strip()
    if k:
        return k
    p = pathlib.Path.home() / ".xai_key"
    if p.exists() and p.read_text().strip():
        return p.read_text().strip()
    sys.exit("Nincs kulcs. XAI_API_KEY vagy ~/.xai_key kell.")


def mondd(szoveg, k, probak=4):
    body = json.dumps({"model": MODEL, "voice_id": VOICE, "language": LANG,
                       "text": szoveg, "format": "mp3"}).encode()
    for n in range(probak):
        try:
            req = urllib.request.Request(API, data=body,
                headers={"Authorization": f"Bearer {k}", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                hang = r.read()
            if len(hang) < 500:
                raise ValueError(f"gyanusan rovid: {len(hang)} bajt")
            return hang
        except Exception as err:                                  # noqa: BLE001
            if n == probak - 1:
                raise
            var = 3 * (n + 1)
            print(f"      ujra {n+1}/{probak-1} — {err} ({var}s)", flush=True)
            time.sleep(var)


def hossz(f):
    ki = subprocess.run(["afinfo", str(f)], capture_output=True, text=True).stdout
    m = re.search(r"estimated duration: ([\d.]+)", ki)
    if not m:
        sys.exit(f"nem tudom megmerni: {f}")
    return float(m.group(1))


def szakaszok():
    """A szoveget szakaszokra es szegmensekre bontja.

    A cimblokk (az elso ── elott) es minden ── fejlec kimarad a beszedbol,
    de a fejlecek adjak a szakaszhatarokat es igy a csend kiosztasat."""
    nyers = SZOVEG.read_text()
    bek = [b.strip() for b in nyers.split("\n\n") if b.strip()]
    ki, aktualis, nev = [], [], None
    for b in bek:
        if "──" in b:
            if nev is not None:
                ki.append((nev, aktualis))
            cim = b.replace("─", "").strip()
            nev = cim.split()[0] if cim.split() else cim
            aktualis = []
        elif nev is not None:                       # a cimblokk igy esik ki
            aktualis.append(b)                      # sortores megmarad
    if nev is not None:
        ki.append((nev, aktualis))
    return ki


def szamokra_bont(sor):
    """'Első kör. Belégzés orron át. egy. kettő. …' -> (felvezetes, [szamindexek])

    A szamolast nem szabad egy klipben hagyni: a TTS gyorsabban szamol, mint
    ahogy lelegezni lehet. A felvezetes marad TTS, a szamok a bankbol jonnek."""
    reszek = [r.strip() for r in re.split(r"(?<=\.)\s+", sor) if r.strip()]
    szam_alak = {sz.strip(".").lower(): i for i, sz in enumerate(SZAMOK)}
    elso = next((i for i, r in enumerate(reszek) if r.strip(".").lower() in szam_alak), None)
    if elso is None:
        return sor, []
    felvezetes = " ".join(reszek[:elso])
    idxek = [szam_alak[r.strip(".").lower()] for r in reszek[elso:]
             if r.strip(".").lower() in szam_alak]
    return felvezetes, idxek


def terv_epit():
    """Szegmenslista: mindegyik vagy sajat TTS-klip, vagy a szambank egy eleme."""
    seg = []
    for nev, bekezdesek in szakaszok():
        prana = nev.startswith("12")
        for b in bekezdesek:
            szamos = prana and re.search(r"\b(egy|kettő|három)\.", b, re.I)
            if not szamos:
                seg.append({"tipus": "tts", "szoveg": " ".join(b.split()), "szakasz": nev})
                continue
            # soronkent: minden legzesfazisnak sajat felvezetese van
            for sor in (s.strip() for s in b.splitlines() if s.strip()):
                felv, idxek = szamokra_bont(" ".join(sor.split()))
                if felv:
                    seg.append({"tipus": "tts", "szoveg": felv, "szakasz": nev})
                for i in idxek:
                    seg.append({"tipus": "bank", "bank": i, "szoveg": SZAMOK[i], "szakasz": nev})
    return seg


def idozit(seg, hosszak):
    """Kiosztja az 'at' ertekeket ugy, hogy az utolso szegmens pontosan
    TELJES-nel erjen veget. A MARADAS belso szunetei nyelik el a maradekot."""
    n = len(seg)
    utolso_a_szakaszban = [i for i in range(n)
                           if i == n - 1 or seg[i]["szakasz"] != seg[i + 1]["szakasz"]]
    res = [0.0] * n
    for i in range(n - 1):
        s, kov = seg[i], seg[i + 1]
        if kov["tipus"] == "bank":                       # szamok: fix lukteles
            res[i] = max(0.2, SZAM_KOZ - hosszak[i])
        elif s["tipus"] == "bank":                       # szamsor utan egy levegonyi
            res[i] = 1.2
        elif i in utolso_a_szakaszban:
            res[i] = SZAKASZ_CSEND.get(s["szakasz"], ALAP_KOZ)
        elif s["szoveg"] == MANTRA:
            res[i] = MANTRA_KOZ
        else:
            res[i] = ALAP_KOZ

    marad_idx = [i for i in range(n - 1) if seg[i]["szakasz"].startswith("17")]
    alap = sum(hosszak) + sum(res)
    csuszas = TELJES - alap
    if marad_idx:
        fejenkent = csuszas / len(marad_idx)
        for i in marad_idx:
            res[i] = max(1.0, res[i] + fejenkent)

    at, t = [], 0.0
    for i in range(n):
        at.append(round(t, 2))
        t += hosszak[i] + (res[i] if i < n - 1 else 0)
    return at, t, csuszas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    seg = terv_epit()
    ttsek = [s for s in seg if s["tipus"] == "tts"]
    kar = sum(len(s["szoveg"]) for s in ttsek)
    print(f"{len(seg)} szegmens — {len(ttsek)} saját klip, "
          f"{len(seg)-len(ttsek)} a számbankból")
    print(f"{kar:,} karakter, becsült költség ${kar/1_000_000*4.2:.4f}")
    if a.dry_run:
        for nev, bek in szakaszok():
            print(f"  {nev:<14} {len(bek):>3} bekezdés")
        return

    k = kulcs()
    MUNKA.mkdir(exist_ok=True)
    bank_dir = MUNKA / "bank"; bank_dir.mkdir(exist_ok=True)
    klip_dir = MUNKA / "klip"; klip_dir.mkdir(exist_ok=True)

    for i, sz in enumerate(SZAMOK):
        f = bank_dir / f"{i}.mp3"
        if not (f.exists() and f.stat().st_size > 500):
            f.write_bytes(mondd(sz, k)); print(f"  szám: {sz}")

    for i, s in enumerate(seg):
        if s["tipus"] != "tts":
            continue
        f = klip_dir / f"{i:03d}.mp3"
        if f.exists() and f.stat().st_size > 500:
            continue
        f.write_bytes(mondd(s["szoveg"], k))
        print(f"  {i+1}/{len(seg)}  {s['szoveg'][:58]}", flush=True)

    # osszefuzeshez a build-guided-audio.swift NN.mp3-at var, folytonos indexszel
    ossz = MUNKA / "ossz"
    shutil.rmtree(ossz, ignore_errors=True); ossz.mkdir()
    hosszak = []
    for i, s in enumerate(seg):
        forras = bank_dir / f"{s['bank']}.mp3" if s["tipus"] == "bank" else klip_dir / f"{i:03d}.mp3"
        shutil.copy(forras, ossz / f"{i:02d}.mp3")
        hosszak.append(hossz(forras))

    at, veg, csuszas = idozit(seg, hosszak)
    beszed = sum(hosszak)
    print(f"\nbeszéd {beszed/60:.1f} perc | csend {(veg-beszed)/60:.1f} perc | "
          f"összesen {veg/60:.1f} perc")
    print(f"a MARADÁS nyelte el: {csuszas/60:.1f} perc")

    terv = {"id": AZONOSITO, "cim": "Az első hoppban állás", "hossz": int(round(veg)),
            "szegmensek": [{"at": at[i], "szoveg": seg[i]["szoveg"]} for i in range(len(seg))]}
    tf = MUNKA / "terv.json"
    tf.write_text(json.dumps(terv, ensure_ascii=False, indent=1))

    ki = ITT / f"{AZONOSITO}.m4a"
    r = subprocess.run(["xcrun", "swift", str(ITT.parent / "build-guided-audio.swift"),
                        str(tf), str(ossz), str(ki), str(int(round(veg)))],
                       capture_output=True, text=True)
    print(r.stdout.rstrip() or r.stderr.rstrip())
    if r.returncode == 0:
        print(f"\nkész: {ki}")


if __name__ == "__main__":
    main()
