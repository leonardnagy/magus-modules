#!/usr/bin/env python3
"""Harmadik minta: a ket megmaradt kiejtes-kerdes + lassabb szamolas.

Leonard eddigi visszajelzesebol ket dolog derult ki:
  - a mondatkezdo nagy "S" [s]-nek jon ki, a mondat kozepi kisbetus "s" [ʃ]-nek
  - a magaban allo "Hét." roviden ejtodik ("het")
Az elso megfigyeles adja a kisbetus szamok otletet.
"""
import json, os, pathlib, shutil, subprocess, sys, urllib.request

API, MODEL, VOICE, LANG = "https://api.x.ai/v1/tts", "grok-tts", "ara", "hu"
KI = pathlib.Path.home() / "Desktop" / "Hoppanalas minta 3"
BANK_REGI = pathlib.Path.home() / "Desktop" / "Hoppanalas minta 2" / ".bank"
GYOKER = pathlib.Path(__file__).resolve().parent.parent

VARIANSOK = [
    # "Tartsd bent." — a jelenlegi rosszul szol
    ("E1-tartsd-bent",     "Tartsd bent."),
    ("E2-tartsd-benn",     "Tartsd benn."),
    ("E3-most-tartsd",     "Most tartsd bent."),
    ("E4-kisbetus",        "És most tartsd bent."),
    ("E5-visszatartod",    "A levegőt bent tartod."),
    # "Hét." — rovid e-vel jon ki
    ("F1-het-kisbetu",     "hét."),
    ("F2-het-nyujtva",     "Héét."),
    ("F3-het-mondatban",   "Hat. Hét. Nyolc."),
    ("F4-szamok-kisbetu",  "egy. kettő. három. négy. öt. hat. hét."),
]

# Ugyanaz a kor, de lassabban: 1.5 mp szamonkent 1.0 helyett.
def kor_terv(koz=1.5):
    sz, t = [], 0.0
    sz.append(("intro0", t)); t += 3.6
    for i in range(4):  sz.append((f"bank{i}", t)); t += koz
    t += 0.8
    sz.append(("intro1", t)); t += 2.0
    for i in range(7):  sz.append((f"bank{i}", t)); t += koz
    t += 0.8
    sz.append(("intro2", t)); t += 2.6
    for i in range(8):  sz.append((f"bank{i}", t)); t += koz
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
    if len(hang) < 500: sys.exit(f"gyanusan rovid: {len(hang)} bajt")
    return hang


def main():
    kar = sum(len(s) for _, s in VARIANSOK)
    print(f"{len(VARIANSOK)} uj hivas, {kar} karakter, ${kar/1_000_000*4.2:.4f}")
    print("(a szamolas-demo a mar legyartott klipekbol keszul, az ingyen van)")
    if "--dry-run" in sys.argv: return

    k = kulcs()
    KI.mkdir(parents=True, exist_ok=True)
    for nev, sz in VARIANSOK:
        cel = KI / f"{nev}.mp3"
        if cel.exists() and cel.stat().st_size > 500: continue
        cel.write_bytes(mondd(sz, k)); print(f"  {nev}")

    seg, hossz = kor_terv()
    munka = KI / ".kor"; munka.mkdir(exist_ok=True)
    szegmensek = []
    for idx, (forras, at) in enumerate(seg):
        shutil.copy(BANK_REGI / f"{forras}.mp3", munka / f"{idx:02d}.mp3")
        szegmensek.append({"at": at, "szoveg": forras})
    terv = {"id": "minta-478-lassu", "cim": "4-7-8 (lassabb)",
            "hossz": int(hossz) + 3, "szegmensek": szegmensek}
    tf = munka / "terv.json"; tf.write_text(json.dumps(terv, ensure_ascii=False))
    r = subprocess.run(["xcrun", "swift", str(GYOKER / "build-guided-audio.swift"),
                        str(tf), str(munka), str(KI / "G-SZAMOLAS-lassabb.m4a"),
                        str(int(hossz) + 3)], capture_output=True, text=True)
    print(r.stdout.rstrip() or r.stderr.rstrip())
    print(f"\negy kor: {hossz:.0f} mp (be {4*1.5:.0f} mp, bent {7*1.5:.1f} mp, ki {8*1.5:.0f} mp)")


if __name__ == "__main__":
    main()
