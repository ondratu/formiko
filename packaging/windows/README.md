# Windows package

The Windows installer is built by
`.github/workflows/build-windows-installer.yml` on an MSYS2 (MINGW64)
runner. It packages the litehtml + SourceView variant of Formiko (no WebKit,
no Vte/vim) with PyInstaller and wraps it in an Inno Setup installer.

Neither the installer nor `formiko.exe` is code-signed, so SmartScreen flags
them as untrusted. Use "More info" -> "Run anyway" the first time.

## Files

| File                      | Purpose                                                         |
|---------------------------|-----------------------------------------------------------------|
| `stage_runtime.sh`        | Stages the native files PyInstaller does not collect itself.    |
| `enchant_winspell.cpp`    | Thread-safe Enchant provider for the Windows spell checker.     |
| `generate_metadata.py`    | Version resource and Inno Setup defines from `formiko/__init__.py`. |
| `make_wizard_images.py`   | Installer wizard images.                                        |
| `formiko.iss`             | Inno Setup script.                                              |

The build is not tied to the CI. Run the steps from the workflow in an MSYS2
MINGW64 shell from the repository root to build locally.

## Release flow

1. Push a tag. The workflow builds the installer and keeps it as a workflow
   artifact.
2. Create a release (a draft is fine) from the tag on GitHub.
3. The workflow waits for that release (up to 30 minutes) and attaches
   `formiko-<version>-windows-x64-setup.exe` to it, draft or not. If it does
   not find the release in time, create it and re-run the failed job.
4. Test the installer from the draft, then publish the release.

The version in the file name comes from `formiko/__init__.py`, not from the
tag.

## Why the build looks the way it does

### litehtmlpy

Its CMake build must link against the MinGW import library the interpreter
actually uses. Its own Python detection falls back to the standard CPython
name, which does not exist on MSYS2, and silently links a second,
uninitialized copy of the runtime; hence `-DPython_LIBRARY=...`. Its Cairo
container class has to be enabled explicitly outside Linux
(`-DLITEHTMLPY_INCLUDE_CAIRO_CONTAINERS=ON`).

The compiled extension ships under the standard CPython Windows platform tag,
which MSYS2's Python does not recognize. It is renamed to the bare
`litehtmlpy.pyd` fallback that every build recognizes.

### Staged runtime files

GTK4's native DLLs and GI typelibs live in the MSYS2 prefix, outside any pip
package. None of the following has a "look next to the exe" fallback, so
`formiko/__main__.py` points at them through environment variables:

- **fontconfig config** - MSYS2's Pango uses the fontconfig/FreeType
  backend, not DirectWrite, so without `fonts.conf` it finds no fonts at all.
- **Compiled GSettings schemas** - libadwaita/GTK look up
  `org.gnome.desktop.interface` internally even on Windows, and an unknown
  schema is a fatal GLib error.
- **`share/`** - GtkSourceView's RelaxNG schemas (its `.lang` files load from
  a GResource bundle, but the schemas that validate them are real files) and
  the icon themes (toolbar and menu icons come from GTK's icon theme lookup,
  not from any resource bundle). The app icon (About dialog) and the symbolic
  toolbar icons the MSYS2 Adwaita theme lacks are added to the hicolor
  fallback theme.
- **Licences** of the MSYS2 packages, shown by the installer.

`formiko/data` (About dialog authors, JSON folding assets) is added to the
bundle explicitly, since PyInstaller only collects Python modules.

### Spell checking (Enchant)

Enchant has no environment variable for its provider modules. It finds them
relative to libenchant's own DLL, and only if that sits in a directory named
`bin` with `lib/enchant-2` next to it (MSYS2's own layout; in a flat
directory it reports "no providers found"). Hence PyInstaller's
`--contents-directory bin` and copying the `enchant` prefix tree beside it.

The `winspell` provider uses the Windows spell checker API, so the
dictionaries are the languages installed in Windows itself. Hunspell with
`en_US`/`en_GB` is only a fallback for English (see `enchant.ordering`).

Upstream's winspell fails on every thread but the one that loaded it.
libspelling checks words on worker threads, so every word came out
misspelled. `enchant_winspell.cpp` is a thread-safe rewrite built against
`enchant-provider.h` from the matching Enchant release, since MSYS2 does not
ship that header.

### PyInstaller

`MSYS2_ARG_CONV_EXCL="*"` is set because `--add-data` takes a single
`src;dest` argument, which MSYS2's automatic POSIX -> Windows path
conversion corrupts.
