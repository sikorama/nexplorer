Label: ready-for-agent

# 03: Symmetric actions on Local

**What to build:** Local offers the same actions as the ZX Spectrum Next pane: new folder, rename, delete, cut, copy and paste inside the Local pane, through the shared actions of ticket 02. Delete sends entries to the system trash after a confirmation (default button Cancel, wording "to the trash"); when the trash is unavailable a second dialog offers permanent deletion or Cancel. The ZX Spectrum Next confirmation now says the deletion is permanent. Dragging Local entries onto a folder of the same Local pane moves them, with Shift copies them. Moves and copies merge folders and never silently overwrite. Names must be plain names, as on the Next side.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Local operations (create folder, rename, trash delete, move, copy, merge, collision refusal, unsafe names) work and report per-entry failures in the same result shape as the Next operations
- [ ] The trash is an injectable collaborator; its failure triggers the permanent-delete choice, and Cancel leaves everything in place
- [ ] Menu, shortcut and context menu drive these actions on the Local pane
- [ ] Cut then paste inside Local moves and clears the clipboard; copy then paste duplicates
- [ ] Drag onto a Local folder moves, Shift-drag copies; existing drops (desktop to ZX Spectrum Next, ZX Spectrum Next to Local, move inside the ZX Spectrum Next) still work
- [ ] Tests: Local operations on a temporary directory with injected trash; window seam for the actions and the drag
