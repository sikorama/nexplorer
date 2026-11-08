"""Qt-free implementation of the `.sync5 -listen` protocol (see docs/protocol.md)."""
from __future__ import annotations

import os
import queue
import socket
import threading
import time
from typing import Callable
from dataclasses import dataclass

MIN_FRAME = 5
MAX_FRAME = 4096
MAX_RESENDS = 12
PUT_CHUNK = 512  # some Next clones corrupt longer UART bursts


def checksum(payload: bytes) -> tuple[int, int]:
    c0 = c1 = 0
    for x in payload:
        c0 ^= x
        c1 = (c1 + c0) & 0xFF
    return c0, c1


def encode_frame(payload: bytes, packetno: int = 0) -> bytes:
    c0, c1 = checksum(payload)
    return (len(payload) + 5).to_bytes(2, "big") + payload + bytes([c0, c1, packetno & 0xFF])


@dataclass(frozen=True)
class Entry:
    name: str
    is_dir: bool
    size: int


@dataclass(frozen=True)
class Drives:
    current: str
    letters: list[str]


class RemoteError(Exception):
    """The Next answered a command with a failure."""


class Cancelled(Exception):
    """The caller asked to stop a put; the file is left partially written on the Next."""


class Listener:
    """Waits for a Next to run `.sync5 -l`; seats at most one Session."""

    def __init__(self, host: str = "0.0.0.0", port: int = 2048):
        self._host, self._port = host, port
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._sessions: queue.Queue[Session] = queue.Queue()
        self._lock = threading.Lock()
        self.current_session: Session | None = None

    @property
    def port(self) -> int:
        return self._server.getsockname()[1]

    def start(self) -> None:
        self._server = socket.socket()
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((self._host, self._port))
        self._server.listen(4)
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.close()

    def end_session(self, timeout: float = 3.0) -> bool:
        """Tell the current Session's Next to quit and wait for it to be gone: the
        Next hears `Q` at its next poll, instead of polling a dead link until it
        gives up. True when no Session is left."""
        with self._lock:
            session = self.current_session
        if session is None:
            return True
        session.close()
        return session.wait_closed(timeout)

    def wait_session(self, timeout: float | None = None) -> Session | None:
        try:
            return self._sessions.get(timeout=timeout)
        except queue.Empty:
            return None

    def _accept_loop(self) -> None:
        while True:
            try:
                conn, _ = self._server.accept()
            except OSError:
                return
            threading.Thread(target=self._greet, args=(conn,), daemon=True).start()

    def _greet(self, conn: socket.socket) -> None:
        conn.settimeout(10)
        try:
            data = b""
            while len(data) < 6:
                chunk = conn.recv(6 - len(data))
                if not chunk:  # ESP connect retry, not a peer
                    conn.close()
                    return
                data += chunk
            if data != b"Listen":
                conn.close()
                return
            with self._lock:
                busy = self.current_session is not None
                if busy:
                    conn.sendall(encode_frame(b"Busy", 0))
                    conn.close()
                    return
                conn.sendall(encode_frame(b"Listening", 0))
                session = Session(conn, on_closed=self._session_closed)
                self.current_session = session
        except OSError:
            conn.close()
            return
        self._sessions.put(session)
        session.start()

    def _session_closed(self, session: Session) -> None:
        with self._lock:
            if self.current_session is session:
                self.current_session = None


class _Trace:
    """Appends what crosses the wire to the file named by NEXPLORER_TRACE:
    `<seconds> rx|tx <length> <first bytes in hex>`, plus `cmd`, `abort`, `end` marks."""

    def __init__(self, path: str):
        self._file = open(path, "a", buffering=1)
        self._start = time.monotonic()
        self._lock = threading.Lock()

    def mark(self, kind: str, text: str = "") -> None:
        with self._lock:
            self._file.write(f"{time.monotonic() - self._start:9.3f} {kind} {text}\n")

    def data(self, kind: str, data: bytes) -> None:
        self.mark(kind, f"{len(data)} {data[:24].hex()}")


class _TracedSocket:
    def __init__(self, sock: socket.socket, trace: _Trace):
        self._sock, self._trace = sock, trace

    def recv(self, n: int) -> bytes:
        data = self._sock.recv(n)
        self._trace.data("rx", data)
        return data

    def sendall(self, data: bytes) -> None:
        self._trace.data("tx", data)
        self._sock.sendall(data)

    def __getattr__(self, name: str):
        return getattr(self._sock, name)


class Session:
    """The active connection with one Next."""

    def __init__(self, sock: socket.socket, on_closed=None):
        path = os.environ.get("NEXPLORER_TRACE")
        self._trace = _Trace(path) if path else None
        self._sock = _TracedSocket(sock, self._trace) if self._trace else sock
        self._on_closed = on_closed
        self._closed = threading.Event()
        self._closing = False
        self._lock = threading.Lock()
        self._dead = False
        self._current: _Call | None = None
        try:
            self.peer_address: str = sock.getpeername()[0]
        except OSError:
            self.peer_address = ""
        self._commands: queue.Queue = queue.Queue()
        self._version: str | None = None

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    # -- public API (callable from any thread)
    def dot_version(self, timeout: float | None = None) -> str | None:
        """The dot's version, or None when the dot is too old to answer `Y`."""
        reply = self._call(b"Y", timeout)
        if reply is None:
            return None
        try:
            return reply[1:].split(b"\x00", 1)[1].decode("ascii")
        except (IndexError, UnicodeDecodeError):
            return None

    def list_dir(self, path: str, timeout: float | None = None) -> list[Entry]:
        """The entries of a folder on the Next, without `.` and `..` (the dot lists
        them); RemoteError if it cannot be opened."""
        blocks = self._call(b"L" + _wire_path(path), timeout, terminals=(b"E", b"F"))
        if blocks[-1][:1] == b"F":
            raise RemoteError(f"cannot list {path}")
        entries: list[Entry] = []
        for block in blocks:
            if block[:1] == b"D":
                entries.extend(_parse_entries(block[1:]))
        return [e for e in entries if e.name not in (".", "..")]

    def drives(self, timeout: float | None = None) -> Drives | None:
        """The drives of the Next, or None when the dot does not answer `W`."""
        reply = self._call(b"W", timeout)
        if reply is None:
            return None
        if reply[:1] != b"O":
            raise RemoteError("cannot read the drives")
        text = reply[1:].decode("ascii")
        return Drives(text[:1], list(text[1:]))

    def free_space(self, drive: str, timeout: float | None = None) -> int | None:
        """Free bytes on a drive, or None when the dot does not answer `Z`."""
        reply = self._call(b"Z" + drive.encode("ascii"), timeout)
        if reply is None:
            return None
        if reply[:1] != b"O" or len(reply) < 5:
            raise RemoteError(f"cannot measure drive {drive}")
        return int.from_bytes(reply[1:5], "little") * 512

    def put_file(
        self,
        local_path: str,
        next_path: str,
        timeout: float | None = None,
        progress: Callable[[int], None] | None = None,
        cancel: Callable[[], bool] | None = None,
    ) -> None:
        """Upload a Local file to `next_path`, replacing it; RemoteError if the Next refuses.

        `progress` gets the bytes sent so far and `cancel` is asked before each
        chunk; both run on the Session's thread. A failed or cancelled put
        leaves a partially written file on the Next."""
        wire = _wire_path(next_path)
        with open(local_path, "rb") as source:
            self._call(b"P" + wire, timeout, source=source, hooks=(progress, cancel))

    def get_file(
        self,
        next_path: str,
        local_path: str,
        timeout: float | None = None,
        progress: Callable[[int], None] | None = None,
    ) -> None:
        """Download one file of the Next into `local_path`, replacing it.

        RemoteError when the Next sends nothing (the dot gives no failure
        indication for a missing path). The file is written beside its target
        and renamed over it once complete: a failed get leaves the target as it
        was and no partial file. `progress` gets the bytes received so far, on
        the Session's thread."""
        wire = _wire_path(next_path)
        receiver = _FileReceiver(local_path, progress)
        try:
            self._call(b"G" + wire, timeout, terminals=(b"B",), sink=receiver.take)
        except BaseException:
            receiver.discard()
            raise
        if not receiver.opened:
            receiver.discard()
            raise RemoteError(f"nothing received for {next_path}")
        receiver.commit()

    def make_dir(self, path: str, timeout: float | None = None) -> None:
        """Create a folder on the Next; RemoteError when it fails (esxDOS gives the
        same error when the folder already exists)."""
        reply = self._call(b"M" + _wire_path(path), timeout)
        if reply is None or reply[:1] != b"O":
            raise RemoteError(f"cannot create {path}")

    def rename(self, old: str, new: str, timeout: float | None = None) -> None:
        """Rename a file or folder on the Next; RemoteError when it is refused."""
        reply = self._call(b"V" + _wire_path(old) + b"\x00" + _wire_path(new), timeout)
        if reply is None or reply[:1] != b"O":
            raise RemoteError(f"cannot rename {old} to {new}")

    def copy(self, src: str, dst: str, timeout: float | None = None) -> None:
        """Copy a file or a whole folder tree on the Next, across drives, with no data on the
        wire. A folder is merged into an existing one. RemoteError when anything fails; the
        files already copied stay. A destination inside the source is refused before sending
        (the dot does not guard against it)."""
        wire_src, wire_dst = _wire_path(src), _wire_path(dst)
        a, b = src.lower().rstrip("/"), dst.lower().rstrip("/")
        if b == a or b.startswith(a + "/"):
            raise RemoteError(f"cannot copy {src} onto or into itself")
        blocks = self._call(b"C" + wire_src + b"\x00" + wire_dst, timeout, terminals=(b"O", b"F"))
        if not blocks or blocks[-1][:1] != b"O":  # no blocks: an old dot ignored the opcode
            raise RemoteError(f"cannot copy {src} to {dst}")

    def remove_file(self, path: str, timeout: float | None = None) -> None:
        """Delete a file on the Next (there is no recycle bin); RemoteError when it fails."""
        reply = self._call(b"X" + _wire_path(path), timeout)
        if reply is None or reply[:1] != b"O":
            raise RemoteError(f"cannot delete {path}")

    def remove_dir(self, path: str, timeout: float | None = None) -> None:
        """Delete an empty folder on the Next; RemoteError when it fails or is not empty."""
        reply = self._call(b"R" + _wire_path(path), timeout)
        if reply is None or reply[:1] != b"O":
            raise RemoteError(f"cannot delete folder {path}")

    def close(self) -> None:
        """End the Session: the Next is told to quit at its next poll."""
        self._closing = True

    def wait_closed(self, timeout: float | None = None) -> bool:
        return self._closed.wait(timeout)

    # -- internals
    def _call(self, command: bytes, timeout: float | None, terminals=None, source=None, sink=None, hooks=None):
        """Send one command and wait for its reply.

        Without `terminals` the reply is one block (returned as bytes, or None
        when the dot ignores the opcode). With `terminals`, blocks are read up
        to one whose opcode is a terminal; the list of blocks is returned."""
        call = _Call(command, terminals, source, sink)
        call.progress, call.cancel_hook = hooks or (None, None)
        with self._lock:
            if self._dead:
                raise ConnectionError("session closed")
            self._commands.put(call)
        if not self._wait(call, timeout):
            call.cancelled = True  # never sent if still queued
            if self._current is call and (call.source is not None or call.sink):
                self._abort()  # a transfer cut short leaves the Session out of step
            raise TimeoutError(f"no reply to {command!r}")
        if call.error:
            raise call.error
        return call.result

    @staticmethod
    def _wait(call: _Call, timeout: float | None) -> bool:
        """Wait for the reply; `timeout` is the silence tolerated, so a transfer
        that keeps moving (each block counts) never expires."""
        if timeout is None:
            return call.done.wait()
        while True:
            remaining = call.activity + timeout - time.monotonic()
            if remaining <= 0:
                return call.done.is_set()
            if call.done.wait(remaining):
                return True

    def _abort(self) -> None:
        """End the Session from another thread: the blocked reader then fails."""
        if self._trace:
            self._trace.mark("abort", "timeout during a transfer: the Session is cut")
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def _recv_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("closed")
            buf += chunk
        return buf

    def _recv_raw(self) -> bytes:
        """Read one raw message (Poll or Bye), accumulating split reads."""
        first = self._recv_exact(1)
        if first == b"P":
            return first + self._recv_exact(3)
        if first == b"B":
            return first + self._recv_exact(2)
        raise ConnectionError(f"unexpected byte {first!r}")

    def _next_call(self) -> _Call | None:
        while True:
            try:
                call = self._commands.get(timeout=0.05)
            except queue.Empty:
                return None
            if not call.cancelled:
                return call

    def _run(self) -> None:
        self._sock.settimeout(620)
        try:
            while True:
                raw = self._recv_raw()
                if raw == b"Bye":
                    self._sock.sendall(encode_frame(b"Later"))
                    return
                if self._closing:
                    self._sock.sendall(encode_frame(b"Q"))
                    return
                call = self._next_call()
                if call is None:
                    self._sock.sendall(encode_frame(b"I"))
                    continue
                self._current = call
                if self._trace:
                    self._trace.mark("cmd", repr(call.command[:60]))
                self._sock.sendall(encode_frame(call.command))
                self._finish(call)
                self._current = None
        except OSError as exc:
            if self._trace:
                self._trace.mark("end", f"{type(exc).__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001 - leave a trace of the bug, then re-raise
            if self._trace:
                self._trace.mark("end", f"BUG {type(exc).__name__}: {exc}")
            raise
        finally:
            self._shutdown()

    def _finish(self, call: _Call) -> None:
        """Read the Next's answer to a command; a raw message means no answer."""
        if call.source is not None:
            self._serve_put(call)
            return
        first = self._recv_exact(1)
        if first[0] < 0x20:  # a framed block: the high byte of its length
            blocks = [self._read_block(first, expected_no=0)]
            count = 1
            while call.terminals and blocks[-1][:1] not in call.terminals:
                blocks.append(self._read_block(self._recv_exact(1), expected_no=count))
                count += 1
                if call.sink:  # streamed: keep only what is still needed
                    self._to_sink(call, blocks.pop(0))
            if call.sink:
                self._to_sink(call, blocks.pop(0))
                call.result = None
            else:
                call.result = blocks if call.terminals else blocks[0]
            call.done.set()
            return
        if first == b"P":  # unknown opcode (old dot): it just polled again
            self._recv_exact(3)
            self._sock.sendall(encode_frame(b"I"))
            call.done.set()  # result stays None: unknown
            return
        if first == b"B":  # BREAK during the command
            self._recv_exact(2)
            self._sock.sendall(encode_frame(b"Later"))
        raise ConnectionError("session ended during a command")

    @staticmethod
    def _to_sink(call: _Call, block: bytes) -> None:
        """Hand a block to the caller's sink; after a sink failure keep draining
        the reply (to stay in step with the Next) without calling it again."""
        if call.error:
            return
        call.activity = time.monotonic()
        try:
            call.sink(block)
        except Exception as exc:  # noqa: BLE001 - reported to the caller
            call.error = exc

    def _serve_put(self, call: _Call) -> None:
        """Serve the file as the Next pulls it (docs/protocol.md, `P` put)."""
        source = call.source
        counter = 0
        last, last_no = b"", 0
        sent = 0
        while True:
            first = self._recv_exact(1)
            if first == b"\x00":  # the Next could not create the file, or gave up
                status = self._read_block(first, expected_no=0)
                call.error = RemoteError("put failed") if status[:1] != b"O" else None
                call.done.set()
                return
            if first == b"G":  # Get (or the mis-transmitted Gee)
                self._recv_exact(2)
                call.activity = time.monotonic()
                try:
                    if call.cancel_hook and call.cancel_hook():
                        self._sock.sendall(encode_frame(b"", counter))  # ends the file where it is
                        call.error = Cancelled("put cancelled")
                        call.done.set()
                        return
                    chunk = source.read(PUT_CHUNK)
                    sent += len(chunk)
                    if call.progress and chunk:
                        call.progress(sent)
                except Exception as exc:  # noqa: BLE001 - reported to the caller
                    self._sock.sendall(encode_frame(b"", counter))  # ends the file where it is
                    call.error = exc
                    call.done.set()
                    return
                last, last_no = chunk, counter
                self._sock.sendall(encode_frame(chunk, counter))
                counter = (counter + 1) & 0xFF
                if not chunk:
                    call.done.set()
                    return
            elif first == b"R":
                self._recv_exact(1)  # "e"
                if self._recv_exact(1) == b"t":  # Retry: the same chunk, the same packetno
                    self._recv_exact(2)
                    self._sock.sendall(encode_frame(last, last_no))
                else:  # Restart: the Next recreated the file and counts from 0
                    self._recv_exact(4)
                    source.seek(0)
                    sent = counter = 0
                    self._sock.sendall(encode_frame(b"Back"))
            else:
                raise ConnectionError(f"unexpected byte {first!r} during a put")

    def _read_block(self, first: bytes, expected_no: int) -> bytes:
        """Read one framed block, asking for a resend while its checksum is bad."""
        for _ in range(MAX_RESENDS + 1):
            total = int.from_bytes(first + self._recv_exact(1), "big")
            if not MIN_FRAME <= total <= MAX_FRAME:
                raise ConnectionError(f"impossible frame length {total}")
            body = self._recv_exact(total - 2)
            payload, (cs0, cs1, no) = body[:-3], body[-3:]
            if checksum(payload) == (cs0, cs1):
                self._sock.sendall(encode_frame(b"Ok", no))
                return payload
            self._sock.sendall(encode_frame(b"Resend", expected_no))
            first = self._recv_exact(1)
        raise ConnectionError("too many corrupt blocks")

    def _shutdown(self) -> None:
        if self._trace:
            self._trace.mark("end", "Session closed")
        self._sock.close()
        with self._lock:
            self._dead = True
        pending = [self._current] if self._current else []
        while not self._commands.empty():
            pending.append(self._commands.get_nowait())
        for call in pending:
            call.error = ConnectionError("session closed")
            call.done.set()
        if self._on_closed:
            self._on_closed(self)
        self._closed.set()


class _FileReceiver:
    """Writes the blocks of one `G` reply (`N`, `D`..., `E`, `B`) into a temporary
    file beside `path`; `commit` renames it over `path`, `discard` removes it."""

    def __init__(self, path: str, progress: Callable[[int], None] | None = None):
        self._path = path
        self._temp = f"{path}.{os.getpid()}.part"
        self._file = None
        self._progress = progress
        self._received = 0
        self.opened = False

    def take(self, block: bytes) -> None:
        kind = block[:1]
        if kind == b"N":
            if self.opened:
                raise RemoteError("the Next sent more than one file")
            self._file = open(self._temp, "wb")
            self.opened = True
        elif kind == b"D" and self._file:
            self._file.write(block[1:])
            self._received += len(block) - 1
            if self._progress:
                self._progress(self._received)
        elif kind == b"E" and self._file:
            self._file.close()
            self._file = None

    def commit(self) -> None:
        self._close()
        os.replace(self._temp, self._path)

    def discard(self) -> None:
        self._close()
        if self.opened:
            try:
                os.remove(self._temp)
            except FileNotFoundError:
                pass

    def _close(self) -> None:
        if self._file:
            self._file.close()
            self._file = None


class _Call:
    def __init__(self, command: bytes, terminals=None, source=None, sink=None):
        self.sink = sink  # called with each block as it arrives, instead of collecting them
        self.command = command
        self.terminals = terminals
        self.progress = None
        self.cancel_hook = None
        self.source = source  # a put: the open Local file being served
        self.result = None
        self.error: Exception | None = None
        self.cancelled = False
        self.activity = time.monotonic()  # last sign of life, for the timeout
        self.done = threading.Event()


MAX_PATH = 254


def _wire_path(path: str) -> bytes:
    """A path as the dot takes it; refuse what it would silently truncate or garble."""
    try:
        raw = path.encode("ascii")
    except UnicodeEncodeError:
        raise RemoteError(f"path is not ASCII: {path!r}") from None
    if len(raw) > MAX_PATH:
        raise RemoteError(f"path over {MAX_PATH} bytes: {path[:40]!r}...")
    if any(part in (".", "..") for part in path.split("/")):
        raise RemoteError(f"path with a '.' or '..' component: {path[:40]!r}")
    return raw


def _parse_entries(data: bytes) -> list[Entry]:
    entries = []
    i = 0
    while i + 6 <= len(data):
        flags = data[i]
        size = int.from_bytes(data[i + 1 : i + 5], "little")
        namelen = data[i + 5]
        name = data[i + 6 : i + 6 + namelen].decode("ascii", "replace")
        entries.append(Entry(name, bool(flags & 1), size))
        i += 6 + namelen
    return entries
