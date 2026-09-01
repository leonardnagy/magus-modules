# A) KÖTELEZŐ A FELOLVASÁSHOZ

## A1. Pipeline — enélkül egyáltalán nincs hang

**1. Nincs terv-JSON, és nincs, ami készítsen.**
A `make-guided-meditations.py` kizárólag JSON-t olvas (`json.loads(...)` → `t["szegmensek"]`), a `.txt`-t az első karakteren `JSONDecodeError`-ral eldobja. A repóban nulla ilyen JSON van. Kell egy `tools/guided/txt2terv.py`:

- a gyökér **LISTA**, nem objektum: `[ { "id": ..., "cim": ..., "hossz": ..., "szegmensek": [...] } ]` — objektummal `TypeError: string indices must be integers`
- kötelező mezők: `id`, `cim`, `hossz` (Int mp), `szegmensek[].at` (Double mp), `szegmensek[].szoveg`
- üres sor mentén bekezdés, bekezdésen belül a sorokat **egyetlen szóközzel** fűzd (egyetlen sor sem végződik kötőjellel, tehát nem vág szót)
- ellenőrzés a végén: `assert not re.search(r"[0-9]|─", " ".join(szegmens_szovegek))` — ma zölden átmegy, mert digit csak fejlécben van

**2. Szűrés — ez az, amit Ara egyébként felolvasna.**
Sem a `make-guided-meditations.py` (nyersen küldi a `szoveg`-et), sem a `generate_audio.py` `clean()` (csak `** __ \` # * _ >`) nem szűri a `─` (U+2500) jelet. A fájlban **20 db** fejléc van, plusz a címblokk. Szabály:

```python
bekezdesek = [b.strip() for b in nyers.split("\n\n") if b.strip()]
elso_fejlec = next(i for i, b in enumerate(bekezdesek) if "──" in b)
szoveges = [b for i, b in enumerate(bekezdesek) if i > elso_fejlec and "──" not in b]
```

Ez egyszerre dobja el: az 1–2. sort (`AZ ELSŐ HOPPANÁLÁS` / `vezetett meditáció — Ara hangján, lassan, óvatosan`), mind a 20 fejlécet, és a 240. sori rendezői utasítást (`── 17. MARADÁS ── (itt jön a hosszú csend)`) — ez utóbbi a `startswith('──')`-ra is illeszkedik, mert önálló bekezdés. **Fontos:** a `──` sorok a szegmenshatárok, ne veszítsd el őket — belőlük lesz a szakasztagolás és a csend.

**3. `MAPPA` — a script a TTS-hívások UTÁN hal meg.**
`make-guided-meditations.py` 33–36. sor csak `ryokah-alchemy` / `ryokah-magick` előtagot ismer; `modul_mappa()` a 121. sorban fut, azaz a 94 API-hívás után. Két javítás:

```python
MAPPA = {
    "ryokah-alchemy": "ryokah.alchemy",
    "ryokah-magick": "ryokah.magick",
    "bashar-shifting": "bashar.shifting",
}
```

és a `main()`-ben, a `print(f"{len(tervek)} meditáció...")` után, a `--dry-run` blokk ELÉ:

```python
for t in tervek:
    modul_mappa(t["id"])   # elore dolunk el: ne API-hivas utan alljon le
```

Az id kövesse a konvenciót: **`bashar-shifting-timer-hoppanalas`** (nem `bashar-hoppanalas`), mert a `MAPPA` prefix-illesztéssel dolgozik. (Modulválasztás bizonytalan: `bashar.shifting` tartalmilag illik, `bashar.meditations` a másik jelölt — Leonardnak kell eldöntenie.)

**4. `at` értékek — mérésből, nem becslésből.**
A csend maga a meditáció; a `build-guided-audio.swift` az átfedő szegmenst némán hátratolja (`if kezdet < utolsoVege { kezdet = utolsoVege }`), tehát rossz `at`-nál a szünetek eltűnnek. A repó saját mért tempója **14,3 kar/mp** (1163 kész Ara/hu mp3-on mérve; a script `--dry-run`-ja is 14-gyel számol). Eljárás: első menetben legyártani a szegmenseket, majd `afinfo` / `ffprobe` a `.guided-tmp/<id>/NN.mp3`-akon, és `at[i] = at[i-1] + hossz[i-1] + szünet[i-1]`. A cache (`if cel.exists() and cel.stat().st_size > 500: continue`) miatt az újraépítés **nem kerül újabb API-pénzbe**.

**5. Utómunka (különben nem jelenik meg az appban):** `audioBase` + `meditaciok` bejegyzés a modul `module.json`-jában a `ryokah.magick` mintájára, majd `python3 tools/build-everything.py`. És `git add tools/guided/` — a mappa jelenleg nyomon követetlen.

**Apró:** a `build-guided-audio.swift` 55–58. sorába érdemes beírni, mennyivel csúszott:
`print(String(format: "  szegmens %02d: tervezett %.1f mp helyett %.1f mp (+%.1f mp)", i, sz.at, CMTimeGetSeconds(utolsoVege), CMTimeGetSeconds(utolsoVege) - sz.at))`

## A2. Írásjelek — amit a TTS félreolvas

**Mért tény:** a `…` a grok-tts-nél NEM lassít (ellipszises fájlok átlaga 14,51 kar/mp, gyorsabb az átlagnál). A lassítás a szegmenshatárokból jön, nem az írásjelből. Ezért a determinisztikus írásjelre cserélés ingyenes.

| Sor | Jelenleg | Helyette |
|---|---|---|
| 19–20 | `Belégzés. Egy… kettő… három… négy. Tartsd bent. Érezd, ahogy a mellkasod / lassan, mélyen kitágul.` | `Belégzés. Egy, kettő, három, négy. Tartsd bent. Érezd, ahogy a mellkasod / lassan, mélyen kitágul.` |
| 22–23 | `Kilégzés. Egy… kettő… három… négy… öt… hat. Engedj ki mindent, ami nem / szolgál.` | `Kilégzés. Egy, kettő, három, négy, öt, hat. Engedj ki mindent, ami már / nem szolgálja a javadat.` |
| 97 | `Óm… namah… Krisna.` | `Óm, namah, Krisna. Óm, namah, Krisna. Óm, namah, Krisna.` (vessző, nem pont — a pont három lezáró kontúrt ad, staccatót; lásd B6) |
| 182 | `Kezdd a négy–hét–nyolc légzést.` | `Kezdd el a négy-hét-nyolc légzést.` (U+2013 → sima kötőjel; technikanév, nem felsorolás — a „négy, hét, nyolc légzést" agrammatikus) |
| 183–184 | `Belégzés orron keresztül négyig. Tartsd bent hétig. Kilégzés szájon / keresztül nyolcig.` | `Belégzés orron keresztül, négyig. Tartsd bent, hétig. Kilégzés szájon / keresztül, nyolcig.` |
| 169 | `mint egy lágy aranyfény-csóvát` | `mint egy lágy arany fénycsóvát` (vessző nélkül, hogy ne vigyünk be új szünetet; a kötőjeles alak amúgy is helyesírási hiba — öt szótag, a mozgószabály nem lép be) |
| 49 | `ragyogó, aranyfehér fényes háttér` | `ragyogó, aranyfehér, fényes háttér` (az eredeti átiratban ott volt a vessző, a javítás során veszett el) |

**Ellenőrzés:** `grep -c '…' bashar-hoppanalas.txt` → várt 0.

**Gondolatjelek (22 db U+2014).** Az eredeti átiratban NULLA em dash van — mind szerkesztői betoldás, tehát semmit nem veszítünk. A cserét a TTS-nek átadott `szoveg` mezőben végezd, a `.txt` maradhat. Nem gépiesen:

- Vesszőre (13 hely): 8–9., 34–35., 38., 45., 60., 107., 162., 218., 246., 254–255., 283. sor
- Pontra (drámai szünet): 89. `Ez a vágy nem könyörgés. Ez a vágy tudás. Én akarom. És már meg is van.` — 148. `Megvilágosodás. Nincs én. Csak tiszta tudat.` — 195–196. `Most. Villámnál is gyorsabb. Mégis teljesen nyugodt. Szeretetteljes. Biztonságos.`
- 232. sor NEM vessző: `Test, lélek, szellem. Tökéletesen egyben.` (vesszővel négyelemű felsorolásnak hangzik)
- 65. sor: `A lábujjaidból, a bokáidon át. Vádli, térd, comb, csípő, has. És megáll a szívednél.`
- 101. sor: `Ismételd hétszer, nyolcszor, kilencszer, tízszer. Vagy ameddig jön.`
- 2. és 58. sor gondolatjele fejlécben van, nem hangzik el

## A3. Kiejtés

**`Bashar` → `Basár`** a 125., 131., 137. sorban. A magyar `s` = [ʃ], tehát a `Basár` pontosan [ˈbɒʃaːr]-t ad, és a hosszú á súlyt ad a második szótagnak. Az eredeti átirat végig „Basar"-t ír, azaz a beszélő így ejtette. A `szoveg` mező tiszta kiejtési utasítás (a Swift sehol nem jeleníti meg), tehát a cserének nulla költsége van. Legjobb megoldás egy tábla a `speak()` hívás elé:

```python
KIEJTES = {"Bashar": "Basár"}
def kiejtesre(t):
    for k, v in KIEJTES.items():
        t = t.replace(k, v)
    return t
```

*(Ne írd át „Napatya"-t „Nap Atya"-ra — az helytelen magyar írásmód, és következetlen a mellette álló „Földanya"-val.)*

## A4. Nyelvtan — felolvasva azonnal hallatszik

| Sor | Jelenleg | Helyette |
|---|---|---|
| 34–35 | `Lassan, tudatosan — minden izomrostot, minden ideget.` | `Lassan, tudatosan — minden izomrostra, minden idegre.` (megszűnik az esetváltás, végig a „-ra/-re" keretben marad) |
| 37–38 | `Érezd, ahogy a figyelem — maga az energia — feltölti melegséggel, fénnyel.` | `Érezd, ahogy a figyelem — maga az energia — lassan feltölti őket melegséggel és fénnyel.` (NE „a testedet" — ott még csak az alsó test van szkennelve) |
| 64–65 | `A lábujjaidból, a bokáidon át — ... — és megáll a szívednél.` | `Felkúszik a lábujjaidból, a bokáidon át. Vádli, térd, comb, csípő, has. És megáll a szívednél.` (egy ige beszúrása megszünteti a lógó „és"-t) |
| 84–85 | `Ez nyit ki minden ajtót, minden dimenziót, minden korlátot.` | `Ez nyit ki minden ajtót. Ez nyit meg minden dimenziót. És ez dönt le minden korlátot.` (korlátot nem lehet kinyitni) |
| 198 | `Egy halk óm. Egy mély. És egyetlen csettintés.` | `Egy halk óm. Mély. És egyetlen csettintés.` (a névelő a hiba, nem a „mély"; a szöveg máshol is használ névelőtlen melléknévi mondatot: „Mély. Erős. Megállíthatatlan.") |
| 246 | `A hely energiáját — ahogy átjár. Ahogy eggyé válsz vele.` | `Érezd a hely energiáját — ahogy lassan átjár. Ahogy eggyé válsz vele.` |
| 178 | `Megfontoltság.` | `Megfontoltság. Nem kapkodsz. Nem erőltetsz semmit. Nyugodt vagy, tiszta vagy, és pontosan tudod, mit teszel.` |

## A5. Szóválasztás / következetesség

| Sor | Jelenleg | Helyette | Indok |
|---|---|---|---|
| 122 | `Most a levegő elem.` | `Most a levegőelem.` | tűzelem / vízelem / földelem / értelem mind egybeírva |
| 129 | `Akaraterő. Készség.` | `Nyitottság. Készség.` | Hawkins 310 = Willingness; az „akaraterő"-t a 58. sor már a tűzhöz rendelte |
| 140 | `Most az értelem. Tiszta. Fényes. Ész. Megértés. Bölcsesség.` | `És most feljebb lépsz. Most az értelem. Tiszta. Fényes. Éber elme. Megértés. Bölcsesség.` | „értelem"/„ész" tautológia; az „Ész" szerkesztői betoldás (az eredetiben „ok" áll) |
| 150 | `A tiszta te.` | `A tiszta éned.` | a „te" főnevesítése angol kalk; a 154. sor már használja az „éned" alakot |
| 170–171 | `Érezd a szagot, ...` | `Érezd az illatokat, a hőmérsékletet, a fényt / a bőrödön, a hangokat.` | névelőt is cserélni kell |
| 230 | `A szagokat.` | `Az illatokat.` | |
| 260 | `A gömb nagyon lassan, gyengéden összehúzódik.` | `A buborék most gömbbé sűrűsödik. És ez a gömb nagyon lassan, gyengéden összehúzódik.` | egy tárgy két néven; így az előadó szava is megmarad |
| 71 | `Most légy szenvedélyes a szenvedélyesség iránt.` | `Most maga a lángolás legyen a szenvedélyed.` | tőismétlés; a „Szeresd ezt az izgalmat" marad utána |
| 175 | `Szenvedélyes vagy a szenvedélyesség iránt.` | `Szenvedély, amely önmagát táplálja.` | megtartja a staccato ritmust |
| 30 / 34 / 37 / 40–42 | vegyes birtokos (`a vállakra`, `a nyakra`) | végig birtokos, egyes szám: `a kisujjadat, a nagyujjadat` / `a lábfejedre. A bokádra. A vádlidra.` / `A térdedre. A combodra. A csípődre.` / `A válladra. A karodra. A könyöködre. Az alkarodra. A csuklódra. ... A nyakadra. A tarkódra. A fejedre. A homlokodra. A szemedre. Az arcodra. A fejed tetejére.` | a páros testrészek többes száma („vállakra", „szemekre") idegenszerű. A **65. sor marad** puszta felsorolás (ritmus) |

**Döntendő (két szemüveg ellentmond):** 221. sor `Ez a cseresznye a tortán.` A kép az eredeti felvételen is elhangzott („Ez a cseresznyi a tortán."), tehát nem átirati hiba, hanem az előadó szava. A magyar frazéma „hab a tortán", DE az is bónuszt jelent, miközben a következő mondat („Ez rögzíti a pillanatot") a lényegi mozzanatot állítja. Ajánlott harmadik út: `Ez a zuhanás és a talpra érkezés. Ez a pecsét az egészen. Ez rögzíti a pillanatot a testedben.` — **kérdezd meg Leonardot.**

## A6. Belső ellentmondás — a szem

Háromszor hangzik el „nyisd ki a szemed", becsukás sosem. A 19. szakasz „Először csak egy kicsit. Aztán teljesen." így értelmét veszti.

- **227. sor** (kötelező): `Nyisd ki teljesen a szemed. Ott vagy.` → `Nyisd ki teljesen a belső szemed. Ott vagy.`
- **162. sor** (opcionális, a szerző maga hedgelte): `Nyisd ki a szemed — de maradj mélyen bent, a buborékban.` → `Most nyisd ki a belső szemed. A külső szemed csukva marad. Te pedig maradj mélyen bent, a buborékban.`
- **268. sor változatlan** — ez az egyetlen valódi szemnyitás.

## A7. Prozódia — az öt azonos sor

A 273–281. sor ötször betűre azonos („Nézd meg az ujjaidat."). Az eredetiben 141-szer szerepelt — ASR-beragadás, nem szerzői szándék. Variált változat, a dimenzió-keretben maradva (nem lucid álom):

```
Nézd meg az ujjaidat.

Nézd meg őket jól. Nagyon lassan.

Ezek a te kezeid. Ebben a dimenzióban.

Nézd meg az ujjaidat. Megérkeztél.

Itt vagy. Egészen itt vagy.
```

## A8. Nyitás lágyítása

A `Zárd be a szemed. Most.` a leghatározottabb mondat az egész szövegben, holott az eredeti felvételen elhangzott, de a javításból kimaradt: „suttogok, lassan, nagyon lassan, mintha a füledben lennék". Beszúrás a 6. sor helyére (két szegmens):

```
Suttogok. Lassan, nagyon lassan, mintha a füledben lennék.

Most pedig hunyd le a szemed. Egészen lassan.
```

*(A `Tartsd bent.` NE változzon — az a 4-7-8 protokoll része, a 183. sor „Tartsd bent, hétig." konkretizálja.)*

---

# B) AMI HIÁNYZIK — fontossági sorrendben

### B1. Előkészület és kontraindikáció ⟶ a `── BELÉPÉS ──` ELÉ, saját szakaszként

Nincs semmilyen felkészítés, és nem hangzik el, hogy vezetés közben ne hallgassa. A modul `module.json`-jában van ilyen mondat, de aki a Meditációk fülről indítja a hangot, azt sosem látja.

```
── ELŐKÉSZÜLET ──

Mielőtt bármibe belefognánk. Keress egy helyet, ahol a gyakorlat idejére
senki nem zavar meg.

Ülj vagy feküdj úgy, hogy a tested el tudjon lazulni. A hátad legyen
megtámasztva. A kezed pihenjen nyugodtan. A lábad legyen szabadon.

Némítsd le a telefont.

És egyvalamit kérek. Ezt a felvételt csak nyugodt, biztonságos helyzetben
hallgasd. Vezetés vagy gépkezelés közben soha. És semmi olyan közben, ami
figyelmet igényel. Ez az idő most csak a tiéd.

Ha ez megvan, kezdhetjük.
```

*(Ne írj bele konkrét percszámot — a hossz a terv `hossz` mezőjéből jön.)*

### B2. Vészkijárat ⟶ a 16. sor („a kezedet. Nem látod, de érzed.") UTÁN

A 284 sorban egyetlen szó sincs arról, hogy meg lehet szakítani. Disszociatív gyakorlatnál ez alap.

```
Mielőtt elindulunk, egyetlen dolgot jegyezz meg. Végig te vezetsz.

Bármikor visszajöhetsz. Nem kell megvárnod a végét, és nem kell engedélyt kérned hozzá.

Ha bármikor sok lenne, csak szorítsd meg a kezemet. Mozgasd meg az ujjaidat, vegyél egy nagy levegőt, és mondd ki halkan: itt vagyok. Ettől azonnal itt vagy, ebben a szobában, épen és egészben.

És ha akarod, folytathatod ott, ahol abbahagytad. Semmi nem vész el.

Ez végig veled van.
```

**Ne** a szem kinyitását tedd kilépő-jellé — a 162. és 227. sor maga utasít szemnyitásra.

### B3. Földelés ⟶ a fájl LEGVÉGÉRE, a 284. sor UTÁN

A jelenlegi zárás: mozgasd meg az ujjaidat, majd vége. Nincs visszaszámlálás, nincs szoba-visszahorgonyzás, nincs kimondva, hogy éber és tiszta. A záró kérdés („melyik dimenzióban vagy most") szándékosan nyitott — ezért a földelés utána jön, nem elé.

```
── 20. FÖLDELÉS ──

És most visszahozlak, egészen. Nem sietünk. Ötig számolok, és minden
számmal egy kicsit inkább itt leszel.

Egy… a levegő megérkezik a tüdőd aljába. Mélyen. Lassan.

Kettő… a szoba visszaépül az aranyporból. A padló. A falak. A mennyezet.
Minden a helyére kerül.

Három… érzed, ahol a hátad megtámaszkodik. Ahol a talpad a padlót éri.
A kezed, a lábad, az arcod. Mind a tiéd. Mind itt van.

Négy… hallod a szoba hangjait. Ami az előbb még messze volt, most újra közel.

Öt… teljesen megérkeztél. Ide. Ebbe a testbe. A mai napba.

Nyújtózz egy nagyot, ha jólesik. Fordítsd a fejed lassan jobbra. Aztán balra.

Éber vagy. Tiszta vagy. Nyugodt vagy. És ez a nyugalom veled marad.

A buborék pedig ott van, a szívedben. Bármikor kinyílik.
```

*(A „Kettő" a BELÉPÉS aranyporát építi vissza; a záró sor konzisztens a 18. szakasszal, ahol a buborék a szívbe húzódik.)*

### B4. Bashar első törvénye + a számozás ⟶ 8. szakasz

A szöveg a „másodikkal" kezd, az első sosem hangzik el, a negyedik („minden változik, kivéve az első hármat") pedig hiányzik. **Figyelem:** ez az eredeti felvételen is így hangzott el, tehát tartalmi szerkesztés — Leonard jóváhagyása kell.

**(a) A 125–126. sor helyére:**
```
Bashar első törvénye: létezel.
Mindig is léteztél, és mindig is léteztél fogsz.
Ez az egyetlen, amit soha, senki nem vehet el tőled.
És mert vagy, mehetsz bárhová.

És ez is igaz: minden itt és most van. Minden lehetséges.
Itt és most.
```
*(elgépelés nélkül: „Mindig is léteztél, és mindig is létezni fogsz.")*

**(b)** 131. sor: `Bashar harmadik törvénye:` → `Bashar második törvénye:`
**(c)** 137. sor: `Bashar negyedik törvénye:` → `Bashar harmadik törvénye:`
**(d)** A 138. sor után, a 140. sor ELÉ:
```
Bashar negyedik törvénye: minden változik — kivéve az első hármat.
Minden mozgásban van, minden alakul, minden átrendeződik.
Ezért lehet, hogy egy pillanattal ezelőtt még nem tudtad — és most már tudod.
A változás az az ajtó, amin átléphetsz.
```

Így mind a négy törvény egy szakaszon belül, hallható sorrendben van, és az elem-törvény párosítások (víz→2., föld→3.) érintetlenek maradnak.

### B5. A 3D ⟶ a 10. szakaszban, a 171. sor UTÁN

Leonard az átirat 3. sorában tételesen megígérte a 3D-t, és a szó egyszer sem szerepel a javított szövegben.

```
És most engedd, hogy a hely körbevegyen. Ne kívülről nézd — állj bele.

Ami előtted van, annak mélysége van. Ami mögötted van, azt a hátaddal érzed.
Fordulj el lassan — és a kép nem tűnik el, hanem folytatódik tovább.
Nézz le a lábad elé. Nézz fel az égre.

Nyújtsd ki a kezed, és érintsd meg, ami ott van. A falat. A fát. A levegőt.
Térfogata van. Súlya van. Hőmérséklete van.

Ez már nem kép. Ez három dimenzió.
És ebben a tested is ott van — nem csak a gondolatod.
```

**„három dimenzió", nem „3D"** — a pipeline nem normalizál számjegyet, a „3D" kiejtése kiszámíthatatlan. A 150. sort NE egészítsd ki „A hoppanálás. A 3D."-vel: az az átiratban a beszélő emlékeztető-listája volt, és a 14. szakasz csattanóját lőné le.

### B6. A mantra vezetése ⟶ 6. szakasz, a 95–103. sor helyére

A hang egyszer mondja ki, majd hétszer-tízszer kéri. Felvételről a ritmust a vezetőnek kell megadnia, aztán átadni.

```
És most halkan, nagyon lassan, kezdd ismételni. Először csak hallgasd, ahogy mondom:

Óm, namah, Krisna.

Óm, namah, Krisna.

Óm, namah, Krisna.

Most mondd velem együtt. Ugyanilyen lassan.

Óm, namah, Krisna.

Óm, namah, Krisna.

Óm, namah, Krisna.

Minden szóval érezd, ahogy a hang a mellkasodban, a gyomrodban, a fejedben rezeg.

És most már egyedül. A saját ritmusodban. Ismételd hétszer, nyolcszor, kilencszer, tízszer — vagy ameddig jön.

Minden ismétlésnél a vágy erősebb. A kapu szélesebb. A szikra fényesebb.
```

**Kivitelezés:** a hat mantra-sor hat KÜLÖN szegmens, 5–7 mp `at` távolsággal — a ritmust a csend adja, ne a TTS prozódiája.

### B7. A prána-légzés vezetése ⟶ 12. szakasz, a 180–187. sor helyére

A szakasz megnevezi a technikát, de nem számol. 4-7-8-nál a számolás maga a gyakorlat.

```
── 12. PRÁNA ──

Most jön a négy-hét-nyolc légzés. Ha a bent tartás bármikor kellemetlen,
engedd el nyugodtan — elég, ha csak lassan lélegzel.

Minden belégzésnél szívd be a Földanya és a Napatya pránáját.
Töltsd fel minden sejtedet. Emeld a rezgésedet. Készítsd fel a testedet.

Első kör. Belégzés orron át: egy… kettő… három… négy.
Tartsd bent: egy… kettő… három… négy… öt… hat… hét.
És ki, szájon át: egy… kettő… három… négy… öt… hat… hét… nyolc.

Második kör. Be: egy… kettő… három… négy.
Tartsd: egy… kettő… három… négy… öt… hat… hét.
Ki: egy… kettő… három… négy… öt… hat… hét… nyolc.

Harmadik kör. Be: egy… kettő… három… négy.
Tartsd: egy… kettő… három… négy… öt… hat… hét.
Ki: egy… kettő… három… négy… öt… hat… hét… nyolc.

És most még egy kört, egyedül, a saját tempódban.
```

A szédülés-figyelmeztetés a számolás ELŐTT áll (utólag értéktelen). **Kivitelezés:** a három kör három külön szegmens, egy kör ~19 mp — különben a TTS gyorsabban számol, mint ahogy lélegezni lehet.

### B8. A megerősítés háromszor ⟶ 16. szakasz, a 235–238. sor helyére

A szöveg azt mondja „Mondd háromszor", de csak egyszer van leírva. A 14 szavas affirmációt egy hallásra nem lehet visszamondani.

```
Mondd velem. Háromszor. Nagyon lassan. Mély, nyugodt, erőteljes hangon.

Először.

Én vagyok a dimenziók ura. Minden dimenzióban jelen vagyok.
A kaland most kezdődik.

Másodszor. Ugyanilyen lassan.

Én vagyok a dimenziók ura. Minden dimenzióban jelen vagyok.
A kaland most kezdődik.

És harmadszor. A legmélyebb, legnyugodtabb hangodon.

Én vagyok a dimenziók ura. Minden dimenzióban jelen vagyok.
A kaland most kezdődik.

Így. Most már a testedben is ott van.
```

*(„Először", nem „Egyszer". Hangerő-fokozás NINCS — a 235. sor maga írja elő a hangszínt, és a megrendelő nyugodt hangnemet kért.)*

### B9. Horgonyzás ⟶ 13. szakasz, a 191. sor helyére

65 karakter, a legrövidebb szakasz — pedig ez tartja a visszatérést. Az „aranykötél" ráadásul határozott névelővel jön be, holott sosem volt bevezetve.

```
Tedd a szívedbe az aranykötelet — ugyanabból az élő aranyfényből, mint a szál a talpad alatt. Érezd, ahogy szilárdan megkapaszkodik ott, a mellkasod közepén. A másik végét nagyon lassan vidd oda, arra a helyre, amit választottál. Kösd össze a helyet a szíveddel. Húzd meg egyszer, gyengéden — és érezd, hogy tart.
```

És a **252. sor UTÁN** (18. VISSZATÉRÉS), hogy a horgony ténylegesen működésbe lépjen:
```
Keresd meg a szívedben az aranykötelet. Ott van, ahol hagytad.
Érintsd meg gyengéden — és a kötél elindít hazafelé.
```

*(„szilárdan megkapaszkodik", nem „a súlya megtelepszik" — a BELÉPÉS épp a nehézséget engedteti el.)*

### B10. Az egyesülés kibontása ⟶ 9. szakasz, a 152–158. sor helyére

Három mondat a meditáció egyik legfontosabb pontján; kimondja az egyesülést, de nincs ideje megélni.

```
── 9. AZ EGYESÜLÉS ──

Most egyesülj a legmagasabb dimenziójú éneddel.

Ő előtted áll. Fényből van. A szeme nyugodt. A teste ragyog.

És ahogy nézed, lassan felismered: nem idegen.
Nem fölötted áll — csak tágabban lát.
Ez te vagy. Az a te, aki soha nem felejtette el, hogy ki ő.

Nézz a szemébe. Nyugodtan. Nem kér számon. Nem méricskél.
Csak vár rád, türelmesen, mint aki mindig is itt állt.

Mondd neki, nagyon lassan:
én most egyesülök veled. Te vagy én. Én vagyok te.

És most tegyél felé egy lépést. Még egyet.
És hagyd, hogy a fénye átjárjon.

A fény belép a homlokodon, a mellkasodon, a tenyereden.
A körvonalai összemosódnak a tieddel.
Egyre nehezebb megmondani, hol végződsz te, és hol kezdődik ő.
És egy ponton már nincs is értelme a kérdésnek.

Egy test. Egy fény. Egy tudat.
Nem lettél több. Csak visszakaptad azt, ami mindig is a tiéd volt.
```

### B11. A szándék az elejére ⟶ BELÉPÉS vége, a 25. sor („Most kezdjük az utazást") ELÉ

Jelenleg a felvétel felénél, mély állapotban kell hirtelen dönteni.

```
És mielőtt elindulunk, engedd, hogy megjelenjen egy hely.

Ne keresd. Ne gondold ki. Csak várd meg, amíg magától ideér.

Lehet egy szoba. Lehet egy tengerpart. Lehet egy hegyoldal.
Lehet valaki, akihez tartozol.

Ha megvan, tedd le a szívedbe. Egészen lazán.
Nem kell figyelned rá. Ott vár ránk, amíg odaérünk.
```

És a **164. sort** ne töröld, hanem bővítsd:
```
És most jöjjön elő az a hely, amit az elején a szívedbe tettél.
Ott van. Végig ott volt.

Ha közben más jött helyette — az is jó. Akkor azt válaszd.
```

### B12. A csettintés magyarázata (engedélycédula) ⟶ 19. szakasz, a 283. sor ELÉ

A meditáció technikai csúcspontja magyarázat nélkül marad; ez egyben megelőzi a kudarcélményt is. **Ne** a 14. szakaszba tedd — ott szétvágná a kioldást.

```
És mielőtt csettintesz, tudj meg valamit.

A csettintés önmagában nem visz sehová.
Nem a hang. Nem az ujjad.
Te vagy az, aki átlép.

A csettintés csak egy engedély, amit magadnak adsz.
Egy jel, amiben megállapodtál önmagaddal.
Egy kulcs ahhoz az ajtóhoz, amelyik eleve nyitva volt.

Ezért működik. És ezért fog mindig működni.
Mert te működteted.
```

### B13. Átvezetés a lépcsőkhöz ⟶ 8. szakasz eleje, a 122. sor ELÉ

A létra első foka (tűz = bátorság) öt szakasszal korábban van, és a szó ott csak a nem elhangzó fejlécben szerepel — a hallgató a létra közepén lép be.

```
Most egy lépcsősor következik. Nagyon lassan megyünk fel rajta, fokról fokra.

Minden fok egy állapot. Nem kell elérned semmit — csak állj meg mindegyiken egy pillanatra, és engedd, hogy átjárjon.

Az első fokon már állsz. Ez a tűz. A bátorság. Ez az, ami a szívednél ég, ami idáig elhozott. Innen lépünk tovább, felfelé.
```

Plusz a **60. sor ELÉ** (3. szakasz), mert a „tűz"/„bátorság" szó jelenleg csak fejlécben van: `Most a tűz elem következik. A bátorság.`

### B14. Testi horgonyok a felső fokokhoz ⟶ 8. szakasz

A létra felső fele csupa elvont főnév. Fokonként EGY sor, hogy a ritmus ne boruljon:

- 135. sor ELÉ (föld, az „Elfogadás." elé): `Engedd rá a súlyodat arra, ami alattad van. A medencéd, a farokcsontod, a combod hátulja elnehezedik. Tart valami — és nem kell tartanod magad.`
- 142. sor UTÁN (szeretet): `Rózsaszín arany fény árad ki a mellkasodból — a vállaidon át, egészen a tenyeredig.`
- 144. sor UTÁN (öröm): `Az arcod magától elmosolyodik. A nevetés ott van benned — nem kell kiengedned.`
- 146. sor UTÁN (béke): `A lélegzeted egészen elcsendesedik. Semmi nem sürget. Semmi nem hiányzik.`
- 148. sor UTÁN (megvilágosodás): `A tested széle ellágyul. Nem tudod pontosan, hol végződsz te, és hol kezdődik a világ. És ez így van rendben.`
- 150. sor UTÁN (hitelesség): `A vállad, az állkapcsod, a szemöldököd elengedi az utolsó álarcot is. Nincs mit visszatartanod. Nincs kinek megfelelned. Ez vagy te, minden réteg nélkül.`

### B15. Permisszív keret ⟶ BELÉPÉS + 4. szakasz

Sehol nincs engedély arra, hogy valaki NE érezzen semmit — ez teljesítménykényszert csinál a meditációból.

**A 23. sor UTÁN, a 25. sor ELÉ:**
```
Semmit nem kell erőltetned. Ha valamit erősen érzel, jó. Ha csak elképzeled,
az ugyanolyan jó — a képzelet ugyanazon az úton visz.
```

**A 80. sor UTÁN (4. SZIKRA):**
```
És ha most alig érzel valamit, az is teljesen rendben van. Elég, ha
elképzeled a szikrát — attól ugyanúgy ott van.
```

*(A „ha bármi mást éreznél a mellkasodban" típusú kilépőt NE tedd be — nocebo, épp a mellkasra irányítaná a figyelmet.)*

### B16. Napló-felhívás ⟶ a 283–284. sor helyére

Ez a szöveg egy magikus napló appban fog élni, és a záró mondat („mondd el nekem") amúgy is válasz nélkül marad.

```
És ha van kedved, ha készen állsz — csettints.

Aztán, amikor jólesik — nem sietve, nem most azonnal — nyisd meg a naplód.

Ne szépítsd. Ne rendezd. Csak azt írd le, ami megmaradt.
Hol voltál. Mit láttál. Mit éreztél a talpad alatt.
Milyen szagot hoztál magaddal.

Egy mondat is elég. És az is odatartozik, ami nem sikerült.

És írd oda azt is, amit most mondanál nekem: melyik dimenzióban vagy.
```

### B17. Zuhanás előre-keretezése ⟶ 15. szakasz eleje, a 207. sor ELÉ

A zuhanásérzet + gyomorugrás a pánikroham testi mintázata; a megnyugtatás („De nem esel.") később jön, mint az ijedség.

```
Egyetlen méter az egész. Semmi több. És végig biztonságban vagy.
```
és a 208. sor végére: `... mintha egy lágy hullám futna végig rajtad. Egy pillanat az egész.`

### B18. A 11. szakasz összegzése ⟶ a 178. sori „Megfontoltság." kibontása után

A B18 és az A4 utolsó tétele ugyanaz — ha bővebb változatot akarsz:
```
Megfontoltság. Nem sietünk. Semmi nem sürget.

Minden a helyén van. A szikra ég. A vágy megállíthatatlan. A siker már
megtörtént. A hely ott vár rád.

Innen már csak a testedet készítjük fel. Lassan, nyugodtan.
```
*(NE mondd, hogy „ami most jön, egyetlen pillanat lesz" — még a prána és a horgonyzás következik.)*

### B19. Tartó mondat a hosszú csendbe ⟶ 17. szakasz

A meglévő sorokat (242., 244., 246., 248.) oszd szét KÜLÖN szegmensekre, 40–60 mp-enként — nem kell hozzá új szöveg. Egyetlen új mondat indokolt, kb. a csend 160. másodpercébe:
```
Itt vagyok melletted. Semmi dolgod.
```

---

# SZÁMOK

**Karakterszám**
- Jelenlegi beszélt anyag (fejlécek és címblokk nélkül): **7 738 karakter**, 94 szegmens
- B) tételek összesen: **≈ +7 000 karakter**
- Új összesen: **≈ 14 700 karakter**, kb. 130–140 szegmens

**Beszédidő**
- Mért Ara/hu tempó: **14,3 kar/mp** (1163 kész mp3-on mérve, medián 14,36, p10 13,80, p90 14,84). A repó saját becslője is 14-gyel számol.
- Ez a szöveg sűrűbben központozott az átlagnál (4,16 írásjel/100 kar), ezért konzervatívan **13,8 kar/mp**:
- **14 700 / 13,8 ≈ 1 065 mp ≈ 17 perc 45 mp tiszta beszéd**
- (A jelenlegi szöveg ugyanezzel: 561 mp ≈ 9,4 perc.)

**Javasolt teljes hossz: 40 perc (`"hossz": 2400`)**
Beszéd 1 070 mp + csend 1 330 mp. Beszédarány 45% — feszesebb, mint a Ryokah-meditációk 26–33%-a, de a szöveg most vezetett számolást és ismétléseket tartalmaz, ahol a beszéd maga adja a ritmust.

**Csend a szakasz UTÁN (mp):**

| Szakasz | Csend | | Szakasz | Csend |
|---|---|---|---|---|
| 0. Előkészület | 10 | | 11. Ami összeér | 10 |
| BELÉPÉS | 25 | | 12. PRÁNA | 90 |
| 1. Testszkennelés | 30 | | 13. Horgonyzás | 20 |
| 2. Fényes ajtó | 15 | | 14. Hoppanálás | **5** |
| 3. Gyökérszál | 20 | | 15. Zuhanás | 12 |
| 4. Szikra | 20 | | 16. Megérkezés | 70 |
| 5. Vágy | 15 | | 17. MARADÁS | **700** |
| 6. MANTRA | 90 | | 18. Visszatérés | 20 |
| 7. Sikerérzés | 20 | | 19. Ébredés | 10 |
| 8. Lépcsők | 40 | | 20. Földelés | 8 |
| 9. Egyesülés | 30 | | napló-zárás | 0 |
| 10. A CÉL | 70 | | **Összesen** | **1 330** |

Három szabály:
- **14. HOPPANÁLÁS után csak 5 mp** — a csettintés után hosszú csend megöli a pillanatot.
- **17. MARADÁS a rugalmas tétel.** Ha a szöveg tovább nő vagy Leonard rövidebb ülést akar, ebből vegyél el, ne a többiből. 30 perces ülésnél ez 100 mp; 50 percesnél 1 300.
- **6. MANTRA 90 mp** (tíz lassú ismétlés 50–70 mp) és **12. PRÁNA 90 mp** (négy teljes 4-7-8 kör 76 mp) — ezek nem tetszőlegesek, a szöveg saját utasításából jönnek.

**Ellenőrzés élesítés előtt:**
`python3 tools/make-guided-meditations.py --dry-run tools/guided/bashar-hoppanalas.json`
Várt: ~14 700 karakter, ~$0,062 becsült költség, ~44% beszédarány. Ha lényegesen eltér, a darabolás hibás. **A `--dry-run` a `modul_mappa()` ELŐTT tér vissza, tehát a MAPPA-hibát nem fogja ki** — azt külön javítsd.

---

# AMIT TÖBB SZEMÜVEG IS FÜGGETLENÜL MEGTALÁLT

Ezek a legerősebb jelek — mindegyiket két vagy három egymástól független ellenőrzés hozta ki:

1. **A `──` fejlécek és a címblokk kiszűrése** — tts, magyar, hawkins és kézműves lencse is (4×). A legtöbbször jelzett tétel.
2. **`MAPPA` hiánya + a késői `sys.exit`** — tts, magyar, kézműves (3×).
3. **Nincs txt→JSON konverter / terv-JSON** — tts, magyar, kézműves (3×).
4. **`Bashar` fonetikus írásmódja** — tts (kétszer, külön találatként), magyar, hawkins (4×).
5. **Bashar első törvénye hiányzik** — bashar és hawkins lencse (2×), egymástól függetlenül, ugyanazzal a következtetéssel.
6. **„Egy mély." befejezetlen** — tts/nyelvhelyesség és magyar lencse (2×), különböző javasolt megoldással.
7. **„Megfontoltság." árva szó** — szerkezet és hiányzó-tartalom lencse (2×).
8. **„négy–hét–nyolc" en dash** — tts és magyar lencse (2×).
9. **„cseresznye a tortán"** — nyelvhelyesség kétszer, két különböző lencséről (2×) — de ellentétes ajánlással, ezért ez a döntendő tétel.
10. **A mantra és a megerősítés ismétlésének hiánya** — kézműves lencse két külön találatként, ugyanazzal a mintázattal („az utasítás X-szer kéri, a hang egyszer mondja").
11. **„Nézd meg az ujjaidat" ötszörös ismétlése** — prozódia és kézműves lencse (2×).
12. **A csend `at`-alapú időzítése, és hogy a lassítás nem írásjel-kérdés** — tts-pipeline és kézműves-prozódia lencse (2×), egymást megerősítve.

**Bizonytalanságok, amiket vállalok:** a grok-tts tényleges viselkedését egyetlen írásjelnél sem tudtam megmérni (nem hívtam API-t) — a `…`-ról viszont van közvetett mérés (14,51 kar/mp, azaz nem lassít). A modulválasztás (`bashar.shifting` vs `bashar.meditations`), a 17. MARADÁS csendjének hossza, a „cseresznye/hab a tortán", és a Bashar-törvények számozásának átírása mind Leonard döntése — mindhárom az ő saját, elhangzott szavait érinti.