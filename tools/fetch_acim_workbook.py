#!/usr/bin/env python3
"""Build the ACIM Workbook module from Wikisource.

The 1975 edition of A Course in Miracles is in the public domain in the
United States: it was published without a copyright notice before 1978,
and a 2003 ruling in the Southern District of New York (Penguin Books USA
v. New Christian Church of Full Endeavor) found the copyright invalid.
Wikisource hosts it on that basis, which is why the text can be carried
here in full rather than paraphrased like the rest of the catalog.

Only the English 1975 text is free. Later editions (1992, 2007) were
re-edited and are claimed separately, and every translation is its own
copyrighted work — so a Hungarian workbook has to come from the reader's
own copy through the app's importer, not from here.

    python3 tools/fetch_acim_workbook.py            # build the module
    python3 tools/fetch_acim_workbook.py --dry-run  # just report what it finds

Re-running is safe: it rebuilds the file from scratch.
"""

import argparse
import json
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request

API = "https://en.wikisource.org/w/api.php"
INDEX = "A Course in Miracles/Workbook for Students"
UA = "MagusNaplo-catalog/1.0 (https://github.com/leonardnagy/magus-modules)"

# Fetched in batches: one request per lesson would be 365 hits on a
# volunteer-run server for a job that fits in eight.
BATCH = 50


def api(params: dict) -> dict:
    params = {**params, "format": "json", "formatversion": "2"}
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def index_entries():
    """(lesson number, page title) for all 365, from the contents page."""
    data = api({"action": "parse", "page": INDEX, "prop": "wikitext"})
    text = data["parse"]["wikitext"]["*"] if "*" in str(data["parse"]["wikitext"]) \
        else data["parse"]["wikitext"]
    if isinstance(text, dict):
        text = text["*"]
    out = []
    # The last five lessons share one page — the Workbook gives 361 to 365
    # the same prayer — so the contents lists them as "361-365.".
    for first, last, title in re.findall(
            r":\s*(\d+)(?:\s*-\s*(\d+))?\.\s*\[\[/(.+?)/?\]\]", text):
        page = f"{INDEX}/{title.split('|')[0]}"
        for num in range(int(first), int(last or first) + 1):
            out.append((num, page))
    return out


def strip_templates(text: str) -> str:
    """Drop {{...}} blocks, brace-counting so nested ones go too."""
    out, depth, i = [], 0, 0
    while i < len(text):
        if text.startswith("{{", i):
            depth += 1
            i += 2
        elif text.startswith("}}", i) and depth:
            depth -= 1
            i += 2
        else:
            if not depth:
                out.append(text[i])
            i += 1
    return "".join(out)


def to_markdown(wikitext: str) -> str:
    s = strip_templates(wikitext)
    s = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", s)     # [[a|b]] -> b
    s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)              # [[a]]   -> a
    s = re.sub(r"'''(.+?)'''", r"**\1**", s, flags=re.S)
    s = re.sub(r"''(.+?)''", r"*\1*", s, flags=re.S)
    s = re.sub(r"^=====\s*(.+?)\s*=====$", r"##### \1", s, flags=re.M)
    s = re.sub(r"^====\s*(.+?)\s*====$", r"#### \1", s, flags=re.M)
    s = re.sub(r"^===\s*(.+?)\s*===$", r"### \1", s, flags=re.M)
    # The indented lines are the phrases to say — a quote block reads them
    # the way they are meant to be used.
    s = re.sub(r"^:+\s*(.+)$", r"> \1", s, flags=re.M)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def fetch_pages(titles):
    """title -> wikitext, in batches."""
    got = {}
    for i in range(0, len(titles), BATCH):
        chunk = titles[i:i + BATCH]
        data = api({"action": "query", "prop": "revisions", "rvprop": "content",
                    "rvslots": "main", "titles": "|".join(chunk)})
        for page in data.get("query", {}).get("pages", []):
            if "revisions" not in page:
                continue
            got[page["title"]] = page["revisions"][0]["slots"]["main"]["content"]
        print(f"  {min(i + BATCH, len(titles))}/{len(titles)}", flush=True)
        time.sleep(0.5)          # be a decent guest
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = pathlib.Path(__file__).resolve().parent.parent
    print("Tartalomjegyzék…", flush=True)
    entries = index_entries()
    print(f"  {len(entries)} lecke a jegyzékben")
    if len(entries) != 365:
        print(f"  FIGYELEM: 365 helyett {len(entries)} — a jegyzék változhatott")
    if args.dry_run:
        for n, t in entries[:3] + entries[-2:]:
            print(f"   {n:>3}. {t.split('/')[-1]}")
        return

    print("Leckék letöltése…", flush=True)
    cimek = list(dict.fromkeys([t for _, t in entries]))     # de-dup: 361-365 share one
    cimek.append(f"{INDEX}/Introduction")
    pages = fetch_pages(cimek)

    items, hianyzo = [], []
    if (bev := pages.get(f"{INDEX}/Introduction".replace("_", " "))):
        items.append({
            "id": "acim-wb-000",
            "kind": "markdown",
            "nevek": {"hu": "Bevezető a Munkafüzethez", "en": "Introduction"},
            "text": {"hu": to_markdown(bev), "en": to_markdown(bev)},
        })

    for num, title in entries:
        raw = pages.get(title.replace("_", " "))
        if raw is None:
            hianyzo.append(num)
            continue
        cim = title.split("/")[-1].replace("_", " ")
        body = to_markdown(raw)
        items.append({
            "id": f"acim-wb-{num:03d}",
            "kind": "markdown",
            "nevek": {"hu": f"{num}. lecke — {cim}", "en": f"Lesson {num} — {cim}"},
            "text": {"hu": body, "en": body},
        })
    if hianyzo:
        print(f"  hiányzó lecke: {len(hianyzo)} → {hianyzo[:10]}")

    modul = {
        "formatVersion": 1,
        "id": "acim-workbook",
        "version": "1.0.0",
        "nevek": {
            "hu": "A csodák tanítása — Munkafüzet (1975, eredeti kiadás)",
            "en": "A Course in Miracles — Workbook for Students (1975 Original Edition)",
        },
        "description": {
            "hu": ("A Munkafüzet mind a 365 leckéje az 1975-ös eredeti kiadásból, "
                   "amely az Egyesült Államokban közkincs. Angolul — a magyar fordítás "
                   "önálló, védett mű, azt a saját példányodból az importálóval "
                   "olvashatod be. Forrás: Wikisource."),
            "en": ("All 365 lessons of the Workbook from the 1975 Original Edition, "
                   "which is in the public domain in the United States. Source: "
                   "Wikisource."),
        },
        "items": items,
    }
    out = root / "acim.workbook"
    out.mkdir(exist_ok=True)
    (out / "module.json").write_text(
        json.dumps(modul, ensure_ascii=False, indent=2) + "\n")
    meret = (out / "module.json").stat().st_size
    print(f"\nacim.workbook/module.json — {len(items)} elem, {meret/1024/1024:.2f} MB")
    leckek = [i for i in items if i["id"] != "acim-wb-000"]
    if len(leckek) != 365:
        sys.exit(f"365 helyett {len(leckek)} lecke — nézd meg a hiányzókat")


if __name__ == "__main__":
    main()
