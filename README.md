# copperscript

> ⚠️ **You are on `spike/v0.1-referencia`.** This branch is a complete, heavily commented reference implementation (comments in Spanish) used for learning and to anticipate design problems. It is **never merged into `main`**; `main` is implemented step by step from its stubs.

**copperscript** is an open-source OSINT tool that organizes collected data and displays it as an interactive graph.

Raw collection is noisy: results are often incomplete, duplicated or uncertain. copperscript normalizes and deduplicates findings, tracks where each one came from and how confident we are in it, and uses Markov chains learned from past investigations to suggest the most promising next steps — so you spend your queries, API quota and time where they matter most.

> Named after Minecraft's copper golem, which takes items out of a copper chest and sorts them into the right chests. copperscript does the same with investigation data. *Not affiliated with Mojang or Microsoft.*

## Status

Early development (v0.1 in progress). The core is designed as **stubs**: functions with types and docstrings whose tests already exist. Run `pytest -rs` to see what is still pending.

## Branches

| Branch | What it is |
|---|---|
| `main` | The real project. Core modules are stubs being implemented step by step. |
| `spike/v0.1-referencia` | A complete, heavily commented reference implementation of v0.1 (in Spanish), used to explore the design and anticipate problems. **Never merged into `main`.** |

## Development

```bash
git clone https://github.com/amarocardenasm/copperscript
cd copperscript
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -rs          # PENDIENTE = stub not implemented yet
ruff check .        # style
```

Planned CLI (v0.1):

```bash
copperscript nuevo mi-caso --nombre "Prueba" --objetivo "Huella de un usuario"
copperscript importar mi-caso amaro_dev.csv      # Sherlock, SpiderFoot (auto-detected)
copperscript entidades mi-caso
copperscript exportar mi-caso obsidian           # or: html
```

## Principles

- **Keyless first**: useful without paying for any API.
- **Bring your own key**: paid or account-based sources are optional modules.
- **Local and private**: your cases live on your machine.
- **Passive and public sources only**: see [USO-RESPONSABLE.md](USO-RESPONSABLE.md).

## Licensing

copperscript is **dual-licensed**:

1. **GNU Affero General Public License v3.0 (AGPL-3.0)** — see [`LICENSE`](LICENSE).
   Free for everyone: individuals, students, researchers, journalists and organizations, as long as they comply with the AGPL. In short: if you modify copperscript and distribute it **or offer it to others over a network** (for example as a web service), you must publish your full modified source code under the same license.

2. **Commercial license** — for companies that want to use, embed or offer copperscript as a service **without** the AGPL obligations (keeping their changes private). To ask about a commercial license, open an issue titled `Commercial license` or contact the maintainer through their GitHub profile ([@amarocardenasm](https://github.com/amarocardenasm)).

## Contributing

Contributions are welcome. Because copperscript is dual-licensed, every contributor must agree to the [Contributor License Agreement](CLA.md) before their first pull request is merged. You keep the copyright of your work; the CLA only allows the maintainer to distribute it under both licenses.

## Responsible use

copperscript is meant for lawful investigation, security research and education. Use only public, passive sources, define the scope of each case before starting, and respect the privacy and data-protection laws of your country. Full principles in [USO-RESPONSABLE.md](USO-RESPONSABLE.md).

Copyright (C) 2026 @amarocardenasm
