# 01: Port-in-use error shown in a dialog

**What to build:** When nexplorer cannot listen on port 2048 (another instance, another program), the user sees a message box with the text "Cannot listen on port 2048" and the system reason, translated (English and French) like the rest of the interface. The same message is still written to standard error and the exit code stays non-zero. This matters because the packaged builds have no console, so today the user would see nothing happen.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] With the port occupied, starting the application shows the dialog with the port number and the reason; the message is also on standard error; the exit code is non-zero.
- [ ] The dialog text exists in both locale files, and the French one is translated.
- [ ] The dialog is injectable (a "show error" function), so the test opens no real dialog; same pattern as the window tests' scripted prompts.
- [ ] pytest test on the offscreen platform covering the above (seam 2 of the spec).
- [ ] The normal start path (port free) is unchanged.
