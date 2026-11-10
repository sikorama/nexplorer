Label: ready-for-agent

# nexplorer: send sync-wrap.bas to the Next

## Problem Statement

To connect, the user must type `.sync5 -l` on the Next each time. The repository ships a NextBASIC program, `sync-wrap.bas`, that does it from the Next's file browser, but the user has to find it in the repository, locate it on their PC and copy it to the Next by hand. Packaged builds (zip, AppImage) do not even contain it. The waiting card now advises running from the D: drive with `sync-wrap.bas`, but gives the user no way to get the program onto the Next.

## Solution

Once a Next is connected, the Transfer menu offers "Send sync-wrap.bas to the ZX Spectrum Next". It sends the program, byte for byte, into the Next folder shown, like any other Send. If a file of that name is already there, the usual Overwrite / Skip / Cancel question is asked. The program ships with every build and is found from the sources too. If it cannot be found, the entry is greyed.

The folder holding the program, its text description and its README is renamed from `examples/` to `sync-wrap/`, since it will hold nothing else. Both READMEs (the global one and the folder's) describe the new option and the new layout.

## User Stories

1. As a Next owner, I want a menu entry that sends `sync-wrap.bas` to the Next, so that I do not have to find the file and copy it by hand.
2. As a Next owner, I want the program to land in the Next folder I am looking at, so that I choose where it lives (it saves its `syncwrap.cfg` beside itself).
3. As a Next owner, I want the entry greyed while no Next is connected, so that I cannot start a send that has nowhere to go.
4. As a Next owner, I want the entry greyed while another operation is running, like Send and Receive, so that two operations never overlap.
5. As a Next owner who already has `sync-wrap.bas` on the Next, I want to be asked Overwrite, Skip or Cancel (Cancel by default), so that I do not lose a copy I edited.
6. As a Next owner, I want the program sent unchanged (it is a PLUS3DOS binary with a header, not text), so that it runs on the Next.
7. As a Next owner, I want the progress bar, the Cancel button and the summary of any transfer, so that this send behaves like the others.
8. As a Next owner, I want the CRC check after upload to follow my setting, so that this send respects my choice.
9. As a Windows or Linux user of a packaged build, I want the program inside the zip or the AppImage, so that the entry works without the source tree.
10. As a user running from the sources (`make run`, `pip install -e`), I want the entry to work from the repository's `sync-wrap/` folder, so that development behaves like the packaged build.
11. As a user whose installation lacks the file, I want the entry greyed rather than failing at click time, so that I am not shown an error for something I cannot fix.
12. As a French-speaking user, I want the entry translated like the rest of the interface, so that the language is consistent.
13. As a reader of the README, I want it to explain the option and the D: advice, so that I know how to get `sync-wrap.bas` onto the Next.
14. As a reader of the `sync-wrap/` folder, I want its README to say what the program does, that the `.txt` is information only (it cannot run on the Next), and that the menu entry sends the `.bas`.
15. As the owner, I want a single copy of the `.bas` in the repository, so that the packaged and source versions cannot drift.
16. As the owner, I want the build to fail if the program is missing from the bundle, so that a release never ships without it.

## Implementation Decisions

- A new Transfer menu entry, "Send sync-wrap.bas to the ZX Spectrum Next", defined once as a shared action with the same enablement rules as Send (a Next connected, no operation running), plus "the bundled file exists". It is not in the toolbar nor in the context menus.
- It sends into the Next folder shown, through the same checked-send path as Send (collision check, Overwrite / Skip / Cancel dialog with Cancel as default, progress, summary, CRC after upload per setting). No fixed destination and no drive forced; nothing is imposed on C:.
- A small function locates the bundled program: inside a PyInstaller bundle it looks in the bundle's data folder, otherwise at the repository root. It returns nothing when the file is absent, which greys the entry. Packaged builds and source runs share one copy.
- The program is stored in the repository once, in the `sync-wrap/` folder at the root (renamed from `examples/`), next to its text description and its README. The `.txt` is never sent.
- The PyInstaller spec adds the `sync-wrap/` folder to the bundle data. The build scripts (or the smoke test) check the program is present in the bundle and fail otherwise.
- The waiting card keeps its advice to run from the D: drive with `sync-wrap.bas`, but its text (and French translation) no longer says "see the examples folder": it points to the `sync-wrap` folder. It does not mention the menu entry, which exists only once connected.
- The French catalogue gets the entry's label. The label uses the file name and introduces no new term, so `GLOSSARY.md` is unchanged. No ADR.
- The global README and the folder's README are rewritten to the present state: the folder's README no longer says the programs are "not included yet"; the global README's link to the examples folder points to the new one and documents the option and the D: advice.
- Other `.md` files that mention `examples/` must be checked and updated (the packaging docs, ticket 15's notes are history and stay).

## Testing Decisions

- A good test drives the window and checks what the user sees (menu entries and their state, files that arrive on the fake Next, dialogs asked), never private methods.
- Main seam: `MainWindow` against the fake Next, as in the existing window tests (menu entries and `trigger_menu` in the actions tests, collision dialogs in the overwrite tests). Cases: entry present and greyed while waiting; enabled once connected; greyed while an operation runs; the file arrives in the folder shown, byte-identical to the shipped one; an existing file triggers the Overwrite / Skip / Cancel question (scripted prompt, as in the overwrite tests) and Cancel leaves it intact; entry greyed when the file is not found. The existing test of the Transfer menu entries is updated.
- Second seam, very small: the locating function, tested alone with a fake bundle folder (bundled run) and the repository layout (source run), and its "absent" result.
- The packaged build is covered by the CI smoke test and the bundle check, not by the unit tests.
- No test touches a real Next. A manual try on the real Next goes to D: only, never C:.

## Out of Scope

- Sending any other file, or the `.txt`.
- Choosing a fixed destination such as the root of D:, or forcing a drive.
- Embedding the program in a Python wheel or a PyPI release.
- Mentioning the option on the waiting card.
- Editing or generating `sync-wrap.bas` (it is supplied by the owner).
- A "send sync-wrap.bas on first connection" prompt.

## Further Notes

- The file is a PLUS3DOS binary: it must go through the normal byte-exact upload, never be re-encoded or read as text.
- The program reads `c:/sys/config/nextsync.cfg` for the server address and offers a Drive option (C:, D:, none) for the launch; the advice to start from D: comes from `improvements.md` (the dot reports D: only when launched from it).
- Implementation order: tests first (`tdd`), then the menu entry, then the folder rename and README changes, then the packaging change.
