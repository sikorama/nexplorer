Label: ready-for-agent

# 02: Menu bar, shared actions, active pane, shortcuts, context menus

**What to build:** The row of buttons is replaced by a menu bar: File (New folder, Rename, Delete, Settings, Quit), Edit (Copy, Cut, Paste, Select all), Transfer (Send, Receive, Compare, Disconnect), View (Show hidden files, Sort by, Refresh), Help (About). Each action is defined once and used by the menu, the shortcut and the right-click menu, which shows the shortcuts. One pane is active (the one that last had focus), marked by an accent border on its header and list, and the actions apply to it. Shortcuts: F2 rename, Delete delete, Ctrl+C/X/V, Ctrl+Shift+N new folder. Right-clicking an unselected row selects it first; a right-click on the empty area offers the actions that need no selection. The existing ZX Spectrum Next actions (new folder, rename, delete, copy, cut, paste) move onto this mechanism with unchanged behaviour. Entries are greyed under the same rules as today (no Session, dot capability missing, busy, no selection).

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] The five menus exist with the entries above, labels and shortcuts shown
- [ ] Focusing a pane makes it active and visibly marked; actions follow the active pane
- [ ] Each shortcut triggers the action on the active pane (ZX Spectrum Next side in this ticket)
- [ ] Context menu on a row, on an unselected row and on empty space offers the right entries
- [ ] Greying follows Session, capabilities, busy state and selection exactly as the former buttons did
- [ ] The former action buttons are gone; Settings and Quit remain reachable
- [ ] Tests (window seam) trigger each action through its menu entry and shortcut and check enablement
