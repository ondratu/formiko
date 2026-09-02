"""Minimal WakaTime (https://wakatime.com) heartbeat client.

Talks directly to the WakaTime REST API instead of shelling out to
wakatime-cli - one HTTP POST per heartbeat, no subprocess, no extra
dependency. There is no separate idle/active window detection: heartbeats
piggyback on Formiko's existing edit-detection loop and save signal, so
when the user stops editing, heartbeats simply stop being triggered.
"""

import platform
import socket
from base64 import b64encode
from enum import Enum
from json import dumps
from os.path import basename, dirname, isdir, join
from threading import Thread
from time import time
from traceback import print_exc
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from formiko import __version__

HEARTBEAT_URL = "https://api.wakatime.com/api/v1/users/current/heartbeats"
# Editor and OS are parsed by WakaTime out of the User-Agent, not out of any
# JSON field - format mirrors what wakatime-cli/editor plugins send: a
# "<name>-wakatime/<version>" token is how WakaTime recognizes the editor
# (shown on the dashboard as "Formiko"), and the "(...)" part is parsed for
# the OS. See https://wakatime.com/help/creating-plugin.
USER_AGENT = (
    f"wakatime/{__version__} ({platform.platform()}) "
    f"Python{platform.python_version()} "
    f"Formiko/{__version__} Formiko-wakatime/{__version__}"
)
# Hostname is not part of the JSON body either - it goes in this header.
MACHINE_NAME = socket.gethostname()
HEARTBEAT_INTERVAL = 120  # seconds; same throttle window as wakatime-cli
AUTH_ERROR_CODES = (401, 403)
# Reading/scrolling without editing - valid "category" value per
# https://wakatime.com/developers#heartbeats. Omitted (None) elsewhere,
# which the API defaults to "coding".
CATEGORY_BROWSING = "browsing"

LANGUAGES = {
    "rst": "reStructuredText",
    "m2r": "Markdown",
    "html": "HTML",
    "json": "JSON",
}


class WakaTimeStatus(Enum):
    """Outcome of the last WakaTime heartbeat request."""

    OK = "ok"
    AUTH_ERROR = "auth_error"  # invalid API key - needs user action
    NETWORK_ERROR = "network_error"  # unreachable/timeout/server error


def _find_project(file_path):
    """Return the git repo's directory name for *file_path*, else own dir."""
    directory = dirname(file_path) or "."
    current = directory
    while True:
        if isdir(join(current, ".git")):
            return basename(current) or current
        parent = dirname(current)
        if not parent or parent == current:
            return basename(directory) or None
        current = parent


class WakaTime:
    """Sends throttled WakaTime heartbeats for edited/saved files."""

    def __init__(self, api_key="", on_status=None):
        self.api_key = api_key
        self.on_status = on_status
        self._last_sent = {}  # file_path -> last heartbeat unix time

    @property
    def enabled(self):
        """True when an API key is configured."""
        return bool(self.api_key)

    def heartbeat(self, file_path, parser=None, is_write=False, category=None):
        """Record activity in *file_path*; send a heartbeat if due.

        A plain (coding) heartbeat is throttled only by its own last send
        time, so it is never delayed by prior "browsing" activity. A
        *category* heartbeat (e.g. "browsing" from scrolling) is also
        throttled against the last plain heartbeat, so it cannot fire
        moments after a real edit just because the edit itself caused an
        incidental scroll (cursor/preview auto-scroll).
        """
        if not self.enabled or not file_path:
            return
        now = time()
        key = (file_path, category)
        last_sent = self._last_sent.get(key, 0)
        if category:
            coding_key = (file_path, None)
            last_sent = max(last_sent, self._last_sent.get(coding_key, 0))
        if not is_write and now - last_sent < HEARTBEAT_INTERVAL:
            return
        self._last_sent[key] = now

        payload = {
            "entity": file_path,
            "type": "file",
            "time": now,
            "is_write": is_write,
            "project": _find_project(file_path),
        }
        if category:
            payload["category"] = category
        language = LANGUAGES.get(parser)
        if language:
            payload["language"] = language
        Thread(
            target=self._send,
            args=(payload, self.api_key, self.on_status),
            daemon=True,
        ).start()

    @staticmethod
    def _send(payload, api_key, on_status):
        """POST one heartbeat and report the outcome. Runs in a thread.

        *on_status* (if given) is called with a :class:`WakaTimeStatus` from
        this background thread - the caller is responsible for any
        main-thread marshalling needed to use the result.
        """
        auth = b64encode(api_key.encode()).decode()
        request = Request(  # noqa: S310
            HEARTBEAT_URL,
            data=dumps(payload).encode(),
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
                "X-Machine-Name": MACHINE_NAME,
            },
            method="POST",
        )
        try:
            urlopen(request, timeout=10)  # noqa: S310
        except HTTPError as error:
            print_exc()
            status = (
                WakaTimeStatus.AUTH_ERROR
                if error.code in AUTH_ERROR_CODES
                else WakaTimeStatus.NETWORK_ERROR
            )
        except URLError:
            print_exc()
            status = WakaTimeStatus.NETWORK_ERROR
        else:
            status = WakaTimeStatus.OK
        if on_status:
            on_status(status)
