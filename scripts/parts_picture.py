#!/usr/bin/env python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""parts_picture.py -- number the parts in the board's view from above.

    parts_picture.py <pcb-top.jpg> <out.jpg>

Draws a numbered marker on each part that the README's "What is on it"
list describes, the list's number on the part. A marker's place is given
as a fraction of the picture's width and height, read off the render: the
places are checked by eye against the new picture whenever a part moves.
Needs Pillow 10.1 or later (the built-in font at a chosen size).
"""
import sys
from PIL import Image, ImageDraw, ImageFont

# The centre of each part's marker: (fraction of the width, of the height).
MARKER_PLACES = {
    1: (0.620, 0.034),  # the two DIN sockets, J1 and J2
    2: (0.420, 0.435),  # the ESP32-S3 module, U1
    3: (0.610, 0.610),  # the Tang Nano 20K, U2
    4: (0.760, 0.815),  # the DAC module, U5
    5: (0.560, 0.930),  # the RCA socket, J3
    6: (0.045, 0.712),  # the USB-C socket for power, J9
    7: (0.045, 0.554),  # the USB-C socket for data, J14
    8: (0.500, 0.298),  # the pin headers and test points
}
MARKER_DIAMETER = 0.070  # of the picture's width
RIM_WIDTH = 0.0058
DIGIT_HEIGHT = 0.039
FILL = '#E09A2B'
RIM = '#FFFFFF'
INK = '#14110A'
SUPERSAMPLING = 4  # the markers are drawn this many times larger and scaled down, for smooth edges


def markers(width, height):
    """A transparent layer of the picture's size holding the numbered markers."""
    scale = SUPERSAMPLING
    layer = Image.new('RGBA', (width * scale, height * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    radius = MARKER_DIAMETER * width * scale / 2
    font = ImageFont.load_default(size=DIGIT_HEIGHT * width * scale)
    for number, (across, down) in MARKER_PLACES.items():
        centre_x, centre_y = across * width * scale, down * height * scale
        draw.ellipse((centre_x - radius, centre_y - radius, centre_x + radius, centre_y + radius),
                     fill=FILL, outline=RIM, width=round(RIM_WIDTH * width * scale))
        # The digit is centred by its ink, not by the font's line box.
        left, top, right, bottom = draw.textbbox((0, 0), str(number), font=font)
        draw.text((centre_x - (left + right) / 2, centre_y - (top + bottom) / 2), str(number), font=font, fill=INK)
    return layer.resize((width, height), Image.Resampling.LANCZOS)


def main(source_path, output_path):
    picture = Image.open(source_path).convert('RGBA')
    numbered = Image.alpha_composite(picture, markers(*picture.size))
    numbered.convert('RGB').save(output_path, quality=90, progressive=True)
    print(f'{output_path}: {numbered.width} x {numbered.height}, {len(MARKER_PLACES)} markers')


if __name__ == '__main__':
    main(*sys.argv[1:3])
