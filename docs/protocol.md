# NextSync `-listen` protocol

Reference for the wire protocol spoken between nexplorer (the **Listener**, a TCP server on port 2048) and the `.sync5` dot command running on the **Next** (the TCP client) in `-listen` mode. It is the single reference for the fake Next and for the protocol module.

Statements marked **Unverified** come from comments or code in the sources, not from a hardware run of nexplorer; they must be checked on a real Next before being relied on.

## Sources

| Short name | What it is |
|---|---|
| dot | The dotN source of `.sync5` (`nextsync/sync/z88dk/nextsync.c`, `free.c`, `rcpy.c`, `rfsize.c`, `crc32.asm`), current version 5.9.14. The authority for what the Next sends and accepts. |
| Unite worker | `run_remote_listen_server` and `_re_session` in `zxnu_workers.py` of ZX-Next-Unite: the Listener side as it has been used on real hardware. |
| Unite console | `nextsync5.py` of ZX-Next-Unite: a standalone Listener with the same framing and opcodes. |

The protocol originates in Jari Komppa's NextSync (Unlicense). The `-listen` mode, the `Listen` handshake and every opcode below were added by Julien Clauzel's `.sync5` and are served by ZX-Next-Unite.

## Roles and shape

- The Next dials in. The Listener never connects out.
- The Next drives. It sends a short raw message, the Listener answers with one framed block. In `-listen` mode the Next sends `Poll` in a loop and the Listener answers each poll with exactly one command (or an idle `I`).
- Everything is stop-and-wait: one outstanding message in each direction. There is no pipelining.
- The Next reaches the Listener through its ESP8266 Wi-Fi module over a UART, so the link is slow (tens of KB/s), can corrupt bytes, and can stall.

## Framing

### Framed blocks

Both directions use the same block layout for every payload:

```
[2 bytes big-endian total][payload (total - 5 bytes)][cs0][cs1][packetno]
```

- `total = len(payload) + 5`.
- Checksum, over the payload bytes only: `c0 = 0; c1 = 0; for x in payload: c0 ^= x; c1 = (c1 + c0) & 0xFF`. `cs0 = c0`, `cs1 = c1`.
- `packetno` is one byte and wraps at 256.
- The Listener rejects a header whose `total` is under 5 or over 4096. The dot's own receive path accepts a total between 5 and 2048.
- The first payload byte of a command or reply is an opcode.

### Raw messages

The Next sends these as bare ASCII, not framed: `Listen` (handshake), `Poll`, `Get` (also seen as `Gee`, a known UART mis-transmit), `Retry`, `Restart`, `Bye`. The Listener must accept `Gee` as `Get`.

A raw message and a framed block can be told apart by their first byte: a frame's first byte is the high byte of its total, at most `0x10` (the total is at most 4096), a raw message starts with an ASCII letter (`0x41` or more). A frame can never start with the two bytes `Po`.

Raw messages are tiny and sent one per exchange, so a single `recv` normally returns exactly one. The Next's UART can still split one across two reads (`Po` + `ll`): a robust reader accumulates until the message is complete rather than comparing a single `recv` result.

## Handshake

1. The Next opens TCP to port 2048 and sends the six bytes `Listen`.
2. The Listener, within 10 seconds, reads at least 6 bytes and replies with one framed block, packetno 0:
   - `Listening` to accept the Session.
   - `Busy` when a Session is already open. The dot (5.7.2 and later) prints "Server busy: another Next" and leaves; older dots fail by timeout.
3. A connection that closes without sending anything is an ESP connect retry, not a peer: ignore it silently. A connection that sends something other than `Listen` (a classic sync client) is closed.
4. The Next then enters its poll loop. Any of its replies that fails the check `len >= 12`, a valid checksum and the prefix `Listening` makes it print "Server too old (-listen)" and leave.

After the handshake the Listener sets TCP keepalive (idle 30 s, interval 30 s, 20 probes) on the seated socket. A Next whose ESP was reset under the link is expected to answer the first probe with RST.

## Poll loop

```
Next -> Listener : Poll                      (raw)
Listener -> Next : one command frame         (framed, packetno 0)
```

The command frame's payload is an opcode followed by an argument. The reply protocol depends on the opcode (see below). When no command is queued the Listener answers `I`; the dot then pauses a short moment and polls again. A Next idles at roughly one poll every one to two seconds.

The Listener must answer every `Poll` with exactly one frame. Answering a poll with a second frame, or answering twice, leaves the two sides one exchange out of step for the rest of the Session.

### Ending a Session

- The Listener sends `Q`. The dot (5.7.5 and later) prints "Listen ended" and closes the socket without a goodbye. A dot of 5.7.4 or older answers `Bye` and waits for `Later`; the Listener should read until the peer closes (bounded, 2 s) and answer a drained `Bye` with a framed `Later`, so that an old dot does not hang.
- The user presses BREAK (CAPS SHIFT + SPACE) on the Next. The dot checks this between commands only, never during a transfer. It then sends the raw message `Bye`; the Listener answers a framed `Later` and the Session ends.
- The Next stops polling: after 8 consecutive bad or empty poll exchanges the dot prints "Connection lost - stopping" and closes.
- The Listener sees EOF or a socket error.
- The Listener may also give up on silence (see Timeouts).

The framed `Q` carrying a trailing `X` (`Q`, `X`) exists in ZX Next Remote and asks the far side to end its application. The `.sync5` dot ignores any extra bytes on `Q`. nexplorer never sends it.

## Replies the Next pushes

A command whose reply is "pushed" is answered by the Next as a sequence of framed blocks, each one acknowledged by the Listener. This is the same mechanism as the older `-send` upload.

- The Next numbers its blocks 0, 1, 2, … for each command; the counter restarts at 0 at the start of every command.
- For each block the Listener replies with a framed `Ok` carrying the **same packetno** as the block it acknowledges.
- Bad checksum: reply a framed `Resend`, packetno = the number it expects next. The Next sends the block again.
- A block whose packetno is the previous one (a duplicate, because the `Ok` was lost): re-acknowledge it with `Ok` and do not process it again.
- Any other out-of-sequence packetno: reply `Err seq` and abandon the command.
- The terminal block of a command (named per opcode) ends the reply.
- The Next retries a block up to 12 times when it gets no valid `Ok`.

Gaps between blocks can legitimately last seconds (SD seeks, the directory re-open walk). The Unite worker allows 60 seconds of silence inside one reply.

If the first thing the Listener reads after sending a command is the two bytes `Po`, the Next sent a raw `Poll` instead of a reply. Either the Next does not know the opcode (an old dot ignores unknown opcodes in silence and goes back to polling), or it missed the command and re-polled. See Capability probing for how to tell them apart.

## Commands

Opcodes are single ASCII bytes. Paths are ASCII, use forward slashes, may start with a drive prefix (`c:/games`, `m:/tmp`), and are at most 254 bytes: the dot copies a path into a 254-byte buffer and **silently truncates** a longer one, so the command would act on a different name. The Listener must refuse a longer path before sending it. A path with no drive prefix refers to the dot's current drive.

| Op | Name | Command payload | Pushed reply | Dot since |
|---|---|---|---|---|
| `I` | idle | none | none (the Next just polls again) | first `-listen` build |
| `L` | ls | path | `D`… then `E`, or one `F` | first `-listen` build |
| `G` | get | path | `N`/`D`/`E` per file, then `B` | first `-listen` build |
| `P` | put | path | none pushed; the Next pulls the data (see Put) | first `-listen` build |
| `M` | mkdir | path | one status block | first `-listen` build |
| `R` | rmdir | path | one status block | first `-listen` build |
| `X` | rm | path | one status block | first `-listen` build |
| `V` | rename | old, `0x00`, new | one status block | unknown |
| `W` | drives | none | one status block | 5.1 |
| `Z` | free | optional drive letter | one status block | 5.2 |
| `C` | rcpy | src, `0x00`, dst | `D`… then `O` or `F` | 5.2 |
| `S` | rfsize | path | `D`… then `O`+totals or `F` | 5.2 |
| `Y` | ident | none | one status block | 5.8.0 |
| `U` | release | none | one status block | 5.9 |
| `K` | crc | path | one status block | 5.9.2 |
| `Q` | quit | none | none | first `-listen` build |

"Dot since" is the version the source comments attribute to the opcode; the opcodes of the first `-listen` build have no recorded version. `V` (rename) has no version comment in the source and is present in 5.9.14: **Unverified** for earlier builds. nexplorer never sends `U`, which only exists so a Listener can replace the dot while it runs.

A **status block** is one framed block, payload `O` (ok) or `F` (failure), packetno 0, acknowledged with `Ok`. Opcodes that return data put it after the `O`.

### `L` ls

Reply: zero or more `D` blocks, then one `E`. Or one `F` block when the folder cannot be opened.

A `D` block payload is `D` followed by packed entries: `[flags][size: 4 bytes little-endian][namelen: 1 byte][name]`. Flags bit 0 is set for a directory. The dot starts a new `D` block when the entries would exceed 1000 bytes. The listing carries name, type and size only: **there is no modification time**. Names are returned as stored on the card (FAT long names; case preserved).

An `F` means the folder is gone or unreadable, not that it is empty: an empty folder yields only `E`.

Whether `.` and `..` appear in a listing is **Unverified**; the dot does not filter them in `ls`, and its own tree walk skips them.

### `G` get

The Next streams the file, or the whole directory tree, to the Listener:

- `N` block: `N`, four zero bytes (length unknown; they are always zero), one byte `namelen`, `name`. The name is the path as the dot knows it, full path for a directory walk. Mapping it to a Local path (stripping the fetched item's parent, rejecting `..`, drive letters and leading slashes) is the Listener's job.
- `D` blocks: `D` followed by up to 1024 file bytes.
- `E` block: `E`, end of this file.
- `B` block: `B`, end of the whole command. This is the terminal block.

A file that cannot be opened is skipped, so a `get` of a missing path produces a lone `B` and **no failure indication**. The Listener has to list or size the path first if it needs to know it exists. A directory walk skips entries whose path would reach 254 bytes.

The terminal `B` is acknowledged like the others; when its `Ok` never reaches the Next it retries and eventually gives up, so a Listener that stops reading mid-get leaves the dot looking successful on its screen while the Listener has nothing.

### `P` put

The Listener sends `P` plus the destination path, then **serves** the file as the Next pulls it. The Next must not be given the file before it asks.

1. The Next opens (creates) the destination file. If it cannot, it pushes a status block `F` (framed, packetno 0) and returns to polling. An existing file is **replaced** (truncated); missing parent folders are created along the path.
2. The Next sends raw `Get`. The Listener replies with a data frame whose payload is the next chunk of the file (up to 512 bytes, see below) and whose **packetno** is the chunk counter, starting at 0 and wrapping at 256.
3. The Next verifies the checksum and that the packetno equals its own counter. On success it writes the chunk and sends `Get` again.
4. After the last data frame the Next sends one more `Get`; the Listener answers a frame with an **empty payload** (still a valid frame, total 5). The Next closes the file and returns to polling. The Listener treats the put as complete as soon as the last data byte has gone out; it must still answer the terminating `Get`.
5. Checksum failure on the Next: it sends raw `Retry`. The Listener resends the **same** chunk with the **same** packetno.
6. Packetno mismatch on the Next: it sends raw `Restart`, closes and recreates the file, and sets its counter to 0. The Listener resets its offset and counter to 0 and answers a frame with the payload `Back`. The Next gives up after 6 failures in a row.
7. When the Next gives up it closes the file, leaving it **partially written**, and pushes a status block `F`. Nothing is deleted on the Next. The Listener must therefore treat a partially written destination as a possible result of any failed put and report its name and size.

While a put is pending the Listener reads either a raw message (`Get`, `Gee`, `Retry`, `Restart`, `Bye`, `Poll`) or a framed `F` block. A frame starts with `0x00`.

**Chunk size is 512 bytes, not the protocol's 1024 cap.** Some Next clones (the N-Go) corrupt continuous UART bursts longer than 512 bytes at the faster rates, always failing the checksum. Real Nexts are indifferent; the cost is one extra 5-byte header per KB.

Verifying a put: a size check by listing the destination folder is always possible; a CRC check needs `K`.

### `M` mkdir, `R` rmdir, `X` rm

One status block each. `O` on success, `F` on failure.

- `R` removes only an **empty** folder. Removing a folder with content is a client-side walk: list it, `X` each file, recurse into sub-folders, then `R` each folder bottom-up. There is no recursive remove opcode.
- `M` returns `F` when the folder cannot be created. esxDOS reports the same error for "already exists" as for a real failure: when that distinction matters, list the parent afterwards.
- `X` removes a file. Its behaviour on a directory is **Unverified**.

### `V` rename

Payload `V`, old path, one `0x00`, new path, in one frame. One status block.

NextZXOS refuses a rename onto an existing name, and a rename of a file the dot itself holds open fails. A rename is a pure directory operation: it is the intended same-drive Move. Whether `V` across two drives succeeds is **Unverified**; the specification treats a cross-drive Move as copy, size check, delete and does not depend on it.

### `W` drives

Status block `O`, then the current drive letter, then the drive letters. The list is exactly `{C, M, current drive}` (C is the boot SD card, M the RAM disk, both guaranteed by NextZXOS; the current one is mounted by definition). It is never probed.

**The Listener must never use a drive letter other than the reported ones**, and never `A:` or `B:`: any path on an unmounted drive, or on the +3DOS floppy drives, crashes the dot. A user-declared extra drive is the user's own risk.

### `Z` free

Payload `Z` plus an optional drive letter (`C`, `M`, …); empty means the dot's current drive. Status block `O` followed by four bytes little-endian: the number of free **512-byte blocks** on that partition. `F` when the drive cannot be measured. Total size is not available.

### `S` rfsize

Total size of a file or of a whole directory tree, measured on the Next with no data transferred. `D` blocks are progress (named with the current directory, plus empty keep-alive blocks every 256 entries). The terminal block is `O` followed by `[files: 4 bytes LE][dirs: 4 bytes LE][size_lo: 4 bytes LE][size_hi: 2 bytes LE]` (15 bytes total payload; bytes = size_hi × 2³² + size_lo), or `F`.

### `C` rcpy

Copies a file or a whole directory tree on the Next, with no data crossing the wire, and across drives (`c:/x` to `m:/y`) as every path is drive-prefixed. Payload `C`, src, `0x00`, dst. `D` blocks are progress: a named one per file (the name is its destination path), an empty keep-alive every 64 KB inside large files. The terminal block is `O` when everything was copied, `F` when anything failed or the link died. Files already copied **stay** (like an interrupted `cp`). A directory copy creates the destination root and merges into it if it exists.

The Listener must refuse a destination inside the source before sending it (the dot does not guard against it). The behaviour for a single-file copy onto an existing destination file is **Unverified**.

The progress gaps are bounded to roughly 64 KB of local SD work, so the reply timeout must be generous.

### `Y` ident

Status block `O`, then `sync`, one `0x00`, then the dot's version string (`5.9.14`). Other Listener peers answer with a different type (`httpbridge`, `n2n`, `zxnt`, `qlnextremote`, `qlnt`); only `sync` is in scope for nexplorer.

### `K` crc

Status block `O` followed by eight upper-case hexadecimal digits: the CRC-32 (IEEE 802.3, reflected, the value `zlib.crc32` returns) of the file. `F` when the file does not open or a read fails midway. The dot prints the digits on its own screen too.

The Next streams the file and answers **nothing meanwhile**: about 30 s per MB. The Listener must use a long reply timeout (Unite uses one hour as its ceiling and sizes the real wait from the file size: 60 s plus size at 15 KB/s) and must not treat the silence as a dead link.

## Capability probing and versions

The dot ignores an opcode it does not know: it sends nothing back and polls again. The Listener sees a raw `Poll` where it expected a frame.

- Ask `Y` first, once per Session, and keep the answer. A `Y` that gets a raw `Poll` back means a dot older than 5.8.0 (or a Listener that does not answer `Y`): record it as unknown and **do not** ask for anything newer.
- Do not send `K` (needs 5.9.2), `Z`/`C`/`S` (5.2) or `W` (5.1) to a dot whose answer says it is older: each costs a wait and a desynchronisation.
- After an unknown opcode the stray `Poll` tail (`ll`) is still in the socket: read and discard it, and answer the poll with an idle `I`, which puts the exchange back in step.
- The frames the Listener sends that owe the Next nothing back are the idle `I`, `Ok`, `Later` and `Back`: a failed send of one of them is not a lost command.

Feature table (dot version needed, from the source comments):

| Feature | Opcode | Version |
|---|---|---|
| list, get, put, mkdir, rmdir, rm, quit | `L G P M R X Q` | the first `-listen` build (version not recorded in the sources) |
| rename | `V` | unknown, present in 5.9.14 |
| drives | `W` | 5.1 |
| free space, copy on the Next, tree size | `Z C S` | 5.2 |
| `Busy` reply for a second Next | handshake | 5.7.2 |
| close without goodbye on `Q` | session end | 5.7.5 |
| ident | `Y` | 5.8.0 |
| CRC-32 | `K` | 5.9.2 |

The minimum `.sync5` version nexplorer asks the user to install is the version that carries every feature the application uses: **5.9.2** (it needs `K` for Verify). Unverified: the exact first build of `V`; until established, the gating line says 5.9.2 and the application checks `Y` and refuses nothing it cannot prove missing.

## Timeouts

| What | Value | Where it comes from |
|---|---|---|
| Handshake read | 10 s | Listener |
| Silence inside one reply | 60 s | Unite worker `RE_REPLY_TIMEOUT` |
| `K` reply | up to 3600 s | Unite worker; sized from file size on the bridge |
| Idle silence from a seated Next | 620 s | Unite worker `PEER_SILENCE_LIMIT`; the dot's own verdict (8 bad polls in a row, each costing a full UART timeout) is meant to land first |
| TCP keepalive | 30 s idle, 30 s interval, 20 probes | Unite worker |

A Listener that reaps a seat silently for less than the Next's own verdict will drop a live Next during a long `K`, `C` or `S`, which do not poll while they run.

## Hardware behaviours that matter

Each was found on real hardware by the sources' authors. A fake Next simulates one of these only because it is listed here.

1. **Long UART bursts corrupt on clones** (N-Go): chunks over 512 bytes fail their checksum deterministically. nexplorer serves 512 bytes.
2. **Late poll.** An idle Next's first command after a long pause can be missed inside its 5-second window; it then re-polls and the command is received afterwards. The reply follows the late command. For `M`, `R`, `X` the Unite worker swallows the stray `Poll` once and keeps waiting; it never answers that `Poll` and never resends the command (rm, rmdir and put are not idempotent).
3. **No failure indication for `G`.** A missing path produces a lone `B`.
4. **Partial files after a failed put** stay on the Next; nothing deletes them.
5. **Unmounted and floppy drives crash the dot.** Only `C`, `M` and the current drive letter are safe.
6. **Rename onto an existing name is refused** by NextZXOS.
7. **Path over 254 bytes is truncated silently** by the dot.
8. **ESP can reset under the link without a FIN.** A dead Next may stay seated until keepalive or silence rules end it.
9. **File I/O while a directory handle is open corrupts the esxDOS directory cursor.** The dot sorts this out itself (re-open, skip, close); a Listener has nothing to do, but a command never needs more than one directory open at a time.

## What the fake Next must do

The fake Next is a stand-in for the dot: a TCP **client** that dials the Listener, over a local socket.

- Connect, send `Listen`, expect a framed `Listening` or `Busy`.
- Poll in a loop with raw `Poll`, execute the framed command it receives against an in-memory file system, and push the replies defined above with correct framing, numbering and acknowledgement handling.
- Serve the put pull (`Get`, empty terminal frame, `Retry`, `Restart`, `F` on failure).
- Answer `Y` with a configurable version, and ignore the opcodes of a configurable older version in silence.
- Be able to: drop the link mid-command, fail a command with `F`, corrupt a data frame to force `Retry`, leave a partial file after a failed put, and refuse a cross-drive rename if a test asks for it.
- Never answer `W` with a drive other than the ones it was configured with.
