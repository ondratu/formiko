"""TEMPORARY: probe libspelling/Enchant behaviour on Windows (see CI)."""

import sys
import threading

import gi

gi.require_version("Spelling", "1")
from gi.repository import Spelling  # noqa: E402

Spelling.init()
provider = Spelling.Provider.get_default()
print("provider:", provider.get_display_name(), flush=True)

model = provider.list_languages()
codes = [model.get_item(i).get_code() for i in range(model.get_n_items())]
print("languages:", len(codes), codes[:40], flush=True)

lang = sys.argv[1] if len(sys.argv) > 1 else "en_US"
checker = Spelling.Checker.new(provider, lang)
print("checker language:", checker.get_language(), flush=True)


def probe(where):
    """Print check_word() results for a good and a bad word."""
    for word in ("hello", "helo", "the", "qzxv"):
        print(f"[{where}] check_word({word!r}) ->",
              checker.check_word(word, -1), flush=True)
    print(f"[{where}] corrections for 'helo':",
          list(checker.list_corrections("helo") or []), flush=True)


probe("main thread")
worker = threading.Thread(target=probe, args=("worker thread",))
worker.start()
worker.join()
