Label: ready-for-agent

# 07: Light and dark themes, Compare restyle

**What to build:** A Theme setting (Light, Dark, System; default Light) in the Settings dialog is applied at once application-wide and remembered in the settings file. Two palettes and one stylesheet cover panes, menus, toolbar, status bar, waiting card, dialogs and the active-pane accent. Icons are tinted to the theme. The Compare view takes the same style, icons and per-theme state colours (only on Local, only on the ZX Spectrum Next, different, identical, unverified) readable in both themes; its behaviour and signals are unchanged.

**Blocked by:** 06

**Status:** ready-for-agent

- [ ] The setting round-trips, rejects invalid values and defaults to Light
- [ ] Choosing a theme in Settings re-styles the open window immediately; System follows the desktop
- [ ] Both palettes define the same colour roles (test)
- [ ] Compare shows the new style in both themes and behaves exactly as before (existing Compare tests pass unchanged)
- [ ] Every new string has a French translation (test)
