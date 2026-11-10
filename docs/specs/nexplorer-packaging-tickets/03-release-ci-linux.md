# 03: Release CI workflow, Linux job

**What to build:** Publishing a GitHub Release builds the AppImage on an `ubuntu-22.04` runner, runs the smoke test, and attaches the file to that release. The workflow can also be started by hand (`workflow_dispatch`); then it produces a downloadable workflow artifact and attaches nothing. Plain pushes and tag pushes do not trigger it. The release tag `vX.Y.Z` must equal the version in the project metadata, otherwise the workflow fails before building; the comparison is a small pure function, called by the workflow.

**Blocked by:** 02 (build script and smoke test).

**Status:** ready-for-agent

- [ ] The pure tag/version function: matching tag and version passes; another version, a missing `v` prefix or a malformed tag fails with a clear message; pytest tests (seam 3 of the spec).
- [ ] The workflow runs on "release published" and on manual dispatch only.
- [ ] On a release, the AppImage is attached to it; on a manual dispatch, it is a downloadable artifact.
- [ ] A failing smoke test stops the job before anything is attached.
- [ ] Checked on GitHub with a manual dispatch; the artifact starts on the owner's Linux machine.
