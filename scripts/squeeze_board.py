#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""squeeze_board.py -- make the board smaller: the parts at its edges closer together, the others beside what they connect to.

    scripts/squeeze_board.py <netlist> <board> <squeeze>

The netlist is the one circuit/board.py writes (board.net). squeeze is the
share that is kept of the room between the parts at the board's edges: 1
leaves them as they are, 0 brings each to its neighbour's courtyard.

The parts at the edges are those circuit/fixed_positions.toml names: what a
person plugs into. Their arrangement stays. It is read off the board, a
relation for every two of them whose rectangles (the one around a part's
courtyard, drawn outline and rule areas, scripts/board_from_circuit.py's
keep_out) face each other:

  - beside each other (their heights overlap): the left one stays left;
  - above each other (their widths overlap): the upper one stays above;
  - a part that the file puts beside another: the two move as one.

The distance between two related parts, and from a part to each edge of the
board, becomes

    floor + squeeze * (distance - floor)

where floor is the gap board_from_circuit.py keeps between courtyards and,
at an edge, the board's copper-to-edge clearance. A distance that is at or
under its floor stays as it is. A part keeps its distance to its own edge
and slides along it.

These parts are packed from the left edge and then from the top edge: each
goes as far left, then as far up, as its relations allow (the longest path
through the relations, as in the compaction of an integrated circuit's
layout). The right and the bottom edge follow them, and the fills follow
the outline. The script prints the chain of parts that sets the width and
the one that sets the height.

Every other part is then placed anew, the ones with the most pads first:
at the free place where its pads are nearest to the pads they connect to,
turned whichever way brings them nearest. A pad's connections are looked
for in the part's own block of the circuit (its SubCircuit), and on the
whole board when the block has none on that net. A pad on the net of a fill
counts only for a part that has no other pad to go by, since a fill is
everywhere. Where such a part sits on the board that is read plays no role.

A part placed so keeps room for a via to every other part: the via of the
default net class and that class's clearance on both sides of it. A
surface-mount pad on the net of a fill is joined to the fill by a via
beside the part (scripts/join_fills.py), and a pad between two parts that
stand courtyard to courtyard has no place for one.

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
                                board_outline, keep_out, read_circuit, settle_at_its_connections)

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


def squeeze_edge_parts(footprints, fixed, outline, edge_floor, squeeze):
    """Move the parts at the board's edges closer together. Returns the
    board's width and height around them and the chains of parts that set
    the two."""
    names = sorted(fixed)
    extent = (outline[RIGHT] - outline[LEFT], outline[BOTTOM] - outline[TOP])
    own_edge = {name: EDGES.get(fixed[name].get("edge")) for name in names}
    # Each part's rectangle, measured from the board's left and top edge.
    box = {name: [side - outline[index % 2] for index, side in enumerate(keep_out(footprints[name]))] for name in names}

    as_one = {tuple(sorted((name, rule["beside"]))) for name, rule in fixed.items() if "beside" in rule}
    beside, above, undecided = [], [], []
    for index, a in enumerate(names):
        for b in names[index + 1:]:
            apart = (gap(box[a], box[b], X), gap(box[a], box[b], Y))
            if (a, b) in as_one:
                continue
            if apart[Y] < 0 or (apart[X] >= 0 and apart[Y] < COURTYARD_GAP):
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
            high_gap={name: (extent[axis] - box[name][axis + 2] if own_edge[name] == HIGH_EDGE[axis]
                             else squeezed(extent[axis] - box[name][axis + 2], edge_floor, squeeze)) for name in names},
            at_low_edge={name for name in names if own_edge[name] == LOW_EDGE[axis]},
            at_high_edge={name for name in names if own_edge[name] == HIGH_EDGE[axis]})

    for name in names:
        footprints[name].Move(pcbnew.VECTOR2I(new_start[X][name] - box[name][X], new_start[Y][name] - box[name][Y]))
    return new_extent, chains


def connections(designator, footprints, parts, nets, placed, fill_nets):
    """For each of the part's pads, by number, the places of the pads it
    connects to on the parts that are placed."""
    on_signals, on_fills = {}, {}
    for net, pads in nets.items():
        for number in {number for part, number in pads if part == designator}:
            others = [(part, other) for part, other in pads if part in placed]
            in_block = [(part, other) for part, other in others if parts[part]["block"] == parts[designator]["block"]]
            targets = [pad.GetPosition() for part, other in in_block or others
                       for pad in footprints[part].Pads() if pad.GetNumber() == other]
            if targets:
                (on_fills if net in fill_nets else on_signals)[number] = targets
    return on_signals or on_fills


def furthest_connection(footprint, reach):
    """The longest of the distances from the part's pads to the nearest pad each connects to."""
    return max(min(math.hypot(pad.GetPosition().x - target.x, pad.GetPosition().y - target.y)
                   for target in reach[pad.GetNumber()])
               for pad in footprint.Pads() if pad.GetNumber() in reach)


def main(netlist_path, board_path, squeeze):
    parts, nets, _ = read_circuit(netlist_path)
    board = pcbnew.LoadBoard(board_path)
    outline_drawings = [drawing for drawing in board.GetDrawings() if drawing.GetLayer() == pcbnew.Edge_Cuts]
    if len(outline_drawings) != 1 or outline_drawings[0].GetShape() != pcbnew.SHAPE_T_RECTANGLE:
        sys.exit("only an outline that is one rectangle is handled")
    outline = board_outline(board)
    extent = (outline[RIGHT] - outline[LEFT], outline[BOTTOM] - outline[TOP])
    fixed = tomllib.load(open(FIXED_POSITIONS, "rb"))
    footprints = {footprint.GetReference(): footprint for footprint in board.GetFootprints()}

    new_extent, chains = squeeze_edge_parts(footprints, fixed, outline,
                                            board.GetDesignSettings().m_CopperEdgeClearance, squeeze)
    corners = [(outline[LEFT], outline[TOP]), (outline[LEFT] + new_extent[X], outline[TOP]),
               (outline[LEFT] + new_extent[X], outline[TOP] + new_extent[Y]), (outline[LEFT], outline[TOP] + new_extent[Y])]
    outline_drawings[0].SetStart(pcbnew.VECTOR2I(*corners[0]))
    outline_drawings[0].SetEnd(pcbnew.VECTOR2I(*corners[2]))
    fill_nets = {fill.GetNetname() for fill in board.Zones()}
    for fill in board.Zones():
        fill.UnFill()
        fill.Outline().RemoveAllContours()
        fill.Outline().NewOutline()
        for corner in corners:
            fill.Outline().Append(*corner)
    for track in list(board.GetTracks()):
        board.Delete(track)

    # The other parts leave the board and come back one at a time, each beside what it connects to.
    default_class = board.GetDesignSettings().m_NetSettings.GetDefaultNetclass()
    room_for_a_via = default_class.GetViaDiameter() + 2 * default_class.GetClearance()
    waiting = sorted(set(footprints) - set(fixed), key=lambda name: (-footprints[name].GetPadCount(), name))
    off_the_board = pcbnew.VECTOR2I(outline[LEFT] - 10 * extent[X], outline[TOP])
    for name in waiting:
        footprints[name].SetPosition(off_the_board)
    placed, furthest = set(fixed), (0, None)
    while waiting:
        for name in waiting:
            reach = connections(name, footprints, parts, nets, placed, fill_nets)
            if reach:
                break
        else:
            sys.exit(f"these connect to nothing that is placed: {' '.join(waiting)}")
        settle_at_its_connections(board, footprints[name], reach, gap=room_for_a_via)
        furthest = max(furthest, (furthest_connection(footprints[name], reach), name))
        placed.add(name)
        waiting.remove(name)
    # The third argument keeps KiCad from rewriting the project file with the board.
    pcbnew.SaveBoard(board_path, board, True)

    def square_cm(width, height):
        return pcbnew.ToMM(width) * pcbnew.ToMM(height) / 100

    rectangles = [keep_out(footprint) for footprint in footprints.values()]
    covered = sum(square_cm(box[RIGHT] - box[LEFT], box[BOTTOM] - box[TOP]) for box in rectangles)
    print(f"squeeze {squeeze:g}: {pcbnew.ToMM(extent[X]):.2f} x {pcbnew.ToMM(extent[Y]):.2f} mm, {square_cm(*extent):.1f} cm2 "
          f"-> {pcbnew.ToMM(new_extent[X]):.2f} x {pcbnew.ToMM(new_extent[Y]):.2f} mm, {square_cm(*new_extent):.1f} cm2; "
          f"the parts' rectangles cover {100 * covered / square_cm(*new_extent):.0f} % of it")
    print("the width is set by: ", ", ".join(chains[X]))
    print("the height is set by:", ", ".join(chains[Y]))
    print(f"{len(footprints) - len(fixed)} parts placed beside what they connect to; "
          f"the furthest pad from its connection: {pcbnew.ToMM(furthest[0]):.1f} mm, on {furthest[1]}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]))
