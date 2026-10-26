#!/bin/bash
set -euo pipefail
VER="${1:?version}"
APPIMAGETOOL="${2:?path to appimagetool}"
OUT=out
rm -rf build/AppDir build/deb "$OUT"
mkdir -p "$OUT"

A=build/AppDir
mkdir -p "$A/usr/lib/fishyu-translate" "$A/usr/share/applications" "$A/usr/share/icons/hicolor/256x256/apps"
cp -a dist/FishyuTranslate/. "$A/usr/lib/fishyu-translate/"
sed 's/^Exec=.*/Exec=AppRun %U/' packaging/linux/fishyu-translate.desktop > "$A/fishyu-translate.desktop"
cp packaging/linux/fishyu-translate.desktop "$A/usr/share/applications/"
mkdir -p "$A/usr/share/doc/fishyu-translate"
cp ../LICENSE ../THIRD_PARTY_NOTICES.md "$A/usr/share/doc/fishyu-translate/"
cp assets/app_icon.png "$A/fishyu-translate.png"
cp assets/app_icon.png "$A/usr/share/icons/hicolor/256x256/apps/fishyu-translate.png"
cat > "$A/AppRun" <<'RUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/lib/fishyu-translate/FishyuTranslate" "$@"
RUN
chmod +x "$A/AppRun"
ARCH=x86_64 "$APPIMAGETOOL" --appimage-extract-and-run --no-appstream "$A" "$OUT/FishyuTranslate-for-Linux-x86_64-v$VER.AppImage"

D=build/deb
mkdir -p "$D/DEBIAN" "$D/opt/fishyu-translate" "$D/usr/bin" "$D/usr/share/applications" "$D/usr/share/icons/hicolor/256x256/apps"
cp -a dist/FishyuTranslate/. "$D/opt/fishyu-translate/"
cat > "$D/usr/bin/fishyu-translate" <<'BIN'
#!/bin/sh
exec /opt/fishyu-translate/FishyuTranslate "$@"
BIN
chmod 755 "$D/usr/bin/fishyu-translate"
cp packaging/linux/fishyu-translate.desktop "$D/usr/share/applications/"
cp assets/app_icon.png "$D/usr/share/icons/hicolor/256x256/apps/fishyu-translate.png"
DOC="$D/usr/share/doc/fishyu-translate"
mkdir -p "$DOC"
{
  echo "Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/"
  echo "Upstream-Name: Fishyu Translate"
  echo "Source: https://github.com/thanhhfishyu/Fishyu-Translate"
  echo
  echo "Files: *"
  echo "Copyright: 2026 thanhhfishyu"
  echo "License: MIT"
  sed -e '1,2d' -e 's/^$/./' -e 's/^/ /' ../LICENSE
  echo
  echo "Files: opt/fishyu-translate/_internal/*"
  echo "Copyright: see /usr/share/doc/fishyu-translate/THIRD_PARTY_NOTICES.md"
  echo "License: various"
  echo " Third-party libraries, models, data and fonts keep their own licenses,"
  echo " listed in /usr/share/doc/fishyu-translate/THIRD_PARTY_NOTICES.md."
} > "$DOC/copyright"
cp ../THIRD_PARTY_NOTICES.md "$DOC/"
chmod 644 "$DOC"/*
SIZE=$(du -sk "$D/opt" | cut -f1)
cat > "$D/DEBIAN/control" <<CTRL
Package: fishyu-translate
Version: $VER
Section: utils
Priority: optional
Architecture: amd64
Installed-Size: $SIZE
Depends: libxcb-cursor0, libxkbcommon-x11-0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0, libxcb-render-util0, libxcb-shape0, libxcb-xinerama0, libxcb-xkb1, libegl1, libgl1, libfontconfig1, libdbus-1-3
Recommends: fonts-noto-cjk, wl-clipboard
Maintainer: thanhhfishyu <thanhhfishyu@gmail.com>
Homepage: https://github.com/thanhhfishyu/Fishyu-Translate
Description: Fishyu Translate for Linux
 Dịch chữ tiếng Trung, tiếng Nhật trên màn hình sang tiếng Việt: khoanh vùng,
 dịch trực tiếp cho game, tra từ, DeepL hoặc dịch offline.
CTRL
find "$D" -type d -exec chmod 755 {} +
dpkg-deb --root-owner-group --build "$D" "$OUT/fishyu-translate_${VER}_amd64.deb"

tar -C dist -czf "$OUT/FishyuTranslate-for-Linux-x86_64-v$VER.tar.gz" FishyuTranslate
ls -la "$OUT"
