Label: ready-for-agent

# 05: Overwrite prompts for send and receive

**What to build:** Sending or receiving, by button, menu, F5, double-click or drag, no longer overwrites silently. Before the batch the destination folder is listed and names that already exist are collected (compared by the destination side's own spelling rules, case-insensitive on the ZX Spectrum Next). One prompt offers Overwrite, Skip and Cancel, with Cancel as the default button and an "apply to all" box. Skip leaves the colliding entries out; Overwrite keeps them; Cancel stops the whole batch. Folders merge, and only colliding files prompt. Copy, move and paste inside the ZX Spectrum Next keep their existing refusal to overwrite. The prompt goes through the same injectable dialog collaborator as the other prompts.

**Blocked by:** None (can start immediately; best done after 04, whose double-click makes it matter)

**Status:** ready-for-agent

- [ ] A send onto an existing name and a receive onto an existing name each raise the prompt; no collision means no prompt and no behaviour change
- [ ] Overwrite, Skip and Cancel each do what they say; Cancel is the default button
- [ ] "Apply to all" answers the remaining collisions of the batch
- [ ] A folder merging into an existing folder prompts only for colliding files
- [ ] Copy, move and paste inside the ZX Spectrum Next still refuse to overwrite
- [ ] Tests (window seam, scripted prompts) cover the three answers, apply-to-all, folder merge and a failing destination listing (the batch is refused with a message, never run without the check)
