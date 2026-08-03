#!/usr/bin/env python3
"""Add a language to every module, practice pack and quote file.

The catalog is authored in Hungarian and English. This walks every JSON,
finds each localized block (a dict whose keys are all language codes),
and fills in the missing language from the English text.

The English is the source rather than the Hungarian because it is the one
written to be translated from — the Hungarian is deliberately colloquial
and second-person, and reads oddly when carried across twice.

Two things in the text are load-bearing and must survive intact:

  * a trailing " *" marks an extraordinary claim, and
  * the "[FINE]" line is the footnote that explains those markers.

If either count changes, the honesty framing quietly breaks — so both are
checked after every batch and the batch is retried when they don't match.

The API key is read from XAI_API_KEY or ~/.xai_key and never printed.

Usage:
    python3 tools/translate.py --lang ro
    python3 tools/translate.py --lang ro --dry-run
    python3 tools/translate.py --lang ro --only 'tarot.oracle/*'
"""

import argparse
import fnmatch
import glob
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

API = "https://api.x.ai/v1/chat/completions"
MODEL = "grok-4.5"
LANGS = {"hu", "en", "de", "es", "fr", "it", "pt", "ro", "pl", "cs", "sk",
         "ja", "zh", "ru", "ar"}

# The footnote is fixed wording, not something to re-invent per file: it is
# the same promise everywhere, and readers should meet it identically.
FOOTNOTE = {
    "ro": "[FINE]* Afirmațiile marcate cu asterisc sunt pretențiile "
          "extraordinare proprii tradiției — măsoară-le după roadele lor "
          "lăuntrice, nu ca pe fapte dovedite.",
}

NYELV_NEV = {"ro": "Romanian (română)"}


def read_api_key() -> str:
    key = os.environ.get("XAI_API_KEY", "").strip()
    if key:
        return key
    path = pathlib.Path.home() / ".xai_key"
    if path.exists():
        return path.read_text().strip()
    sys.exit("No API key. Set XAI_API_KEY or write it to ~/.xai_key.")


def localized_blocks(node, out):
    """Every dict that is a localized block, in document order.

    A block holds either one string per language, or one list of strings —
    quiz options are authored as parallel arrays.
    """
    if isinstance(node, dict):
        keys = set(node.keys())
        if "en" in keys and keys <= LANGS:
            out.append(node)
            return
        for value in node.values():
            localized_blocks(value, out)
    elif isinstance(node, list):
        for value in node:
            localized_blocks(value, out)


def units(block):
    """(block, slot, english) for each translatable string in a block.

    `slot` is None for a plain string block, or the list index for an
    array block — which is how the answer is put back in the right place.
    """
    en = block.get("en")
    if isinstance(en, str):
        return [(block, None, en)] if en.strip() else []
    if isinstance(en, list):
        return [(block, i, s) for i, s in enumerate(en)
                if isinstance(s, str) and s.strip()]
    return []


def marker_count(text: str) -> int:
    """Trailing ' *' claim markers — not '**bold**', which is markdown."""
    count = 0
    for i in range(len(text) - 1):
        if text[i] == " " and text[i + 1] == "*":
            after = text[i + 2] if i + 2 < len(text) else ""
            if after != "*":
                count += 1
    return count


def system_prompt(lang: str) -> str:
    return f"""You translate a spiritual-practice study app from English into {NYELV_NEV[lang]}.

Return ONLY a JSON array of strings, the same length and order as the input array. No prose, no markdown fence.

Rules, in order of importance:

1. Translate meaning, not words. The result must read as if written in {NYELV_NEV[lang]} by a warm, clear teacher. Address the reader informally (second person singular).
2. A sentence ending in " *" (space asterisk) MUST still end in " *". These mark extraordinary claims and the count must not change.
3. If the text contains a line starting with "[FINE]", replace that whole line with exactly:
   {FOOTNOTE[lang]}
4. Keep markdown structure exactly: headings (#), bold (**), italics, lists, blank lines, line breaks.
5. Never translate: proper names (Franz Bardon, José Silva, Bashar, Vadim Zeland…), module ids, URLs, anything inside {{curly braces}}, and technical terms the tradition uses untranslated (akasha, chakra names, mudra…). Sanskrit and Hebrew terms stay, with the local spelling where one is established.
6. Add nothing and drop nothing. No explanations, no softening, no extra claims. If a sentence makes a strong claim, it stays a strong claim — the asterisk is what qualifies it.
7. An empty string stays an empty string."""


def translate_batch(texts, lang, key, retries=4):
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt(lang)},
            {"role": "user", "content": json.dumps(texts, ensure_ascii=False)},
        ],
        "temperature": 0.2,
    }
    data = json.dumps(body).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                API, data=data,
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as resp:
                payload = json.load(resp)
            content = payload["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            out = json.loads(content)
            if not isinstance(out, list) or len(out) != len(texts):
                raise ValueError(f"expected {len(texts)} items, got "
                                 f"{len(out) if isinstance(out, list) else type(out)}")
            for src, dst in zip(texts, out):
                if not isinstance(dst, str):
                    raise ValueError("non-string in result")
                if src.strip() and not dst.strip():
                    raise ValueError("empty translation for non-empty source")
                if marker_count(src) != marker_count(dst):
                    raise ValueError(
                        f"claim markers {marker_count(src)} -> {marker_count(dst)}")
                if ("[FINE]" in src) != ("[FINE]" in dst):
                    raise ValueError("[FINE] footnote lost or invented")
            return out
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                OSError, ValueError, KeyError, json.JSONDecodeError) as err:
            if attempt == retries - 1:
                raise
            wait = 3 * (attempt + 1)
            print(f"    retry {attempt + 1}/{retries - 1} after {err} "
                  f"({wait}s)", flush=True)
            time.sleep(wait)


def ensure_slot(block: dict, lang: str):
    """Make room for the new language, right after 'en' so files stay readable."""
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


def put(block: dict, lang: str, slot, value: str):
    ensure_slot(block, lang)
    if slot is None:
        block[lang] = value
    else:
        block[lang][slot] = value


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="ro", choices=sorted(FOOTNOTE))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default="*")
    ap.add_argument("--batch-chars", type=int, default=6000)
    args = ap.parse_args()
    lang = args.lang

    root = pathlib.Path(__file__).resolve().parent.parent
    os.chdir(root)
    files = (sorted(glob.glob("*/module.json"))
             + sorted(glob.glob("practices/*.json"))
             + sorted(glob.glob("quotes/*.json")))
    files = [f for f in files if fnmatch.fnmatch(f, args.only)]

    grand_fields = grand_chars = 0
    failures = []

    for path in files:
        doc = json.loads(pathlib.Path(path).read_text())
        blocks = []
        localized_blocks(doc, blocks)
        todo = [u for b in blocks if lang not in b for u in units(b)]
        # An empty English string is an empty slot everywhere — mirror it.
        for b in blocks:
            if lang not in b and not units(b):
                ensure_slot(b, lang)
        if not todo:
            continue
        chars = sum(len(t) for _, _, t in todo)
        grand_fields += len(todo)
        grand_chars += chars
        print(f"{path:<52} {len(todo):4d} mező {chars:8,d} kar", flush=True)
        if args.dry_run:
            continue

        key = read_api_key()
        batch, size = [], 0
        batches = []
        for unit in todo:
            if batch and (size + len(unit[2]) > args.batch_chars or len(batch) >= 30):
                batches.append(batch)
                batch, size = [], 0
            batch.append(unit)
            size += len(unit[2])
        if batch:
            batches.append(batch)

        done = True
        for i, group in enumerate(batches, 1):
            try:
                out = translate_batch([t for _, _, t in group], lang, key)
            except Exception as err:                      # noqa: BLE001
                print(f"    !! batch {i}/{len(batches)} feladva: {err}", flush=True)
                failures.append((path, i, str(err)))
                done = False
                continue
            for (block, slot, _), text in zip(group, out):
                put(block, lang, slot, text)
            print(f"    {i}/{len(batches)} kész", flush=True)
        if not done:
            # A half-filled block would look translated to the parity check,
            # so leave the file for the next run rather than writing a lie.
            print(f"    {path}: hiányos, fájl változatlan", flush=True)
            continue

        pathlib.Path(path).write_text(
            json.dumps(doc, ensure_ascii=False, indent=2) + "\n")

    print("-" * 68)
    print(f"összesen {grand_fields:,} mező, {grand_chars:,} karakter")
    if args.dry_run:
        # Rough: output runs a little longer than the English source.
        tok_in = grand_chars / 4
        tok_out = grand_chars / 3.4
        print(f"becslés: ~{tok_in/1000:.0f}k be / ~{tok_out/1000:.0f}k ki token")
    if failures:
        print(f"SIKERTELEN kötegek: {len(failures)}")
        for f in failures:
            print("  ", f)
        sys.exit(1)


if __name__ == "__main__":
    main()
