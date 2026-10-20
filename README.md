# copperscript

**copperscript** is an open-source OSINT tool that organizes collected data and displays it as an interactive graph.

Raw collection is noisy: results are often incomplete, duplicated or uncertain. copperscript normalizes and deduplicates findings, tracks where each one came from and how confident we are in it, and uses Markov chains learned from past investigations to suggest the most promising next steps — so you spend your queries, API quota and time where they matter most.

> Named after Minecraft's copper golem, which takes items out of a copper chest and sorts them into the right chests. copperscript does the same with investigation data. *Not affiliated with Mojang or Microsoft.*

## Status

Early development. Nothing to install yet.

## Principles

- **Keyless first**: useful without paying for any API.
- **Bring your own key**: paid or account-based sources are optional modules.
- **Local and private**: your cases live on your machine.
- **Passive and public sources only**: see [USO-RESPONSABLE / Responsible use](#responsible-use).

## Licensing

copperscript is **dual-licensed**:

1. **GNU Affero General Public License v3.0 (AGPL-3.0)** — see [`LICENSE`](LICENSE).
   Free for everyone: individuals, students, researchers, journalists and organizations, as long as they comply with the AGPL. In short: if you modify copperscript and distribute it **or offer it to others over a network** (for example as a web service), you must publish your full modified source code under the same license.

2. **Commercial license** — for companies that want to use, embed or offer copperscript as a service **without** the AGPL obligations (keeping their changes private). To ask about a commercial license, open an issue titled `Commercial license` or contact the maintainer through their GitHub profile ([@amarocardenasm](https://github.com/amarocardenasm)).

## Contributing

Contributions are welcome. Because copperscript is dual-licensed, every contributor must agree to the [Contributor License Agreement](CLA.md) before their first pull request is merged. You keep the copyright of your work; the CLA only allows the maintainer to distribute it under both licenses.

## Responsible use

copperscript is meant for lawful investigation, security research and education. Use only public, passive sources, define the scope of each case before starting, and respect the privacy and data-protection laws of your country.

Copyright (C) 2026 @amarocardenasm
