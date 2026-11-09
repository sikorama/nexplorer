Label: ready-for-agent

# nexplorer: interface refresh and symmetric actions

## Problem Statement

I use nexplorer and the functions work, but the window looks like a default Tk application: a row of nine text buttons above two panes, no menu bar, no icons, no context menus. The two panes are not aligned (the Next pane has an extra "Drive" row, Local has none). Modifying actions (new folder, rename, delete, cut, copy, paste) exist only on the Next side and are all labelled "on Next", so Local feels like a second-class pane. Double-clicking a file does nothing useful, deleting a Local file is impossible from the application, and the interface calls the machine "the Next", which reads badly in French.

## Solution

One window whose two panes have the same structure and the same set of actions, driven by a menu bar, an icon toolbar, keyboard shortcuts and right-click menus that show those shortcuts. One pane is active at a time and the actions apply to it. Double-clicking a file transfers it to the other side; double-clicking a folder enters it. The look follows a light theme by default, with a dark theme and a "follow the system" choice in Settings, embedded icons, a status bar, a waiting page that is a clear card, and a restyled Compare view. The interface says "ZX Spectrum Next" (French: "du ZX Spectrum Next", "sur le ZX Spectrum Next"); the domain term **Next** stays unchanged in the code and the glossary.

## User Stories

1. As a user, I want a menu bar (File, Edit, Transfer, View, Help), so that every action is discoverable without hunting through a row of buttons.
2. As a user, I want the same actions on Local and on the ZX Spectrum Next (new folder, rename, delete, cut, copy, paste), so that I do not have to remember which side can do what.
3. As a user, I want the two panes to have the same layout (header, drive selector, Up button, address field, list, status line), so that rows and columns line up.
4. As a user, I want a drive selector on the Local pane, so that I can switch between drives as I do on the Next pane.
5. As a Windows user, I want the Local drive selector to list drive letters, so that I can reach C:, D: and removable drives.
6. As a Linux user, I want the Local drive selector to offer Home, `/` and the mount points under `/media`, `/mnt` and `/run/media/<user>`, so that I can reach a USB stick or SD card reader.
7. As a user, I want the mount list re-read each time I open the selector, so that a card I just plugged in appears.
8. As a user, I want free space shown on both panes, so that I know whether a transfer will fit.
9. As a user, I want a visible mark on the active pane, so that I know which pane a menu action or shortcut will hit.
10. As a user, I want clicking or tabbing into a pane to make it active, so that I never have to say which pane I mean.
11. As a user, I want F5 to transfer the selection to the other side, so that I can copy without reaching for the mouse.
12. As a user, I want "Send" and "Receive" menu entries that each fix their direction, so that I can use them whichever pane is active.
13. As a user, I want double-clicking a file to transfer it to the folder shown in the other pane, so that copying is one gesture.
14. As a user, I want double-clicking a folder to enter it, so that browsing stays natural.
15. As a user, I want Enter to open folders only and never transfer, so that a stray key press cannot start a transfer.
16. As a user, I want a right-click menu on a file, folder or the empty list area, showing the actions and their shortcuts, so that I learn the shortcuts while working.
17. As a user, I want right-clicking an unselected row to select it first, so that the menu acts on what I pointed at.
18. As a user, I want F2 to rename, Delete to delete, Ctrl+C/X/V to copy, cut and paste, and Ctrl+Shift+N for a new folder, in whichever pane is active, so that the shortcuts match my file explorer.
19. As a user, I want to rename a Local file or folder, so that I need not leave the application.
20. As a user, I want to create a Local folder, so that I can prepare a destination before sending.
21. As a user, I want to delete Local entries to the system trash after a confirmation, so that a mistake is recoverable.
22. As a user, I want a clear message when the trash is unavailable and the choice to delete permanently or cancel, so that nothing is lost silently.
23. As a user, I want deleting on the ZX Spectrum Next to stay permanent with its confirmation, and the confirmation to say that it is permanent, so that I know the difference between the two sides.
24. As a user, I want to cut, copy and paste inside the Local pane, so that I can reorganise Local folders as I do on the Next.
25. As a user, I want copying on one side and pasting on the other to transfer the entries, so that the clipboard works across panes.
26. As a user, I want pasting a cut selection onto the other side to be refused (Paste greyed), so that no "transfer then delete the source" can half-fail.
27. As a user, I want to drag Local entries onto a folder of the same Local pane to move them, and hold Shift to copy, so that Local behaves like the Next pane.
28. As a user, I want existing drag-and-drop between the panes and from the desktop to keep working.
29. As a user, I want a prompt when a send or receive would overwrite a name that already exists at the destination, so that a double-click cannot destroy a file.
30. As a user, I want the prompt to offer Overwrite, Skip and Cancel, with Cancel as the default button, so that the safe answer is the one Enter picks.
31. As a user, I want an "apply to all" box in that prompt, so that a large batch does not ask once per file.
32. As a user, I want folders merged into an existing folder to prompt only for the files that collide, so that I am not asked about the folder itself.
33. As a user, I want the copy, move and paste actions inside the Next to keep refusing to overwrite, as today.
34. As a user, I want a status bar showing the connection state (green dot and address), the "dot too old" warning, and the selection ("3 items, 1.2 MB"), so that the panes keep their height.
35. As a user, I want transfer progress and the Cancel button to stay visible during a transfer, so that I can stop it.
36. As a user, I want a waiting page that shows my Local IP addresses, the command `.sync5 -l` with a Copy button, and the config-file reminder in a centred card, so that connecting is easy.
37. As a user, I want the toolbar and address bar of the ZX Spectrum Next pane greyed (not hidden) while waiting, so that the two panes stay aligned.
38. As a user, I want a draggable divider between the panes and a bigger default window (1100x650, minimum 800x450), so that long names fit.
39. As a user, I want icons in the toolbar, the menus and the lists (system icons for Local files, an embedded set for the ZX Spectrum Next with ZX types such as `.nex`, `.tap`, `.sna`, `.bas`), so that I tell files apart at a glance.
40. As a user, I want alternating row colours in the lists, so that I can follow a row across a wide pane.
41. As a user, I want a light theme by default, so that the first impression is clean.
42. As a user, I want to choose Light, Dark or System in Settings, applied at once and remembered, so that the application fits my desktop.
43. As a user, I want the toolbar and menu icons to follow the theme, so that none becomes invisible on a dark background.
44. As a user, I want the Compare view to use the same style, icons and readable state colours in both themes, with its behaviour unchanged.
45. As a user, I want the menu entries that need a Session or a capability of the dot to be greyed with the same rules as today, so that nothing offers an action that cannot succeed.
46. As a user, I want menu entries to be greyed when nothing is selected or the pane is busy, so that I only see valid actions.
47. As a French-speaking user, I want every new label translated, with "ZX Spectrum Next" written in the grammatically correct form, so that the interface reads naturally.
48. As a maintainer, I want the third-party icon licence recorded in the notices file, so that the redistribution terms are met.
49. As a maintainer, I want Windows and Linux to behave the same except for the drive list and the trash, so that testing one covers the other.

## Implementation Decisions

- **Window structure.** The row of buttons is replaced by a menu bar, one icon toolbar and a status bar. A centre column between the panes carries the Send (→) and Receive (←) buttons. The two panes sit in a splitter.
- **Menus.** File: New folder, Rename, Delete, Settings, Quit. Edit: Copy, Cut, Paste, Select all. Transfer: Send, Receive, Compare, Disconnect. View: Show hidden files, Sort by, Refresh. Help: About. Each entry is one shared action object used by the menu, the toolbar, the context menu and the shortcut, so that enablement, label and shortcut are defined once.
- **Active pane.** The window tracks which pane last had focus and exposes it. All shared actions are enabled or greyed according to the active pane, its selection, the Session and the dot's capabilities. The active pane shows an accent border on its header and list.
- **Pane structure.** One pane layout serves both sides: header (title), drive selector with free space, Up button and address field, list, status line. The list columns stay Name, Size, Type (the protocol carries no modification time, so there is no Date column). Local gets a drive selector; the Next pane's drive selector is unchanged.
- **Local drive source.** A function returns the Local roots for a platform: drive letters on Windows; Home, `/` and the mount points of removable media on Linux. The platform and the mount sources are injectable so the function is testable on any machine. macOS has no dedicated handling.
- **Local file operations.** A module of Local operations offers: create folder, rename, delete (to trash, with a permanent fallback decided by the caller), move and copy (merging folders, never silently overwriting), and name validation shared with the Next side (plain names only). The trash is an injectable collaborator. A failure reports a reason per entry, in the same result shape as the Next operations, so the window reports both the same way.
- **Delete confirmations.** Same dialog on both sides, with the default button on Cancel. The Local wording says "to the trash"; the Next wording says "permanently". When the trash fails, a second dialog offers permanent deletion.
- **Clipboard.** One window-level clipboard holding the side, the folder, the entries and the mode (copy or cut). Paste decides: same side = copy or move inside that side; opposite side with mode copy = transfer; opposite side with mode cut = Paste greyed. Cutting then pasting inside one side clears the clipboard after a successful paste, as the Next side does today.
- **Double-click and Enter.** Double-click on a folder enters it; on a file it starts a transfer of that file to the folder shown in the other pane (a Send from Local, a Receive from the Next). Enter and the activation key only enter folders. F5 transfers the whole selection the same way. Double-click on a file does nothing when no Session exists.
- **Overwrite policy.** Before a send or a receive, the destination folder is listed and names that exist (compared by the destination side's own spelling rules, case-insensitive on the Next) are collected. The window shows one prompt with Overwrite, Skip and Cancel and an "apply to all" box; Skip leaves the colliding entries out of the batch, Overwrite keeps them. Folders merge; only colliding files prompt. The prompt is behind the same injectable dialog collaborator as the other prompts. Copy, move and paste inside the Next keep their existing refusal to overwrite. The listing adds one round trip on the Next side.
- **Drag and drop.** Dropping Local entries on a folder row of the same Local pane moves them; with Shift it copies. Existing drops keep their meaning: files from the desktop onto the Next pane send, Next entries onto the Local pane receive, Next entries onto a Next folder move.
- **Status bar and waiting page.** The connection state, the dot version notice and the selection summary move to the status bar. The waiting page is a centred card with an icon, the Local addresses, the command with a Copy button and the config reminder. The Next pane keeps its toolbar, greyed.
- **Theme.** A new setting holds Light, Dark or System, default Light, validated and persisted like the existing settings. Two palettes and one stylesheet are applied application-wide; changing the setting in the Settings dialog re-applies them at once. Colours for Compare states and the active-pane accent are defined per theme.
- **Icons.** An embedded SVG set (Lucide, ISC licence) provides toolbar, menu, status and ZX file-type icons, tinted to the current theme. Local file rows use the system icon provider. The licence is added to the third-party notices.
- **Compare view.** Restyled with the same toolbar, icons and state colours; its signals and behaviour are untouched.
- **Window geometry.** Default 1100x650, minimum 800x450, splitter position and geometry persisted as today.
- **Wording.** Every interface string that said "Next" now says "ZX Spectrum Next"; "on Next" suffixes disappear because both sides carry the actions. The French catalogue is updated with it. The glossary term **Next** and the code identifiers do not change.
- **Order of work.** (1) structure: identical panes, status bar, splitter, waiting page; (2) symmetric Local actions; (3) menu bar, shortcuts, context menus, active pane, double-click, clipboard; (4) overwrite prompts; (5) themes, icons, Compare restyle.

## Testing Decisions

- A good test drives external behaviour only: it triggers an action the way a user would (a menu action, a shortcut, a context-menu entry, a double-click, a drop), then checks what the panes list, what the fake Next holds, what is on the Local disk and what the prompts were asked. It never reads private widgets or layout internals.
- **Seam 1, the main window offscreen** with the fake Next and the scripted prompts, driving the shared actions. Covers: action enablement per active pane, selection, Session and capabilities; double-click on file and folder; Enter on a folder and on a file; F5 in both directions; cross-pane copy and paste; refused cross-pane cut; same-side cut and paste; Local rename, new folder, delete to trash and the trash-failure path; Local drag move and Shift copy; the overwrite prompt in all three answers, "apply to all", folder merge and Cancel default; status bar contents; waiting page content and greyed toolbar; the drive selector on both panes; the theme change taking effect from Settings. Prior art: the existing window test files.
- **Seam 2, Local operations** tested on a temporary directory with an injectable trash and platform: rename, mkdir, move, copy, merge, collision refusal, unsafe names, per-entry failures, the Local roots function for Windows and Linux fixtures. Prior art: the transfer tests and the Local pane tests.
- **Seam 3, settings**: the theme value round-trips, rejects bad values and defaults to Light. Prior art: the settings tests.
- Appearance is not tested by rendering. Tests check that every icon name used by the interface exists in the embedded set, that both palettes define the same colour roles, and that every new string has a French translation. Prior art: the translation test.
- Ticket boundaries are test boundaries: each ticket ends with its seam-1 tests green and only the tests touching its changes run during development.

## Out of Scope

- A Date column (the protocol does not provide a modification time).
- Cut across sides and move by drag between the panes.
- A trash on the ZX Spectrum Next side.
- Changes to the protocol, the dot, Compare's logic or the transfer engine other than the overwrite prompt.
- Dedicated macOS support, tested or packaged.
- Settings for custom shortcuts or a user-defined theme.
- Changing the glossary term **Next** or any code identifier.

## Further Notes

- Today a send overwrites silently and a receive overwrites silently; the overwrite prompt is a behaviour change for both, justified by the double-click making accidental transfers easy.
- The "dot too old" capability gating stays as it is and keeps greying the same entries, now in menus and toolbar as well as buttons.
- `improvements.md` already lists UI gaps (no indication while a listing runs, closing the window while a worker runs); this spec does not fix them but must not make them worse.
- The README's feature description and screenshots, if any, need updating once the work lands.
