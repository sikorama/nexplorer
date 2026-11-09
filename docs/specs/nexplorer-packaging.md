Label: ready-for-agent

# nexplorer: distributable builds for Windows and Linux

## Problem Statement

nexplorer runs only from a source checkout: the user needs Python, a virtual environment and `pip install`. Someone who just owns a ZX Spectrum Next and wants to manage its SD card cannot download the application and double-click it. There is no release process either, so the owner has no repeatable way to publish a version. A packaged build also has no console, so the one startup error the application reports today (the port is already in use) would be invisible: the user would see nothing happen.

## Solution

Each time the owner publishes a GitHub Release, a CI workflow builds two downloadable files and attaches them to that release: a portable zip for Windows (x64) and an AppImage for Linux (x86_64). Both run without Python installed. The same build scripts can be run locally to try a build. A smoke test of the packaged program runs in CI before anything is published. The README tells users where to download, what Windows shows at first launch (SmartScreen, firewall prompt) and what the Linux build needs. When the listening port is taken, the application tells the user in a dialog instead of exiting silently.

## User Stories

1. As a Windows user, I want to download one zip, unpack it anywhere and run `nexplorer.exe`, so that I do not have to install Python or an installer.
2. As a Linux user, I want to download one AppImage, make it executable and run it, so that I can use nexplorer without installing packages.
3. As a Linux user on a recent distribution, I want the AppImage to carry the Qt platform library it needs (`libxcb-cursor`), so that it starts even if my system does not have it.
4. As a Linux user on an older but still common distribution, I want the AppImage to run there, so that I am not told my system library is too old.
5. As a user, I want my settings and my chosen folders kept in my user profile as before, so that unpacking a new version does not lose them.
6. As a user who launches nexplorer from a desktop icon, I want a dialog telling me "Cannot listen on port 2048" when another instance holds the port, so that I understand why no window appears.
7. As a French-speaking user, I want that dialog translated like the rest of the interface, so that the language is consistent.
8. As a user of a build without a console, I want the same error still written to standard error, so that a terminal launch keeps showing it.
9. As a Windows user, I want the README to explain the SmartScreen warning on the first launch of an unsigned program, so that I know it is expected.
10. As a Windows user, I want the README to explain the firewall prompt for port 2048, so that I know to allow it for the Next to connect.
11. As a user, I want the README to start with a "Download" section pointing to the Releases page, above "Run from source", so that I find the files first.
12. As a user, I want each archive to contain the licence, the third-party notices and the README, so that I can read the terms and credits without going online.
13. As a user, I want the third-party notices to carry the real copyright line of ZX-Next-Unite instead of a placeholder, so that the MIT attribution is correct.
14. As a user, I want the notices to say that Qt/PySide6 is used under the LGPL and is shipped as replaceable libraries, so that the licence obligation is met.
15. As the owner, I want the build to start when I publish a GitHub Release, not at every push, so that CI time is spent only on versions I mean to ship.
16. As the owner, I want the files attached to the release I just published, so that I do not upload anything by hand.
17. As the owner, I want the workflow to fail if the release tag (`vX.Y.Z`) differs from the version in the project metadata, so that a file is never published under the wrong version.
18. As the owner, I want to start the same workflow manually without publishing, so that I can test the CI and download the artifacts before the real release.
19. As the owner, I want the build to fail if the packaged program does not start, so that a broken bundle (missing locale files, missing icons, missing trash module) is never published.
20. As the owner, I want the smoke test to check that the packaged program listens on port 2048 with the offscreen platform, so that "starts" means "serves", not just "does not crash".
21. As the owner, I want one build script per platform that both the CI and I run, so that a local build and the CI build cannot drift apart.
22. As the owner, I want files named `nexplorer-vX.Y.Z-windows-x64.zip` and `nexplorer-vX.Y.Z-linux-x86_64.AppImage`, so that users can tell them apart.
23. As the owner, I want the zip to contain one root folder `nexplorer-vX.Y.Z/` with `nexplorer.exe`, so that unpacking does not scatter files.
24. As the owner, I want the Linux build to run on an older Ubuntu image, so that the AppImage works on most current distributions.
25. As the owner, I want a minimal application icon (`.ico` for Windows, `.png` and a desktop entry for the AppImage), so that the program has an identity and I can replace it later without touching the CI.
26. As the owner, I want the release notes generated by GitHub and no changelog file, so that releasing stays a few clicks.
27. As the owner, I want a short note on how to build locally and how to publish a release, so that I can do it again months later.
28. As the owner, I want the portable-mode idea (settings next to the executable) recorded as a possible later feature, so that it is not lost.
29. As the owner, I want a PySide6 dependency limited to the modules the application imports, so that bundles and virtual environments stay small.
30. As a maintainer, I want the trash dependency installed by the build and found by the bundler even though it is imported lazily, so that moving a file to the trash works in the packaged build.

## Implementation Decisions

- **Trigger.** The workflow runs on "release published" and on manual dispatch. Manual runs produce downloadable workflow artifacts and attach nothing to a release. Plain pushes and tag pushes do not trigger it.
- **Version source.** The release tag `vX.Y.Z` names the files. A small pure function compares the tag with the version in the project metadata and the workflow fails on a mismatch. A manual dispatch has no tag and uses the metadata version.
- **Bundler.** PyInstaller in directory mode for both platforms, driven by a versioned spec file in a `packaging` folder. The spec declares the locale JSON files and the SVG icons as data and includes the lazily imported trash module. The application is built windowed (no console).
- **Windows output.** The bundle directory is zipped under a single root folder named after the version; the executable is `nexplorer.exe`. x64 only. No installer and no code signing.
- **Linux output.** The bundle directory is placed in an AppDir with a desktop entry and an icon, then packed with `appimagetool`. `libxcb-cursor` is copied into the AppDir. x86_64 only. The build runs on an Ubuntu 22.04 runner so the glibc requirement stays low.
- **Build scripts.** One script per platform in the `packaging` folder (shell for Linux, PowerShell for Windows). Each installs build dependencies, runs the bundler and produces the final file. The CI workflow only calls them; the owner can run the same script locally. A local Linux build on a recent system is a functional check, not the distributable file.
- **Smoke test.** After each build, the CI launches the packaged program with the offscreen Qt platform for a few seconds, checks that it stays alive and that port 2048 accepts a connection, then stops it. The job publishes nothing if this fails. The same check is run on both platforms against the final artifact (the unpacked zip, the AppImage).
- **Startup error dialog.** In the application's start-up path, when the listener cannot bind, a translated message box ("Cannot listen on port N" plus the system reason) is shown in addition to the existing message on standard error. The exit code stays non-zero. The string is added to both locale files, English and French.
- **Dependencies.** The project depends on `PySide6-Essentials` (already done) and `send2trash`; the build environment installs both. The trash module is only imported at call time, so the bundler must be told about it explicitly.
- **Icon.** A minimal icon derived from an existing embedded SVG, exported as `.ico` and `.png`. Replacing it later changes no workflow.
- **Archive content.** Both archives contain `LICENSE`, `THIRD_PARTY_NOTICES.md` and `README.md`. The notices gain the LGPL statement for Qt/PySide6 (dynamic libraries, replaceable) and the placeholder copyright line of ZX-Next-Unite is replaced by the real one taken from that project's licence file.
- **Documentation.** `README.md` gets a "Download" section above "Run from source" listing the two files, the SmartScreen note, the firewall note and the Linux requirements. A short `packaging/README.md` explains the local build and the release procedure, in present tense, with no history. No ADR and no glossary change: the decisions are easy to reverse and introduce no domain term.
- **Release process.** The owner creates the release by hand in the GitHub interface with generated notes and no changelog file. Before the first release (`v0.1.0`) the owner runs the manual dispatch, then tries the Windows zip on a Windows machine or VM and the AppImage on a Linux machine.
- **Settings location.** Unchanged: the user profile on both platforms. A real portable mode is recorded in the improvements file, not built.

## Testing Decisions

- **What makes a good test here.** Test what a user or the release process observes: the packaged program starts and serves; the dialog appears with the right text when the port is taken; a wrong tag is refused. No test of how the spec file or the scripts are written.
- **Seam 1, packaged program (highest).** The CI smoke test above. It is the only test that proves the bundle contains every resource and module. It runs in CI, not in the pytest suite.
- **Seam 2, application start-up.** A pytest test on the offscreen platform: occupy the port, start the application's entry function, assert that the error dialog is shown with the translated text, written to standard error too, and that the exit code is non-zero. Prior art: the window tests inject dialogs (scripted prompts) instead of opening real ones; follow that pattern with an injectable "show error" function. Add the locale-file parity check already used by the i18n tests if one exists.
- **Seam 3, tag and version check.** A pytest test of the pure comparison function: matching tag and version passes; a different version, a missing `v` prefix or a malformed tag fails with a clear message. The workflow calls this function.
- Not automated: a real launch on Windows and a real desktop launch of the AppImage; the owner does these by hand before `v0.1.0` (see the release process).

## Out of Scope

- Installers (MSI, Inno Setup, `.deb`, Flatpak, Snap), macOS builds, ARM builds, 32-bit builds.
- Windows code signing and notarisation.
- A portable mode with settings next to the executable (noted in the improvements file).
- Auto-update and update notifications.
- A changelog file.
- Publishing to PyPI.
- Reducing the size of the bundle beyond using `PySide6-Essentials` and what the bundler already prunes.

## Further Notes

- The venv size dropped from about 705 MB to 273 MB when `PySide6-Essentials` replaced the `PySide6` metapackage; the packaged bundle is expected to be well below that, since the bundler only includes imported modules. Measure it during the first build and note any surprise.
- The application listens on TCP port 2048 from launch; this is why Windows shows a firewall prompt and why a second instance fails. Both are expected behaviour.
- Cross-compiling is not possible: the Windows file is built on a Windows runner and the Linux file on a Linux runner.
