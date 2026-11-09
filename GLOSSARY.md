# nexplorer

A minimal desktop file manager for a ZX Spectrum Next's SD card, driven over Wi-Fi through the `.sync5` dot command, with a Compare view to transfer files between a Local folder and a Next folder.

## Language

**Next**:
The remote ZX Spectrum Next machine whose file system is browsed and modified.
_Avoid_: remote, host, server, SD card

**Local**:
The PC running nexplorer and its file system.
_Avoid_: PC (in the interface), client

**Listener**:
The Local server that waits for a Next to run `.sync5 -l`.
_Avoid_: server, sync server

**Session**:
The active connection between nexplorer and one Next. There is at most one at a time.
_Avoid_: connection, peer

**Compare**:
The view showing the differences between a Local folder and a Next folder, from which the user chooses what to transfer. Nothing is transferred or deleted automatically.
_Avoid_: Sync, synchronise, mirror

**Difference**:
A row of Compare whose state is not identical: only on Local, only on the Next, different, or unverified.
_Avoid_: diff, change

**Move**:
Relocating a file or folder within one side: on the Next, by rename on the same drive or by copy then delete across drives (the source is deleted only after the copy is confirmed); on Local, into another folder. Between Local and the Next it is never a Move: that is a transfer.
_Avoid_: cut, cut/paste as the name of the operation (Cut is the Clipboard mark, see below)

**Clipboard**:
The entries marked by Copy or Cut, with the side they come from. A Cut entry only stays marked: it becomes a Move when pasted in the same pane. Copied entries can be pasted in either pane, which transfers them when it is the other side.
_Avoid_: buffer

**Active pane**:
The pane (Local or Next) that last had the keyboard focus, marked by an accent border. Menu entries, shortcuts and context menus act on it.
_Avoid_: current pane, focused pane
