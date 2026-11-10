# sync-wrap

`sync-wrap.bas` is a NextBASIC program that starts the `.sync5` dot command in one step, without typing it. Selected from the Next's file browser, it runs `.sync5 -l` so that the Next connects to nexplorer. Its screen lets you set the options of the dot (mode, speed, drive, ...) and the server address.

`sync-wrap.txt` is the same program as readable text, for information only: it cannot be run on the Next.

## Putting it on the Next

Once a Next is connected, use **Transfer > Send sync-wrap.bas to the ZX Spectrum Next** in nexplorer. The program is sent into the Next folder shown; if a file of that name is already there, nexplorer asks before replacing it. The program saves its settings in `syncwrap.cfg` next to itself.

Run it from the D: drive: the Next pane can only browse the drive the dot was launched from.
