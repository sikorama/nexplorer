Label: ready-for-agent

# 02: Tracer: connect and waiting screen

**What to build:** The thinnest complete path from launch to an open Session. Project scaffold (MIT licence, Python 3.10+, PySide6 as the only runtime dependency, pytest for development, launchable from a source checkout with one command), the single translation function keyed by the English text, a fake Next (in-memory file system served over a local socket speaking the documented protocol), and the Qt-free protocol module with Listener and Session (handshake and reported dot version). The window shows Local left and Next right in the system theme. Until a Next connects, the Next pane shows the Local IP address of each network interface, the command `.sync5 -l` and the reminder about the Local address in `c:/sys/config/nextsync.cfg`. Once connected it shows a coloured status dot and the Next's address; when the Session ends it returns to the waiting screen. The Listener starts at launch on port 2048.

**Blocked by:** 01 (Protocol reference)

**Status:** ready-for-agent

- [ ] App launches from a source checkout with one command and listens on port 2048 immediately
- [ ] Waiting screen shows each interface's Local IP, `.sync5 -l` and the `nextsync.cfg` reminder
- [ ] A fake Next connecting opens a Session; the pane shows a green dot and the Next's address; the Session reports the dot version
- [ ] Ending the Session returns the pane to the waiting screen
- [ ] Only one Session at a time is accepted
- [ ] Every displayed string goes through the translation function
- [ ] Session module has no Qt dependency; Session calls reach the UI through a thin off-thread layer with signals
- [ ] Offscreen smoke test: the window opens and the waiting screen shows the command
- [ ] Tests drive Session against the fake Next, asserting on returned values and fake file system contents only
