Label: ready-for-agent

# 08: Settings

**What to build:** The app opens as the user left it. One JSON file in the standard user configuration folder (XDG location or platform equivalent, found without an extra dependency) stores the last Local and Next folders, window geometry, language, hidden-files choice, CRC choice and each pane's sort order. A small settings dialog (a few checkboxes and a language choice, not tabbed) edits it. The language choice selects a JSON translation catalogue; English is the fallback.

**Blocked by:** 03 (Browse Local and Next)

**Status:** ready-for-agent

- [ ] Restarting the app restores last folders, window geometry, sort order and the checkbox choices
- [ ] Settings live in a single JSON file in the user config folder and nowhere else
- [ ] The settings dialog exposes hidden files, CRC after upload and language
- [ ] Translation catalogues are JSON files, one per language; a missing key falls back to the English text
- [ ] Interface uses system theme, no animation, no custom styling
