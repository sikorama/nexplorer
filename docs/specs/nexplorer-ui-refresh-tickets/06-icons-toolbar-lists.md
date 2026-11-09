Label: ready-for-agent

# 06: Icons, toolbar, list styling

**What to build:** An embedded SVG icon set (Lucide, ISC licence, recorded in `THIRD_PARTY_NOTICES.md`) gives the interface its icons: a toolbar under the menu bar for the frequent actions, icons in the menus, and icons in the lists. Local rows use the system file icons; ZX Spectrum Next rows use the embedded set by type, including ZX types (`.nex`, `.tap`, `.sna`, `.bas`...). Lists get alternating row colours. Icons are tinted to follow the current colours so they stay visible on any background.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] The toolbar offers the frequent actions, bound to the shared actions, with the same enablement as the menus
- [ ] Menus and lists show icons; folders, generic files and the listed ZX types have distinct icons on the ZX Spectrum Next side
- [ ] Every icon name used by the interface exists in the embedded set (test)
- [ ] The Lucide licence is in the third-party notices
- [ ] Alternating rows are enabled in both lists
