Label: ready-for-agent

# 01: Identical panes, status bar, splitter, waiting card

**What to build:** The Local and ZX Spectrum Next panes have the same structure (header, drive selector with free space, Up button, address field, list, status line) so rows line up. Local gets a drive selector: drive letters on Windows; Home, `/` and the mount points under `/media`, `/mnt` and `/run/media/<user>` on Linux, re-read each time the selector opens. A status bar at the bottom shows the connection (green dot and address), the "dot too old" warning and the selection summary ("3 items, 1.2 MB"); transfer progress and Cancel stay visible. A draggable splitter separates the panes; the window opens at 1100x650 with a minimum of 800x450. While no ZX Spectrum Next is connected, its pane shows a centred card with an icon, the Local addresses, the command `.sync5 -l` with a Copy button and the config-file reminder, and its toolbar stays visible but greyed. Every interface string that said "Next" now says "ZX Spectrum Next" (French: "sur le / du ZX Spectrum Next"); the glossary term and code identifiers do not change.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Both panes show the same rows in the same order and the same sort behaviour; the Next pane's drive row no longer shifts it
- [ ] The Local drive selector lists the right roots for a Windows and a Linux fixture (platform and mount sources injectable) and shows free space like the Next pane
- [ ] Connection state, dot warning and selection summary appear in the status bar and nowhere else; progress and Cancel remain reachable during a transfer
- [ ] The waiting card shows the addresses, the command with a working Copy button and the config reminder; the Next pane's toolbar is greyed, not hidden
- [ ] Default size, minimum size and splitter position are applied and persisted
- [ ] No interface string says "the Next" or "on Next"; `fr.json` has the translated forms
- [ ] Tests (window seam, offscreen) cover the above; the roots function is tested on temporary fixtures
