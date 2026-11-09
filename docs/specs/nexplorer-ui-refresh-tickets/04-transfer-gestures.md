Label: ready-for-agent

# 04: Transfer gestures

**What to build:** Double-clicking a file transfers it to the folder shown in the other pane (a Send from Local, a Receive from the ZX Spectrum Next); double-clicking a folder enters it. Enter and the activation key only enter folders, never transfer. F5 transfers the whole selection of the active pane to the other side. A centre column between the panes carries Send (→) and Receive (←) buttons, and the Transfer menu entries Send and Receive each fix their direction whichever pane is active. Copy on one side then Paste on the other transfers the entries; Cut on one side then Paste on the other is refused (Paste greyed). Without a Session, double-click on a file does nothing.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] Double-click on a file starts a transfer in the right direction; on a folder it enters it
- [ ] Enter on a folder enters it; Enter on a file transfers nothing
- [ ] F5 and the centre buttons transfer the selection; the menu entries fix their direction
- [ ] Cross-pane Copy then Paste transfers; cross-pane Cut leaves Paste greyed; same-side Cut and Copy keep working
- [ ] No Session: double-click and F5 on a file do nothing
- [ ] Tests (window seam) cover each gesture in both directions against the fake ZX Spectrum Next
