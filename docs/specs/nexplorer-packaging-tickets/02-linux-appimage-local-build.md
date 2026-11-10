# 02: Linux AppImage build, runnable locally

**What to build:** One script that, run on a Linux machine, produces `nexplorer-vX.Y.Z-linux-x86_64.AppImage` (the version taken from the project metadata) which starts without Python installed. It installs the build dependencies (`PySide6-Essentials`, `send2trash`, the bundler), bundles the application with PyInstaller in directory mode from a versioned spec file (locale JSON files, SVG icons and the lazily imported trash module declared), builds an AppDir with a desktop entry and a minimal icon, embeds `libxcb-cursor`, and packs it with `appimagetool`. `LICENSE`, `THIRD_PARTY_NOTICES.md` and `README.md` are included. A shared smoke-test script launches a packaged program offscreen for a few seconds, checks that it stays alive and that port 2048 accepts a connection, then stops it. A build made on a recent machine is a functional check; the distributable file comes from CI (ticket 03).

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Running the build script locally produces an AppImage with the agreed name; making it executable and running it opens the window.
- [ ] The smoke-test script passes on that AppImage and fails when the program is made to exit at start or a resource is removed from the bundle (check by hand once).
- [ ] Locale files, icons and the trash module are present in the bundle (moving a file to the trash works from the packaged program).
- [ ] The icon exists as `.png` and `.ico`, derived from an existing embedded SVG; replacing it changes no script.
- [ ] The smoke-test script takes the path of the program to test, so it can be reused on Windows (ticket 04).
- [ ] The measured bundle and AppImage sizes are noted in the ticket's report for the owner.
