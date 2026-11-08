"""Fake Next: a TCP client standing in for the .sync5 dot in -listen mode.

Speaks the protocol documented in docs/protocol.md against an in-memory state.
"""
import socket
import threading
import time


def checksum(payload: bytes) -> tuple[int, int]:
    c0 = c1 = 0
    for x in payload:
        c0 ^= x
        c1 = (c1 + c0) & 0xFF
    return c0, c1


def frame(payload: bytes, packetno: int = 0) -> bytes:
    c0, c1 = checksum(payload)
    return (len(payload) + 5).to_bytes(2, "big") + payload + bytes([c0, c1, packetno])


class FakeNext:
    def __init__(
        self,
        port: int,
        version: str = "5.9.14",
        host: str = "127.0.0.1",
        ignores: frozenset[bytes] = frozenset(),
        drops_on: frozenset[bytes] = frozenset(),
        poll_interval: float = 0.005,
        ident_payload: bytes | None = None,
        corrupt_replies: int = 0,
        bad_header_total: int | None = None,
        fs: dict[str, bytes | None] | None = None,
        drives: str = "CM",
        current_drive: str = "C",
        free_blocks: dict[str, int] | None = None,
        truncate_puts_to: int | None = None,
        truncated_put_reports_failure: bool = True,
        put_retry_chunks: frozenset[int] = frozenset(),
        put_restart_at_chunk: int | None = None,
        put_chunk_delay: float = 0.0,
        put_stalls_at_chunk: int | None = None,
        get_drops_after_blocks: int | None = None,
    ):
        """`ignores`: opcodes an older dot does not know (silently ignored).
        `drops_on`: opcodes on which the link dies mid-command.
        `ident_payload`: raw reply to `Y` instead of the well-formed one.
        `corrupt_replies`: how many reply blocks go out with a bad checksum
        (the Next then resends it on `Resend`). `bad_header_total`: send a
        header announcing that total length instead of a real reply.
        `fs`: the Next's files, full path (lower case, drive-prefixed) to its
        content, or to None for a folder. `drives`, `current_drive`: what `W` answers. `free_blocks`: free
        512-byte blocks per drive letter for `Z` (others answer `F`). `truncate_puts_to`: a put keeps only that many bytes; the Next then gives up
        and pushes `F` (the partial file stays), or, when
        `truncated_put_reports_failure` is False, pretends to succeed (a silent
        short write that only a size check can notice). `put_retry_chunks`: indexes of put chunks the Next claims arrived with a bad
        checksum (it sends `Retry` once for each). `put_restart_at_chunk`: the
        Next claims a packetno mismatch at that chunk index (it sends `Restart`
        once and starts the file again). `put_chunk_delay`: seconds the Next takes
        before asking for each put chunk. `put_stalls_at_chunk`: the Next stops
        answering a put at that chunk index (until `drop`). `get_drops_after_blocks`: the link dies after that many `D`
        blocks of a get. `commands`: opcodes received, in order (idle `I` excluded)."""
        self.host, self.port, self.version = host, port, version
        self.ignores, self.drops_on, self.poll_interval = ignores, drops_on, poll_interval
        self.commands: list[bytes] = []
        self.resends = 0  # `Resend` requests received from the Listener
        self.ident_payload, self.corrupt_replies = ident_payload, corrupt_replies
        self.bad_header_total = bad_header_total
        self.drives, self.current_drive = drives, current_drive
        self.free_blocks = {k.upper(): v for k, v in (free_blocks or {}).items()}
        self.truncate_puts_to = truncate_puts_to
        self.truncated_put_reports_failure = truncated_put_reports_failure
        self.put_retry_chunks = set(put_retry_chunks)
        self.put_restart_at_chunk = put_restart_at_chunk
        self.put_chunk_delay, self.put_stalls_at_chunk = put_chunk_delay, put_stalls_at_chunk
        self.get_drops_after_blocks = get_drops_after_blocks
        self.retries_sent = 0
        self.listed: list[str] = []  # paths received by `L`, in order
        self.max_listing_block = 0  # largest `D` listing block sent, in bytes
        self.fs = {k.lower(): v for k, v in (fs or {}).items()}
        self.sock: socket.socket | None = None
        self.handshake_reply: bytes = b""
        self.ended = threading.Event()
        self._stop = False
        self._thread: threading.Thread | None = None

    # -- wire helpers
    def _recv_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("closed")
            buf += chunk
        return buf

    def _recv_frame(self) -> tuple[bytes, int]:
        total = int.from_bytes(self._recv_exact(2), "big")
        body = self._recv_exact(total - 2)
        payload, (cs0, cs1, no) = body[:-3], body[-3:]
        assert checksum(payload) == (cs0, cs1), "bad checksum from Listener"
        return payload, no

    # -- lifecycle
    def connect(self) -> bytes:
        """Dial the Listener, send Listen, return the handshake reply payload."""
        self.sock = socket.create_connection((self.host, self.port), timeout=5)
        self.sock.sendall(b"Listen")
        try:
            self.handshake_reply, _ = self._recv_frame()
        except ConnectionError:
            self.handshake_reply = b""
            self.ended.set()
            return b""
        if self.handshake_reply == b"Listening":
            self._thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._thread.start()
        else:
            self.sock.close()
            self.ended.set()
        return self.handshake_reply

    def bye(self) -> None:
        """BREAK pressed: send Bye, expect Later, close."""
        self._stop = True
        if self._thread:
            self._thread.join(timeout=2)
        self.sock.sendall(b"Bye")
        try:
            self._recv_frame()
        except (ConnectionError, OSError):
            pass
        self.sock.close()
        self.ended.set()

    def drop(self) -> None:
        """Vanish without a goodbye."""
        self._stop = True
        self.sock.close()
        self.ended.set()

    # -- poll loop
    def _poll_loop(self) -> None:
        try:
            while not self._stop:
                self.sock.sendall(b"Poll")
                payload, _ = self._recv_frame()
                op, arg = payload[:1], payload[1:]
                if op == b"I":
                    time.sleep(self.poll_interval)
                    continue
                self.commands.append(op)
                if op in self.ignores:
                    continue
                if op in self.drops_on:
                    self.sock.close()
                    self.ended.set()
                    return
                if op == b"Y":
                    if self.bad_header_total is not None:
                        self.sock.sendall(self.bad_header_total.to_bytes(2, "big"))
                        continue
                    self._push_status(
                        self.ident_payload
                        if self.ident_payload is not None
                        else b"O" + b"sync\x00" + self.version.encode()
                    )
                elif op == b"L":
                    self._list(arg.decode("ascii"))
                elif op == b"W":
                    self._push_status(b"O" + self.current_drive.encode() + self.drives.encode())
                elif op == b"Z":
                    drive = (arg.decode("ascii") or self.current_drive).upper()
                    if drive in self.free_blocks:
                        self._push_status(b"O" + self.free_blocks[drive].to_bytes(4, "little"))
                    else:
                        self._push_status(b"F")
                elif op == b"G":
                    self._get(arg.decode("ascii"))
                elif op == b"M":
                    self._mkdir(arg.decode("ascii"))
                elif op == b"P":
                    self._put(arg.decode("ascii"))
                elif op == b"Q":
                    self.sock.close()
                    self.ended.set()
                    return
        except (ConnectionError, OSError, AssertionError):
            self.ended.set()

    def _push_status(self, payload: bytes, no: int = 0) -> None:
        while True:
            data = frame(payload, no)
            if self.corrupt_replies > 0:
                self.corrupt_replies -= 1
                data = data[:-3] + bytes([data[-3] ^ 0xFF]) + data[-2:]
            self.sock.sendall(data)
            answer, _ = self._recv_frame()
            if answer != b"Resend":
                return
            self.resends += 1

    def _list(self, path: str) -> None:
        self.listed.append(path)
        folder = path.lower().rstrip("/")
        is_root = len(folder) == 2 and folder[1] == ":"
        if not is_root and self.fs.get(folder, b"") is not None:
            self._push_status(b"F")
            return
        blocks: list[bytes] = []
        packed = b""
        for full, content in self.fs.items():
            parent, _, name = full.rpartition("/")
            if parent != folder:
                continue
            raw = name.encode("ascii")
            size = 0 if content is None else len(content)
            entry = bytes([content is None]) + size.to_bytes(4, "little") + bytes([len(raw)]) + raw
            if packed and len(packed) + len(entry) > 1000:  # the dot's block limit
                blocks.append(b"D" + packed)
                packed = b""
            packed += entry
        if packed:
            blocks.append(b"D" + packed)
        for block in blocks:
            self.max_listing_block = max(self.max_listing_block, len(block))
            self._push_status(block)
        self._push_status(b"E")

    def _put(self, path: str) -> None:
        """The Next creates the file, then pulls it chunk by chunk with `Get`."""
        key = path.lower()
        self.fs[key] = b""
        counter = index = 0
        while True:
            time.sleep(self.put_chunk_delay)
            if index == self.put_stalls_at_chunk:
                while not self._stop:
                    time.sleep(0.01)
                return
            self.sock.sendall(b"Get")
            payload, no = self._recv_frame()
            assert no == counter, "unexpected packetno from Listener"
            if index in self.put_retry_chunks:
                self.put_retry_chunks.discard(index)
                self.retries_sent += 1
                self.sock.sendall(b"Retry")
                again, again_no = self._recv_frame()
                assert (again, again_no) == (payload, no), "Retry must resend the same chunk"
            if index == self.put_restart_at_chunk:
                self.put_restart_at_chunk = None
                self.sock.sendall(b"Restart")
                back, _ = self._recv_frame()
                assert back == b"Back"
                self.fs[key] = b""
                counter = index = 0
                continue
            if not payload:  # the empty frame ends the file
                return
            limit = self.truncate_puts_to
            if limit is not None and len(self.fs[key]) + len(payload) > limit:
                self.fs[key] += payload[: limit - len(self.fs[key])]
                if self.truncated_put_reports_failure:
                    self._push_status(b"F")  # the Next gives up, file left partial
                    return
                counter = (counter + 1) & 0xFF
                index += 1
                continue
            self.fs[key] += payload
            counter = (counter + 1) & 0xFF
            index += 1

    def _get(self, path: str) -> None:
        """Stream a file as `N`, `D`..., `E`, then `B`; a missing path gives a lone `B`."""
        content = self.fs.get(path.lower())
        no = 0
        if content is not None:
            name = path.rsplit("/", 1)[-1].encode("ascii")
            self._push_status(b"N" + bytes(4) + bytes([len(name)]) + name, no)
            no += 1
            for n, i in enumerate(range(0, len(content), 1024)):
                if n == self.get_drops_after_blocks:
                    self.sock.close()
                    self.ended.set()
                    raise ConnectionError("dropped mid-get")
                self._push_status(b"D" + content[i : i + 1024], no)
                no += 1
            self._push_status(b"E", no)
            no += 1
        self._push_status(b"B", no)

    def _mkdir(self, path: str) -> None:
        key = path.lower().rstrip("/")
        parent = key.rpartition("/")[0]
        parent_ok = (len(parent) == 2 and parent[1] == ":") or self.fs.get(parent, b"") is None
        if key in self.fs or not parent_ok:  # esxDOS: the same error for "exists" and others
            self._push_status(b"F")
            return
        self.fs[key] = None
        self._push_status(b"O")
