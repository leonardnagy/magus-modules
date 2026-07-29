#!/usr/bin/env python3
"""Pre-render module lesson audio with the xAI TTS API (Ara voice).

Why pre-render instead of calling a TTS API from the app: no API key ever ships
in the binary, there is no per-play cost, it works offline, and the phone plays
a real neural voice instead of the on-device synthesizer.

The audio lands next to the module it belongs to:

    <module-dir>/audio/<lang>/<item-id>.mp3

The app looks for exactly that file; if it is missing it falls back to the
built-in on-device read-aloud, so partial coverage is always safe.

Usage
-----
    export XAI_API_KEY=...            # never pass the key on the command line
    python3 tools/generate_audio.py acim.easy --dry-run     # count + cost only
    python3 tools/generate_audio.py acim.easy               # generate
    python3 tools/generate_audio.py --all --lang hu         # everything

The text is cleaned the same way the app's Felolvaso.tisztit() cleans it, so
the spoken words match what the reader hears from the built-in voice.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENDPOINT = "https://api.x.ai/v1/tts"
USD_PER_MILLION_CHARS = 4.20        # xAI TTS list price
MAX_CHARS_PER_REQUEST = 15_000      # xAI unary limit

# BCP-47 codes for the languages the content is authored in.
LANG_TAGS = {"hu": "hu", "en": "en"}


def read_api_key() -> str | None:
    """The key comes from the environment, or from ~/.xai_key — never from the
    command line (which would leave it in the shell history) and never from the
    repo (which would publish it)."""
    env = os.environ.get("XAI_API_KEY")
    if env and env.strip():
        return env.strip()
    key_file = Path.home() / ".xai_key"
    if key_file.exists():
        value = key_file.read_text().strip()
        if value:
            return value
    return None


def clean(text: str) -> str:
    """Mirror of the app's Felolvaso.tisztit(): drop the [FINE] footnote and
    markdown scaffolding, then join lines into sentences."""
    if "[FINE]" in text:
        text = text.split("[FINE]", 1)[0]
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)      # [label](url) -> label
    for token in ("**", "__", "`", "#", "*", "_", ">"):
        text = text.replace(token, "")
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line[-1] not in ".!?;:,。！？；：、．":
            line += "."
        lines.append(line)
    return " ".join(lines).strip()


def chunks(text: str, limit: int = MAX_CHARS_PER_REQUEST):
    """Split on sentence boundaries so no chunk exceeds the API limit."""
    if len(text) <= limit:
        return [text]
    out, current = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if len(current) + len(sentence) + 1 > limit and current:
            out.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        out.append(current.strip())
    return out


def synthesize(text: str, lang: str, voice: str, api_key: str, bitrate: int) -> bytes:
    """One TTS call. Returns raw MP3 bytes."""
    body = json.dumps({
        "text": text,
        "voice_id": voice,
        "language": LANG_TAGS.get(lang, lang),
        "output_format": {"codec": "mp3", "sample_rate": 24000, "bit_rate": bitrate},
    }).encode()
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            # Rate limits and transient server errors are worth another go.
            if exc.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** attempt * 2)
                continue
            raise SystemExit(f"xAI TTS failed ({exc.code}): {detail}")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            # A read that times out mid-response surfaces as a bare TimeoutError,
            # not a URLError — which used to kill a long run outright.
            if attempt < 3:
                time.sleep(2 ** attempt * 2)
                continue
            raise SystemExit(f"xAI TTS unreachable: {exc}")
    raise SystemExit("xAI TTS failed after retries")


def readable_items(module: dict, lang: str):
    """(item_id, cleaned_text) for every lesson item that has spoken text."""
    for item in module.get("items", []):
        if item.get("kind") not in ("markdown", "text"):
            continue
        text = (item.get("text") or {}).get(lang, "")
        body = clean(text)
        if body:
            yield item["id"], body


def process(module_dir: Path, lang: str, voice: str, bitrate: int,
            dry_run: bool, force: bool, api_key: str | None):
    module_path = module_dir / "module.json"
    if not module_path.exists():
        return 0, 0, 0
    module = json.loads(module_path.read_text())
    out_dir = module_dir / "audio" / lang
    items = list(readable_items(module, lang))
    total_chars = sum(len(t) for _, t in items)
    written = written_bytes = 0

    if dry_run:
        print(f"  {module_dir.name:26} {len(items):3} items  {total_chars:>8,} chars "
              f"≈ ${total_chars / 1_000_000 * USD_PER_MILLION_CHARS:.2f}")
        return total_chars, 0, 0

    out_dir.mkdir(parents=True, exist_ok=True)
    for item_id, text in items:
        target = out_dir / f"{item_id}.mp3"
        if target.exists() and not force:
            print(f"  skip (exists) {target.relative_to(REPO)}")
            continue
        audio = b"".join(synthesize(part, lang, voice, api_key, bitrate)
                         for part in chunks(text))
        target.write_bytes(audio)
        written += 1
        written_bytes += len(audio)
        print(f"  wrote {target.relative_to(REPO)}  "
              f"({len(text):,} chars → {len(audio) / 1024:.0f} KB)")
    return total_chars, written, written_bytes


def practice_text(g: dict, lang: str) -> str:
    """A practice read end to end: title, aim, each method step, the frame."""
    parts = [(g.get("cim") or {}).get(lang, ""), (g.get("cel") or {}).get(lang, "")]
    parts += [(step or {}).get(lang, "") for step in g.get("modszer", [])]
    parts.append((g.get("keret") or {}).get(lang, ""))
    if g.get("etika"):
        parts.append(g["etika"].get(lang, ""))
    return clean("\n".join(p for p in parts if p))


def process_practices(lang: str, voice: str, bitrate: int,
                      dry_run: bool, force: bool, api_key: str | None):
    """Practice ids are globally unique across packs, so one flat folder is
    enough and a pack can be installed without knowing which file belongs where."""
    out_dir = REPO / "audio" / "practices" / lang
    total_chars = written = written_bytes = 0

    for pack_path in sorted((REPO / "practices").glob("*.json")):
        pack = json.loads(pack_path.read_text())
        for g in pack.get("gyakorlatok", []):
            text = practice_text(g, lang)
            if not text:
                continue
            total_chars += len(text)
            if dry_run:
                continue
            out_dir.mkdir(parents=True, exist_ok=True)
            target = out_dir / f"{g['id']}.mp3"
            if target.exists() and not force:
                continue
            audio = b"".join(synthesize(part, lang, voice, api_key, bitrate)
                             for part in chunks(text))
            target.write_bytes(audio)
            written += 1
            written_bytes += len(audio)
            print(f"  wrote {target.relative_to(REPO)}  "
                  f"({len(text):,} chars → {len(audio) / 1024:.0f} KB)")

    if dry_run:
        print(f"  {'practices':26} {total_chars:>10,} chars "
              f"≈ ${total_chars / 1_000_000 * USD_PER_MILLION_CHARS:.2f}")
    return total_chars, written, written_bytes


def main():
    ap = argparse.ArgumentParser(description="Pre-render module audio with xAI TTS.")
    ap.add_argument("modules", nargs="*", help="module directory names (e.g. acim.easy)")
    ap.add_argument("--all", action="store_true", help="every module in the repo")
    ap.add_argument("--practices", action="store_true", help="render the practice packs instead")
    ap.add_argument("--lang", default="hu", choices=sorted(LANG_TAGS))
    ap.add_argument("--voice", default="ara", help="ara | eve | leo | rex | sal")
    ap.add_argument("--bitrate", type=int, default=64000, help="MP3 bit rate")
    ap.add_argument("--dry-run", action="store_true", help="count characters and cost only")
    ap.add_argument("--force", action="store_true", help="regenerate existing files")
    args = ap.parse_args()

    if args.practices:
        dirs = []
    elif args.all:
        dirs = sorted(p.parent for p in REPO.glob("*/module.json"))
    else:
        dirs = [REPO / name for name in args.modules]
        missing = [d.name for d in dirs if not (d / "module.json").exists()]
        if not dirs or missing:
            raise SystemExit(f"no module.json for: {missing or '(nothing given)'}")

    api_key = read_api_key()
    if not args.dry_run and not api_key:
        raise SystemExit(
            "No xAI API key found. Either of these works:\n"
            "  1. printf '%s' 'YOUR_KEY' > ~/.xai_key && chmod 600 ~/.xai_key\n"
            "  2. export XAI_API_KEY=YOUR_KEY   (e.g. from ~/.zshrc)\n"
            "Get a key at https://console.x.ai — run with --dry-run to see the\n"
            "character count and cost without one."
        )

    chars = files = size = 0
    for d in dirs:
        c, f, s = process(d, args.lang, args.voice, args.bitrate,
                          args.dry_run, args.force, api_key)
        chars += c
        files += f
        size += s
    if args.practices:
        c, f, s = process_practices(args.lang, args.voice, args.bitrate,
                                    args.dry_run, args.force, api_key)
        chars += c
        files += f
        size += s

    print("-" * 68)
    print(f"{'TOTAL':26} {chars:>10,} chars  ≈ ${chars / 1_000_000 * USD_PER_MILLION_CHARS:.2f}"
          f"   ({args.lang}, voice: {args.voice})")
    if not args.dry_run:
        print(f"{'':26} {files} files written, {size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    sys.exit(main())
