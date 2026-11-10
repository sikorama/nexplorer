# 04: Windows portable zip and CI job

**What to build:** A PowerShell script that, run on Windows, produces `nexplorer-vX.Y.Z-windows-x64.zip` containing one root folder `nexplorer-vX.Y.Z/` with `nexplorer.exe` (windowed, no console), its libraries, `LICENSE`, `THIRD_PARTY_NOTICES.md` and `README.md`. It reuses the spec file, the icon (`.ico`) and the smoke-test script from ticket 02. The workflow from ticket 03 gains a Windows job (x64 runner) that builds the zip, runs the smoke test on the unpacked program and attaches the zip to the release (or uploads an artifact on manual dispatch). This cannot be run on Linux; it is verified by CI and then by the owner by hand.

**Blocked by:** 02, 03.

**Status:** ready-for-agent

- [ ] The script produces the zip with the agreed name and single root folder.
- [ ] The Windows job runs the smoke test on the unpacked zip; a failure blocks publication.
- [ ] Both jobs attach their file to the same release; a failure of one does not publish the other half-way without the owner noticing (state the chosen behaviour in the ticket report).
- [ ] Checked with a manual dispatch on GitHub; the owner runs the zip on a real Windows machine or VM (window opens, settings saved in the profile, firewall prompt seen).
