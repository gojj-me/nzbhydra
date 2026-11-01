# NZBHydra

NZBHydra v1 maintenance by [gojj-me](https://github.com/gojj-me).

NZBHydra searches multiple NZB indexers from one place and provides a combined indexer endpoint for other applications. This repository maintains the original Python application, targeting Linux containers.

## Development and releases

```sh
git clone https://github.com/gojj-me/nzbhydra.git
cd nzbhydra
```

Read [AGENTS.md](AGENTS.md) for contribution instructions and the [maintenance policy](docs/maintenance.md) for versioning, release requirements, cleanup scope, and milestone-based planning.

The next release is [0.3.0](https://github.com/gojj-me/nzbhydra/milestone/1), followed by the 0.3.x series until 0.4.0 is explicitly selected.

The application version is recorded in [version.txt](version.txt); changes for released application versions are recorded in [changelog.md](changelog.md). The legacy application requires Python 2.7.9 or later within the Python 2 series and explicitly rejects Python 3. Future runtime and container changes require separate compatibility work.

## Source history

Based on [theotherp/nzbhydra](https://github.com/theotherp/nzbhydra), version **0.2.233**, at commit [`526a7c71eeea56ae2e3bc5677c3f9c5da224539f`](https://github.com/theotherp/nzbhydra/commit/526a7c71eeea56ae2e3bc5677c3f9c5da224539f). Original Git history is preserved; see [source provenance](docs/source-provenance.md).

## License and attribution

Original NZBHydra by The other P and its contributors. Distributed under the Apache License, Version 2.0; see [LICENSE](LICENSE). Original copyright and third-party notices remain in their respective files.
