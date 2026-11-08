Label: ready-for-agent

# 10: Compare: one level and Apply

**What to build:** A Compare button replaces the two panes with a list of Differences between the Local folder and the Next folder the panes showed, so the user does not choose them twice. One level is listed. Each row has one state among only on Local, only on the Next, different and identical; size is compared first, so files of different size are different without being read. Rows propose a direction (Local to Next for only-Local, Next to Local for only-Next); different rows start unchecked with no direction. The user can reverse a row's direction, uncheck or check it, transfer a single file from the list, or Apply all checked rows sequentially. Compare never deletes on either side.

**Blocked by:** 04 (Send and receive)

**Status:** ready-for-agent

- [ ] Compare replaces the panes and keeps the folders previously shown
- [ ] Rows show only on Local, only on the Next, different or identical based on name and size
- [ ] Direction proposals are as specified; different rows are unchecked with no direction
- [ ] A row's direction can be reversed and the row checked or unchecked
- [ ] A single row can be transferred on its own; Apply transfers every checked row sequentially
- [ ] Files existing on one side only are never deleted from the other side
- [ ] Returning from Compare restores the two panes
- [ ] Tests use a real temporary Local folder and the fake Next; offscreen smoke test covers Compare activation
