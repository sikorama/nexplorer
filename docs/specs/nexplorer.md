Label: ready-for-agent

# nexplorer: minimal Next file manager with Compare

## Problem Statement

I own a ZX Spectrum Next and want to manage its SD card over Wi-Fi from my PC. ZX-Next-Unite does this through its Remote Explorer, but it is buried in a very large application: emulators, disk images, online catalogues, an MCP server, an HTTP bridge, themes, animations and a multi-machine session model. The interface is busy and not to my taste. Two things I need are missing or unreliable: moving a file inside the Next (Cut then Paste copied the file but never deleted the source, so I deleted it by hand), and a controlled way to bring a Local folder and a Next folder into line.

## Solution

A small, public, MIT-licensed Python desktop application, `nexplorer`, with one window and two panes: Local on the left, Next on the right. It reuses the existing Next-side dot command `.sync5` unchanged and listens on port 2048 from launch. Until a Next connects, the Next pane shows only what is needed to connect: the Local IP address(es), the command to type on the Next (`.sync5 -l`), and a reminder that the Local address must be set in `c:/sys/config/nextsync.cfg` on the Next.

Once a Session is open, the user browses, sends, receives, creates folders, renames, deletes (with confirmation), copies and moves. Move works inside the Next: a rename on the same drive, a copy then delete across drives, and the source is deleted only once the copy is confirmed.

A Compare mode replaces the two panes with a list of Differences between a Local folder and a Next folder. The user chooses the direction per row, can transfer a single file or apply everything selected, and nothing is transferred or deleted automatically.

The interface uses very few words, English first, with every string routed through a translation function so that languages can be added later as JSON catalogues.

## User Stories

1. As a Next owner, I want the app to listen for the Next as soon as it starts, so that I do not have to configure a server before connecting.
2. As a Next owner, I want to see the Local IP address of each network interface while waiting, so that I know which address to put in the Next's configuration.
3. As a Next owner, I want to see the exact command to type on the Next (`.sync5 -l`), so that I do not have to remember it.
4. As a Next owner, I want a reminder that `c:/sys/config/nextsync.cfg` holds the Local address, so that I can fix a connection that does not come up.
5. As a Next owner, I want a coloured status dot and the Next's address once connected, so that I can see the Session state at a glance.
6. As a Next owner, I want the pane to return to the waiting screen when the Session ends, so that I know the Next is no longer reachable.
7. As a Next owner, I want example NextBASIC programs in the repository that launch the dot, so that connecting takes one command.
8. As a user, I want a Local pane showing a normal file tree with name, size and type, so that I can pick what to send.
9. As a user, I want a Next pane showing the Next's folders and files, so that I can see the SD card without removing it.
10. As a user, I want to switch between drives on the Next, so that I can reach every partition.
11. As a user, I want to see the free space of a drive, so that I know whether a transfer will fit.
12. As a user, I want to navigate up, into folders and to type a path, in both panes, so that I can reach any location quickly.
13. As a user, I want to sort each pane by name, size and type and have the choice remembered, so that the panes look the way I left them.
14. As a user, I want to select several entries at once, so that I can act on a group.
15. As a user, I want to send selected Local entries to the Next folder shown, so that I can put files on the Next.
16. As a user, I want to receive selected Next entries into the Local folder shown, so that I can back files up.
17. As a user, I want to drop files from my system file manager onto the Next pane, so that sending is one gesture.
18. As a user, I want to drop onto a specific Next subfolder to send into it, so that I do not have to navigate first.
19. As a user, I want to drag entries from the Next pane to the Local pane to receive them, so that receiving is one gesture.
20. As a user, I want to create a folder on the Next, so that I can organise it.
21. As a user, I want to rename a file or folder on the Next, so that I can fix its name.
22. As a user, I want to delete files and folders on the Next, including non-empty folders, so that I can free space.
23. As a user, I want every delete on the Next to ask for confirmation naming the number of items and the first name, so that I never delete by accident.
24. As a user, I want the app never to delete anything on Local, so that my PC files are safe from mistakes.
25. As a user, I want to copy entries inside the Next without a round trip through the PC, so that duplicating is fast.
26. As a user, I want to move entries inside the Next with Ctrl+X then Ctrl+V or by dragging them onto a folder, so that I can reorganise without copying and deleting by hand.
27. As a user, I want a move on the same drive to be an instant rename, so that moving a large folder takes no time.
28. As a user, I want a move across drives to copy, check and only then delete the source, so that a failure never loses data.
29. As a user, I want a failed move to keep the source and say so, so that I can retry.
30. As a user, I want a progress bar with the current file, percentage and a Cancel button at the bottom of the window, so that long transfers do not freeze the app.
31. As a user, I want only one modifying operation to run at a time, with the other modifying actions greyed out, so that the single serial link is not overloaded.
32. As a user, I want to keep browsing Local while an operation runs, so that I can prepare the next action.
33. As a user, I want a batch to continue after a failed file and end with a summary of failures, so that one bad file does not abort the rest.
34. As a user, I want a partially written file after a dropped Session to be listed in the summary with its name and size, so that I can remove it myself.
35. As a user, I want the size checked after every upload, so that a truncated upload is noticed.
36. As a user, I want an optional setting to verify the CRC after each upload, off by default, so that I can choose safety over speed.
37. As a user, I want a Compare button that replaces the two panes with a list of Differences between a Local folder and a Next folder, so that I can see what is out of line.
38. As a user, I want Compare to keep the folders I had in the panes, so that I do not choose them twice.
39. As a user, I want each Compare row to show one state: only on Local, only on the Next, different, identical, unverified, ignored, not scanned, conflict or invalid, so that I understand every row.
40. As a user, I want files of different size marked different without reading them, so that Compare is quick.
41. As a user, I want a Verify action that asks the Next for the CRC of same-size files, so that I can check content on demand.
42. As a user, I want Compare to list one level at a time and expand folders on demand, so that a large tree does not take minutes before I can act.
43. As a user, I want a Scan all option with progress and Cancel, so that I can still compare a whole tree when I choose to.
44. As a user, I want unscanned folders marked not scanned and never shown as identical, so that I am never misled.
45. As a user, I want each row to propose a direction (Local to Next for only-Local, Next to Local for only-Next), so that the common case is one click.
46. As a user, I want to reverse a row's direction, uncheck it or check it, so that I stay in control.
47. As a user, I want rows marked different to start unchecked with no direction, so that I choose which side wins.
48. As a user, I want to transfer a single file from the list, so that I do not have to apply everything.
49. As a user, I want an Apply button that transfers all checked rows, so that I can bring a folder into line in one action.
50. As a user, I want files that exist on only one side never to be deleted from the other side, so that Compare cannot destroy data.
51. As a user, I want names compared without regard to case, so that Compare matches the Next's case-insensitive file system.
52. As a user, I want two Local files that differ only by case flagged as a conflict and not transferred, so that one never overwrites the other on the Next.
53. As a user, I want a path that is too long or contains a character the Next's file system refuses shown as an error with an icon and excluded from transfer, so that it fails visibly rather than silently.
54. As a user, I want hidden files and folders such as `.git` shown or hidden by a setting and never ignored silently, so that I know what is excluded.
55. As a user, I want an optional `.nexplorerignore` file at the compared folder's root with glob patterns, so that temporary files are not offered for transfer.
56. As a user, I want ignored rows shown greyed with the word "ignored", so that I can see what the ignore file excluded.
57. As a user, I want actions the connected dot does not support greyed out, so that I am not offered operations that would fail.
58. As a user, I want a short message telling me to update `.sync5` and the minimum version needed when the dot is too old, so that I know how to fix it.
59. As a user, I want the app never to update the dot on its own, so that nothing is installed on my Next without my action.
60. As a user, I want settings stored in one JSON file in the standard user configuration folder, so that the app leaves nothing elsewhere.
61. As a user, I want the app to remember my last Local and Next folders, window geometry, language, hidden-files choice, CRC choice and sort order, so that it opens as I left it.
62. As a user, I want a small settings screen with a few checkboxes and a language choice, so that I can adjust the app without a tabbed dialog.
63. As a user, I want the app to look like my system theme with no animation, so that it stays calm and fast.
64. As a user, I want few words on screen and icons where clear, so that the interface is quick to read and easy to translate.
65. As a translator, I want every displayed string to go through one translation function keyed by the English text, so that adding a language is only a new JSON file.
66. As a contributor, I want a written protocol reference in the repository, so that I can understand the Next's behaviour without reading three code bases.
67. As a contributor, I want a fake Next that speaks the protocol over a local socket, so that I can test without hardware.
68. As a maintainer, I want the app to run on Linux first with nothing that blocks Windows or macOS, so that a later port is cheap.
69. As a Next owner, I want to launch the app from a source checkout with one command, so that no packaging is needed.

## Implementation Decisions

- New standalone public repository `nexplorer`, MIT licence. Code reused from ZX-Next-Unite keeps the MIT notice of its author; the NextSync protocol origin (Jari Komppa, Unlicense) is credited in the third-party notices. HDFM-Gooey and hdfmonkey are not used and are not credited as dependencies.
- Everything in the repository (code, comments, README, GLOSSARY, ADRs) is in English. Python 3.10 minimum. The only runtime dependency is PySide6; pytest is a development dependency. Linux first, no platform-specific code that prevents a port. No packaging, no PyInstaller, Flatpak or PyPI.
- Domain vocabulary is the one in `GLOSSARY.md`: Next, Local, Listener, Session, Compare, Difference, Move. These words are used in code names and the interface.
- The Next-side dot `.sync5` is used unchanged (the user's copy comes from GetIt 2). The project does not build or modify Z80 code and does not bundle or update the dot.
- **Protocol module**: pure Python, no Qt. It exposes a Session abstraction speaking the existing `.sync5 -listen` wire protocol: directory listing, drives, free space, version/identification, get, put, make folder, remove file, remove folder, recursive remove, rename, copy on the Next, size of a tree, CRC-32 of a file. The Session reports the dot's version so that callers can gate features. The Listener accepts one Session at a time on port 2048 and starts at launch.
- Transfer payload size is 512 bytes per frame, the value Unite settled on because some Next clones corrupt longer UART bursts.
- A written `docs/protocol.md` (opcodes, framing, handshake, error cases, version differences) is produced first from the three existing sources (the Unite server, the Unite worker, and the dotN C source), before the protocol module is implemented. It is the reference for both the fake Next and the module.
- **Move**: same-drive Move is a rename. Cross-drive Move is a copy on the Next, a size check, then a delete of the source; any failure keeps the source. Move exists only inside the Next. Moving between Local and Next is out of scope. Ctrl+X marks entries, Ctrl+V performs the Move, and dragging entries onto a Next folder performs the same Move.
- **Compare**: a mode of the same window replacing both panes. Row states: only on Local, only on the Next, different, identical, unverified, ignored, not scanned, conflict, invalid. Size is compared first; CRC-32 is requested from the Next only on demand, only for same-size files. Lists load one level at a time, with an optional Scan all that has progress and Cancel. Name comparison is case-insensitive. Paths over 254 bytes or with FAT-forbidden characters are shown as errors and excluded. Hidden entries follow a setting and are never silently dropped. An optional `.nexplorerignore` at the compared folder's root uses glob patterns, one per line, with `#` comments; ignored rows are shown greyed with "ignored".
- Compare proposes Local to Next for only-Local rows and Next to Local for only-Next rows. Different rows start unchecked with no direction. The direction is reversible per row. Apply transfers every checked row sequentially; single-file transfer is available per row. Compare never deletes on either side.
- **Operations**: one modifying operation at a time, shown by a thin non-modal progress bar with Cancel at the bottom of the window. Modifying actions are greyed while it runs; Local navigation stays free. A batch continues after a failure and ends with a summary. A dropped Session stops the operation, leaves untransferred rows as they were, lists partially written Next files by name and size, and returns the Next pane to the waiting screen. Nothing is deleted automatically after a failure.
- Deleting on the Next always asks confirmation naming the item count and first name. The Next has no recycle bin. The app never deletes on Local.
- Upload check: size is always checked after an upload by listing the folder; a setting, off by default, adds a CRC check after each upload.
- Dot capability gating: the Session reads the announced version and greys actions the dot does not support. A short line states the minimum `.sync5` version and tells the user to update it; the app never updates the dot.
- **Waiting screen**: lists the Local IP address of each network interface, the command `.sync5 -l`, and the reminder about the Local address in `c:/sys/config/nextsync.cfg` on the Next. The repository ships an `examples` folder with NextBASIC launcher programs supplied by the owner.
- **Window**: one window, Local pane left and Next pane right, system theme, no animation, no custom styling. Settings screen is a small dialog with a few checkboxes and a language choice, not a tabbed window.
- **Drag and drop**: dropping external files on the Next pane sends them into the shown folder or the folder under the cursor. Dragging Next entries onto the Local pane receives them. Dragging out of the application to the system file manager is not supported.
- **Settings**: one JSON file in the standard user config folder (the XDG location, or the platform equivalent, found without an extra dependency). It stores the last Local and Next folders, window geometry, language, hidden-files choice, CRC choice and each pane's sort order.
- **Translation**: every displayed string goes through one function keyed by the English text, which also serves as the fallback. Catalogues are JSON files, one per language, chosen by a setting. English only at first. No gettext, no Qt Linguist.
- UI threading: a thin layer runs Session calls off the UI thread and delivers results to the UI by signals; the Session module stays free of Qt.

## Testing Decisions

- A good test drives external behaviour only: what the Session returns and what the fake Next's file system contains afterwards, never internal state or frame-level details of the module.
- One seam: the Session API connected to a fake Next, an in-memory file system served over a local socket that speaks the protocol documented in `docs/protocol.md`. All features that reach the Next are tested at this seam: listing, drives, free space, put, get, make folder, rename, copy on the Next, recursive delete, Move (same drive and cross-drive, including a failure that must keep the source), CRC, version gating, dropped Session and partial files.
- Compare is tested at the same seam, with a real temporary Local folder and the fake Next: states, size then CRC, not scanned, case conflicts, invalid paths, `.nexplorerignore`, direction proposals, Apply, and the guarantee that nothing is deleted.
- The interface has only an offscreen smoke test: the window opens, Compare activates, the waiting screen shows the command. No other automated UI tests.
- Tests use pytest with targeted runs during development. The fake Next also simulates dot behaviours that real hardware showed as hard (clones corrupting long bursts, OS-protected writes) only if `docs/protocol.md` documents them.
- Prior art: ZX-Next-Unite's `tests/test_remote_listen.py`, `test_listen.py`, `test_remote_explorer_widget.py` and `test_ui_offscreen.py`, plain scripts that already exercise the protocol and an offscreen UI. They show the shape of a fake peer but not a reusable fixture.

## Out of Scope

- Emulators (CSpect, MAME, ESP emulation), HDF disk images and SD-card tooling, online catalogues (GetIt, ZXDB, zxArt, itch.io), the MCP server, the HTTP bridge.
- Several simultaneous Sessions, passing a clipboard between Nexts, per-machine names and colours.
- Self-update of the app or of the dot, deploying `.sync5` into an image, any packaging.
- The original one-way Classic sync (`.sync`, `syncpoint.dat`, `syncignore.txt`) and the Sync4 `-send` mode.
- Mirror mode with deletion, automatic or scheduled synchronisation.
- Moving between Local and Next, dragging out to the system file manager.
- Changes to the Z80 dot or its build.
- Languages other than English at first; the structure to add them is in scope, the translations are not.
- Windows and macOS builds and testing.

## Further Notes

- The cause of Unite's failing Cut (a move implemented as copy, wait for a completion marker, then delete) is unknown without hardware. nexplorer avoids that path on the same drive by renaming; the cross-drive path must be tested on the real Next before it is trusted.
- The Next's listing carries name, type and size but no modification time, which is why Compare uses size then CRC.
- A listing across the UART is slow, which is why Compare scans one level at a time.
- Whether Unite's `.sync5` versions all support rename, CRC, copy on the Next and free space is to be established in `docs/protocol.md`; the minimum version stated by the gating line comes from it.
