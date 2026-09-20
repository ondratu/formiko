#!/usr/bin/env bash
# Stage everything the PyInstaller bundle needs that is not a Python package.
#
# Run from the repository root inside an MSYS2 MINGW64 shell (MINGW_PREFIX
# set). Writes dist-runtime/, which the PyInstaller step adds to the bundle.
# See packaging/windows/README.md for why each part is needed.
set -euo pipefail

runtime=dist-runtime
mkdir -p "$runtime/dlls" "$runtime/share"

# GTK4 native DLLs and GObject Introspection typelibs.
cp "$MINGW_PREFIX"/bin/*.dll "$runtime/dlls/"
cp -r "$MINGW_PREFIX"/lib/girepository-1.0 "$runtime/gi_typelibs"

# fontconfig, GSettings schemas, GtkSourceView data and icon themes.
cp -r "$MINGW_PREFIX"/etc/fonts "$runtime/fontconfig"
glib-compile-schemas "$MINGW_PREFIX/share/glib-2.0/schemas"
cp -r "$MINGW_PREFIX"/share/glib-2.0/schemas "$runtime/glib-schemas"
cp -r "$MINGW_PREFIX"/share/gtksourceview-5 "$runtime/share/gtksourceview-5"
cp -r "$MINGW_PREFIX"/share/icons "$runtime/share/icons"

# The app icon and the symbolic toolbar icons the MSYS2 Adwaita theme lacks
# go into hicolor, the fallback theme.
hicolor=$runtime/share/icons/hicolor
mkdir -p "$hicolor"/scalable/apps "$hicolor"/scalable/actions
cp icons/formiko.svg "$hicolor"/scalable/apps/
cp icons/symbolic/*.svg "$hicolor"/scalable/actions/
rm -f "$hicolor"/icon-theme.cache

# Licence texts of the bundled MSYS2 packages, shown by the installer.
cp -r "$MINGW_PREFIX"/share/licenses "$runtime/licenses"

# Spell checking (libspelling -> Enchant), laid out like an install prefix;
# the workflow copies it next to the PyInstaller output.
enchant=$runtime/enchant
mkdir -p "$enchant"/lib/enchant-2 "$enchant"/share/enchant-2 "$runtime"/share/hunspell
cp "$MINGW_PREFIX"/lib/enchant-2/enchant_hunspell.dll "$enchant"/lib/enchant-2/
# hunspell only looks for dictionaries in XDG_DATA_DIRS/hunspell
cp "$MINGW_PREFIX"/share/hunspell/en_US.* "$MINGW_PREFIX"/share/hunspell/en_GB.* \
    "$runtime"/share/hunspell/
echo '*:winspell,hunspell' > "$enchant"/share/enchant-2/enchant.ordering

# winspell: our thread-safe build of Enchant's Windows provider. MSYS2 ships
# no enchant-provider.h, so take it from the matching Enchant release.
build=$(mktemp -d)
ver=$(pacman -Q mingw-w64-x86_64-enchant | cut -d' ' -f2 | cut -d- -f1)
curl -fsSL \
    "https://raw.githubusercontent.com/rrthomas/enchant/v$ver/lib/enchant-provider.h" \
    -o "$build"/enchant-provider.h
: > "$build"/config.h
# shellcheck disable=SC2046  # pkg-config output must be word-split
g++ -shared -O2 -std=c++17 \
    -I"$build" -I"$MINGW_PREFIX"/include/enchant-2 $(pkg-config --cflags glib-2.0) \
    -D_WIN32_WINNT=0x0602 -DNTDDI_VERSION=0x06020000 -D_ENCHANT_BUILD=1 \
    -o "$enchant"/lib/enchant-2/enchant_winspell.dll \
    packaging/windows/enchant_winspell.cpp \
    -L"$MINGW_PREFIX"/lib -lenchant-2 $(pkg-config --libs glib-2.0) \
    -lole32 -loleaut32 -luuid
