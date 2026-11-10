# Packaging

Builds a portable zip for Windows (x64) and an AppImage for Linux (x86_64) with PyInstaller in directory mode. `nexplorer.spec` declares the data files (locales, SVG icons, `sync-wrap/sync-wrap.bas`, which the build fails without) and the lazily imported `send2trash`. `icon.png` and `icon.ico` are the application icon; replacing them changes no script (`make-icon.sh` regenerates them from an embedded SVG).

## Build locally

Both scripts are the ones the CI runs. Output goes to `dist/`, intermediate files to `build/`.

- Linux: `packaging/build-linux.sh` produces `nexplorer-vX.Y.Z-linux-x86_64.AppImage`. It needs Python 3.10+, `curl` and `libxcb-cursor0`, and downloads `appimagetool`. A build on a recent system is a functional check; the distributable file comes from CI, built on Ubuntu 22.04 for a low glibc requirement.
- Windows: `packaging\build-windows.ps1` produces `nexplorer-vX.Y.Z-windows-x64.zip` with the single root folder `nexplorer-vX.Y.Z\`.
- The version comes from `pyproject.toml`.
- Test a built program: `packaging/smoke-test.sh PROGRAM`. It launches the program offscreen, checks that it stays alive and that port 2048 accepts a connection. Port 2048 must be free.

## Publish a release

The workflow `.github/workflows/release.yml` runs when a release is published and on manual dispatch. Each platform builds, smoke-tests and uploads its file as a workflow artifact. Only on a release, and only if both builds pass, the `publish` job attaches both files to it. The release tag `vX.Y.Z` must equal the version in `pyproject.toml`, otherwise the workflow fails before building (`check_release_tag.py`).

1. Set `version` in `pyproject.toml`, commit and push.
2. Pre-release check: start the workflow by hand (Actions, Release, Run workflow). Download both artifacts. Run the zip on a Windows machine or VM (window opens, settings saved in the profile, firewall prompt seen) and the AppImage on a Linux machine (`chmod +x`, then run).
3. Create the release in the GitHub interface: tag `vX.Y.Z`, **Generate release notes**, publish. There is no changelog file.
4. The files appear on the release when the workflow ends.
