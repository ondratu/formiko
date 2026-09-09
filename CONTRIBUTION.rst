Contribution Guide
===================

Thanks for your interest in contributing to Formiko!

GNOME / GTK first
------------------

Formiko is a GNOME/GTK desktop application before anything else. When in
doubt, prefer the option that fits the platform over the one that is
merely convenient in Python:

* Follow the `GNOME Human Interface Guidelines
  <https://developer.gnome.org/hig/>`_ for UI, layout, icons and
  interaction patterns. New windows, dialogs and widgets should look and
  behave like a native GNOME application, not like a generic cross-platform
  toolkit app.
* Prefer GTK/GLib idioms (``Gio.Settings``, ``Gtk.Application`` actions,
  signals, ``GObject`` properties) over ad-hoc Python state where GTK
  already offers a standard mechanism. Formiko already reads system font
  settings via GNOME ``gsettings`` (see ``formiko/window.py``) — new
  features should integrate with the desktop the same way rather than
  reinventing configuration or storage.
* Do not add behaviour that conflicts with GNOME conventions: no custom
  window chrome/title bars unless following ``Adwaita``/``libadwaita``
  patterns, no blocking the main loop (use GLib idle/timeout or async
  APIs), no silently writing files or telemetry a GNOME user wouldn't
  expect.
* This does not override sane Python practice — GNOME/GTK conventions
  govern *how the app behaves and is structured*, PEP 8 / PEP 257 still
  govern *how the Python code is written* (see below). The two are not in
  conflict; when they appear to be, ask before picking one over the other.

Flatpak
-------

Formiko is distributed as a Flatpak, so changes should stay
sandbox-friendly:

* Don't assume unrestricted filesystem access — use portals
  (``xdg-desktop-portal``, ``Gtk.FileChooserNative``, etc.) for file
  access instead of raw paths outside the sandbox.
* Don't shell out to host tools that may not exist inside the Flatpak
  runtime; if an external tool is genuinely required, check it degrades
  gracefully when missing.
* Keep the application id (``cz.zeropage.Formiko``) consistent across the
  ``.desktop`` file, ``.metainfo.xml`` and any code that references it
  (e.g. ``StartupWMClass``, ``Gio.Settings`` schema paths).
* If a change affects the runtime/SDK version, permissions, or added
  dependencies, mention it explicitly in the PR description — those need
  a matching update in the Flatpak manifest maintained outside this
  repository.

Python style
------------

Formiko targets Python 3 and follows PEP 8 / PEP 257 conservatively.
Linting is enforced locally and in CI — please run it *before* opening a
PR, not after:

* ``ruff`` (see ``ruff.toml``) — a fairly wide rule set (pyflakes,
  pycodestyle, pydocstyle, bugbear, simplify, pylint subset, …),
  79-column line length. Fix what ruff reports rather than adding new
  ``noqa``/ignore entries; if a rule genuinely doesn't apply, discuss it
  in the PR instead of silencing it locally.
* ``flake8`` — runs alongside ruff via pre-commit.
* ``codespell`` — spelling is checked repo-wide (config in
  ``pyproject.toml``); fix typos rather than adding words to the ignore
  list unless they are genuine false positives (e.g. GObject
  Introspection's ``.gir`` files).
* ``rst-linter`` (pre-commit-hooks-markup) — for ``.rst`` documentation.
* Standard pre-commit hygiene: no trailing whitespace, files end with a
  newline, YAML stays valid.

Install and enable the hooks once per checkout::

    pip install pre-commit
    pre-commit install

Then just ``git commit`` as usual; if a hook rewrites a file, review the
diff, ``git add`` it, and commit again.

Tests live under ``tests/`` and run with ``pytest`` (see
``[tool.pytest.ini_options]`` in ``pyproject.toml``). Add or update tests
for any behavioural change.

Tests must pass without a graphical session — no X11 or Wayland display
server (e.g. ``unset DISPLAY WAYLAND_DISPLAY`` before running them, as CI
does). This does not mean that GTK, GObject Introspection, or the GTK
typelibs are optional: the test environment still needs the libraries
used by the imported code. The suite must not require a display server,
though. Widgets that only need to be constructed and manipulated (not
shown, realized, or run through a main loop) can be used headlessly, so
prefer building the real GTK objects a test touches (e.g. ``Gtk.ListBox``,
``Gtk.Label``) over mocking them. Reach for ``unittest.mock.Mock`` for
everything a test does not itself exercise (e.g. the surrounding window).

Unsetting ``DISPLAY`` and ``WAYLAND_DISPLAY`` is a guard against accidental
display use, not a workaround that makes GTK tests headless. If a test
needs to show or realize a widget, it belongs in a separate display-backed
test job (for example with ``xvfb-run``), rather than weakening this suite.

**Sanity check**: ``env -u DISPLAY -u WAYLAND_DISPLAY pytest -q`` should
behave the same as a plain ``pytest -q`` run.

Commit messages
----------------

Prefer a precise but modest commit message: describe *what* changed, in
one short line, without embellishment. A commit message documents the
change for other developers reading ``git log`` — it does not need to
sell the change or restate the obvious from the diff.

Good::

    Fix RST include directive with relative paths

Avoid::

    Massive improvement to include handling, finally works great!

If more explanation is genuinely needed, add it as a short body after a
blank line — still plain and factual, not a marketing pitch.

ChangeLog
---------

The ``ChangeLog`` file is written for *users*, not just developers —
keep that audience in mind. Not every commit deserves an entry; add one
when a change is something a user would notice or care about (a new
feature, a fixed bug, a behaviour change), and skip it for purely
internal changes (refactors, lint fixes, CI tweaks, typo fixes with no
user-visible effect).

When an entry is warranted:

* Add it under the current ``Version X.Y.Z.dev`` heading at the top of
  ``ChangeLog``, following the existing bullet style.
* Keep it short and clear — one line for a simple change, with nested
  sub-bullets only if the feature genuinely has multiple user-facing
  parts (see the existing entries for the tab support or custom
  directives as examples of when that's warranted).
* Write it in plain language a non-developer user can understand; avoid
  internal file/function names, issue numbers, or implementation detail
  that only makes sense to someone reading the code.

Pull requests
--------------

* Keep PRs focused — one logical change per PR is easier to review than
  a bundle of unrelated fixes.
* Make sure ``pre-commit`` and ``pytest`` pass locally before opening the
  PR; CI runs the same checks (see ``.github/workflows``).
* Mention any GNOME/GTK HIG or Flatpak sandboxing implications in the PR
  description, even if you believe they don't apply — it saves a review
  round-trip.
