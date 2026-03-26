# Adwaita / GTK4 Editor Freeze — Complete Research Notes

## Shrnutí problému

V aplikaci Formiko (větev `tabs`) dochází při psaní do editoru `GtkSource.View`
k vizuálnímu zamrznutí: stisknuté klávesy jsou zapisovány do bufferu, ale editor
se nepřekreslí, dokud myš nepřejede nad panel WebKit rendereru.
Problém **se nevyskytuje na větvi `master`** (bez karet) — je specifický pro
kombinaci `AdwTabView → AdwBin → GtkSource.View + GtkPaned`.

Projevuje se na:
- Wayland + Debian (libadwaita 1.7.2, GTK 4.18+)
- X11 + Debian (libadwaita 1.7.6, GTK 4.18.6) — stejný problém
- Starší Flatpak GNOME SDK 48 — na X11 neodemkne přejetí nad prázdným WebKitem,
  je nutné přejet nad odkazem ve WebKitu

---

## Kdy a jak se projevuje

1. **Psaní — Enter / nový řádek** — nejspolehlivější spouštěč; psaní normálních
   znaků na stejném řádku obvykle nevyvolá freeze.
2. **Načtení souboru do prázdné karty** — přidá velké množství textu najednou;
   freeze je snáze reprodukovatelný.
3. **Programové vložení prázdného řádku do bufferu** — funguje jako spouštěč.
4. Freeze **nevznikne** pokud je Paned přepnutý jen na editor nebo jen na WebView.
5. Freeze **nevznikne** s `GDK_DEBUG=no-offload` (vypne DMA-BUF subsurface
   offloading) — ale to není použitelné řešení.
6. Freeze odemkne pohyb myší **přes GtkPaned dělič** nebo přes WebKit panel —
   postačí přiblížit se k dělicímu prvku ze strany editoru.

---

## Identifikovaná příčina — GTK4 LAYOUT deadlock

### Widget hierarchie (relevantní část)

```
AdwTabView
  └─ AdwBin                          ← zde zamrzne alloc_needed=TRUE
       └─ DocumentPage (GtkBox)
            └─ GtkPaned
                 ├─ SourceView (GtkScrolledWindow + GtkSource.View)
                 └─ Renderer (GtkOverlay + WebKitWebView)
```

### Mechanismus deadlocku

GDK frame clock spouští LAYOUT while-loop (max 4 iterace):
- Soubor: `gtk4-4.22.1+ds/gdk/gdkframeclockidle.c`, řádek 605–614
- Pokud po 4 iteracích stále `alloc_needed=TRUE` → warning
  `"gdk-frame-clock: layout continuously requested, giving up after 4 tries"`

**Průběh deadlocku (přesná analýza GTK zdrojových kódů):**

**Liché iterace (1., 3.):**
```
ensure_allocate(AdwBin)
  → alloc_needed=TRUE → jde do ELSE větve (size_allocate, řádky 4355–4356)
  → size_allocate → flush_first_validate
  → výška textu se změní → queue_resize(AdwBin)
  → gate v queue_resize selže (resize_queued=FALSE) → alloc_needed=TRUE nastaven
  → ale line 4355 clears resize_queued; line 4356 clears alloc_needed=FALSE
```

**Sudé iterace (2., 4.):**
```
ensure_allocate(AdwBin)
  → alloc_needed=FALSE → jde do IF větve (ensure_allocate_on_children, řádek 4320)
  → flush_first_validate
  → výška textu se změní → queue_resize(AdwBin)
  → gate selže → alloc_needed=TRUE nastaven
  → v IF větvi NEJSOU řádky 4355–4356!
  → alloc_needed=TRUE ZŮSTANE nastaveno
```

**Po 4. iteraci:**
- `alloc_needed=TRUE` na AdwBin
- `do_snapshot(AdwBin)` → warning + early return → stará render node → vizuální freeze
- Zdrojový kód: `gtkwidget.c` řádek 12171

### Klíčové řádky GTK zdrojového kódu

| Soubor | Řádek | Popis |
|--------|-------|-------|
| `gdkframeclockidle.c` | 605 | LAYOUT while-loop (max 4 iters) |
| `gdkframeclockidle.c` | 612 | `if (iter == 5)` → "continuously requested" warning |
| `gtkwidget.c` | 3724 | `queue_resize` gate: `if (resize_queued) return` |
| `gtkwidget.c` | 4320 | IF větev (`ensure_allocate_on_children`) vs ELSE (size_allocate) |
| `gtkwidget.c` | 4355–4356 | `clear_resize_queued` + `alloc_needed=FALSE` — POUZE v ELSE větvi |
| `gtkwidget.c` | 11013 | `ensure_allocate` maže `resize_queued` před kontrolou `alloc_needed` |
| `gtkwidget.c` | 12171 | `do_snapshot` returns early if `alloc_needed=TRUE` (warning) |

### Proč GtkSource.View způsobuje deadlock (a GtkTextView ne)

GtkSource.Buffer má syntax highlighting engine, který spouští validaci textu
asynchronně přes idle callbacks. Tato validace mění výšky řádků a způsobuje
`queue_resize` volání **během LAYOUT fáze** — přesně v době, kdy GTK4 iteruje
while-loop. To způsobuje spolehlivý deadlock.

Prostý `GtkTextView` má jednodušší/rychlejší validaci — freeze se neobjevuje
nebo se rychle vyřeší.

---

## Výsledky izolačních testů (debug stubs)

Stub systém: `FORMIKO_STUB_EDITOR=<jméno> python3 -m formiko`

Každý stub je `GtkScrolledWindow` s `GtkSource.View` (nebo `GtkTextView`).
Freezy testovány: psaním (Enter) a načtením souboru.

### Tabulka výsledků — základní izolace

| Stub (`FORMIKO_STUB_EDITOR=`) | Zamrzne psaním | Zamrzne načtením | Poznámka |
|-------------------------------|:--------------:|:----------------:|----------|
| `1` / `tv` (GtkTextView) | ❌ | ❌ | Žádný GtkSource → bez freeze |
| `gsv` (bare GSV, bez jazyka) | ❌ (těžko) | ✅ | Bez syntax enginu |
| `gsv_lang` (+ RST/MD jazyk) | ✅ snadné | ✅ | Syntax engine aktivní |
| `gsv_gutter` (+ číslování řádků) | ✅ snadné | ✅ | |
| `gsv_full` (+ HCL + AI + TW=4) | ❌ | ✅ | Kombinace zabrání psaní |

### Tabulka výsledků — co zabrání freeze při psaní (stub `gsv_lang` + …)

| Přidaná vlastnost | Nastavena PŘED set_child | Freeze psaním |
|-------------------|:------------------------:|:-------------:|
| nic | — | ✅ |
| `auto_indent=True` | ✅ | ❌ |
| `highlight_current_line=True` | ✅ | ❌ |
| `tab_width=4` | ✅ | ❌ |
| `highlight_syntax=False` | ✅ | ❌ (ale černé trojúhelníky) |
| CSS monospace font | ✅ | ❌ |

**Kritický nález: záleží na pořadí vůči `set_child()`!**

| Vlastnost | Před set_child | Po set_child |
|-----------|:--------------:|:------------:|
| `auto_indent=True` | ❌ bez freeze | ✅ freeze |

### Tabulka výsledků — pořadí operací

| Stub | Popis | Freeze psaním | Freeze načtením |
|------|-------|:-------------:|:---------------:|
| `gsv_lang_ai` | AI **před** set_child | ❌ | ❌ (nebo těžko) |
| `gsv_lang_ai_after` | AI **po** set_child | ✅ | ✅ |
| `gsv_lang_css` | CSS před set_child, bez props | ❌ | ✅ |
| `gsv_real_order` | CSS před + props po set_child | ❌ | ✅ |
| `gsv_real_color` | CSS před + props po + color scheme po | ❌ | ✅ |
| Reálný SourceView (po všech opravách) | VŠE před set_child | ✅ | ✅ |

---

## Pokusy o opravu — co nezabralo

### Pokus 1 — `buffer.changed → request_phase(LAYOUT)` (commit 7d740b7)

**Idea:** Po každé změně bufferu vynutit LAYOUT fázi, aby frame clock znovu
zkusil alokovat AdwBin.

**Výsledek:** SELHALO. Request_phase(LAYOUT) nevyvolá novou iteraci while-loopu
uvnitř stejného frame — jen naplánuje nový frame. Do té doby je stav
`alloc_needed=TRUE` stále na AdwBin a PAINT frame projde se starým render nodem.

**Kód (stále v `document_page.py`):**
```python
def _on_buf_changed_request_layout(self, _buf):
    clock = self.get_frame_clock()
    if clock is not None:
        clock.request_phase(Gdk.FrameClockPhase.LAYOUT)
```

### Pokus 2 — frame clock "layout" → `parent.allocate()` na každé iteraci

**Idea:** Napojit se na signal `clock.connect("layout", handler)` a volat
`parent.allocate(w, h, -1, None)` při každé emisi.

**Výsledek:** SELHALO. IF větev (alloc_needed=FALSE) se spouští při každém
sudém volání → opakované `allocate()` znovu vstupuje do IF větve →
`"layout continuously requested"` warning zaplaví konzoli.

### Pokus 3 — `parent.queue_allocate() + parent.allocate()` na každé iteraci

**Výsledek:** SELHALO. Stejný problém jako pokus 2 + flood warnings.

### Pokus 4 — `parent.allocate()` pouze na 4. iteraci (aktuální kód)

**Idea:** Počítat iterace pomocí `frame_counter`, zavolat `allocate()` jen na
4. iteraci (přesně ta, kde freezne).

**Kód (v `document_page._on_frame_layout_alloc_fix`):**
```python
def _on_frame_layout_alloc_fix(self, clock):
    frame = clock.get_frame_counter()
    if frame != self._fix_layout_frame:
        self._fix_layout_frame = frame
        self._fix_layout_iter = 0
    self._fix_layout_iter += 1
    if self._fix_layout_iter < 4:
        return
    parent = self.get_parent()  # AdwBin
    alloc = parent.get_allocation()
    if alloc.width > 0 and alloc.height > 0:
        parent.allocate(alloc.width, alloc.height, -1, None)
```

**Výsledek:** SELHALO. Freeze může nastat i na 2. iteraci — while-loop se
ukončí předčasně, pokud `resize_queued=TRUE` na rodičovi zastaví propagaci
`queue_resize` k `GtkNative`.

### Pokus 5 — Přesun vlastností SourceView PŘED `set_child()`

**Idea:** Stubs ukázaly, že nastavení `auto_indent` / `tab_width` / HCL
**před** `set_child()` zabrání freeze při psaní. Přesunout inicializaci
reálného SourceView ve stejném pořadí.

**Přesunuté položky:**
- `set_tab_width`, `set_auto_indent`, `set_show_line_numbers`, `set_highlight_current_line`
- `set_right_margin_*`, `set_text_wrapping`, `set_white_chars`
- `set_spaces_instead_of_tabs`
- `_apply_color_scheme()` (volá `text_buffer.set_style_scheme()`)
- `Spelling.TextBufferAdapter.new()` + `set_enabled(False)` + `insert_action_group` + `set_extra_menu`
- `checker.connect("notify::language", ...)`
- `set_check_spelling()`
- `SearchContext.new()`

**Výsledek:** SELHALO. Reálný SourceView stále zamrzá při psaní i načtení.

**Paradox:** Stubs `gsv_real_order` a `gsv_real_color` (které mají props
nastaveny **po** set_child, ale mají CSS **před** set_child) **nezamrzají při
psaní** — přestože reálný SourceView s props **před** set_child zamrzá. To
naznačuje, že existuje ještě jiný faktor v reálném SourceView.

---

## Neprobádané teorie / možné směry

### 1. Ongoing runtime behavior — ne inicializace

Hypotéza: Problém není v inicializaci (co je před/po set_child), ale v tom,
co se děje za běhu při každém stisknutí Enter:

- GtkSource syntax engine spouští highlight validaci po každé změně bufferu
- Tato validace mění výšky řádků → `queue_resize` → propaguje k AdwBin
- Toto se děje **kdykoli** (i dávno po inicializaci)
- Přesun inicializace před `set_child()` tedy nemůže tento runtime problém opravit

Stubs fungují (nezamrzají při psaní) pravděpodobně proto, že jsou **mnohem
jednodušší** — nemají color scheme, spell checker, search context, CSS font
přesně kombinované se stavem AdwBin allocatoru v daném okamžiku.

### 2. GDK subsurface offloading — propojení s WebKit

`GDK_DEBUG=no-offload` freeze odstraní. WebKit používá DMA-BUF subsurface
pro kompozici. Když je WebKit na druhé straně GtkPaned a pohyb myší přes něj
freeze odemkne — možná jde o interakci mezi subsurface alokací WebKitu a
AdwBin allocatorem.

Checkpointy 003, 004 zkoumaly tuto cestu (viz `checkpoints/` v session state).

### 3. GtkPaned a jeho interakce s AdwBin

Problém nastane POUZE s GtkPaned se dvěma stranami (editor + renderer).
S jednou stranou (jen editor nebo jen renderer) freeze nevznikne.

GtkPaned může způsobovat specifické pořadí alokací svých dětí, které
zhoršuje deadlock v AdwBin.

### 4. Chyba v GTK4 / libadwaita

Warning `"Trying to snapshot AdwBin 0x... without a current allocation"`
je interní GTK4 chyba. Jde o situaci, která by neměla nastat za normálních
okolností. Možná jde o bug v GTK4/libadwaita kombinaci s AdwTabView.

Relevantní GTK issues:
- https://gitlab.gnome.org/GNOME/gtk/-/issues/1959 (GtkPaned reset workaround
  je již v kódu — `893fcb1`)

### 5. AdwTabView / AdwBin specifické chování

`AdwBin` je speciální widget — obsahuje tab obsah. Jeho allocátor se může
chovat jinak než standardní `Gtk.Box` nebo `Gtk.Widget`. V master větvi
(bez karet, bez AdwTabView) se problém neobjevuje.

---

## Workarounds (nefunkční jako permanentní řešení)

| Workaround | Funguje | Poznámka |
|------------|:-------:|----------|
| `GDK_DEBUG=no-offload` | ✅ | Zakáže DMA-BUF, černé trojúhelníky u WebKit |
| `FORMIKO_STUB_EDITOR=1` | ✅ při psaní | Nahradí GSV za GtkTextView — ztráta syntax |
| Psát jen na jedné straně Paned | ✅ | Nepoužitelné |

---

## Aktuální stav kódu (větev `tabs`)

### `formiko/sourceview.py` — SourceView.__init__

Aktuálně inicializuje VŠE před `set_child()` (po pokusech 1–5):
```
1. GtkSource.Buffer s jazykem
2. GtkSource.View s bufferem
3. setup_list_features() — event controllers
4. CSS provider + system font (před set_child)
5. Všechny view properties (před set_child)
6. _apply_color_scheme() — text_buffer.set_style_scheme() (před set_child)
7. Spelling.TextBufferAdapter (před set_child)
8. SearchContext (před set_child)
9. set_child(source_view)   ← pouze toto po inicializaci
10. Signal connections pro style changes
11. set_period_save(), timeout_add()
```

### `formiko/document_page.py` — _on_realize / _on_frame_layout_alloc_fix

Obsahuje pokus 1 + pokus 4 (oba nefunkční, ale neodstraněny):
- `_on_buf_changed_request_layout` — `buffer.changed → request_phase(LAYOUT)`
- `_on_frame_layout_alloc_fix` — `clock.layout → parent.allocate()` na 4. iteraci

### `formiko/debug_stubs.py` — stub systém

Env var `FORMIKO_STUB_EDITOR=<jméno>` nahradí editor stubem:

| Jméno | Popis |
|-------|-------|
| `1` / `tv` | GtkTextView |
| `gsv` | bare GtkSource.View, bez jazyka |
| `gsv_lang` | + RST/MD jazyk |
| `gsv_gutter` | + číslování řádků |
| `gsv_full` | + HCL + AI + tab_width=4 |
| `gsv_lang_hcl` | gsv_lang + highlight_current_line před set_child |
| `gsv_lang_ai` | gsv_lang + auto_indent před set_child |
| `gsv_lang_tw` | gsv_lang + tab_width=4 před set_child |
| `gsv_lang_nohl` | gsv_lang, syntax highlighting OFF |
| `gsv_lang_ai_after` | gsv_lang + auto_indent **po** set_child |
| `gsv_lang_css` | gsv_lang + CSS font před set_child |
| `gsv_real_order` | CSS před + props po set_child |
| `gsv_real_color` | CSS před + props po + color scheme po set_child |

`FORMIKO_STUB_RENDERER=1` — nahradí WebKit za Gtk.Label.

---

## Klíčový paradox (dosud nevyřešený)

```
gsv_real_order (CSS před, props PO set_child)   → ❌ bez psaní freeze
gsv_real_color (+ color scheme PO)              → ❌ bez psaní freeze
Reálný SourceView (VŚE PŘED set_child)          → ✅ STÁLE freeze
```

Co má reálný SourceView navíc oproti `gsv_real_color`?
- Žádný z přidaných featur (proto přesunutých před set_child)
- Jen runtime engine: syntax highlighting se aktualizuje po každém
  stisknutí klávesy a mění výšky řádků → to nelze "přesunout před set_child"

Stubs pravděpodobně nezamrzají proto, že jsou natolik prosté,
že syntax engine nestihne způsobit problematický `queue_resize` dostatečně
rychle — nebo proto, že bez color scheme / CSS font / spell checker
je efekt výškové změny menší a nevede k deadlocku.

---

## Soubory zdrojového kódu relevantní pro debugging

```
formiko/
  sourceview.py          — reálný SourceView (GtkScrolledWindow + GSV)
  document_page.py       — per-tab widget, pokusné opravy v _on_realize
  debug_stubs.py         — stub systém pro izolaci

gtk4-4.22.1+ds/          — lokální kopie GTK4 zdrojáků (read-only reference)
  gdk/gdkframeclockidle.c
  gtk/gtkwidget.c
```
