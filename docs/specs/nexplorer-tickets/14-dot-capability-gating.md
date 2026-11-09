Label: ready-for-agent

# 14: Dot capability gating

**What to build:** The Session reads the version announced by the dot and the interface greys out actions the dot does not support (rename, copy on the Next, CRC, free space, according to the table in `docs/protocol.md`). A short line states the minimum `.sync5` version needed and tells the user to update it. The app never updates the dot or installs anything on the Next.

**Blocked by:** 07 (Copy and Move inside the Next), 12 (Compare: Verify (CRC))

**Status:** ready-for-agent

- [ ] With a fake Next announcing an old version, unsupported actions are greyed out in the interface
- [ ] A short message gives the minimum `.sync5` version and asks the user to update the dot
- [ ] With a current version, every action is available
- [ ] Nothing is ever sent to the Next to update or install the dot
- [ ] Tests cover version gating at the Session/fake Next seam
