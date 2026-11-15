#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""silkscreen_clearance.py -- is every print far enough from every pad?

    scripts/silkscreen_clearance.py <board>

JLCPCB keeps 0.15 mm between a pad and the silkscreen
(https://jlcpcb.com/capabilities/pcb-capabilities, Legend). KiCad's DRC
reports print that lies on a pad's solder mask opening and says nothing of
print beside one, whatever the board's silkscreen clearance is set to, so
the distance is measured here: from every line, shape and text on a
silkscreen layer, a footprint's own print included, to every solder mask
opening of a pad on the same side of the board, with the shapes KiCad
itself draws them by.

Prints each print that is nearer than that with its distance, to a
hundredth of a millimetre, and the pad it is nearest to, then the count.
The exit status is 1 when there is one.

Runs under the system's Python, which has KiCad's pcbnew module.
"""
import sys

import pcbnew

CLEARANCE = pcbnew.FromMM(0.15)     # JLCPCB: pad to silkscreen
RESOLUTION = pcbnew.FromMM(0.01)    # of the distances printed
SIDES = ((pcbnew.F_SilkS, pcbnew.F_Mask), (pcbnew.B_SilkS, pcbnew.B_Mask))


def is_text(item):
    return item.GetClass() in ("PCB_TEXT", "PCB_FIELD")


def printed_items(board, silkscreen):
    """The print on the layer, as (owner, what it is, item): a footprint's
    shapes, texts and visible fields under its designator, the board's own
    under 'board'."""
    for footprint in board.GetFootprints():
        fields = [field for field in footprint.GetFields() if field.IsVisible()]
        for item in list(footprint.GraphicalItems()) + fields:
            if item.GetLayer() == silkscreen:
                yield footprint.GetReference(), describe(item), item
    for drawing in board.GetDrawings():
        if drawing.GetLayer() == silkscreen:
            yield "board", describe(drawing), drawing


def describe(item):
    return f'text "{item.GetText()}"' if is_text(item) else item.ShowShape().lower()


def shape_of(item, layer):
    return item.GetEffectiveTextShape() if is_text(item) else item.GetEffectiveShape(layer)


def distance(print_shape, opening):
    """How far the print is from the opening, to RESOLUTION, for a print
    that is nearer than CLEARANCE."""
    nearer, further = 0, CLEARANCE
    while further - nearer > RESOLUTION // 2:
        middle = (nearer + further) // 2
        if print_shape.Collide(opening, middle):
            further = middle
        else:
            nearer = middle
    return further


def main(board_path):
    board = pcbnew.LoadBoard(board_path)
    findings, prints, openings = [], 0, 0
    for silkscreen, mask in SIDES:
        pads = [(footprint.GetReference(), pad, pad.GetEffectiveShape(mask), pad.GetBoundingBox())
                for footprint in board.GetFootprints() for pad in footprint.Pads() if pad.IsOnLayer(mask)]
        openings += len(pads)
        for owner, what, item in printed_items(board, silkscreen):
            prints += 1
            print_shape = shape_of(item, silkscreen)
            reach = item.GetBoundingBox()
            reach.Inflate(CLEARANCE)
            near = [(distance(print_shape, opening), designator, pad.GetNumber())
                    for designator, pad, opening, box in pads
                    if reach.Intersects(box) and print_shape.Collide(opening, CLEARANCE)]
            if near:
                findings.append((owner, what, board.GetLayerName(silkscreen)) + min(near))

    for owner, what, layer, gap, designator, pad_number in sorted(findings):
        print(f"{owner:6} {what} on {layer}: {pcbnew.ToMM(gap):.2f} mm from pad {pad_number} of {designator}")
    print(f"{prints} prints against {openings} pads' solder mask openings: "
          f"{len(findings)} nearer than {pcbnew.ToMM(CLEARANCE):g} mm")
    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
