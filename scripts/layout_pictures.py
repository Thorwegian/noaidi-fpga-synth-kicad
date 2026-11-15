#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""layout_pictures.py -- pictures of the board's copper, close enough to judge a layout by.

    scripts/layout_pictures.py [--out <folder>] [--title <text>] <board> [<designator> ...]

Writes into build/pictures/, or into the folder given:

  whole.png                the whole board at 600 dpi;
  quarter_<where>.png      four overlapping quarters at 1200 dpi;
  tile_<row>_<column>.png  the whole board at 600 dpi, cut into overlapping
                           tiles of 1080 x 1020 pixels;
  detail_<designator>.png  for each designator given, a piece of the same
                           size at 1200 dpi around that part: for sockets
                           and parts with fine pitch;
  fill_<layer>.png         each copper layer with its fill at 600 dpi, the
                           copper black;
  overlay.png              the whole board at 600 dpi with every layer's
                           fill laid over the others in a pale colour.

The whole board and the quarters are for a person to zoom into, and carry a
title, the track counts and the legend. The tiles and the details are for an
agent: a larger image reaches it scaled down, and a track is then narrower
than a pixel. The script prints which part of the board each tile shows.

Front copper is red and back copper blue. Where both layers have copper the
picture is dark purple: with a white hole it is a pad or a via, where the
layers are joined; without one it is a crossing. The fabrication layer's
part outlines and designators are black, the silkscreen is ochre (a module's
outline is often drawn there only), the board's edge is green. The copper pours are left
out of all but the fill pictures and the overlay: with them a layer is one
filled area. In the overlay the front's fill is pale red, the back's pale
blue and the inner layers' pale green and yellow, so where a layer has no
copper its colour is missing from the mix: a band beside a track is the gap
that track makes in its layer's fill, a ring around a hole the gap in the
inner fills, and white has no copper on any layer. The board file is not
changed.

Needs kicad-cli (KiCad 10), pdftoppm (poppler-utils) and the system's
Python, which has KiCad's pcbnew module and Pillow (python3-pil).
"""
import argparse
import math
import os
import subprocess
import sys

import pcbnew
from PIL import Image, ImageChops, ImageDraw, ImageFont

# Layer, its colour, and whether the holes are drawn on it. Holes are drawn
# on the copper only: on another layer they would cover the copper's.
LAYERS = (
    ("B.Cu", (40, 110, 230), True),
    ("F.Cu", (225, 45, 45), True),
    ("F.Fab", (0, 0, 0), False),
    ("F.Silkscreen", (185, 120, 0), False),
    ("Edge.Cuts", (0, 130, 0), False),
)
DPI = 1200                  # of the quarters and details; the whole board and the tiles have half
MARGIN_MM = 1.5             # around what is drawn
QUARTER = 0.55              # of the board's width and height, so that the four overlap
TILE = (1080, 1020)
TILE_OVERLAP_MM = 1.0
FILL_FRONT, FILL_BACK, FILL_INNER = (255, 190, 190), (190, 210, 255), ((195, 240, 195), (255, 240, 170))
OVERLAY_LEGEND = (
    "Fills in pale colour, laid over each other: front red, inner layers green and yellow, back blue. Where a layer",
    "has no copper its colour is missing from the mix: a band beside a track is the gap in that layer's fill, a ring",
    "around a hole the gap in the inner fills, white no copper at all.  Tracks and pads: red = front, blue = back.",
)
LEGEND = (
    "Red = front copper.  Blue = back copper.  Dark purple = copper on both layers at that spot:",
    "with a white hole it is a pad or via (the layers are joined), without one it is a crossing (not joined).",
    "Black = part outlines and designators (fabrication layer).  Ochre = silkscreen.  Green = board edge.  Fills left out.",
)


def run(*command):
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode:
        sys.exit(f"{' '.join(command)}\n{done.stdout}{done.stderr}")


def extent_mm(board):
    """The rectangle (left, top, right, bottom) around the board's edge and
    its parts, with the margin."""
    boxes = [drawing.GetBoundingBox() for drawing in board.GetDrawings() if drawing.GetLayer() == pcbnew.Edge_Cuts]
    boxes += [footprint.GetBoundingBox(False) for footprint in board.GetFootprints()]
    return (pcbnew.ToMM(min(box.GetLeft() for box in boxes)) - MARGIN_MM,
            pcbnew.ToMM(min(box.GetTop() for box in boxes)) - MARGIN_MM,
            pcbnew.ToMM(max(box.GetRight() for box in boxes)) + MARGIN_MM,
            pcbnew.ToMM(max(box.GetBottom() for box in boxes)) + MARGIN_MM)


def layer_image(board_path, layer, holes, extent, folder):
    """One layer of the board in grey, black on white, cut to the extent.
    kicad-cli plots a board at its own coordinates on the page."""
    stem = os.path.join(folder, layer)
    run("kicad-cli", "pcb", "export", "pdf", "--mode-single", "--black-and-white", "--exclude-value",
        "--drill-shape-opt", "2" if holes else "0", "--layers", layer, "--output", stem + ".pdf", board_path)
    left, top, right, bottom = (round(mm * DPI / 25.4) for mm in extent)
    run("pdftoppm", "-gray", "-png", "-singlefile", "-r", str(DPI), "-x", str(left), "-y", str(top),
        "-W", str(right - left), "-H", str(bottom - top), stem + ".pdf", stem)
    return Image.open(stem + ".png").convert("L")


def tinted(grey, colour):
    return Image.merge("RGB", [grey.point(lambda value, part=part: 255 - (255 - value) * (255 - part) // 255)
                               for part in colour])


def cut_to_drawing(picture, extent):
    """The picture cut to what is drawn in it and the margin, and where its
    top left corner is on the board, in mm. A part's rectangle also holds
    what the part has on layers that are not pictured."""
    left, top, right, bottom = ImageChops.invert(picture.convert("L")).getbbox()
    margin = round(MARGIN_MM * DPI / 25.4)
    box = (max(left - margin, 0), max(top - margin, 0),
           min(right + margin, picture.width), min(bottom + margin, picture.height))
    return picture.crop(box), (extent[0] + box[0] * 25.4 / DPI, extent[1] + box[1] * 25.4 / DPI)


def with_heading(picture, title, dpi, counts, legend=LEGEND):
    """The picture under its title, the counts and the legend."""
    size = picture.width / 3200
    lines = [(title, 48), (f"{counts}  {dpi} dpi: a 0.2 mm track is {0.2 * dpi / 25.4:.0f} pixels wide.", 30)]
    lines += [(line, 27) for line in legend]
    heading = round((sum(height for _, height in lines) * 1.4 + 32) * size)
    out = Image.new("RGB", (picture.width, picture.height + heading), "white")
    out.paste(picture, (0, heading))
    draw = ImageDraw.Draw(out)
    y = 16 * size
    for text, height in lines:
        draw.text((40 * size, y), text, fill="black" if height > 27 else (70, 70, 70),
                  font=ImageFont.load_default(height * size))
        y += height * 1.4 * size
    return out


def starts(length, piece, overlap):
    """Where pieces of one size start so that they cover the length and
    each overlaps the next by the overlap or more."""
    if length <= piece:
        return [0]
    count = math.ceil((length - overlap) / (piece - overlap))
    return [round(index * (length - piece) / (count - 1)) for index in range(count)]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="build/pictures")
    parser.add_argument("--title")
    parser.add_argument("board")
    parser.add_argument("designators", nargs="*")
    arguments = parser.parse_args()
    title = arguments.title or os.path.basename(arguments.board)
    out = arguments.out
    os.makedirs(os.path.join(out, "layers"), exist_ok=True)

    board = pcbnew.LoadBoard(arguments.board)
    tracks = list(board.GetTracks())
    vias = sum(1 for track in tracks if track.Type() == pcbnew.PCB_VIA_T)
    length = sum(track.GetLength() for track in tracks if track.Type() != pcbnew.PCB_VIA_T)
    counts = f"{len(tracks) - vias} track segments, {vias} vias, {pcbnew.ToMM(length):.0f} mm of track."
    extent = extent_mm(board)
    centres = {}
    for designator in arguments.designators:
        footprint = board.FindFootprintByReference(designator)
        if not footprint:
            sys.exit(f"no part {designator} on the board")
        centre = footprint.GetBoundingBox(False).Centre()
        centres[designator] = (pcbnew.ToMM(centre.x), pcbnew.ToMM(centre.y))
    stack = list(board.GetEnabledLayers().CuStack())
    fills = None
    for number, layer in enumerate(stack):
        name = board.GetLayerName(layer)
        os.makedirs(os.path.join(out, "layers", "filled"), exist_ok=True)
        grey = layer_image(arguments.board, name, True, extent, os.path.join(out, "layers", "filled"))
        pale = (FILL_FRONT if number == 0 else FILL_BACK if layer == stack[-1] else FILL_INNER[number % 2])
        fills = ImageChops.multiply(fills, tinted(grey, pale)) if fills else tinted(grey, pale)
        filled = grey.resize((grey.width // 2, grey.height // 2), Image.LANCZOS).convert("RGB")
        ImageDraw.Draw(filled).text((40, 16), f"{title}: {name} with its fill. Black = copper.",
                                    fill=(200, 0, 0), font=ImageFont.load_default(36))
        filled.save(os.path.join(out, f"fill_{name}.png"), optimize=True)
    for pour in list(board.Zones()):
        board.Delete(pour)
    without_pours = os.path.join(out, "layers", "board.kicad_pcb")
    # The third argument keeps KiCad from writing a project file with the board.
    pcbnew.SaveBoard(without_pours, board, True)

    layers = [tinted(layer_image(without_pours, layer, holes, extent, os.path.join(out, "layers")), colour)
              for layer, colour, holes in LAYERS]
    close = layers[0]
    for layer in layers[1:]:
        close = ImageChops.multiply(close, layer)
    overlay, _ = cut_to_drawing(ImageChops.multiply(fills, close), extent)
    overlay = overlay.resize((overlay.width // 2, overlay.height // 2), Image.LANCZOS)
    with_heading(overlay, f"{title}, the fills overlaid", DPI // 2, counts, OVERLAY_LEGEND).save(
        os.path.join(out, "overlay.png"), optimize=True)
    close, origin = cut_to_drawing(close, extent)
    whole = close.resize((close.width // 2, close.height // 2), Image.LANCZOS)

    with_heading(whole, title, DPI // 2, counts).save(os.path.join(out, "whole.png"), optimize=True)
    width, height = round(close.width * QUARTER), round(close.height * QUARTER)
    for where, x, y in (("top_left", 0, 0), ("top_right", close.width - width, 0),
                        ("bottom_left", 0, close.height - height),
                        ("bottom_right", close.width - width, close.height - height)):
        quarter = close.crop((x, y, x + width, y + height))
        with_heading(quarter, f"{title}, {where.replace('_', ' ')} quarter", DPI, counts).save(
            os.path.join(out, f"quarter_{where}.png"), optimize=True)

    def millimetres(x, y, piece, dpi):
        return (f"x {origin[0] + x * 25.4 / dpi:6.1f} to {origin[0] + (x + piece.width) * 25.4 / dpi:6.1f} mm, "
                f"y {origin[1] + y * 25.4 / dpi:6.1f} to {origin[1] + (y + piece.height) * 25.4 / dpi:6.1f} mm")

    overlap = round(TILE_OVERLAP_MM * (DPI // 2) / 25.4)
    for row, y in enumerate(starts(whole.height, TILE[1], overlap), 1):
        for column, x in enumerate(starts(whole.width, TILE[0], overlap), 1):
            tile = whole.crop((x, y, min(x + TILE[0], whole.width), min(y + TILE[1], whole.height)))
            tile.save(os.path.join(out, f"tile_{row}_{column}.png"))
            print(f"tile_{row}_{column}.png  {millimetres(x, y, tile, DPI // 2)}")
    for designator, (centre_x, centre_y) in centres.items():
        x = min(max(round((centre_x - origin[0]) * DPI / 25.4) - TILE[0] // 2, 0), max(close.width - TILE[0], 0))
        y = min(max(round((centre_y - origin[1]) * DPI / 25.4) - TILE[1] // 2, 0), max(close.height - TILE[1], 0))
        detail = close.crop((x, y, min(x + TILE[0], close.width), min(y + TILE[1], close.height)))
        detail.save(os.path.join(out, f"detail_{designator}.png"))
        print(f"detail_{designator}.png  {millimetres(x, y, detail, DPI)}")
    print(f"whole.png and four quarters in {out}: {counts}")


if __name__ == "__main__":
    main()
