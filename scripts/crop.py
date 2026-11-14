#!/usr/bin/env python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""crop.py -- crop a kicad-cli render to the board plus an even margin.

    crop.py <render.png> <out.jpg> [margin px, default 60]

The board is found as the green pixels (its solder mask); the grey
background and the floor shadow are not green. Needs Pillow.
"""
import sys
from PIL import Image
src, dst = sys.argv[1], sys.argv[2]
margin = int(sys.argv[3]) if len(sys.argv) > 3 else 60
im = Image.open(src).convert('RGB')
W, H = im.size
px = im.load()
x0, x1, y0, y1 = W, 0, H, 0
for y in range(H):
    for x in range(W):
        r, g, b = px[x, y]
        if g > r + 8 and g > b + 8:
            if x < x0: x0 = x
            if x > x1: x1 = x
            if y < y0: y0 = y
            if y > y1: y1 = y
box = (max(0, x0 - margin), max(0, y0 - margin), min(W, x1 + 1 + margin), min(H, y1 + 1 + margin))
out = im.crop(box)
out.save(dst, quality=85, optimize=True, progressive=True)
print('board', (x0, y0, x1, y1), 'crop', box, 'out', out.size)
