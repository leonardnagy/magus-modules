# Magus Napló — Modules

Downloadable content modules for the Magus Napló iOS app.

Install: copy a module's **raw** link below and paste it in the app
(Modulok tab → + → paste → Install).

| Module | Raw link |
|---|---|
| Full Bardon catalog (27 modules, one link) | `https://raw.githubusercontent.com/leonardnagy/magus-modules/main/iih-all/catalog.json` |
| Ryokah Alchemy | `https://raw.githubusercontent.com/leonardnagy/magus-modules/main/ryokah.alchemy/module.json` |
| Ryokah High Magick | `https://raw.githubusercontent.com/leonardnagy/magus-modules/main/ryokah.magick/module.json` |
| Saint Germain — Violet Flame | `https://raw.githubusercontent.com/leonardnagy/magus-modules/main/saintgermain.violetflame/module.json` |
| Bashar — Reality Shifting | `https://raw.githubusercontent.com/leonardnagy/magus-modules/main/bashar.shifting/module.json` |
| Hermes Trismegistus — The Ancient Root | `https://raw.githubusercontent.com/leonardnagy/magus-modules/main/hermes.trismegistos/module.json` |
| Osiris — Death & Rebirth | `https://raw.githubusercontent.com/leonardnagy/magus-modules/main/osiris.rebirth/module.json` |
| Ptah — Creation by Heart & Tongue | `https://raw.githubusercontent.com/leonardnagy/magus-modules/main/ptah.creation/module.json` |
| Thoth — The Wisdom of the Scribe | `https://raw.githubusercontent.com/leonardnagy/magus-modules/main/thoth.wisdom/module.json` |
| Ra — The Way of the Sun | `https://raw.githubusercontent.com/leonardnagy/magus-modules/main/ra.solar/module.json` |
| Kloss-Ignatenko — Cosmohumanism | `https://raw.githubusercontent.com/leonardnagy/magus-modules/main/ignatenko.cosmohumanism/module.json` |
| Sathya Sai Baba — Love & Service | `https://raw.githubusercontent.com/leonardnagy/magus-modules/main/saibaba.love/module.json` |
| Kashpirovsky — The Two Edges of Suggestion | `https://raw.githubusercontent.com/leonardnagy/magus-modules/main/kashpirovsky.suggestion/module.json` |
| Mentalism — The Craft and the Shield | `https://raw.githubusercontent.com/leonardnagy/magus-modules/main/mentalism.craft/module.json` |

Individual Bardon Step / theme modules live in their own folders (`iih.step.NN`, `iih.theme.*`).

## Practice packs (Gyakorlat-tár)

Downloadable packs of example practices for the in-app Practice Library
(Practice Journal → ⋯ → Gyakorlat-tár → + → paste a link or scan a QR).
Installed packs **add to** the app's built-in seed practices.

Together these packs hold **102 practices** (installed packs de-duplicate by id, so the built-in seed is never doubled).

| Pack | Raw link |
|---|---|
| Core practice pack (15) | `https://raw.githubusercontent.com/leonardnagy/magus-modules/main/practices/core.json` |
| Built-in practices (11) | `https://raw.githubusercontent.com/leonardnagy/magus-modules/main/practices/seed.json` |
| Bardon — the ten Steps (14) | `https://raw.githubusercontent.com/leonardnagy/magus-modules/main/practices/bardon-steps.json` |
| The elements & vital energy (10) | `https://raw.githubusercontent.com/leonardnagy/magus-modules/main/practices/elements.json` |
| Soul work & mirrors (12) | `https://raw.githubusercontent.com/leonardnagy/magus-modules/main/practices/soul.json` |
| Egyptian masters (15) | `https://raw.githubusercontent.com/leonardnagy/magus-modules/main/practices/egyptian.json` |
| Channeled masters (13) | `https://raw.githubusercontent.com/leonardnagy/magus-modules/main/practices/channeled.json` |
| Modern masters & the shield (12) | `https://raw.githubusercontent.com/leonardnagy/magus-modules/main/practices/modern.json` |

Pack format: `{ formatVersion, id, nevek{hu,en}, gyakorlatok:[…] }`, where each practice has
`id, mester, szint (kezdo|halado|mester), sik (szellem|lelek|test|null),
elem (Tuz|Levego|Viz|Fold|Eter|Ido|"Materia Prima"|null), cim{hu,en}, cel{hu,en},
modszer[{hu,en}…], keret{hu,en}, etika{hu,en}?`.

All content is original paraphrase (HU+EN) with source citations and disclaimers inside each module.
