Label: ready-for-agent

# 04: Send and receive

**What to build:** The user selects Local entries and sends them to the Next folder shown, or selects Next entries and receives them into the Local folder shown. Folders transfer recursively. A thin non-modal progress bar at the bottom of the window shows the current file, the percentage and a Cancel button. Only one modifying operation runs at a time, the other modifying actions are greyed while it runs, and Local navigation stays free. After every upload the size is checked by listing the folder, so a truncated upload is noticed.

**Blocked by:** 03 (Browse Local and Next)

**Status:** ready-for-agent

- [ ] Selected Local files and folders are sent to the shown Next folder; the fake Next file system holds them afterwards
- [ ] Selected Next files and folders are received into the shown Local folder
- [ ] Progress bar shows current file, percentage and Cancel; Cancel stops the operation
- [ ] While an operation runs, modifying actions are greyed and Local navigation still works
- [ ] A truncated upload is detected by the post-upload size check and reported
- [ ] The app never deletes anything on Local
- [ ] Tests cover put, get and the size check at the Session/fake Next seam
