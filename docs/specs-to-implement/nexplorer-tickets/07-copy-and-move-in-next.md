Label: ready-for-agent

# 07: Copy and Move inside the Next

**What to build:** The user copies entries inside the Next without a round trip through the PC, and Moves entries with Ctrl+X then Ctrl+V or by dragging them onto a Next folder. A Move on the same drive is an instant rename. A Move across drives copies on the Next, checks the size, and only then deletes the source. Any failure keeps the source and says so, so the user can retry. Moving between Local and Next is out of scope.

**Blocked by:** 06 (Create folder, rename, delete)

**Status:** ready-for-agent

- [x] Copy inside the Next duplicates entries without transferring data through Local
- [x] Ctrl+X marks entries, Ctrl+V performs the Move; dragging onto a Next folder performs the same Move
- [x] Same-drive Move is a rename and leaves no copy of the source
- [x] Cross-drive Move copies, checks size, then deletes the source
- [x] A failing cross-drive Move (fake Next failure injected) keeps the source and reports the failure
- [x] Tests cover same-drive and cross-drive Move, including the failure that must keep the source
