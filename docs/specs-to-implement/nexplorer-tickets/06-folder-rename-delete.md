Label: ready-for-agent

# 06: Create folder, rename, delete

**What to build:** On the Next pane the user can create a folder, rename a file or folder, and delete files and folders, including non-empty folders. Every delete asks for confirmation naming the number of items and the first name; the Next has no recycle bin. Nothing is ever deleted on Local.

**Blocked by:** 04 (Send and receive)

**Status:** ready-for-agent

- [x] Creating a folder on the Next shows it in the listing
- [x] Renaming a file or folder on the Next updates the listing
- [x] Deleting selected entries, including non-empty folders, removes them from the fake Next after confirmation
- [x] The confirmation names the item count and the first item's name; declining deletes nothing
- [x] Operations use the shared one-at-a-time progress mechanism
- [x] Tests cover make folder, rename and recursive remove at the Session/fake Next seam
