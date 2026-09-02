"""Tests for formiko.wakatime."""

import json
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

import pytest

from formiko.wakatime import (
    CATEGORY_BROWSING,
    HEARTBEAT_INTERVAL,
    WakaTime,
    WakaTimeStatus,
    _find_project,
)

# ---------------------------------------------------------------------------
# _find_project
# ---------------------------------------------------------------------------


def test_find_project_returns_git_repo_dir_name(tmp_path):
    """A file inside a git repo reports the repo's own directory name."""
    repo = tmp_path / "myproject"
    (repo / ".git").mkdir(parents=True)
    (repo / "docs").mkdir()
    file_path = repo / "docs" / "index.rst"

    assert _find_project(str(file_path)) == "myproject"


def test_find_project_falls_back_to_own_dir_without_git(tmp_path):
    """A file outside any git repo reports its own directory name."""
    directory = tmp_path / "notes"
    directory.mkdir()
    file_path = directory / "todo.md"

    assert _find_project(str(file_path)) == "notes"


# ---------------------------------------------------------------------------
# WakaTime.enabled
# ---------------------------------------------------------------------------


def test_disabled_without_api_key():
    """No API key means the client is disabled."""
    assert WakaTime("").enabled is False
    assert WakaTime().enabled is False


def test_enabled_with_api_key():
    """An API key means the client is enabled."""
    assert WakaTime("some-key").enabled is True


# ---------------------------------------------------------------------------
# WakaTime.heartbeat
# ---------------------------------------------------------------------------


@pytest.fixture
def wakatime_no_thread():
    """Build a WakaTime client whose _send() runs synchronously in-thread."""
    wt = WakaTime("some-key")
    with patch("formiko.wakatime.Thread") as thread_cls:
        def run_immediately(target, args, daemon):  # noqa: ARG001
            target(*args)
            return Mock()
        thread_cls.side_effect = run_immediately
        yield wt


def test_heartbeat_noop_when_disabled(tmp_path):
    """A disabled client never spawns a heartbeat thread."""
    wt = WakaTime("")
    with patch("formiko.wakatime.Thread") as thread_cls:
        wt.heartbeat(str(tmp_path / "doc.rst"))
        thread_cls.assert_not_called()


def test_heartbeat_noop_without_file_path(wakatime_no_thread):
    """An empty file path never triggers a request."""
    with patch("formiko.wakatime.urlopen") as urlopen_mock:
        wakatime_no_thread.heartbeat("")
        urlopen_mock.assert_not_called()


def test_heartbeat_sends_request_with_expected_payload(
    wakatime_no_thread, tmp_path,
):
    """A due heartbeat POSTs the expected URL, auth header and JSON body."""
    repo = tmp_path / "proj"
    (repo / ".git").mkdir(parents=True)
    file_path = str(repo / "doc.rst")

    with patch("formiko.wakatime.urlopen") as urlopen_mock:
        wakatime_no_thread.heartbeat(file_path, parser="rst", is_write=True)

    urlopen_mock.assert_called_once()
    request = urlopen_mock.call_args.args[0]
    assert request.full_url == (
        "https://api.wakatime.com/api/v1/users/current/heartbeats"
    )
    assert request.get_header("Authorization").startswith("Basic ")
    assert request.get_header("User-agent").startswith("wakatime/")
    assert "Formiko-wakatime/" in request.get_header("User-agent")
    assert request.get_header("X-machine-name")

    payload = json.loads(request.data)
    assert payload["entity"] == file_path
    assert payload["type"] == "file"
    assert payload["is_write"] is True
    assert payload["project"] == "proj"
    assert payload["language"] == "reStructuredText"


def test_heartbeat_omits_language_for_unknown_parser(
    wakatime_no_thread, tmp_path,
):
    """An unrecognized parser is sent without a language field."""
    with patch("formiko.wakatime.urlopen") as urlopen_mock:
        wakatime_no_thread.heartbeat(
            str(tmp_path / "doc.txt"), parser="txt",
        )

    payload = json.loads(urlopen_mock.call_args.args[0].data)
    assert "language" not in payload


def test_heartbeat_throttles_edits_within_interval(
    wakatime_no_thread, tmp_path,
):
    """A second non-write heartbeat for the same file is skipped in-window."""
    file_path = str(tmp_path / "doc.rst")

    with patch("formiko.wakatime.urlopen") as urlopen_mock, \
            patch("formiko.wakatime.time", return_value=1000.0):
        wakatime_no_thread.heartbeat(file_path)
    urlopen_mock.assert_called_once()

    with patch("formiko.wakatime.urlopen") as urlopen_mock, \
            patch("formiko.wakatime.time", return_value=1010.0):
        wakatime_no_thread.heartbeat(file_path)
    urlopen_mock.assert_not_called()


def test_heartbeat_sends_again_after_interval_elapses(
    wakatime_no_thread, tmp_path,
):
    """Once the throttle window elapses, the next heartbeat is sent."""
    file_path = str(tmp_path / "doc.rst")

    with patch("formiko.wakatime.urlopen"), \
            patch("formiko.wakatime.time", return_value=1000.0):
        wakatime_no_thread.heartbeat(file_path)

    later = 1000.0 + HEARTBEAT_INTERVAL
    with patch("formiko.wakatime.urlopen") as urlopen_mock, \
            patch("formiko.wakatime.time", return_value=later):
        wakatime_no_thread.heartbeat(file_path)
    urlopen_mock.assert_called_once()


def test_heartbeat_always_sends_on_write_even_within_interval(
    wakatime_no_thread, tmp_path,
):
    """A save (is_write=True) bypasses the throttle window."""
    file_path = str(tmp_path / "doc.rst")

    with patch("formiko.wakatime.urlopen"), \
            patch("formiko.wakatime.time", return_value=1000.0):
        wakatime_no_thread.heartbeat(file_path)

    with patch("formiko.wakatime.urlopen") as urlopen_mock, \
            patch("formiko.wakatime.time", return_value=1001.0):
        wakatime_no_thread.heartbeat(file_path, is_write=True)
    urlopen_mock.assert_called_once()


def test_heartbeat_not_throttled_across_different_files(
    wakatime_no_thread, tmp_path,
):
    """The throttle window is tracked per file, not globally."""
    with patch("formiko.wakatime.urlopen") as urlopen_mock, \
            patch("formiko.wakatime.time", return_value=1000.0):
        wakatime_no_thread.heartbeat(str(tmp_path / "one.rst"))
        wakatime_no_thread.heartbeat(str(tmp_path / "two.rst"))
    assert urlopen_mock.call_count == 2


def test_heartbeat_sends_category_in_payload(wakatime_no_thread, tmp_path):
    """A given category is included in the JSON payload verbatim."""
    with patch("formiko.wakatime.urlopen") as urlopen_mock:
        wakatime_no_thread.heartbeat(
            str(tmp_path / "doc.rst"), category=CATEGORY_BROWSING,
        )

    payload = json.loads(urlopen_mock.call_args.args[0].data)
    assert payload["category"] == CATEGORY_BROWSING


def test_heartbeat_omits_category_by_default(wakatime_no_thread, tmp_path):
    """No category means the field is omitted (API defaults to coding)."""
    with patch("formiko.wakatime.urlopen") as urlopen_mock:
        wakatime_no_thread.heartbeat(str(tmp_path / "doc.rst"))

    payload = json.loads(urlopen_mock.call_args.args[0].data)
    assert "category" not in payload


def test_heartbeat_throttle_window_is_separate_per_category(
    wakatime_no_thread, tmp_path,
):
    """A recent browsing heartbeat must not swallow a coding heartbeat.

    Both categories share the same file, so without a category-aware
    throttle key the second call here would be incorrectly skipped.
    """
    file_path = str(tmp_path / "doc.rst")

    with patch("formiko.wakatime.urlopen") as urlopen_mock, \
            patch("formiko.wakatime.time", return_value=1000.0):
        wakatime_no_thread.heartbeat(file_path, category=CATEGORY_BROWSING)
    urlopen_mock.assert_called_once()

    with patch("formiko.wakatime.urlopen") as urlopen_mock, \
            patch("formiko.wakatime.time", return_value=1001.0):
        wakatime_no_thread.heartbeat(file_path)
    urlopen_mock.assert_called_once()


def test_heartbeat_browsing_suppressed_right_after_coding(
    wakatime_no_thread, tmp_path,
):
    """A browsing heartbeat right after a coding one is suppressed.

    It is almost certainly that edit's own incidental scroll
    (cursor/preview auto-scroll), not a separate reading session.
    """
    file_path = str(tmp_path / "doc.rst")

    with patch("formiko.wakatime.urlopen") as urlopen_mock, \
            patch("formiko.wakatime.time", return_value=1000.0):
        wakatime_no_thread.heartbeat(file_path)
    urlopen_mock.assert_called_once()

    with patch("formiko.wakatime.urlopen") as urlopen_mock, \
            patch("formiko.wakatime.time", return_value=1002.6):
        wakatime_no_thread.heartbeat(file_path, category=CATEGORY_BROWSING)
    urlopen_mock.assert_not_called()

    later = 1000.0 + HEARTBEAT_INTERVAL
    with patch("formiko.wakatime.urlopen") as urlopen_mock, \
            patch("formiko.wakatime.time", return_value=later):
        wakatime_no_thread.heartbeat(file_path, category=CATEGORY_BROWSING)
    urlopen_mock.assert_called_once()


def test_send_swallows_url_errors():
    """A network failure is logged, not raised, since it runs in a thread."""
    with patch("formiko.wakatime.urlopen", side_effect=URLError("boom")):
        WakaTime._send({"entity": "x"}, "key", None)


# ---------------------------------------------------------------------------
# WakaTime status reporting (on_status)
# ---------------------------------------------------------------------------


def _run_heartbeat_sync(on_status, tmp_path, *, urlopen_side_effect=None):
    """Send one heartbeat with Thread/urlopen patched, calling on_status."""
    wt = WakaTime("some-key", on_status=on_status)
    with patch("formiko.wakatime.Thread") as thread_cls:
        def run_immediately(target, args, daemon):  # noqa: ARG001
            target(*args)
            return Mock()
        thread_cls.side_effect = run_immediately
        with patch(
            "formiko.wakatime.urlopen", side_effect=urlopen_side_effect,
        ):
            wt.heartbeat(str(tmp_path / "doc.rst"))


def test_heartbeat_reports_ok_on_success(tmp_path):
    """A successful heartbeat reports WakaTimeStatus.OK."""
    on_status = Mock()
    _run_heartbeat_sync(on_status, tmp_path)
    on_status.assert_called_once_with(WakaTimeStatus.OK)


def test_heartbeat_reports_auth_error_on_401(tmp_path):
    """An HTTP 401 reports WakaTimeStatus.AUTH_ERROR (invalid API key)."""
    on_status = Mock()
    error = HTTPError("url", 401, "Unauthorized", {}, None)
    _run_heartbeat_sync(on_status, tmp_path, urlopen_side_effect=error)
    on_status.assert_called_once_with(WakaTimeStatus.AUTH_ERROR)


def test_heartbeat_reports_network_error_on_other_http_error(tmp_path):
    """A non-auth HTTP error reports WakaTimeStatus.NETWORK_ERROR."""
    on_status = Mock()
    error = HTTPError("url", 500, "Server Error", {}, None)
    _run_heartbeat_sync(on_status, tmp_path, urlopen_side_effect=error)
    on_status.assert_called_once_with(WakaTimeStatus.NETWORK_ERROR)


def test_heartbeat_reports_network_error_on_url_error(tmp_path):
    """An unreachable host reports WakaTimeStatus.NETWORK_ERROR."""
    on_status = Mock()
    _run_heartbeat_sync(
        on_status, tmp_path, urlopen_side_effect=URLError("boom"),
    )
    on_status.assert_called_once_with(WakaTimeStatus.NETWORK_ERROR)
