Label: ready-for-agent

# 03: Browse Local and Next

**What to build:** Both panes become usable for browsing. The Local pane is a normal file tree with name, size and type. The Next pane shows the Next's folders and files, lets the user switch drive, shows the free space of the drive, and supports going up, entering folders and typing a path. Both panes sort by name, size and type and support multi-selection. Listings run off the UI thread so the window never freezes.

**Blocked by:** 02 (Tracer: connect and waiting screen)

**Status:** ready-for-agent

- [ ] Local pane lists name, size and type and navigates up, into folders and by typed path
- [ ] Next pane lists the folders and files of the current Next folder and navigates up, into folders and by typed path
- [ ] The user can switch between drives on the Next and sees the free space of the current drive
- [ ] Each pane sorts by name, size and type
- [ ] Several entries can be selected at once in each pane
- [ ] Tests at the Session/fake Next seam cover listing, drives and free space
