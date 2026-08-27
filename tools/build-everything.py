#!/usr/bin/env python3
"""Rebuild everything.json — the one-scan install bundle.

modules   : every */module.json except acim-workbook (1.5 MB of English-only
            lesson text does not belong in the one-tap install), sorted by id
practices : every practices/*.json pack, sorted by id
quotes    : every quotes/*.json entry, concatenated in filename order
"""
import glob, io, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCLUDED_MODULES = {'acim-workbook'}

def load(path):
    with io.open(path, encoding='utf-8') as f:
        return json.load(f)

modules = []
for path in sorted(glob.glob(os.path.join(ROOT, '*', 'module.json'))):
    m = load(path)
    if m['id'] not in EXCLUDED_MODULES:
        modules.append(m)
modules.sort(key=lambda m: m['id'])

practices = [load(p) for p in sorted(glob.glob(os.path.join(ROOT, 'practices', '*.json')))]
practices.sort(key=lambda p: p['id'])

quotes = []
for path in sorted(glob.glob(os.path.join(ROOT, 'quotes', '*.json'))):
    quotes.extend(load(path))

bundle = {'formatVersion': 1, 'modules': modules, 'practices': practices, 'quotes': quotes}
out = os.path.join(ROOT, 'everything.json')
with io.open(out, 'w', encoding='utf-8') as f:
    f.write(json.dumps(bundle, ensure_ascii=False, separators=(',', ':')))

n_pr = sum(len(p['gyakorlatok']) for p in practices)
print('%s: %d modules, %d practice packs (%d practices), %d quotes, %.1f MB'
      % (os.path.basename(out), len(modules), len(practices), n_pr, len(quotes),
         os.path.getsize(out) / 1024 / 1024))
