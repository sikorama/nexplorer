"""Qt-free implementation of the `.sync5 -listen` protocol (see docs/protocol.md)."""
from __future__ import annotations

import queue
import socket
import threading
from dataclasses import dataclass

MIN_FRAME = 5
MAX_FRAME = 4096
MAX_RESENDS = 12


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


class Session:
    """The active connection with one Next."""

    def __init__(self, sock: socket.socket, on_closed=None):
        self._sock = sock
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
        """The entries of a folder on the Next; RemoteError if it cannot be opened."""
        blocks = self._call(b"L" + _wire_path(path), timeout, terminals=(b"E", b"F"))
        if blocks[-1][:1] == b"F":
            raise RemoteError(f"cannot list {path}")
        entries: list[Entry] = []
        for block in blocks:
            if block[:1] == b"D":
                entries.extend(_parse_entries(block[1:]))
        return entries

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

    def close(self) -> None:
        """End the Session: the Next is told to quit at its next poll."""
        self._closing = True

    def wait_closed(self, timeout: float | None = None) -> bool:
        return self._closed.wait(timeout)

    # -- internals
    def _call(self, command: bytes, timeout: float | None, terminals=None):
        """Send one command and wait for its reply.

        Without `terminals` the reply is one block (returned as bytes, or None
        when the dot ignores the opcode). With `terminals`, blocks are read up
        to one whose opcode is a terminal; the list of blocks is returned."""
        call = _Call(command, terminals)
        with self._lock:
            if self._dead:
                raise ConnectionError("session closed")
            self._commands.put(call)
        if not call.done.wait(timeout):
            call.cancelled = True  # never sent if still queued
            raise TimeoutError(f"no reply to {command!r}")
        if call.error:
            raise call.error
        return call.result

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
                self._sock.sendall(encode_frame(call.command))
                self._finish(call)
                self._current = None
        except OSError:
            pass
        finally:
            self._shutdown()

    def _finish(self, call: _Call) -> None:
        """Read the Next's answer to a command; a raw message means no answer."""
        first = self._recv_exact(1)
        if first[0] < 0x20:  # a framed block: the high byte of its length
            blocks = [self._read_block(first, expected_no=0)]
            while call.terminals and blocks[-1][:1] not in call.terminals:
                blocks.append(self._read_block(self._recv_exact(1), expected_no=len(blocks)))
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


class _Call:
    def __init__(self, command: bytes, terminals=None):
        self.command = command
        self.terminals = terminals
        self.result = None
        self.error: Exception | None = None
        self.cancelled = False
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
