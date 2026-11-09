# Third-party notices

## NextSync (protocol origin)

The network protocol that nexplorer speaks with the Next descends from NextSync by Jari Komppa, released under the Unlicense (public domain). The `.sync5` dot command used on the Next extends that protocol.

## ZX-Next-Unite

Parts of nexplorer reuse or derive from ZX-Next-Unite (its Remote Explorer listener and worker, and its console listener `nextsync5.py`), which is distributed under the MIT licence:

```
MIT License

Copyright (c) 2026 Julien Clauzel

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

## Lucide

The interface icons (`nexplorer/ui/svg/`) are a subset of Lucide, distributed under the ISC licence. Lucide includes portions derived from Feather (MIT, Copyright (c) 2013-2023 Cole Bemis).

```
ISC License

Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as part of Feather (MIT). All other copyright (c) for Lucide are held by Lucide Contributors 2022.

Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee is hereby granted, provided that the above copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
```

## Qt and PySide6

The graphical interface uses Qt through PySide6 (the Qt for Python bindings), which are distributed under the GNU Lesser General Public Licence version 3 (LGPLv3). nexplorer is not a modification of Qt or PySide6. The packaged builds ship them as separate, dynamically loaded libraries (in the `_internal` folder of the Windows zip and inside the AppImage), which you can replace with another build of the same version of the libraries. Sources and licence texts: <https://www.qt.io/> and <https://doc.qt.io/qtforpython-6/>.

## send2trash

Moving a file to the trash on the Local side uses Send2Trash, distributed under the BSD 3-Clause licence.

## Python

The packaged builds include the Python runtime, distributed under the Python Software Foundation Licence, and are assembled with PyInstaller (GPLv2 with an exception that allows the bundled program to be distributed under any licence).
