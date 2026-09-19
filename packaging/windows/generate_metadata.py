"""Generate the Windows version resource and Inno Setup metadata.

Run from the repository root. Reads the project metadata (version, author,
copyright, homepage, description) from formiko/__init__.py - the same
values the About dialog shows - and writes, into the current directory:

- version_info.txt: PyInstaller ``--version-file`` for formiko.exe
  (the Details tab of its file properties, Task Manager, UAC prompts).
- formiko_meta.iss: ``#define`` lines included by formiko.iss.
"""

import ast
from pathlib import Path

PRODUCT_NAME = "Formiko"
EXE_NAME = "formiko.exe"


def read_metadata():
    """Return the string constants assigned in formiko/__init__.py."""
    tree = ast.parse(Path("formiko/__init__.py").read_text(encoding="utf-8"))
    return {
        target.id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Constant)
        for target in node.targets
        if isinstance(target, ast.Name)
    }


def numeric_version(version):
    """Return *version* as the four integers Windows version info needs.

    "2.1.0.dev" -> (2, 1, 0, 0): parsing stops at the first non-numeric
    part, the rest is zero-padded.
    """
    parts = []
    for token in version.split("."):
        if not token.isdigit():
            break
        parts.append(int(token))
    return tuple((parts + [0] * 4)[:4])


def build_info():
    """Collect every value both output files are built from."""
    meta = read_metadata()
    author = meta["__author__"]
    name, _, email = author.partition(" <")
    return {
        "version": meta["__version__"],
        "numeric": numeric_version(meta["__version__"]),
        "publisher": name,
        "contact": email.rstrip(">"),
        "url": meta["__url__"],
        "comments": meta["__comment__"],
        "copyright": f"Copyright {meta['__copyright__']} The Formiko Team",
    }


def version_info(info):
    """Return the PyInstaller version file text for formiko.exe."""
    strings = {
        "CompanyName": info["publisher"],
        "FileDescription": (
            "Formiko - reStructuredText and Markdown editor"
            " and live previewer"
        ),
        "FileVersion": info["version"],
        "InternalName": "formiko",
        "LegalCopyright": info["copyright"],
        "OriginalFilename": EXE_NAME,
        "ProductName": PRODUCT_NAME,
        "ProductVersion": info["version"],
        "Comments": f"{info['comments']} {info['url']}",
    }
    rows = ",\n".join(
        f"        StringStruct({ascii(key)}, {ascii(value)})"
        for key, value in strings.items()
    )
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={info["numeric"]},
    prodvers={info["numeric"]},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
{rows}
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def inno_defines(info):
    """Return the ``#define`` lines formiko.iss includes."""
    defines = {
        "MyAppName": PRODUCT_NAME,
        "MyAppVersion": info["version"],
        "MyAppNumericVersion": ".".join(map(str, info["numeric"])),
        "MyAppPublisher": info["publisher"],
        "MyAppContact": info["contact"],
        "MyAppURL": info["url"],
        "MyAppComments": info["comments"],
        "MyAppCopyright": info["copyright"],
        "MyAppExeName": EXE_NAME,
    }
    for value in defines.values():
        assert '"' not in value, value  # noqa: S101 - would break the .iss
    return "".join(f'#define {k} "{v}"\n' for k, v in defines.items())


if __name__ == "__main__":
    build = build_info()
    Path("version_info.txt").write_text(version_info(build), encoding="utf-8")
    # BOM: Inno Setup reads BOM-less files as ANSI, mangling the diacritics
    # in the publisher's name.
    Path("formiko_meta.iss").write_text(
        inno_defines(build), encoding="utf-8-sig",
    )
