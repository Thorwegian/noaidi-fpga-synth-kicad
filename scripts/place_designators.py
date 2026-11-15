#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""place_designators.py -- puts each part's designator where it can be read.

    scripts/place_designators.py [--height <mm>] <board>

A designator can be read on the finished board when it is printed whole, no
part covers it, and it is plain which part it names. So each designator is
put at the free place nearest its part where:

  - it is outside the rectangle around every part's courtyard and drawn
    outline, its own part's included, since a part covers what is under
    it (a module's outline reaches past its courtyard where the module
    overhangs its pins);
  - it keeps JLCPCB's pad-to-silkscreen distance of 0.15 mm
    (https://jlcpcb.com/capabilities/pcb-capabilities, Legend) from every
    pad and hole, and the same from every line and text of the silkscreen
    and from every other designator;
  - it is on no via, where the hole breaks the print;
  - it is inside the board's edge by the board's edge clearance.

It is written horizontally, or vertically reading from the right, at the
height given: 1.2 mm unless told otherwise, with a line a sixth of that.
JLCPCB's limits are 1.0 mm and 0.15 mm, below which it calls a character
unidentifiable, and its preferred ratio of line to height is 1:6.

The places tried lie along the four sides of the part's courtyard, the
nearest first, out to REACH. A horizontal one is preferred to a vertical
one a little further in, and a place that is not plainly nearer its own
part than any other part is taken only when there is no other; the script
prints the designators that end up in such a place. The parts with the fewest
free places choose first; then every designator gets to choose again with
all the others in place.

The script runs after scripts/route.sh, since the vias are in the way. It
prints the designators it found no place for and leaves those where they
were; its exit status is then 1.
"""
import argparse
import collections
import sys

import pcbnew

CLEARANCE = pcbnew.FromMM(0.15)     # JLCPCB: pad to silkscreen
NEAREST = pcbnew.FromMM(0.3)        # how near its part a designator may be: two line widths of JLCPCB's minimum
REACH = pcbnew.FromMM(8.0)          # how far from its part a designator may be
STEP = pcbnew.FromMM(0.25)          # between the places tried
VERTICAL = pcbnew.FromMM(0.5)       # what a horizontal designator may be further away than a vertical one
OTHERS = pcbnew.FromMM(4.0)         # the cost of being as near to another part
MARGIN = pcbnew.FromMM(0.5)         # how much nearer its own part a designator is to be than any other
CELL = pcbnew.FromMM(4.0)


def box_of(item, grow=0):
    box = item.GetBoundingBox()
    return (box.GetLeft() - grow, box.GetTop() - grow, box.GetRight() + grow, box.GetBottom() + grow)


def meet(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def apart(a, b):
    """The distance between two rectangles, 0 when they meet."""
    return max(a[0] - b[2], b[0] - a[2], a[1] - b[3], b[1] - a[3], 0)


class Taken:
    """Rectangles, found by the cells they lie in."""

    def __init__(self):
        self.cells = collections.defaultdict(list)

    def cells_of(self, box):
        for x in range(box[0] // CELL, box[2] // CELL + 1):
            for y in range(box[1] // CELL, box[3] // CELL + 1):
                yield x, y

    def add(self, box, owner=None):
        for cell in self.cells_of(box):
            self.cells[cell].append((box, owner))

    def remove(self, owner):
        for cell in self.cells.values():
            cell[:] = [entry for entry in cell if entry[1] != owner]

    def free(self, box):
        return not any(meet(box, other) for cell in self.cells_of(box) for other, _ in self.cells[cell])


def courtyard(footprint):
    """The rectangle around the part's courtyard and its outline on the
    silkscreen and the fabrication layer."""
    boxes = [box_of(item) for item in footprint.GraphicalItems()
             if item.GetClass() == "PCB_SHAPE" and item.GetLayer() in (pcbnew.F_CrtYd, pcbnew.F_SilkS, pcbnew.F_Fab)]
    return (min(box[0] for box in boxes), min(box[1] for box in boxes),
            max(box[2] for box in boxes), max(box[3] for box in boxes))


def lettering(text, height):
    """Set the text's size, and return for each of the two angles its
    rectangle's width and height and where that rectangle's middle lies from
    the text's position."""
    text.SetTextSize(pcbnew.VECTOR2I(height, height))
    text.SetTextThickness(round(height / 6 / 10000) * 10000)
    text.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    text.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    text.SetKeepUpright(True)
    text.SetVisible(True)
    text.SetLayer(pcbnew.F_SilkS)
    shapes = {}
    for angle in (0, 90):
        text.SetTextAngle(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T))
        # The rectangle around the strokes: the text's bounding box has room above and below them.
        box = text.GetEffectiveTextShape().BBox()
        shapes[angle] = (box.GetWidth(), box.GetHeight(),
                         box.Centre().x - text.GetPosition().x, box.Centre().y - text.GetPosition().y)
    return shapes


def places(own, shapes):
    """The rectangles to try around the part's courtyard, as (cost before
    the other parts are counted, distance, angle, rectangle)."""
    left, top, right, bottom = own
    middle_x, middle_y = (left + right) // 2, (top + bottom) // 2
    for gap in range(NEAREST, REACH, STEP):
        for angle, (width, height, _, _) in shapes.items():
            for x in range(left - width // 2, right + width // 2 + 1, STEP):
                for y in (top - gap - height // 2, bottom + gap + height // 2):
                    yield gap, angle, abs(x - middle_x), (x - width // 2, y - height // 2, x + width // 2, y + height // 2)
            for y in range(top - height // 2, bottom + height // 2 + 1, STEP):
                for x in (left - gap - width // 2, right + gap + width // 2):
                    yield gap, angle, abs(y - middle_y), (x - width // 2, y - height // 2, x + width // 2, y + height // 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--height", type=float, default=1.2)
    parser.add_argument("board")
    arguments = parser.parse_args()
    board = pcbnew.LoadBoard(arguments.board)
    footprints = sorted(board.GetFootprints(), key=lambda footprint: footprint.GetReference())
    if any(footprint.IsFlipped() for footprint in footprints):
        sys.exit("a part is on the back, and this script arranges the front's designators only")

    taken = Taken()
    courtyards = {footprint.GetReference(): courtyard(footprint) for footprint in footprints}
    for footprint in footprints:
        taken.add(courtyards[footprint.GetReference()])
        for pad in footprint.Pads():
            taken.add(box_of(pad, CLEARANCE))
        for item in list(footprint.GraphicalItems()) + [field for field in footprint.GetFields() if not field.IsReference()]:
            if item.GetLayer() == pcbnew.F_SilkS and (item.GetClass() != "PCB_FIELD" or item.IsVisible()):
                taken.add(box_of(item, CLEARANCE))
    for track in board.GetTracks():
        if track.Type() == pcbnew.PCB_VIA_T:
            taken.add(box_of(track))
    for drawing in board.GetDrawings():
        if drawing.GetLayer() == pcbnew.F_SilkS:
            taken.add(box_of(drawing, CLEARANCE))
    edge = board.GetBoardEdgesBoundingBox()
    inset = board.GetDesignSettings().m_CopperEdgeClearance
    inside = (edge.GetLeft() + inset, edge.GetTop() + inset, edge.GetRight() - inset, edge.GetBottom() - inset)

    shapes = {footprint.GetReference(): lettering(footprint.Reference(), pcbnew.FromMM(arguments.height))
              for footprint in footprints}

    def doubtful(designator, box):
        """Whether another part is as near the rectangle as the designator's own."""
        own = apart(box, courtyards[designator]) + MARGIN
        return any(apart(box, other) < own for name, other in courtyards.items() if name != designator)

    def best(designator):
        own, found = courtyards[designator], None
        for gap, angle, aside, box in places(own, shapes[designator]):
            if found and gap > found[0]:
                break       # every later place costs more than the one found
            if not (inside[0] <= box[0] and inside[1] <= box[1] and box[2] <= inside[2] and box[3] <= inside[3]):
                continue
            if not taken.free(box):
                continue
            cost = gap + (VERTICAL if angle else 0) + (OTHERS if doubtful(designator, box) else 0) + aside // 20
            if not found or cost < found[0]:
                found = (cost, angle, box)
        return found

    def count_free(designator):
        return sum(1 for _, _, _, box in places(courtyards[designator], shapes[designator])
                   if inside[0] <= box[0] and inside[1] <= box[1] and box[2] <= inside[2] and box[3] <= inside[3]
                   and taken.free(box))

    chosen = {}
    order = sorted(courtyards, key=count_free)
    for turn in range(3):
        for designator in order:
            taken.remove(designator)
            found = best(designator)
            if found:
                chosen[designator] = found
                taken.add(tuple(value + sign * CLEARANCE for value, sign in zip(found[2], (-1, -1, 1, 1))), designator)
            elif designator in chosen:
                box = chosen[designator][2]
                taken.add(tuple(value + sign * CLEARANCE for value, sign in zip(box, (-1, -1, 1, 1))), designator)

    for footprint in footprints:
        designator = footprint.GetReference()
        if designator not in chosen:
            continue
        _, angle, box = chosen[designator]
        _, _, aside_x, aside_y = shapes[designator][angle]
        text = footprint.Reference()
        text.SetTextAngle(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T))
        text.SetPosition(pcbnew.VECTOR2I((box[0] + box[2]) // 2 - aside_x, (box[1] + box[3]) // 2 - aside_y))
    # The third argument keeps KiCad from rewriting the project file with the board.
    pcbnew.SaveBoard(arguments.board, board, True)

    away = sorted(apart(chosen[name][2], courtyards[name]) for name in chosen)
    missing = sorted(set(courtyards) - set(chosen))
    unsure = sorted(name for name in chosen if doubtful(name, chosen[name][2]))
    print(f"{len(chosen)} of {len(courtyards)} designators placed at {arguments.height:g} mm, "
          f"{sum(1 for name in chosen if chosen[name][1])} of them vertical; "
          f"from its part: half within {pcbnew.ToMM(away[len(away) // 2]):.2f} mm, the furthest {pcbnew.ToMM(away[-1]):.2f} mm")
    if unsure:
        print("as near another part as its own, to be looked at: " + " ".join(unsure))
    if missing:
        print("no place found for: " + " ".join(missing))
        sys.exit(1)


if __name__ == "__main__":
    main()
