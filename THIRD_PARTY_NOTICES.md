# Third-party notices

## NextSync (protocol origin)

The network protocol that nexplorer speaks with the Next descends from NextSync by Jari Komppa, released under the Unlicense (public domain). The `.sync5` dot command used on the Next extends that protocol.

## ZX-Next-Unite

Parts of nexplorer reuse or derive from ZX-Next-Unite (its Remote Explorer listener and worker, and its console listener `nextsync5.py`), which is distributed under the MIT licence:

```
MIT License

Copyright (c) <YEAR> <COPYRIGHT HOLDER OF ZX-NEXT-UNITE>   [PLACEHOLDER: to be filled in by the repository owner from the ZX-Next-Unite LICENSE file]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

The `.sync5` listen mode and its opcodes were added by Julien Clauzel; they are documented in [docs/protocol.md](docs/protocol.md).
