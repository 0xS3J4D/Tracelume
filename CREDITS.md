# Credits

Tracelume is an orchestration and analysis layer. The forensic heavy lifting is done by
outstanding open source tools written by others. Each runs unmodified in its own container
and keeps its own licence. Tracelume does not relicense or bundle their source.

| Tool | Authors | Licence | Used for | Status |
|---|---|---|---|---|
| [ALEAPP](https://github.com/abrignoni/ALEAPP) | Alexis Brignoni and contributors | MIT | Android artifacts | Included |
| [iLEAPP](https://github.com/abrignoni/iLEAPP) | Alexis Brignoni and contributors | MIT | iOS artifacts | Included |
| [Plaso / log2timeline](https://github.com/log2timeline/plaso) | Plaso developers (Joachim Metz, Daniel White, et al.) | Apache-2.0 | Super-timeline | Included |
| [Volatility 3](https://github.com/volatilityfoundation/volatility3) | Volatility Foundation | Volatility Software License | Memory analysis | Included |
| [The Sleuth Kit](https://github.com/sleuthkit/sleuthkit) | Brian Carrier and contributors | IBM Public License / CPL / GPL (per component) | Disk & file systems, deleted files | Included |
| [RegRipper 3](https://github.com/keydet89/RegRipper3.0) | Harlan Carvey | MIT | Windows registry | Included |
| [Hayabusa](https://github.com/Yamato-Security/hayabusa) | Yamato Security | AGPL-3.0 | Windows event log triage | Included |
| [Chainsaw](https://github.com/WithSecureLabs/chainsaw) | WithSecure Labs | GPL-3.0 | Event log hunting (Sigma) | Included |
| [ExifTool](https://exiftool.org/) | Phil Harvey | Artistic / GPL (Perl terms) | Media metadata | Included |
| [YARA](https://github.com/VirusTotal/yara) | VirusTotal / Victor M. Alvarez | BSD-3-Clause | Pattern scanning | Included |
| [MVT](https://github.com/mvt-project/mvt) | Amnesty International Security Lab | MVT License 1.1 | Mobile compromise indicators | Included |
| [Natural Earth](https://www.naturalearthdata.com/) via world-atlas | Natural Earth / Mike Bostock | Public domain / ISC | Offline basemap | Included |
| [evtx](https://github.com/omerbenamram/evtx) | Omer Ben-Amram | MIT / Apache-2.0 | EVTX parsing | Included |
| [MFTECmd](https://github.com/EricZimmerman/MFTECmd) | Eric Zimmerman | MIT | NTFS $MFT / $J | Included |

Hayabusa, Chainsaw and evtx_dump are compiled from their pinned source tags inside their images; the
Hayabusa/Chainsaw rule sets and MVT's public indicators are bundled at image build time so analysis
runs offline. Licences are checked again whenever a plugin is added. Some licences (for example MVT's)
put conditions on use, and the plugin docs must state them.

| [libimobiledevice](https://libimobiledevice.org/) + usbmuxd | libimobiledevice contributors | LGPL-2.1 / GPL-2.0 | iPhone backup over USB (Linux) | Beta |
| Tracelume SQLite carver | Tracelume contributors | GPL-3.0-or-later | Deleted SQLite records | Included |

## Libraries and data
FastAPI, SQLModel, SQLAlchemy, Pydantic, RQ, Redis, PostgreSQL, React, Vite, Tailwind CSS,
Playwright. See `backend/pyproject.toml` and `frontend/package.json`.

## Public test data referenced in docs
NIST CFReDS, and Joshua Hickman's public Android and iOS reference images (thebinaryhick.blog).
