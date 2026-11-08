# Third-party notices

These files supplement, and do not replace, the original source headers and license files retained in this distribution. NZBHydra's own Apache license does not relicense bundled components.

[manifest.json](manifest.json) records component associations, upstream release/archive URLs and hashes, restored notice paths/hashes, source-file witnesses, and explicit uncertainties. Verbatim notices preserve the publisher's text. Canonical texts are identified as canonical references; no missing copyright owner or year is fabricated from a package name.

The retained code includes multiple license families, including BSD/MIT, Unlicense, PSF/ZPL, Apache, GPL and LGPL. Alternatives and nested components remain distinct. Cryptography's upstream BSD/Apache alternatives are both retained. Requests' nested urllib3, chardet and IDNA, setuptools' nested packaging, and Werkzeug's separate debug-font terms have their own evidence. The functools backport's stated Python recipe origin is also recorded.

Frontend associations use the embedded source-map inputs and hashes, not just dependency ranges. Font Awesome's font/code/documentation policy is preserved with OFL, MIT and documentation-license texts. Typicons' publisher distinguishes artwork and font terms; its precise retained CSS revision is unverified and Typicons font files are not shipped here. Bootstrap font files match its published distribution; original font metadata is retained. The slider's separately identified Bridget component is not silently assigned the slider's license.

Some unversioned or locally patched copies cannot be tied to one exact release. Those uncertainties remain in the manifest. A source match can establish a shared file without proving that an entire local directory is an unmodified release. Component associations never override per-file notices, dual-license choices, or obligations beyond attribution. This is restoration evidence, not a legal-compliance certification or a claim that source cleanup retracts prior publication.

The notice directory resides under the already-supported libs/ release root so both application packaging and existing persistent maintenance staging retain it without a runtime/tool-interface change. It contains data only, is not imported by the application, and is not a source of credentials or machine-specific records.

Use the project's offline notice validator before packaging. Do not substitute a new license from an unpinned dependency upgrade or fetch licenses automatically during application startup.
