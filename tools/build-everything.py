#!/usr/bin/env python3
"""Rebuild everything.json — the one-scan install bundle.

modules   : every */module.json except acim-workbook (1.5 MB of English-only
            lesson text does not belong in the one-tap install), sorted by id
practices : every practices/*.json pack, sorted by id, each practice stamped
            with the modules it belongs to
quotes    : every quotes/*.json entry, concatenated in filename order

Every practice carries a `modulok` list naming the modules it belongs to. The
module is the hub the three halves of the app meet at: a module knows its
meditations by construction (they live in its own manifest), and this is what
lets a practice reach them — and a meditation reach back.

The link is resolved HERE rather than in the app, so the phone reads a plain
list and never has to guess. Its source is tools/modul-kotes.json: the pack
decides where it can (a pack is about one subject), the practice's master
decides for the thematic packs that mix several. Fifty lines of table for 736
practices, instead of a pairing written out by hand.
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

kotes = load(os.path.join(ROOT, 'tools', 'modul-kotes.json'))
ismert = {m['id'] for m in modules}
hianyzo = set()
for pack in practices:
    csomag_modulok = kotes['csomag'].get(pack['id'])
    for gy in pack['gyakorlatok']:
        # The pack is the sharper answer where it has one; the master is the
        # fallback for packs that gather several teachers under one theme.
        talalat = csomag_modulok or kotes['mester'].get(gy['mester']) or []
        # A module excluded from the bundle would be a link to nothing.
        gy['modulok'] = [m for m in talalat if m in ismert]
        if not gy['modulok']:
            hianyzo.add((pack['id'], gy['mester']))
if hianyzo:
    print('FIGYELEM: modul nelkuli gyakorlatok:')
    for pid, mester in sorted(hianyzo):
        print('  %s / %s' % (pid, mester))

quotes = []
for path in sorted(glob.glob(os.path.join(ROOT, 'quotes', '*.json'))):
    quotes.extend(load(path))

bundle = {'formatVersion': 1, 'modules': modules, 'practices': practices, 'quotes': quotes}
out = os.path.join(ROOT, 'everything.json')
with io.open(out, 'w', encoding='utf-8') as f:
    f.write(json.dumps(bundle, ensure_ascii=False, separators=(',', ':')))

n_pr = sum(len(p['gyakorlatok']) for p in practices)
n_kotve = sum(1 for p in practices for g in p['gyakorlatok'] if g['modulok'])
print('modul-kotes: %d/%d gyakorlat' % (n_kotve, n_pr))
print('%s: %d modules, %d practice packs (%d practices), %d quotes, %.1f MB'
      % (os.path.basename(out), len(modules), len(practices), n_pr, len(quotes),
         os.path.getsize(out) / 1024 / 1024))
