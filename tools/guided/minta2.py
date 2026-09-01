#!/usr/bin/env python3
"""Masodik hangminta: a harom nyitott kiejtes-kerdes + a szamolas tempoja.

Leonard visszajelzese alapjan Ara az "s"-t nehol [s]-nek ejti [ʃ] helyett
("szuttogok", "kriszna"). Itt kiderul, rendszeres-e, es melyik irasmod javitja.

A szamolast szegmensenkent rakjuk ossze: egy szam = egy klip, masodpercre
kiosztva. Igy a tempot a csend adja, nem a TTS prozodiaja.
"""
import json, os, pathlib, shutil, subprocess, sys, urllib.request, urllib.error

API, MODEL, VOICE, LANG = "https://api.x.ai/v1/tts", "grok-tts", "ara", "hu"
KI = pathlib.Path.home() / "Desktop" / "Hoppanalas minta 2"
GYOKER = pathlib.Path(__file__).resolve().parent.parent

# 1. Rendszeres-e az s -> sz? Ugyanaz a hang tobb szoban.
S_TESZT = [
    ("A1-s-hangok",      "Suttogok. A siker íze édes. Sikerült. Ez a siker."),
    ("A2-s-kisbetuvel",  "Én itt vagyok melletted, suttogok, lassan, nagyon lassan."),
    ("A3-s-nyujtva",     "Ssuttogok. Nagyon halkan ssúgok neked."),
]

# 2. Mantra: melyik irasmodbol lesz "óm namah krisna"?
MANTRA = [
    ("B1-krisna",         "Óm namah Krisna. Óm namah Krisna."),
    ("B2-krishna",        "Óm namah Krishna. Óm namah Krishna."),
    ("B3-namaha",         "Ómm namaha Krisna. Ómm namaha Krisna."),
    ("B4-kulon-mondat",   "Óm. Namah. Krisna."),
]

# 3. Hoppban allas — Leonard javitasa a sajat szavara.
HOPP = [
    ("C1-hoppban",  "Hoppban állás. Most. És most teljes testtel átlépsz."),
    ("C2-kotojel",  "Hopp-ban állás. Most."),
    ("C3-mult",     "Mintha már megtörtént volna. Már hoppban álltál. Már ott vagy."),
]

# 4. Szamolas: szambank + idozites. Egy szam = egy klip.
BANK = ["Egy.", "Kettő.", "Három.", "Négy.", "Öt.", "Hat.", "Hét.", "Nyolc."]
INTRO = ["Első kör. Belégzés orron át.", "Tartsd bent.", "És ki, szájon át."]

# 4-7-8: be 4 mp, bent 7 mp, ki 8 mp. A szamok masodpercenkent.
def kor_terv(t0=0.0):
    sz, t = [], t0
    sz.append(("intro0", t)); t += 3.0
    for i in range(4):  sz.append((f"bank{i}", t)); t += 1.0      # be: 1..4
    t += 0.5
    sz.append(("intro1", t)); t += 2.0
    for i in range(7):  sz.append((f"bank{i}", t)); t += 1.0      # bent: 1..7
    t += 0.5
    sz.append(("intro2", t)); t += 2.5
    for i in range(8):  sz.append((f"bank{i}", t)); t += 1.0      # ki: 1..8
    return sz, t


def kulcs():
    k = os.environ.get("XAI_API_KEY", "").strip()
    if k: return k
    p = pathlib.Path.home() / ".xai_key"
    if p.exists() and p.read_text().strip(): return p.read_text().strip()
    sys.exit("Nincs kulcs.")


def mondd(szoveg, k):
    body = json.dumps({"model": MODEL, "voice_id": VOICE, "language": LANG,
                       "text": szoveg, "format": "mp3"}).encode()
    req = urllib.request.Request(API, data=body,
        headers={"Authorization": f"Bearer {k}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        hang = r.read()
    if len(hang) < 500:
        sys.exit(f"gyanusan rovid valasz: {len(hang)} bajt")
    return hang


def main():
    egyszeru = S_TESZT + MANTRA + HOPP
    kar = sum(len(s) for _, s in egyszeru) + sum(map(len, BANK)) + sum(map(len, INTRO))
    n = len(egyszeru) + len(BANK) + len(INTRO)
    print(f"{n} hivas, {kar} karakter, becsult koltseg ${kar/1_000_000*4.2:.4f}")
    if "--dry-run" in sys.argv: return

    k = kulcs()
    KI.mkdir(parents=True, exist_ok=True)
    for nev, sz in egyszeru:
        cel = KI / f"{nev}.mp3"
        if cel.exists() and cel.stat().st_size > 500: continue
        cel.write_bytes(mondd(sz, k)); print(f"  {nev}")

    # szambank + intro klipek
    bank_dir = KI / ".bank"; bank_dir.mkdir(exist_ok=True)
    for i, sz in enumerate(BANK):
        f = bank_dir / f"bank{i}.mp3"
        if not (f.exists() and f.stat().st_size > 500):
            f.write_bytes(mondd(sz, k)); print(f"  szám: {sz}")
    for i, sz in enumerate(INTRO):
        f = bank_dir / f"intro{i}.mp3"
        if not (f.exists() and f.stat().st_size > 500):
            f.write_bytes(mondd(sz, k)); print(f"  intro: {sz}")

    # a kor osszerakasa: a bank klipjeit a megfelelo indexre masoljuk
    seg, hossz = kor_terv()
    munka = KI / ".kor"; munka.mkdir(exist_ok=True)
    szegmensek = []
    for idx, (forras, at) in enumerate(seg):
        shutil.copy(bank_dir / f"{forras}.mp3", munka / f"{idx:02d}.mp3")
        szegmensek.append({"at": at, "szoveg": forras})
    terv = {"id": "minta-478", "cim": "4-7-8 légzés (minta)",
            "hossz": int(hossz) + 3, "szegmensek": szegmensek}
    tf = munka / "terv.json"; tf.write_text(json.dumps(terv, ensure_ascii=False))
    r = subprocess.run(["xcrun", "swift", str(GYOKER / "build-guided-audio.swift"),
                        str(tf), str(munka), str(KI / "D-SZAMOLAS-igy-lenne-jo.m4a"),
                        str(int(hossz) + 3)], capture_output=True, text=True)
    print(r.stdout.rstrip() or r.stderr.rstrip())
    print(f"\negy kör hossza: {hossz:.0f} mp (4-7-8 = 19 mp számolás + a felvezetések)")


if __name__ == "__main__":
    main()
