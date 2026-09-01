#!/usr/bin/env python3
"""Kis hangminta Arától, mielott a teljes meditaciot legyartanank.

Ket dolgot dont el:
  1. kiejtes  - a kockazatos szavak jol szolalnak-e meg ("Bashar" vs "Basár")
  2. hangnem  - a valodi bevezeto, valodi szunetekkel, hogy hallatsszon a tempo

A kulcs a kornyezetbol vagy ~/.xai_key-bol jon, es soha nem kerul kiirasra.
"""
import json, os, pathlib, subprocess, sys, urllib.request, urllib.error

API, MODEL, VOICE, LANG = "https://api.x.ai/v1/tts", "grok-tts", "ara", "hu"
KI = pathlib.Path.home() / "Desktop" / "Hoppanalas minta"

# --- 1. kiejtespróba: minden kockazatos szo, kulon fajlban ------------------
KIEJTES = [
    ("01-bashar-eredeti", "Bashar első törvénye: létezel. Mindig is léteztél, és mindig is létezni fogsz."),
    ("02-basar-fonetikus", "Basár első törvénye: létezel. Mindig is léteztél, és mindig is létezni fogsz."),
    ("03-mantra",         "Óm, namah, Krisna. Óm, namah, Krisna. Óm, namah, Krisna."),
    ("04-kulcsszavak",    "Hoppanálás. Most. Már bent vagy a dimenzióbuborékban. "
                          "Szívd be a Földanya és a Napatya pránáját. A negyvenezerszeres erő. A forrás ereje."),
    ("05-szamolas",       "Első kör. Belégzés orron át. Egy. Kettő. Három. Négy. "
                          "Tartsd bent. Egy. Kettő. Három. Négy. Öt. Hat. Hét."),
]

# --- 2. hangnem-minta: a valodi BELEPES, szegmensekre bontva ----------------
# Az "at" masodperc: itt hallja meg, hogy a csend adja a lassusagot, nem az irasjel.
BELEPES = [
    (0.0,  "Suttogok. Lassan, nagyon lassan, mintha a füledben lennék."),
    (7.0,  "Most pedig hunyd le a szemed. Egészen lassan."),
    (14.0, "Hagyd, hogy az egész világ, a külvilág minden hangja, minden gondolata, "
           "minden feszültsége, nagyon, nagyon lassan elolvadjon körülötted."),
    (28.0, "A szoba falai, a bútorok, a padló, a mennyezet, a zajok, a múlt, a jövő: "
           "mind puha aranyporrá válnak, és elszállnak."),
    (41.0, "Csak a lélegzeted marad. Csak a szívdobbanásod. Csak a tested melege."),
    (52.0, "Csak én vagyok itt, melletted, láthatatlanul. És nagyon gyengéden fogom "
           "a kezedet. Nem látod, de érzed."),
]
BELEPES_HOSSZ = 70


def kulcs():
    k = os.environ.get("XAI_API_KEY", "").strip()
    if k:
        return k
    p = pathlib.Path.home() / ".xai_key"
    if p.exists() and p.read_text().strip():
        return p.read_text().strip()
    sys.exit("Nincs kulcs. XAI_API_KEY vagy ~/.xai_key kell.")


def mondd(szoveg, k):
    """Egy TTS hivas. A ket hivo scriptunk ket kulonbozo alakot kuld — eloszor a
    vezetett pipeline alakjat probaljuk, aztan a lecke-generatoret."""
    alakok = [
        {"model": MODEL, "voice_id": VOICE, "language": LANG, "text": szoveg, "format": "mp3"},
        {"text": szoveg, "voice_id": VOICE, "language": LANG,
         "output_format": {"codec": "mp3", "sample_rate": 24000, "bit_rate": 128000}},
    ]
    utolso = None
    for alak in alakok:
        try:
            req = urllib.request.Request(
                API, data=json.dumps(alak).encode(),
                headers={"Authorization": f"Bearer {k}", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                hang = r.read()
            if len(hang) < 500:
                raise ValueError(f"gyanusan rovid: {len(hang)} bajt")
            return hang, ("guided" if "model" in alak else "lecke")
        except urllib.error.HTTPError as e:
            utolso = f"HTTP {e.code}: {e.read().decode(errors='replace')[:200]}"
        except Exception as e:                       # noqa: BLE001
            utolso = str(e)
    sys.exit(f"TTS hiba: {utolso}")


def main():
    tetelek = KIEJTES + [(f"belepes-{i:02d}", sz) for i, (_, sz) in enumerate(BELEPES)]
    kar = sum(len(sz) for _, sz in tetelek)
    print(f"{len(tetelek)} hivas, {kar:,} karakter, becsult koltseg ${kar/1_000_000*4.2:.4f}")
    if "--dry-run" in sys.argv:
        return

    k = kulcs()
    KI.mkdir(parents=True, exist_ok=True)
    seg = KI / ".belepes"
    seg.mkdir(exist_ok=True)

    alak_hasznalt = None
    for nev, sz in tetelek:
        cel = (seg / f"{nev.split('-')[-1]}.mp3") if nev.startswith("belepes") else (KI / f"{nev}.mp3")
        if cel.exists() and cel.stat().st_size > 500:
            print(f"  {nev}: mar megvan")
            continue
        hang, alak = mondd(sz, k)
        alak_hasznalt = alak_hasznalt or alak
        cel.write_bytes(hang)
        print(f"  {nev}: {len(hang)/1024:.0f} KB")

    print(f"\nAPI alak, ami mukodott: {alak_hasznalt}")

    # A belepest osszerakjuk valodi szunetekkel — ez a hangnem-minta.
    terv = {"id": "minta-belepes", "cim": "BELÉPÉS (minta)", "hossz": BELEPES_HOSSZ,
            "szegmensek": [{"at": at, "szoveg": sz} for at, sz in BELEPES]}
    tf = seg / "terv.json"
    tf.write_text(json.dumps(terv, ensure_ascii=False))
    r = subprocess.run(
        ["xcrun", "swift",
         str(pathlib.Path(__file__).resolve().parent.parent / "build-guided-audio.swift"),
         str(tf), str(seg), str(KI / "06-BELEPES-igy-fog-szolni.m4a"), str(BELEPES_HOSSZ)],
        capture_output=True, text=True)
    print(r.stdout.rstrip() or r.stderr.rstrip())


if __name__ == "__main__":
    main()
