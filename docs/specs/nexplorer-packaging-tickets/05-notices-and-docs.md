# 05: Third-party notices and user documentation

**What to build:** The distributed archives carry correct legal notices, and users find the downloads. In the notices file, the placeholder copyright line of ZX-Next-Unite is replaced by the real one, taken from that project's licence file, and a statement is added that Qt/PySide6 is used under the LGPL and shipped as replaceable libraries. The README gets a "Download" section above "Run from source": the Releases page, the two files, the SmartScreen warning on first launch of an unsigned program, the Windows firewall prompt for port 2048, and the Linux requirements (make the AppImage executable). A short packaging README explains how to build locally and how to publish a release, including the owner's pre-release check (manual dispatch, then try the zip on Windows and the AppImage on Linux). Present tense, no history.

**Blocked by:** 04 (file names and procedure must be final).

**Status:** ready-for-agent

- [ ] No placeholder remains in the notices file; the copyright line matches the ZX-Next-Unite licence file.
- [ ] The LGPL statement for Qt/PySide6 is present.
- [ ] The README "Download" section lists both files and the three notes above, and its names match the ones the workflow produces.
- [ ] The packaging README describes the local build, the release procedure and the manual pre-release check.
- [ ] Other `.md` files made obsolete by the packaging are reported (the Further Notes of the spec expect none in the glossary).
