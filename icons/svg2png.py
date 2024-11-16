"""Support PNG generator from SVG."""

from os import makedirs

from gi.repository.GdkPixbuf import Pixbuf


def main():
    """Create the png files from svg."""
    for size in (16, 22, 24, 32, 48, 64, 128, 256, 512):
        icon = Pixbuf.new_from_file_at_scale("formiko.svg", size, size, True)
        makedirs(f"{size}x{size}")
        icon.savev(f"{size}x{size}/formiko.png", "png", [], [])


if __name__ == "__main__":
    main()
