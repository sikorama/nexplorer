Label: ready-for-agent

# 11: Compare: expand on demand and Scan all

**What to build:** Compare lists one level at a time. Subfolders appear as not scanned and expand on demand, so a large tree does not take minutes before the user can act. An optional Scan all compares a whole tree, with progress and Cancel. A folder that has not been scanned is never shown as identical.

**Blocked by:** 10 (Compare: one level and Apply)

**Status:** ready-for-agent

- [ ] Folders present on either side show as not scanned until expanded
- [ ] Expanding a folder lists its next level with the same states and proposals
- [ ] Scan all expands the whole tree with progress; Cancel stops it and leaves unreached folders not scanned
- [ ] A not scanned folder is never displayed as identical
- [ ] Tests cover not scanned, expansion and Scan all at the fake Next seam
