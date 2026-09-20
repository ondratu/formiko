"""Render the Inno Setup wizard images (formiko.iss) from the app icon.

Run from the repository root; writes PNGs there. Several sizes per image
let Setup pick the sharpest one for the display's DPI scaling (100%,
150%, 200%).
"""

from PIL import Image

ICON = Image.open("icons/512x512/formiko.png").convert("RGBA")

# (width, height) of the tall image on the welcome/finish pages.
LARGE_SIZES = [(202, 386), (336, 643), (430, 824)]
# Side of the square image in the top-right corner of the other pages.
SMALL_SIZES = [58, 97, 124]


def scaled_icon(side):
    """Return the app icon scaled to *side* x *side* pixels."""
    return ICON.resize((side, side), Image.LANCZOS)


for width, height in LARGE_SIZES:
    image = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    side = round(width * 0.7)
    image.alpha_composite(
        scaled_icon(side), ((width - side) // 2, round(height * 0.2)),
    )
    image.convert("RGB").save(f"wizard-large-{width}.png")

for side in SMALL_SIZES:
    scaled_icon(side).save(f"wizard-small-{side}.png")
