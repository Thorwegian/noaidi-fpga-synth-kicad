#!/usr/bin/env python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""crop.py -- crop a kicad-cli render to what it shows plus an even margin.

    crop.py <render.png> <mask.png> <out.jpg> [margin px, default 60]

The mask is the same view rendered with a transparent background and no
floor: it is opaque where the board or a part on it is, and nowhere
else, so a part that reaches beyond the board's outline is inside the
crop. The render itself cannot say this: its background and the floor's
shadows are pixels like any other. Needs Pillow.
"""
import sys
from PIL import Image
render_path, mask_path, output_path = sys.argv[1:4]
margin = int(sys.argv[4]) if len(sys.argv) > 4 else 60
render = Image.open(render_path).convert('RGB')
mask = Image.open(mask_path)
if mask.size != render.size:
    sys.exit(f'{mask_path} is {mask.size} and {render_path} is {render.size}: not the same view')
opaque = mask.getchannel('A').point([0] * 128 + [255] * 128)
left, top, right, bottom = opaque.getbbox()
box = (left - margin, top - margin, right + margin, bottom + margin)
if box[0] < 0 or box[1] < 0 or box[2] > render.width or box[3] > render.height:
    sys.exit(f'{render_path}: the frame {render.size} does not hold {box}, '
             f'what it shows plus {margin} px: render the view at a lower zoom')
cropped = render.crop(box)
cropped.save(output_path, quality=85, optimize=True, progressive=True)
print('shown', (left, top, right - 1, bottom - 1), 'crop', box, 'out', cropped.size)
