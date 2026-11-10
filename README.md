# nexplorer

A small desktop file manager for a ZX Spectrum Next. One window, two panes: **Local** (your PC) on the left, **Next** (the Next's SD card) on the right. It talks to the Next over Wi-Fi through the existing dot command `.sync5`, which is used unchanged.

Features:

- Browse both sides. The pane that last had the focus (accent border) is the one the menus, shortcuts and context menus act on.
- Create folders, rename and delete on both sides. On Local, delete goes to the trash, and permanent deletion is offered when the trash cannot take an entry. The Next has no trash: its deletions are confirmed and permanent.
- Cut, copy and paste (Ctrl+X, Ctrl+C, Ctrl+V) inside a pane. Copied entries can also be pasted into the other pane, which sends or receives them. Cut is a mark that becomes a move on paste, within its own pane. Drag and drop moves entries inside a pane (Shift: copies) and transfers them between panes.
- Transfer the selection to the other side with a double-click, **F5**, the buttons between the panes or the Transfer menu. When a name already exists at the destination, nexplorer asks: overwrite, skip or cancel, optionally for all.
- Other shortcuts: Ctrl+A select all, Ctrl+R refresh, Ctrl+Shift+N new folder, Del delete, Ctrl+Q quit.
- Compare one Local folder with one Next folder.
- Themes **Light**, **Dark** and **System** (follows the desktop), and the interface language, in Settings.

## Download

Get the latest files from the [Releases page](../../releases/latest) (`X.Y.Z` is the version). No Python is needed.

| System | File |
| --- | --- |
| Windows (x64) | `nexplorer-vX.Y.Z-windows-x64.zip` |
| Linux (x86_64) | `nexplorer-vX.Y.Z-linux-x86_64.AppImage` |

**Windows.** Unpack the zip anywhere and run `nexplorer.exe` from the `nexplorer-vX.Y.Z` folder.

- The program is not signed, so SmartScreen shows "Windows protected your PC" at the first launch. Click **More info**, then **Run anyway**.
- nexplorer listens on port 2048, so Windows Firewall asks whether to allow it. Allow it on your private network, otherwise the Next cannot connect.

**Linux.** Make the file executable and run it:

```
chmod +x nexplorer-vX.Y.Z-linux-x86_64.AppImage
./nexplorer-vX.Y.Z-linux-x86_64.AppImage
```

The AppImage needs FUSE 2 (package `libfuse2`, or `libfuse2t64` on recent Ubuntu); without it, run it with `--appimage-extract-and-run`. It carries `libxcb-cursor`; the OpenGL libraries (`libegl1`, `libgl1`) come from the system, as on any desktop install. It is built on Ubuntu 22.04, so the system needs glibc 2.35 or later. Allow incoming connections on port 2048 in your firewall.

Settings are kept in your user profile, not next to the program, so a new version keeps them.

## Run from a source checkout

Requirements: Python 3.10 or later.

```
git clone <repository-url> nexplorer
cd nexplorer
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
nexplorer                        # or: python -m nexplorer
```

nexplorer listens on TCP port 2048 from the moment it starts. Until a Next connects, the Next pane shows the Local IP address(es), the command to type on the Next and a reminder about the configuration file. Allow incoming connections on port 2048 in your PC firewall.

To run the tests: `pip install -e .[dev]` then `pytest`.

## Connect a Next

1. Start nexplorer on the PC and note the Local address shown in the Next pane.
2. Make sure `c:/sys/config/nextsync.cfg` on the Next holds that address (see the tutorial below).
3. On the Next, run:

   ```
   .sync5 -l
   ```

The Next pane switches to the Next's SD card when the connection is made. Use **Disconnect** to end the session.

## Compare

**Compare** opens a one-level comparison of the folder shown in the Local pane with the folder shown in the Next pane. Each name found on either side gets one row, with its state: only on Local, only on the Next, different (sizes differ) or identical. Rows only on one side are checked and point towards the other side. Different rows are unchecked and have no direction until you choose one with **Reverse direction**. **Apply** sends or receives the checked rows, each in its own direction. **Transfer this file** applies the selected row alone. Compare never deletes anything on either side.

## Beginner tutorial: set up a Next to use nexplorer

### 1. Configure Wi-Fi

Use the Next's own Wi-Fi setup so that the Next joins the same network as your PC (the same router). Follow the official Next documentation for your core version and check that the Next gets an address on that network. Wifi configurator app is located in `C:/APPS/WIFI/SETUP`)

### 2. Install the `.sync5` dot command

Install it with `gettit`, a really nice aplicattion downloader (it's preinstalled in C:/APPS/GETTIT). If `gettit` is not installed yet, install it first (you can install `gettit2` at the same time if you do not have it). Then search for `sync5` in `gettit` and install it. The dot command is a file named `sync5`; once installed it lives in the `DOT` folder at the root of the SD card. Move it usingf Browser app if needed ('v' key then 'p' in C:/DOT)

### 3. Place the file in `c:/DOT`

If the installer put the sync file somewhere else, move it to `c:/DOT`. Dot commands are only found there.

### 4. Point the Next at your PC and connect

Edit `C:/sys/config/nextsync.cfg` on the Next so that it contains the PC's address, the Local address shown by nexplorer. Then:
You also can send `.sync <PC IP>` command.

1. Run nexplorer on the PC.
2. Run `.sync5 -l` on the Next.

### 5. Optional: launch the dot from the file browser

To avoid typing the command, copy `wrap-sync` NextBASIC program to the Next. It runs `.sync5 -l` for you when you select it from the browser. The programs are listed in [examples/README.md](examples/README.md).

## Documentation

- [docs/protocol.md](docs/protocol.md): the `.sync5` listen protocol as implemented.
- [GLOSSARY.md](GLOSSARY.md): the vocabulary used in the code and the interface.

## Licence

MIT, see [LICENSE](LICENSE). Credits for third-party work are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
