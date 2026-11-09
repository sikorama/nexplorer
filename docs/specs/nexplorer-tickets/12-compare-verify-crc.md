Label: ready-for-agent

# 12: Compare: Verify (CRC)

**What to build:** Files of the same size are shown as unverified until the user chooses Verify, which asks the Next for the CRC-32 of those files and compares it with the Local CRC. Verified files become identical or different. CRC is requested only on demand and only for same-size files.

**Blocked by:** 10 (Compare: one level and Apply)

**Status:** ready-for-agent

- [ ] Same-size files show as unverified before Verify
- [ ] Verify requests the Next's CRC-32 only for same-size files and updates each row to identical or different
- [ ] No CRC is requested for files of different size or before the user asks
- [ ] Tests cover size then CRC at the fake Next seam
