# Legacy release-content audit

Evidence for [issue #4](https://github.com/gojj-me/nzbhydra/issues/4), reviewed for the Python 2.7 / existing-image 0.2.300 release on 2026-11-07. GitHub owns acceptance, remediation decisions and status; this report is an inventory and rationale, not a separate backlog or a security certification.

## Reproduce the inventory

Run from the checkout with Python 3:

    python3 scripts/audit_release_content.py --output /tmp/nzbhydra-dependency-inventory.json

The [checked-in snapshot](dependency-inventory.json) enumerates tracked files present in the working tree, with the base revision and changed paths. It records 264 top-level Python library components (both packages and single modules), literal declared versions where available, static application-import candidates, standalone license files, source license declarations/indicators, frontend declarations, and source-map input identities/content hashes. Nested packages remain within their top-level component; this is not a complete transitive SBOM. Missing version evidence stays unknown. A textual license indicator does not establish that required license text is complete.

## Runtime references and retention

The entry point puts libs/ first on the import path after initial interpreter imports. Standard-library copies and compatibility shims can therefore shadow image modules; removing an apparently unused file may change dependency resolution. Static direct references are only candidates: transitive, optional and dynamic imports also matter.

| Area | Reference/evidence | Disposition in this cleanup |
| --- | --- | --- |
| Flask/Werkzeug/Jinja2, webargs/marshmallow | Web routing, authentication, templates and API schemas; transitive Flask imports | Retain |
| Peewee/playhouse, Arrow/dateutil | Persistence, queued workers, migrations, dates/retention | Retain, including existing local modifications |
| Requests and its nested urllib3/chardet/idna, separate urllib3 | Shared provider access; optional TLS backend imports; multiple bundled versions | Retain; duplication alone is not proof either copy is removable |
| PyJWT and optional OpenSSL/cryptography/cffi paths | Authentication and optional transitive crypto/TLS imports | Retain Python sources; remove only identified Windows native binaries |
| future/builtins, six, standard-library copies | Compatibility imports and interpreter/transitive dependencies | Retain; no blanket deletion of Windows-named standard-library modules |
| Other providers, parsing helpers and metadata clients | Adapter imports, optional configured parsers, metadata conversion | Retain; provider support decisions are separate from dependency deletion |

Observed applicable image runtime: Python 2.7.18, OpenSSL 1.1.1g, Requests 2.12.1. Its native extension suffixes are .so and module.so. Import/test success in that image does not verify all optional parsers, crypto backends, architectures, Docker hosts or provider services.

## Frontend/build inputs and compiled output

templates/index.html loads static/js/alllibs.js, static/js/nzbhydra.js, the vendor CSS and selected theme. Static templates, images and fonts are runtime assets. Six committed source maps embed their inputs: 47 vendor-JavaScript sources, 52 application-JavaScript sources, 13 vendor-CSS sources, and 68/69/68 theme sources for bright/dark/grey.

gulpfile.js traces application inputs from ui-src/, vendor inputs through Bower/wiredep, generated JavaScript/CSS and source maps, and copied Bootstrap/Font Awesome fonts. Retain these shipped assets and build inputs. Removing a manifest entry solely because its package is not directly imported by Python would break this separation.

bower.json declares 47 dependencies and package.json declares 30 development dependencies. These are ranges, not a reproducible lockfile or proof of the exact bundled versions. Bower's transitive dependencies can add inputs absent from the top-level declaration, including jQuery. The legacy Gulp file imports gulp, which is not explicitly listed in package.json; its index task also stages generated files through gulp-git. The package main points to missing gruntfile.js, npm test is a placeholder, and make test points to missing startTests.py. These paths are not advertised as working release checks. No package installation, dependency upgrade, frontend rebuild or build-reproducibility claim is made by this audit; use the verified checks in AGENTS.md.

## License evidence

The application Apache license is not a substitute for third-party notices. The inventory found only two standalone license files inside libs/: the enum license and Werkzeug's bundled font license. Some other components contain inline notices or license labels; several explicitly refer to absent standalone license files, for example Flask and Requests. Python standard-library copies and distributed frontend/font components also need their applicable notices assessed.

Frontend source maps retain some upstream notices/source content, while minification may remove banners from the executable bundle. Preserve all existing source/header notices, maps, fixtures and standalone licenses. Do not infer license completeness from an SPDX-like label, a version header or the presence of the application's LICENSE. Restoration of missing notices and their inclusion in release/staging manifests needs explicit verification under #4 or its agreed linked work.

## Linux-only removals

- Removed the Windows binary updater and .exe-based manager selection. Linux source/Git manager selection and the managed-build source-overwrite prohibition remain.
- Removed macOS Git-location and Windows command-case fallback branches. Configured Linux Git paths and global git fallback remain.
- Removed three PE32 Windows DLL extension files: libs/cryptography/hazmat/bindings/_constant_time.pyd, _openssl.pyd and _padding.pyd. These are Windows binaries, not Linux .so modules. The corresponding Python source and dependencies remain.
- Retained portable path helpers, the small frozen-application base-path fallback and generic Python compatibility code; names or age alone do not establish safe removal. Historical distribution-build files had already been removed before this audit.

## Fixture and credential review

A limited tracked-fixture scan found inherited credential-shaped literals and email-like values. A metadata-provider value in recorded fixtures also occurs in runtime metadata-provider code. Validity and ownership were not tested, and values are not reproduced in this report. No claim is made that this scan proves the absence of other private data or credentials.

Replacing a functional embedded provider credential requires a deliberate configuration/failure-behavior migration and synthetic fixtures, rather than silently breaking metadata conversion. Existing recordings must not be rerecorded against real accounts. Sanitizing the current tree cannot retract already published Git history; do not republish values in patches, reports or issue comments. Resolution remains on #4 pending the maintainer's tracking choice.

## Validation boundary

The initial candidate passed 116 focused application regressions, including five new updater tests and the three existing TLS controls, under the applicable isolated Python 2.7 image without provider networking. Two added updater cases then verified configured/global Git lookup and no probing of retired platform paths, bringing the focused updater suite to seven passing tests.

Packaging the actual candidate tree in a disposable Git repository produced a 1,210-file manifest with no Windows binaries, bytecode, tests or frontend build inputs. Runtime assets and the existing standalone notices remained present; all manifest hashes matched, and maintenance staging/immutable-tree verification passed. Two release-packaging tests and version metadata checks also passed. This validates the specific removals; it does not resolve the notice/fixture findings or certify a release.

No production image/runtime replacement, database migration, dependency upgrade, native host support claim or 0.3.0 modernization is included.
