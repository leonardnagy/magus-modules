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

# Pictures. The pack names the one its practices share; a practice whose
# subject has a picture of its own names that instead. Resolved here for the
# same reason as the modules: the phone reads a key and never has to guess.
RAW = 'https://raw.githubusercontent.com/leonardnagy/magus-modules/main'
KEP_BASE = RAW + '/illustrations'
kepek = load(os.path.join(ROOT, 'tools', 'kep-kotes.json'))
van_kep = {os.path.splitext(f)[0] for f in os.listdir(os.path.join(ROOT, 'illustrations'))
           if f.endswith('.png')}
kep_hiany = set()
for pack in practices:
    csomag_kep = kepek['csomag'].get(pack['id'])
    if csomag_kep in van_kep:
        pack['kep'] = csomag_kep
        pack['kepBase'] = KEP_BASE
    for gy in pack['gyakorlatok']:
        k = kepek['gyakorlat'].get(gy['id']) or csomag_kep
        if k in van_kep:
            gy['kep'] = k
        else:
            gy.pop('kep', None)
            kep_hiany.add(pack['id'])
    if 'kep' in pack and 'kepBase' not in pack:
        pack['kepBase'] = KEP_BASE
if kep_hiany:
    print('FIGYELEM: kep nelkuli csomagok: ' + ', '.join(sorted(kep_hiany)))

def meret(mappa, kiterjesztes):
    """(files, bytes) of one kind of file directly inside `mappa`."""
    if not os.path.isdir(mappa):
        return 0, 0
    f = [os.path.join(mappa, x) for x in os.listdir(mappa) if x.endswith(kiterjesztes)]
    return len(f), sum(os.path.getsize(x) for x in f)

# What the phone can fetch after the install, and how big it is. The app
# estimates "what is still missing here" from these averages, so its download
# button can say how much it is about to spend before it spends it — and it
# only asks for a narration language that actually exists, instead of spending
# a thousand requests on 404s for a language nobody recorded.
letoltheto = {'kepBase': KEP_BASE}
db, b = meret(os.path.join(ROOT, 'illustrations'), '.png')
letoltheto['kepek'] = {'db': db, 'bajt': b}
gyh = {}
for nyelv in sorted(os.listdir(os.path.join(ROOT, 'audio', 'practices'))):
    db, b = meret(os.path.join(ROOT, 'audio', 'practices', nyelv), '.mp3')
    if db:
        gyh[nyelv] = {'db': db, 'bajt': b}
letoltheto['gyakorlatHang'] = gyh
mh = {}
for m in modules:
    base = m.get('audioBase') or ''
    if not base.startswith(RAW + '/'):
        continue
    mappa = os.path.join(ROOT, base[len(RAW) + 1:])
    if not os.path.isdir(mappa):
        continue
    for nyelv in os.listdir(mappa):
        db, b = meret(os.path.join(mappa, nyelv), '.mp3')
        if db:
            t = mh.setdefault(nyelv, {'db': 0, 'bajt': 0})
            t['db'] += db
            t['bajt'] += b
letoltheto['modulHang'] = mh
# The recordings live on Drive, not here, so their size cannot be measured at
# build time. Measured once over the Drive folder and written down.
med_meret = load(os.path.join(ROOT, 'tools', 'meditacio-meret.json'))
letoltheto['meditacio'] = med_meret['meditacio']
letoltheto['meditacioModul'] = med_meret.get('modulonkent', {})

quotes = []
for path in sorted(glob.glob(os.path.join(ROOT, 'quotes', '*.json'))):
    quotes.extend(load(path))

bundle = {'formatVersion': 1, 'modules': modules, 'practices': practices, 'quotes': quotes,
          'letoltheto': letoltheto}
out = os.path.join(ROOT, 'everything.json')
with io.open(out, 'w', encoding='utf-8') as f:
    f.write(json.dumps(bundle, ensure_ascii=False, separators=(',', ':')))

n_pr = sum(len(p['gyakorlatok']) for p in practices)
n_kotve = sum(1 for p in practices for g in p['gyakorlatok'] if g['modulok'])
print('modul-kotes: %d/%d gyakorlat' % (n_kotve, n_pr))
n_kep = sum(1 for p in practices for g in p['gyakorlatok'] if g.get('kep'))
print('kep-kotes: %d/%d gyakorlat' % (n_kep, n_pr))
print('letoltheto: ' + json.dumps(letoltheto, ensure_ascii=False))
print('%s: %d modules, %d practice packs (%d practices), %d quotes, %.1f MB'
      % (os.path.basename(out), len(modules), len(practices), n_pr, len(quotes),
         os.path.getsize(out) / 1024 / 1024))
