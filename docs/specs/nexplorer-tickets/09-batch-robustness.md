Label: ready-for-agent

# 09: Batch robustness

**What to build:** A batch continues after a failed file and ends with a summary of failures. A dropped Session stops the operation, leaves untransferred items as they were, lists partially written Next files by name and size, and returns the Next pane to the waiting screen. Nothing is deleted automatically after a failure. A setting, off by default, adds a CRC-32 check after each upload.

**Blocked by:** 04 (Send and receive), 08 (Settings)

**Status:** ready-for-agent

- [ ] A failing file does not abort the batch; a final summary lists every failure
- [ ] A Session dropped mid-batch stops the operation and the summary lists partial files with name and size
- [ ] The Next pane returns to the waiting screen after a dropped Session
- [ ] No partial file is deleted automatically
- [ ] With the CRC setting on, each upload is verified by CRC-32 and a mismatch is reported; off by default
- [ ] Tests cover dropped Session, partial files and CRC at the Session/fake Next seam
