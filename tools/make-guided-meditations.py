#!/usr/bin/env python3
"""Render timed meditation scripts into finished guided-audio files.

Each script names what is said and the second it is said at. This speaks the
segments with the xAI voice, then hands them to build-guided-audio.swift,
which lays them on a timeline as long as the sitting — the gaps between are
the meditation.

    python3 tools/make-guided-meditations.py <script.json> [<script.json> …]
    python3 tools/make-guided-meditations.py --dry-run <script.json>

Finished files land in <module-dir>/audio/meditacio/<id>.m4a.

The API key is read from XAI_API_KEY or ~/.xai_key and never printed. Spending
here is small but real, so --dry-run reports the cost before anything is sent.
"""

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

API = "https://api.x.ai/v1/tts"
MODEL = "grok-tts"

# Which module a meditation id belongs to — the audio has to live beside the
# module that declares it.
MAPPA = {
    "ryokah-alchemy": "ryokah.alchemy",
    "ryokah-magick": "ryokah.magick",
    "bashar-shifting": "bashar.shifting",
}


def read_api_key() -> str:
    key = os.environ.get("XAI_API_KEY", "").strip()
    if key:
        return key
    p = pathlib.Path.home() / ".xai_key"
    if p.exists():
        return p.read_text().strip()
    sys.exit("No API key. Set XAI_API_KEY or write it to ~/.xai_key.")


def speak(text: str, key: str, lang: str, voice: str, retries: int = 4) -> bytes:
    body = json.dumps({
        "model": MODEL, "voice_id": voice, "language": lang,
        "text": text, "format": "mp3",
    }).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                API, data=body,
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                audio = r.read()
            if len(audio) < 500:
                raise ValueError(f"gyanusan rovid valasz: {len(audio)} bajt")
            return audio
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                OSError, ValueError) as err:
            if attempt == retries - 1:
                raise
            wait = 3 * (attempt + 1)
            print(f"      ujra {attempt + 1}/{retries - 1} — {err} ({wait}s)", flush=True)
            time.sleep(wait)


def modul_mappa(med_id: str) -> str:
    for elotag, mappa in MAPPA.items():
        if med_id.startswith(elotag):
            return mappa
    sys.exit(f"nem tudom, melyik modulhoz tartozik: {med_id}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scripts", nargs="+")
    ap.add_argument("--lang", default="hu")
    ap.add_argument("--voice", default="ara")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    gyoker = pathlib.Path(__file__).resolve().parent.parent
    osszes_kar = 0
    tervek = []
    for s in args.scripts:
        for t in json.loads(pathlib.Path(s).read_text()):
            tervek.append(t)
            osszes_kar += sum(len(x["szoveg"]) for x in t["szegmensek"])

    for t in tervek:
        modul_mappa(t["id"])       # elore dol el, ne API-hivas utan alljon le
    print(f"{len(tervek)} meditáció, {osszes_kar:,} karakter")
    print(f"becsült költség: ~${osszes_kar / 1_000_000 * 4.2:.3f}")
    if args.dry_run:
        for t in tervek:
            b = sum(len(x["szoveg"]) for x in t["szegmensek"])
            print(f"  {t['cim']:<34} {t['hossz']:>4}s  {len(t['szegmensek']):>2} szegmens  "
                  f"{b:>5} kar  (~{b/14:.0f}s beszéd, {b/14/t['hossz']*100:.0f}%)")
        return

    key = read_api_key()
    munka = gyoker / ".guided-tmp"
    munka.mkdir(exist_ok=True)

    for t in tervek:
        print(f"\n{t['cim']}")
        seg_dir = munka / t["id"]
        seg_dir.mkdir(exist_ok=True)
        for i, sz in enumerate(t["szegmensek"]):
            cel = seg_dir / f"{i:02d}.mp3"
            if cel.exists() and cel.stat().st_size > 500:
                continue
            print(f"    {i + 1}/{len(t['szegmensek'])} …", flush=True)
            cel.write_bytes(speak(sz["szoveg"], key, args.lang, args.voice))

        ki_dir = gyoker / modul_mappa(t["id"]) / "audio" / "meditacio"
        ki_dir.mkdir(parents=True, exist_ok=True)
        ki = ki_dir / f"{t['id']}.m4a"

        terv_fajl = seg_dir / "terv.json"
        terv_fajl.write_text(json.dumps(t, ensure_ascii=False))
        r = subprocess.run(
            ["xcrun", "swift", str(gyoker / "tools" / "build-guided-audio.swift"),
             str(terv_fajl), str(seg_dir), str(ki), str(t["hossz"])],
            capture_output=True, text=True)
        print(r.stdout.rstrip() or r.stderr.rstrip())
        if r.returncode != 0:
            sys.exit(f"osszerakas hiba: {t['id']}")

    print(f"\nkész — a szegmensek itt maradtak: {munka} (törölhető)")


if __name__ == "__main__":
    main()
