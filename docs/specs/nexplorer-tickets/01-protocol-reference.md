Label: ready-for-agent

# 01: Protocol reference

**What to build:** A written `docs/protocol.md` describing the `.sync5 -listen` wire protocol as the Next actually speaks it, produced from the three existing sources (the Unite server, the Unite worker, the dotN C source). It covers opcodes, framing, handshake, error cases, the 512-byte frame size and why, and version differences. It also states which `.sync5` versions support rename, CRC, copy on the Next and free space, which fixes the minimum version used later by capability gating. It documents the dot behaviours real hardware showed as hard (clones corrupting long bursts, OS-protected writes) so the fake Next can simulate them. It is the single reference for both the fake Next and the protocol module.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Every operation the app needs is documented: listing, drives, free space, version/identification, get, put, make folder, remove file, remove folder, recursive remove, rename, copy on the Next, size of a tree, CRC-32
- [ ] Framing, handshake and error cases are described precisely enough to implement a client and a fake peer without reading the sources
- [ ] Differences between `.sync5` versions are listed, with the minimum version per feature
- [ ] Written in English
