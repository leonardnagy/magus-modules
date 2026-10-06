#!/usr/bin/env python3
"""Index every pre-rendered narration file: its size and the start of its sha256.

    python3 tools/hang_index.py            # writes hangok.json at the repo root

Why: the phone used to keep a narration for as long as a file of that name was
on it. A recording rendered again under the same name (the 36 rvap-* with
corrected accents) never reached a phone that already had the old one, and a
lesson that was never recorded kept a download arrow that could never clear.
With this list the app knows, per language and per id, exactly which
recordings exist and what each one should be: a file whose hash differs is
fetched again, an id that is not listed has no read-aloud button at all.

No API calls: it only reads files. Runs on its own, and build-everything.py
runs it too and embeds the same object in everything.json as "hangok", so the
one-scan install brings the list with the catalog. The root hangok.json is
what the app re-reads once a day, so a pushed re-recording arrives without
scanning again.

Order after rendering:  audio  ->  build-everything.py (runs this)  ->  one
commit with the mp3 files, hangok.json and everything.json  ->  push.

Shape (sorted, so the diffs stay small):

    {"formatVersion": 1,
     "gyakorlatok": {"audioBase": ".../audio/practices",
                     "nyelvek": {"hu": {"rvap-cue-alap": [339648, "d4a67eb190a215cd"]}}},
     "modulok":     {"rv-basics": {"audioBase": ".../rv.basics/audio",
                                   "nyelvek": {"hu": {"<itemId>": [size, "sha16"]}}}},
     "munkafuzetek": {"acim-workbook": {"audioBase": ".../acim.workbook/audio",
                                        "hangNyelv": "en", "nyelvek": {"en": {...}}}},
     "utmutatok":   {"audioBase": ".../audio/guides", "nyelvek": {"hu": {"kvantum-1": [...]}}}}

Only files git tracks or would add are listed (ignored files are not). A file
that is not in git yet is listed with a warning: it has to go up in the same
commit, or the phone is promised a file the server does not have.
"""
import glob
import hashlib
import io
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = 'https://raw.githubusercontent.com/leonardnagy/magus-modules/main'
SHA_LEN = 16
# A workbook is read in its own language whatever the interface is: the
# English Workbook's lessons carry the English text under "hu" too.
WORKBOOKS = {'acim-workbook': 'en'}
GUIDES_DIR = 'audio/guides'


def load(path):
    with io.open(path, encoding='utf-8') as f:
        return json.load(f)


def git_files():
    """(every path git tracks or would add, the ones it does not track yet)."""
    def ls(*args):
        out = subprocess.run(['git', '-C', ROOT, 'ls-files', '-z'] + list(args),
                             check=True, capture_output=True).stdout
        return {p.decode('utf-8') for p in out.split(b'\0') if p}
    try:
        tracked = ls('--cached')
        untracked = ls('--others', '--exclude-standard')
    except (OSError, subprocess.CalledProcessError) as e:
        sys.exit('git ls-files failed: %s' % e)
    return tracked | untracked, untracked


def fingerprint(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return [os.path.getsize(path), h.hexdigest()[:SHA_LEN]]


def folder_of(base):
    """The repo folder an audioBase points at, or None for one hosted elsewhere."""
    base = (base or '').strip().rstrip('/')
    if not base.startswith(RAW + '/'):
        return None
    return base[len(RAW) + 1:]


def narratable(item, lang):
    if item.get('kind') not in ('markdown', 'text'):
        return False
    return bool(((item.get('text') or {}).get(lang) or '').strip())


class Index:
    def __init__(self, verbose):
        self.verbose = verbose
        self.in_git, self.untracked = git_files()
        self.warnings = []
        self.new_files = []
        self.fresh = []

    def warn(self, text):
        self.warnings.append(text)

    def scan(self, rel_folder, known_ids=None):
        """{lang: {id: [size, sha]}} for the mp3 files under rel_folder/<lang>/."""
        out = {}
        folder = os.path.join(ROOT, rel_folder)
        if not os.path.isdir(folder):
            return out
        now = time.time()
        for lang in sorted(os.listdir(folder)):
            lang_dir = os.path.join(folder, lang)
            if not os.path.isdir(lang_dir):
                continue
            files = {}
            for name in sorted(os.listdir(lang_dir)):
                if not name.endswith('.mp3'):
                    continue
                rel = '%s/%s/%s' % (rel_folder, lang, name)
                if rel not in self.in_git:
                    continue
                file_id = name[:-4]
                if known_ids is not None and file_id not in known_ids:
                    self.warn('arva fajl (nincs mogotte elem): %s' % rel)
                    continue
                if not all(ord(c) < 128 for c in file_id):
                    self.warn('nem ASCII azonosito: %s' % rel)
                path = os.path.join(lang_dir, name)
                if now - os.path.getmtime(path) < 60:
                    self.fresh.append(rel)
                if os.path.getsize(path) == 0:
                    self.warn('ures fajl, kihagyva: %s' % rel)
                    continue
                if rel in self.untracked:
                    self.new_files.append(rel)
                files[file_id] = fingerprint(path)
            if files:
                out[lang] = files
        return out

    def build(self):
        result = {'formatVersion': 1}

        # Practices: ids are unique across packs, so one flat folder per
        # language serves them all (see generate_audio.process_practices).
        packs = [load(p) for p in sorted(glob.glob(os.path.join(ROOT, 'practices', '*.json')))]
        ids = {g['id'] for p in packs for g in p.get('gyakorlatok', [])}
        bases = sorted({p.get('audioBase') for p in packs if p.get('audioBase')})
        if len(bases) > 1:
            self.warn('a gyakorlatcsomagok kulonbozo audioBase-t adnak: %s' % ', '.join(bases))
        if bases and folder_of(bases[0]):
            nyelvek = self.scan(folder_of(bases[0]), ids)
            result['gyakorlatok'] = {'audioBase': bases[0], 'nyelvek': nyelvek}
            for lang, files in nyelvek.items():
                missing = sorted(ids - set(files))
                if missing:
                    self.warn('%d gyakorlat felvetel nelkul (%s): %s%s' % (
                        len(missing), lang, ', '.join(missing[:12]), ' …' if len(missing) > 12 else ''))

        # Modules, and the workbook, which the app keeps apart from them.
        modulok, fuzetek = {}, {}
        for path in sorted(glob.glob(os.path.join(ROOT, '*', 'module.json'))):
            m = load(path)
            base = m.get('audioBase')
            rel = folder_of(base)
            if not rel:
                continue
            items = m.get('items', [])
            ids = {i['id'] for i in items}
            nyelvek = self.scan(rel, ids)
            if m['id'] in WORKBOOKS:
                fuzetek[m['id']] = {'audioBase': base, 'hangNyelv': WORKBOOKS[m['id']], 'nyelvek': nyelvek}
                continue
            if not nyelvek:
                continue
            modulok[m['id']] = {'audioBase': base, 'nyelvek': nyelvek}
            for lang, files in nyelvek.items():
                missing = sorted(i['id'] for i in items if narratable(i, lang) and i['id'] not in files)
                if missing:
                    self.warn('%s: %d lecke felvetel nelkul (%s): %s%s' % (
                        m['id'], len(missing), lang, ', '.join(missing[:8]), ' …' if len(missing) > 8 else ''))
        result['modulok'] = modulok
        result['munkafuzetek'] = fuzetek

        # The app's own guides (the Quantum Jumping steps, the channeling
        # session's entry and close, the question bank). Their ids are the
        # app's, so they are not checked against anything here.
        guides = self.scan(GUIDES_DIR)
        if guides:
            result['utmutatok'] = {'audioBase': RAW + '/' + GUIDES_DIR, 'nyelvek': guides}
        return result

    def report(self, result):
        def count(group):
            return sum(len(v) for v in (group or {}).get('nyelvek', {}).values())
        n_gy = count(result.get('gyakorlatok'))
        n_m = sum(count(g) for g in result.get('modulok', {}).values())
        n_wb = sum(count(g) for g in result.get('munkafuzetek', {}).values())
        n_ut = count(result.get('utmutatok'))
        print('hangok: %d gyakorlat, %d lecke (%d modul), %d munkafuzet-lecke, %d utmutato'
              % (n_gy, n_m, len(result.get('modulok', {})), n_wb, n_ut))
        if not self.verbose:
            return
        for w in self.warnings:
            print('FIGYELEM: ' + w)
        if self.new_files:
            print('FIGYELEM: %d fajl meg nincs a gitben — ugyanabban a commitban menjen fel, mint a hangok.json:'
                  % len(self.new_files))
            for p in self.new_files[:10]:
                print('  ' + p)
            if len(self.new_files) > 10:
                print('  …')
        if self.fresh:
            print('FIGYELEM: %d fajl az utolso percben valtozott (meg irodik?). Generalas utan futtasd ujra.'
                  % len(self.fresh))


def build(verbose=True):
    idx = Index(verbose)
    result = idx.build()
    idx.report(result)
    return result


def write(result, path=None):
    path = path or os.path.join(ROOT, 'hangok.json')
    with io.open(path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
    return path


def main():
    result = build()
    path = write(result)
    print('%s: %.0f KB' % (os.path.relpath(path, ROOT), os.path.getsize(path) / 1024))


if __name__ == '__main__':
    main()
