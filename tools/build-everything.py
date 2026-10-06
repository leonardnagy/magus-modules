#!/usr/bin/env python3
"""Rebuild everything.json — the one-scan install bundle.

modules     : every */module.json except acim-workbook (1.5 MB of English-only
              lesson text does not belong in the one-tap install), sorted by id
practices   : every practices/*.json pack, sorted by id, each practice stamped
              with the modules it belongs to
quotes      : every quotes/*.json entry, concatenated in filename order
modulPolcok : tools/modul-polcok.json as written, the Modules tab's shelves
              and each module's tile (symbol, colour, short caption), checked
              against the modules that actually exist
hangok      : every narration file with its size and sha (tools/hang_index.py,
              which also writes the root hangok.json the app re-reads daily).
              The Workbook's text stays out; its narration list goes in, so the
              one scan brings the Workbook's recordings too.

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
import glob, io, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hang_index

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
# Modules installed from private Drive bundles: not in the repo, but real
# on the phone, and a practice may link to the recordings they bring.
ismert |= set(load(os.path.join(ROOT, 'tools', 'privat-modulok.json'))['modulok'])
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
# The narration's numbers come from the same list the phone gets, so they
# count exactly the files that belong to something: the orphans left in the
# folder by renamed practices are neither listed nor counted.
hangok = hang_index.build()
hang_index.write(hangok)

def osszeg(csoportok):
    t = {}
    for cs in csoportok:
        for nyelv, fajlok in (cs or {}).get('nyelvek', {}).items():
            x = t.setdefault(nyelv, {'db': 0, 'bajt': 0})
            x['db'] += len(fajlok)
            x['bajt'] += sum(f[0] for f in fajlok.values())
    return t

letoltheto['gyakorlatHang'] = osszeg([hangok.get('gyakorlatok')])
letoltheto['modulHang'] = osszeg(hangok.get('modulok', {}).values())
letoltheto['munkafuzetHang'] = osszeg(hangok.get('munkafuzetek', {}).values())
# The recordings live on Drive, not here, so their size cannot be measured at
# build time. Measured once over the Drive folder and written down.
med_meret = load(os.path.join(ROOT, 'tools', 'meditacio-meret.json'))
letoltheto['meditacio'] = med_meret['meditacio']
letoltheto['meditacioModul'] = med_meret.get('modulonkent', {})

# The practices' `mester` is a key, Hungarian for the traditions without a
# person's name; the screen shows `mesterNevek` in the reader's language.
mester_nevek = load(os.path.join(ROOT, 'tools', 'mester-nevek.json'))['nevek']
for pack in practices:
    for gy in pack['gyakorlatok']:
        if gy['mester'] in mester_nevek:
            gy['mesterNevek'] = mester_nevek[gy['mester']]
        else:
            gy.pop('mesterNevek', None)

quotes = []
for path in sorted(glob.glob(os.path.join(ROOT, 'quotes', '*.json'))):
    quotes.extend(load(path))
# The Hungarian original goes into the translations too, so the app can show
# any language and come back to Hungarian without keeping two copies apart.
for q in quotes:
    if q.get('forditasok'):
        q['forditasok'].setdefault('hu', {'szoveg': q['szoveg'], 'forras': q['forras'],
                                          'cimkek': q.get('cimkek') or []})

# The Modules tab's shelves, laid out like the Tools tab: which shelf a module
# sits on and in what order, and the symbol, colour and caption of its tile.
# Copied through as written; the build only checks it against the modules that
# exist, so a new module that was never given a place shows up here first.
polc_tabla = load(os.path.join(ROOT, 'tools', 'modul-polcok.json'))
modul_polcok = {'polcok': polc_tabla['polcok'], 'modulok': polc_tabla['modulok']}
bundle_ids = {m['id'] for m in modules}
polcon = [mid for polc in modul_polcok['polcok'] for mid in polc['modulok']]
# A private module is real on the phone, so a shelf may hold it (see above).
polc_ismeretlen = set(polcon) - ismert
if polc_ismeretlen:
    print('FIGYELEM: polcon levo ismeretlen modulok: ' + ', '.join(sorted(polc_ismeretlen)))
polc_nelkul = bundle_ids - set(polcon)
if polc_nelkul:
    print('FIGYELEM: polc nelkuli modulok: ' + ', '.join(sorted(polc_nelkul)))
csempe_nelkul = (bundle_ids | set(polcon)) - set(modul_polcok['modulok'])
if csempe_nelkul:
    print('FIGYELEM: csempe nelkuli modulok: ' + ', '.join(sorted(csempe_nelkul)))

bundle = {'formatVersion': 1, 'modules': modules, 'practices': practices, 'quotes': quotes,
          'letoltheto': letoltheto, 'modulPolcok': modul_polcok, 'hangok': hangok}
out = os.path.join(ROOT, 'everything.json')
with io.open(out, 'w', encoding='utf-8') as f:
    f.write(json.dumps(bundle, ensure_ascii=False, separators=(',', ':')))

n_pr = sum(len(p['gyakorlatok']) for p in practices)
n_kotve = sum(1 for p in practices for g in p['gyakorlatok'] if g['modulok'])
print('modul-kotes: %d/%d gyakorlat' % (n_kotve, n_pr))
n_kep = sum(1 for p in practices for g in p['gyakorlatok'] if g.get('kep'))
print('kep-kotes: %d/%d gyakorlat' % (n_kep, n_pr))
print('letoltheto: ' + json.dumps(letoltheto, ensure_ascii=False))
print('modul-polcok: %d polc, %d/%d modul polcon, %d csempe'
      % (len(modul_polcok['polcok']), len(bundle_ids & set(polcon)), len(bundle_ids),
         len(modul_polcok['modulok'])))
print('%s: %d modules, %d practice packs (%d practices), %d quotes, %.1f MB'
      % (os.path.basename(out), len(modules), len(practices), n_pr, len(quotes),
         os.path.getsize(out) / 1024 / 1024))
