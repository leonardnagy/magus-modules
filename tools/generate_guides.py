#!/usr/bin/env python3
"""Render the app's own spoken guidance with the xAI TTS API (Ara voice).

The app has no on-device voice any more, so every line it reads aloud needs
a recording. Most are catalog content (generate_audio.py); these are the
app's own texts: the Quantum Jumping guide, the "two self-images" step cards,
the channeling session's entry, close and question bank. They are listed, with
the exact words, in tools/utmutato-hangok.json:

    [{"id": "kvantum-1", "lang": "hu", "text": "...", "dest": ".../audio/guides/hu/kvantum-1.mp3"}]

The app looks for them under audio/guides/<lang>/<id>.mp3 and shows the
read-aloud button only once hangok.json lists the file. The channeling entry
and close play only when every line of the chosen language and entity is
there, so render a whole group, not single lines.

Usage
-----
    python3 tools/generate_guides.py --dry-run          # count + cost only
    python3 tools/generate_guides.py                    # render what is missing
    python3 tools/generate_guides.py --only kvantum-    # ids starting with this
    python3 tools/build-everything.py                   # then re-index, and push

Costs money: Leonard approves every run (see the dry run's total).
"""
import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_audio import (REPO, USD_PER_MILLION_CHARS, chunks, read_api_key,  # noqa: E402
                            synthesize)

LIST = REPO / 'tools' / 'utmutato-hangok.json'


def main():
    ap = argparse.ArgumentParser(description='Render the app guides with xAI TTS.')
    ap.add_argument('--list', default=str(LIST), help='the JSON list to render')
    ap.add_argument('--lang', choices=['hu', 'en'], help='only this language')
    ap.add_argument('--only', default='', help='only ids starting with this')
    ap.add_argument('--voice', default='ara')
    ap.add_argument('--bitrate', type=int, default=64000)
    ap.add_argument('--dry-run', action='store_true', help='count characters and cost only')
    ap.add_argument('--force', action='store_true', help='render existing files again')
    args = ap.parse_args()

    with io.open(args.list, encoding='utf-8') as f:
        entries = json.load(f)
    todo = []
    for e in entries:
        if args.lang and e['lang'] != args.lang:
            continue
        if not e['id'].startswith(args.only):
            continue
        dest = os.path.join(str(REPO), e['dest'])
        if os.path.exists(dest) and not args.force:
            continue
        todo.append((e, dest))

    chars = sum(len(e['text']) for e, _ in todo)
    print('%d files, %s chars ≈ $%.3f' % (len(todo), format(chars, ','),
                                          chars / 1_000_000 * USD_PER_MILLION_CHARS))
    if args.dry_run or not todo:
        return
    api_key = read_api_key()
    if not api_key:
        raise SystemExit('No xAI API key (see generate_audio.py).')
    for e, dest in todo:
        audio = b''.join(synthesize(part, e['lang'], args.voice, api_key, args.bitrate)
                         for part in chunks(e['text']))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        tmp = dest + '.part'
        with open(tmp, 'wb') as f:
            f.write(audio)
        os.replace(tmp, dest)
        print('  wrote %s (%d chars -> %.0f KB)' % (os.path.relpath(dest, str(REPO)), len(e['text']),
                                                    len(audio) / 1024))


if __name__ == '__main__':
    main()
