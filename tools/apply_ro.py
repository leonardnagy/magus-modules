#!/usr/bin/env python3
"""Hand a file's untranslated strings out, and take the translations back.

Companion to translate.py for when the translating is done by something
other than the API — the ordering logic is shared so the strings go back
exactly where they came from, instead of being matched up by eye.

    python3 tools/apply_ro.py --list practices/seed.json > todo.json
    # …fill in a JSON array of the same length, same order…
    python3 tools/apply_ro.py --apply practices/seed.json ro.json

--apply refuses the whole file unless every string passes: same count, no
empties, the same number of trailing " *" claim markers, and [FINE] present
in the translation exactly when it is present in the English. A partial
write would look finished to the parity check, which is worse than nothing.
"""

import argparse
import json
import pathlib
import sys

LANGS = {"hu", "en", "de", "es", "fr", "it", "pt", "ro", "pl", "cs", "sk",
         "ja", "zh", "ru", "ar"}

FOOTNOTE_RO = ("[FINE]* Afirmațiile marcate cu asterisc sunt pretențiile "
               "extraordinare proprii tradiției — măsoară-le după roadele lor "
               "lăuntrice, nu ca pe fapte dovedite.")


def blocks(node, out):
    if isinstance(node, dict):
        if "en" in node and set(node) <= LANGS:
            out.append(node)
            return
        for value in node.values():
            blocks(value, out)
    elif isinstance(node, list):
        for value in node:
            blocks(value, out)


def missing_units(doc, lang):
    """(block, slot, english) for everything still untranslated, in order."""
    found = []
    blocks(doc, found)
    out = []
    for block in found:
        if lang in block:
            continue
        en = block.get("en")
        if isinstance(en, str):
            if en.strip():
                out.append((block, None, en))
        elif isinstance(en, list):
            for i, s in enumerate(en):
                if isinstance(s, str) and s.strip():
                    out.append((block, i, s))
    return out


def marker_count(text: str) -> int:
    return sum(1 for i in range(len(text) - 1)
               if text[i] == " " and text[i + 1] == "*"
               and (i + 2 >= len(text) or text[i + 2] != "*"))


def ensure_slot(block, lang):
    if lang in block:
        return
    en = block.get("en")
    blank = [""] * len(en) if isinstance(en, list) else ""
    items = list(block.items())
    block.clear()
    for k, v in items:
        block[k] = v
        if k == "en":
            block[lang] = blank
    if lang not in block:
        block[lang] = blank


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="ro")
    ap.add_argument("--list", metavar="FILE")
    ap.add_argument("--apply", nargs=2, metavar=("FILE", "TRANSLATIONS"))
    args = ap.parse_args()

    if args.list:
        doc = json.loads(pathlib.Path(args.list).read_text())
        units = missing_units(doc, args.lang)
        print(json.dumps([t for _, _, t in units], ensure_ascii=False, indent=1))
        return

    if not args.apply:
        ap.error("use --list or --apply")

    path, tpath = args.apply
    doc = json.loads(pathlib.Path(path).read_text())
    units = missing_units(doc, args.lang)
    trans = json.loads(pathlib.Path(tpath).read_text())

    if not isinstance(trans, list) or len(trans) != len(units):
        sys.exit(f"{path}: expected {len(units)} strings, got "
                 f"{len(trans) if isinstance(trans, list) else type(trans)}")

    problems = []
    for i, ((_, _, en), ro) in enumerate(zip(units, trans)):
        if not isinstance(ro, str) or not ro.strip():
            problems.append(f"[{i}] empty")
            continue
        if marker_count(en) != marker_count(ro):
            problems.append(f"[{i}] claim markers {marker_count(en)}"
                            f" -> {marker_count(ro)}")
        if ("[FINE]" in en) != ("[FINE]" in ro):
            problems.append(f"[{i}] [FINE] footnote lost or invented")
        elif "[FINE]" in ro and FOOTNOTE_RO not in ro:
            problems.append(f"[{i}] [FINE] footnote is not the fixed wording")
    if problems:
        sys.exit(f"{path}: {len(problems)} problem(s), nothing written\n  "
                 + "\n  ".join(problems[:12]))

    for (block, slot, _), ro in zip(units, trans):
        ensure_slot(block, args.lang)
        if slot is None:
            block[args.lang] = ro
        else:
            block[args.lang][slot] = ro

    pathlib.Path(path).write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    print(f"{path}: {len(trans)} strings written")


if __name__ == "__main__":
    main()
