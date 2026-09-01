#!/usr/bin/env python3
"""A kesz hangfajlt bekoti a modulba, hogy megjelenjen a Meditaciok fulon.

A hang a modul melle kerul (audio/meditacio/), a module.json pedig megkapja
a meditaciok bejegyzest — ugyanabban az alakban, ahogy a Ryokah-meditaciok.
"""
import json, pathlib, shutil, subprocess, sys

GYOKER = pathlib.Path(__file__).resolve().parent.parent.parent
ITT = pathlib.Path(__file__).resolve().parent
MODUL = "bashar.shifting"
AZON = "bashar-shifting-timer-hoppban-allas"
CIM = "Az első hoppban állás"
CSOPORT = "Bashar — vezetett gyakorlat"

def main():
    hang = ITT / f"{AZON}.m4a"
    if not hang.exists():
        sys.exit(f"nincs meg a hang: {hang}")

    cel_dir = GYOKER / MODUL / "audio" / "meditacio"
    cel_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(hang, cel_dir / hang.name)
    print(f"hang: {cel_dir / hang.name}  ({hang.stat().st_size/1024/1024:.1f} MB)")

    mj = GYOKER / MODUL / "module.json"
    d = json.loads(mj.read_text())
    url = f"{d['audioBase']}/meditacio/{AZON}.m4a"
    bejegyzes = {"nevek": {"hu": CIM}, "csoport": {"hu": CSOPORT},
                 "sorszam": 1, "url": url}
    meds = [m for m in d.get("meditaciok", []) if m.get("url") != url]
    meds.append(bejegyzes)
    d["meditaciok"] = meds
    # a verziot emelni kell, kulonben a telefon nem tolti ujra a modult
    fo, kozep, kis = (int(x) for x in str(d.get("version", "1.0.0")).split("."))
    d["version"] = f"{fo}.{kozep + 1}.0"
    mj.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
    print(f"module.json: {len(meds)} meditáció, verzió {d['version']}")

    r = subprocess.run([sys.executable, str(GYOKER / "tools" / "build-everything.py")],
                       capture_output=True, text=True, cwd=GYOKER)
    print((r.stdout or r.stderr).rstrip()[-600:])
    if r.returncode != 0:
        sys.exit("build-everything.py hiba")

if __name__ == "__main__":
    main()
