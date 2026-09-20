"""Tests for the system section of the About dialog's debug info."""

import platform

import pytest

from formiko import dialogs

FLATPAK_INFO = """\
[Application]
name=cz.zeropage.Formiko
runtime=runtime/org.gnome.Platform/x86_64/48
"""


@pytest.fixture(autouse=True)
def _no_flatpak(monkeypatch, tmp_path):
    """Pretend to run outside a Flatpak sandbox unless a test says so."""
    monkeypatch.setattr(dialogs, "FLATPAK_INFO", str(tmp_path / "missing"))


def _flatpak(monkeypatch, tmp_path, content=FLATPAK_INFO):
    info = tmp_path / ".flatpak-info"
    info.write_text(content)
    monkeypatch.setattr(dialogs, "FLATPAK_INFO", str(info))


def _os_release(monkeypatch, **values):
    monkeypatch.setattr(
        platform, "freedesktop_os_release", lambda: values, raising=False,
    )


def test_linux_shows_distribution_and_kernel(monkeypatch):
    """A native Linux install names its distribution and kernel."""
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(platform, "release", lambda: "6.8.0")
    _os_release(monkeypatch, PRETTY_NAME="Fedora Linux 42")

    assert dialogs._system_info() == [
        "System: Linux",
        "  Release: Fedora Linux 42",
        "  Kernel:  6.8.0",
    ]


def test_linux_without_os_release_still_names_the_system(monkeypatch):
    """A missing os-release file only leaves the distribution out."""
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(platform, "release", lambda: "6.8.0")

    def missing():
        raise OSError

    monkeypatch.setattr(
        platform, "freedesktop_os_release", missing, raising=False,
    )

    assert dialogs._system_info() == ["System: Linux", "  Kernel:  6.8.0"]


def test_flatpak_is_marked_and_names_its_runtime(monkeypatch, tmp_path):
    """Inside a Flatpak the sandbox and its runtime are reported."""
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(platform, "release", lambda: "6.8.0")
    _os_release(monkeypatch, PRETTY_NAME="Freedesktop SDK 24.08")
    _flatpak(monkeypatch, tmp_path)

    lines = dialogs._system_info()

    assert lines[0] == "System: Linux (Flatpak)"
    assert lines[-1] == (
        "  Flatpak runtime: runtime/org.gnome.Platform/x86_64/48"
    )


def test_unreadable_flatpak_info_is_not_fatal(monkeypatch, tmp_path):
    """A Flatpak without a runtime entry is still marked as one."""
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(platform, "release", lambda: "6.8.0")
    _os_release(monkeypatch, PRETTY_NAME="Fedora Linux 42")
    _flatpak(monkeypatch, tmp_path, content="not a key file")

    lines = dialogs._system_info()

    assert lines[0] == "System: Linux (Flatpak)"
    assert not any("runtime" in line for line in lines)


def test_windows_shows_version_and_build(monkeypatch):
    """Windows reports its release and build number."""
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        platform, "win32_ver", lambda: ("11", "10.0.22631", "SP0", ""),
    )

    assert dialogs._system_info() == [
        "System: Windows",
        "  Release: Windows 11 (10.0.22631)",
    ]


def test_macos_shows_its_version(monkeypatch):
    """MacOS is called Darwin by Python but not by its users."""
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        platform, "mac_ver", lambda: ("14.5", ("", "", ""), ""),
    )

    assert dialogs._system_info() == [
        "System: Darwin",
        "  Release: macOS 14.5",
    ]


def test_debug_info_starts_with_the_system(monkeypatch):
    """The system is the first thing a bug report shows."""
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        platform, "win32_ver", lambda: ("10", "10.0.1", "", ""),
    )

    first, second = dialogs._build_debug_info().splitlines()[:2]

    assert first == "System: Windows"
    assert second.startswith("  Release:")
