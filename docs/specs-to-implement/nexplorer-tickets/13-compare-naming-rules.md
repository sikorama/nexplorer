Label: ready-for-agent

# 13: Compare: naming rules

**What to build:** Compare respects the Next's file system rules and never hides exclusions silently. Names are compared without regard to case. Two Local files that differ only by case are a conflict and are not transferred. A path over 254 bytes or containing a character the Next's file system refuses is shown as invalid (error with an icon) and excluded from transfer. Hidden files and folders such as `.git` are shown or hidden by the hidden-files setting. An optional `.nexplorerignore` at the compared folder's root (glob patterns, one per line, `#` comments) marks matching rows as ignored: greyed, with the word "ignored", and not offered for transfer.

**Blocked by:** 10 (Compare: one level and Apply), 08 (Settings)

**Status:** ready-for-agent

- [ ] `Foo.TXT` on Local and `foo.txt` on the Next match as the same name
- [ ] Two Local entries differing only by case appear as conflict and are never transferred
- [ ] Over-long or FAT-forbidden paths appear as invalid with an icon and are excluded from Apply
- [ ] The hidden-files setting shows or hides hidden entries; none is dropped silently
- [ ] `.nexplorerignore` patterns grey matching rows with "ignored" and exclude them from transfer
- [ ] Tests cover case conflicts, invalid paths and the ignore file with a real temporary Local folder
