#!/usr/bin/env bash
# Builds dist/nexplorer-vX.Y.Z-linux-x86_64.AppImage on a Linux x86_64 machine.
# The version comes from pyproject.toml. The distributable file is built in CI on an
# old Ubuntu image (low glibc requirement); a build on a recent machine is a
# functional check only.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

version="$(sed -n 's/^version *= *"\(.*\)"/\1/p' pyproject.toml | head -n1)"
[ -n "$version" ] || { echo "version not found in pyproject.toml" >&2; exit 1; }
name="nexplorer-v$version-linux-x86_64"
build="$root/build"
venv="$build/venv"
appdir="$build/AppDir"

rm -rf "$build/lib" "$build/pyinstaller" "$appdir" "$root/dist/$name.AppImage"
mkdir -p "$build" "$root/dist"

# Build dependencies
[ -d "$venv" ] || python3 -m venv "$venv"
"$venv/bin/pip" install --quiet --upgrade pip
"$venv/bin/pip" install --quiet "$root" pyinstaller

# Bundle (directory mode)
"$venv/bin/pyinstaller" --noconfirm --clean \
    --distpath "$build/pyinstaller/dist" --workpath "$build/pyinstaller/work" \
    packaging/nexplorer.spec

# AppDir
mkdir -p "$appdir/usr/bin" "$appdir/usr/lib"
cp -r "$build/pyinstaller/dist/nexplorer" "$appdir/usr/bin/nexplorer"
cp LICENSE THIRD_PARTY_NOTICES.md README.md "$appdir/usr/bin/nexplorer/"
cp packaging/icon.png "$appdir/nexplorer.png"
cat > "$appdir/nexplorer.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=nexplorer
Comment=File manager for a ZX Spectrum Next
Exec=nexplorer
Icon=nexplorer
Categories=Utility;FileTools;
DESKTOP
cat > "$appdir/AppRun" <<'APPRUN'
#!/bin/sh
here="$(dirname "$(readlink -f "$0")")"
export LD_LIBRARY_PATH="$here/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$here/usr/bin/nexplorer/nexplorer" "$@"
APPRUN
chmod +x "$appdir/AppRun"

# libxcb-cursor (needed by Qt's xcb platform plugin) and its own xcb dependencies
cursor="$(ldconfig -p | awk '/libxcb-cursor\.so\.0 / && /x86-64/ {print $NF}' | head -n1)"
[ -n "$cursor" ] || { echo "libxcb-cursor.so.0 not found (apt install libxcb-cursor0)" >&2; exit 1; }
cp -L "$cursor" "$appdir/usr/lib/"
for dep in $(ldd "$cursor" | awk '/libxcb-(image|render-util|util|icccm|keysyms)/ {print $3}'); do
    cp -L "$dep" "$appdir/usr/lib/"
done

# appimagetool
tool="$build/appimagetool-x86_64.AppImage"
if [ ! -x "$tool" ]; then
    curl -fsSL -o "$tool" \
        https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x "$tool"
fi
ARCH=x86_64 "$tool" --appimage-extract-and-run "$appdir" "$root/dist/$name.AppImage"

echo "bundle:   $(du -sh "$appdir/usr/bin/nexplorer" | cut -f1)"
echo "AppImage: $(du -h "$root/dist/$name.AppImage" | cut -f1)  dist/$name.AppImage"
