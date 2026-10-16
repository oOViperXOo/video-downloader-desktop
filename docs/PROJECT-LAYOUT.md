# Project layout

- Root: application modules, launch/build scripts, dependency files and user guides.
- `assets/`: product icon and Windows version metadata.
- `browser-extension/`: browser companion source and tests.
- `tests/`: application regression suite.
- `tools/`: build, verification, benchmark and cleanup utilities.
- `docs/`: branding, current release notes and current product screenshots.

Generated `dist/`, `build/`, virtual environments, runtime binaries, diagnostics,
review notes and archives are ignored by Git. Release files are distributed through
GitHub Releases rather than committed to the repository.

Run `powershell -File tools/clean_workspace.ps1 -WhatIf` to preview generated-file
cleanup; omit `-WhatIf` to apply. It preserves releases, runtime tools and `.venv`.
