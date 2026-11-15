#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""squeeze_board.py -- move the board's parts closer together and draw the outline around them.

    scripts/squeeze_board.py <board> <squeeze>

The arrangement of the parts stays; the room between them shrinks. squeeze
is the share of that room that is kept: 1 leaves the board as it is, 0
brings every part to its neighbour's courtyard.

The arrangement is read off the board, a relation for every two parts whose
rectangles (the courtyard's, scripts/board_from_circuit.py's keep_out) face
each other:

  - beside each other (their heights overlap): the left one stays left;
  - above each other (their widths overlap): the upper one stays above;
  - rectangles that overlap (round test points set between each other), and
    a part that circuit/fixed_positions.toml puts beside another: the two
    move as one.

The distance between two related parts, and from a part to each edge of the
board, becomes

    floor + squeeze * (distance - floor)

where floor is the gap board_from_circuit.py keeps between courtyards and,
at an edge, the board's copper-to-edge clearance. A distance that is at or
under its floor stays as it is.

A part that circuit/fixed_positions.toml gives an edge keeps its distance
to that edge and slides along it.

The parts are packed from the left edge and then from the top edge: each
part goes as far left, then as far up, as its relations allow (the longest
path through the relations, as in the compaction of an integrated circuit's
layout). The right and the bottom edge follow the parts, and the fills
follow the outline. The script prints the chain of parts that sets the
width and the one that sets the height: a smaller board at the same squeeze
takes a change to a relation in those chains.

The tracks and vias are removed: they no longer meet the pads, and
scripts/route.sh lays them anew. Whether the squeezed board can be routed
is for route.sh and KiCad's DRC to say.

Runs under the system's Python, which has KiCad's pcbnew module.
"""
import math
import os
import sys
import tomllib

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from board_from_circuit import (BOTTOM, COURTYARD_GAP, EDGES, FIXED_POSITIONS, LEFT, RIGHT, TOP,  # noqa: E402
                                board_outline, keep_out)

STEP = pcbnew.FromMM(0.01)      # distances are rounded up to this
X, Y = 0, 1
LOW_EDGE, HIGH_EDGE = (LEFT, TOP), (RIGHT, BOTTOM)
EDGE_NAME = {LEFT: "the left edge", TOP: "the top edge", RIGHT: "the right edge", BOTTOM: "the bottom edge"}


def squeezed(distance, floor, squeeze):
    if distance <= floor:
        return distance
    return min(distance, floor + math.ceil(squeeze * (distance - floor) / STEP) * STEP)


def gap(a, b, axis):
    """The distance between two rectangles along an axis; negative where they overlap."""
    return max(a[axis] - b[axis + 2], b[axis] - a[axis + 2])


def pack(axis, names, start, size, relations, moving_as_one, low_gap, high_gap, at_low_edge, at_high_edge):
    """Each part as near the low edge as its relations allow.

    relations holds (first, second, distance): second starts at least
    distance after first ends. moving_as_one holds (a, b, offset): b starts
    offset after a starts. Returns each part's start, the extent of the
    board along the axis, and the chain of parts that sets the extent.
    """
    at_least = [(a, b, size[a] + distance) for a, b, distance in relations]
    at_least += [(a, b, offset) for a, b, offset in moving_as_one] + [(b, a, -offset) for a, b, offset in moving_as_one]
    lowest = {name: start[name] if name in at_low_edge else low_gap[name] for name in names}
    extent, chain = 0, []
    while True:
        position, pushed_by = dict(lowest), {}
        for _ in range(len(names) + 1):
            moved = False
            for a, b, distance in at_least:
                if position[b] < position[a] + distance:
                    position[b], pushed_by[b], moved = position[a] + distance, a, True
            if not moved:
                break
        else:
            sys.exit("the relations between the parts contradict each other")
        reach, last = max((position[name] + size[name] + high_gap[name], name) for name in names)
        if reach > extent:
            extent, chain = reach, [last]
            while chain[-1] in pushed_by and len(chain) <= len(names):
                chain.append(pushed_by[chain[-1]])
        behind = [name for name in at_high_edge if position[name] < extent - size[name] - high_gap[name]]
        if not behind:
            break
        for name in behind:
            lowest[name] = extent - size[name] - high_gap[name]
    return position, extent, [EDGE_NAME[LOW_EDGE[axis]]] + chain[::-1] + [EDGE_NAME[HIGH_EDGE[axis]]]


def main(board_path, squeeze):
    board = pcbnew.LoadBoard(board_path)
    outline_drawings = [drawing for drawing in board.GetDrawings() if drawing.GetLayer() == pcbnew.Edge_Cuts]
    if len(outline_drawings) != 1 or outline_drawings[0].GetShape() != pcbnew.SHAPE_T_RECTANGLE:
        sys.exit("only an outline that is one rectangle is handled")
    outline = board_outline(board)
    extent = (outline[RIGHT] - outline[LEFT], outline[BOTTOM] - outline[TOP])
    edge_floor = board.GetDesignSettings().m_CopperEdgeClearance
    fixed = tomllib.load(open(FIXED_POSITIONS, "rb"))

    footprints = {footprint.GetReference(): footprint for footprint in board.GetFootprints()}
    names = sorted(footprints)
    # Each part's rectangle, measured from the board's left and top edge.
    box = {name: [side - outline[index % 2] for index, side in enumerate(keep_out(footprints[name]))] for name in names}

    as_one = {tuple(sorted((name, rule["beside"]))) for name, rule in fixed.items() if "beside" in rule}
    beside, above, undecided = [], [], []
    for index, a in enumerate(names):
        for b in names[index + 1:]:
            apart = (gap(box[a], box[b], X), gap(box[a], box[b], Y))
            if (a, b) in as_one:
                continue
            if apart[X] < 0 and apart[Y] < 0:
                as_one.add((a, b))
            elif apart[Y] < 0 or (apart[X] >= 0 and apart[Y] < COURTYARD_GAP):
                beside.append((a, b) if box[a][X] < box[b][X] else (b, a))
            elif apart[X] < COURTYARD_GAP:
                above.append((a, b) if box[a][Y] < box[b][Y] else (b, a))
            else:
                undecided.append((a, b) if box[a][Y] < box[b][Y] else (b, a))

    new_start, new_extent, chains = {}, [0, 0], [[], []]
    for axis, pairs in ((X, beside), (Y, above)):
        if axis == Y:
            # Two parts that were apart both ways and now share a width are kept above each other.
            for a, b in undecided:
                a_start, b_start = new_start[X][a], new_start[X][b]
                if max(a_start - b_start - (box[b][X + 2] - box[b][X]),
                       b_start - a_start - (box[a][X + 2] - box[a][X])) < COURTYARD_GAP:
                    pairs = pairs + [(a, b)]
        start = {name: box[name][axis] for name in names}
        size = {name: box[name][axis + 2] - box[name][axis] for name in names}
        new_start[axis], new_extent[axis], chains[axis] = pack(
            axis, names, start, size,
            relations=[(a, b, squeezed(gap(box[a], box[b], axis), COURTYARD_GAP, squeeze)) for a, b in pairs],
            moving_as_one=[(a, b, start[b] - start[a]) for a, b in sorted(as_one)],
            low_gap={name: squeezed(start[name], edge_floor, squeeze) for name in names},
            high_gap={name: (extent[axis] - box[name][axis + 2] if EDGES.get(fixed.get(name, {}).get("edge")) == HIGH_EDGE[axis]
                             else squeezed(extent[axis] - box[name][axis + 2], edge_floor, squeeze)) for name in names},
            at_low_edge={name for name in names if EDGES.get(fixed.get(name, {}).get("edge")) == LOW_EDGE[axis]},
            at_high_edge={name for name in names if EDGES.get(fixed.get(name, {}).get("edge")) == HIGH_EDGE[axis]})

    for name in names:
        footprints[name].Move(pcbnew.VECTOR2I(new_start[X][name] - box[name][X], new_start[Y][name] - box[name][Y]))
    corners = [(outline[LEFT], outline[TOP]), (outline[LEFT] + new_extent[X], outline[TOP]),
               (outline[LEFT] + new_extent[X], outline[TOP] + new_extent[Y]), (outline[LEFT], outline[TOP] + new_extent[Y])]
    outline_drawings[0].SetStart(pcbnew.VECTOR2I(*corners[0]))
    outline_drawings[0].SetEnd(pcbnew.VECTOR2I(*corners[2]))
    for fill in board.Zones():
        fill.UnFill()
        fill.Outline().RemoveAllContours()
        fill.Outline().NewOutline()
        for corner in corners:
            fill.Outline().Append(*corner)
    for track in list(board.GetTracks()):
        board.Delete(track)
    # The third argument keeps KiCad from rewriting the project file with the board.
    pcbnew.SaveBoard(board_path, board, True)

    def square_cm(width, height):
        return pcbnew.ToMM(width) * pcbnew.ToMM(height) / 100

    courtyards = sum(square_cm(box[name][X + 2] - box[name][X], box[name][Y + 2] - box[name][Y]) for name in names)
    print(f"squeeze {squeeze:g}: {pcbnew.ToMM(extent[X]):.2f} x {pcbnew.ToMM(extent[Y]):.2f} mm, {square_cm(*extent):.1f} cm2 "
          f"-> {pcbnew.ToMM(new_extent[X]):.2f} x {pcbnew.ToMM(new_extent[Y]):.2f} mm, {square_cm(*new_extent):.1f} cm2; "
          f"the parts' rectangles cover {100 * courtyards / square_cm(*new_extent):.0f} % of it")
    print(f"{len(beside)} pairs beside each other, {len(above)} above each other, "
          f"{len(as_one)} moving as one: {' '.join('+'.join(pair) for pair in sorted(as_one))}")
    print("the width is set by: ", ", ".join(chains[X]))
    print("the height is set by:", ", ".join(chains[Y]))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], float(sys.argv[2]))
