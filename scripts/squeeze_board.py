#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""squeeze_board.py -- make the board smaller: the parts at its edges packed along them, the others beside what they connect to.

    scripts/squeeze_board.py <netlist> <board> <room> [<widest mm>]

The netlist is the one circuit/board.py writes (board.net).

The parts at the edges are those circuit/fixed_positions.toml names: what a
person plugs into. Each is at the edge the file gives it, at the distance
to an edge that it has on the board, and is free to slide along it; one the
board has at another edge is turned to face the file's. A part the file
puts beside another moves with that one, and a part the file puts near pads
of another sits level with them. Where the others sit along their edges on
the board that is read plays no role.

No part with a pad of a net class that an antenna is kept clear of
(circuit/antennas.toml) is put inside that antenna's clearance, which
moves with the antenna's part and is drawn on the board where that part
ends up.

Every other part belongs to one of them: the one it has the most
connections to, directly or through a part that belongs to it. A part at
an edge keeps a margin free on the sides that do not face its edge, for
the parts that belong to it and their tracks: as wide as it takes for the
band around those three sides, with its two corners, to hold

    room * (the area of the parts that belong to it)

so room is how many times the area those parts cover is kept free, and
the one number that says how tight the board is. Two parts at different
edges are at least the sum of their margins apart, and each is its margin
from the edges that are not its own. Two parts at the same edge may stand
side by side, with room for a via between them: their own parts then sit
on the side that faces the board. A part's area is that of its rectangle
(the one around its courtyard, drawn outline and rule areas,
scripts/board_from_circuit.py's keep_out), with room for a via added to
its width and its height.

The script looks for the smallest outline, by area, in which the parts at
the edges can be put down so: it finds the smallest height for the board's
width, then makes the board narrower step by step, raising the height
whenever the parts no longer fit; for a width and a height it tries the
places along the edges one part after the other. The right and the bottom
edge move; the fills follow the outline. Without a width the outline is no
larger than the board is. With one it is no wider than that, and as tall
as it takes: the smallest outline is not the narrowest.

Every other part is then placed anew, the ones with the most pads first:
at the free place where its pads are nearest to the pads they connect to,
turned whichever way brings them nearest. A pad's connections are looked
for in the part's own block of the circuit (its SubCircuit), and on the
whole board when the block has none on that net. A pad on the net of a fill
counts only for a part that has no other pad to go by, since a fill is
everywhere. A part that finds no place near its connections is looked for
one further away, on a coarser grid. No part is placed where a
differential pair will run (scripts/lay_pairs.py's lanes).

A part placed so keeps room for a via to every other part: the via of the
default net class and that class's clearance on both sides of it. A
surface-mount pad on the net of a fill is joined to the fill by a via
beside the part (scripts/join_fills.py), and a pad between two parts that
stand courtyard to courtyard has no place for one.

The tracks and vias are removed: they no longer meet the pads, and
scripts/route.sh lays them anew. Whether the board can be routed is for
route.sh and KiCad's DRC to say.

Runs under the system's Python, which has KiCad's pcbnew module.
"""
import collections
import math
import os
import sys
import tomllib

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from board_from_circuit import (ANTENNAS, BOTTOM, EDGES, FIXED_POSITIONS, LEFT, RIGHT, TOP, NoFreePlace,  # noqa: E402
                                antenna_clearances, beside_offset, board_outline, closed_to, draw_antenna_clearances,
                                keep_out, middle, nearer_than, pad_centre, pad_named, read_circuit,
                                settle_at_its_connections)
from lay_pairs import lanes  # noqa: E402

STEP = pcbnew.FromMM(2.0)       # of the search for the outline and for the places along the edges
FURTHER = pcbnew.FromMM(60.0)   # how far from its connections a part is looked for a place when there is none near them
FURTHER_GRID = pcbnew.FromMM(1.0)
EDGE_NAME = {LEFT: "left", TOP: "top", RIGHT: "right", BOTTOM: "bottom"}


def connections(designator, footprints, parts, nets, placed, fill_nets):
    """For each of the part's pads, by number, the pads it connects to on
    the parts that are placed, as [(part, place)]."""
    on_signals, on_fills = {}, {}
    for net, pads in nets.items():
        for number in {number for part, number in pads if part == designator}:
            others = [(part, other) for part, other in pads if part in placed]
            in_block = [(part, other) for part, other in others if parts[part]["block"] == parts[designator]["block"]]
            targets = [(part, pad.GetPosition()) for part, other in in_block or others
                       for pad in footprints[part].Pads() if pad.GetNumber() == other]
            if targets:
                (on_fills if net in fill_nets else on_signals)[number] = targets
    return on_signals or on_fills


def in_order(waiting, footprints, parts, nets, fixed, fill_nets):
    """The parts that are not at an edge, one at a time, each with its
    connections to the parts before it: the first in the list that connects
    to a part already dealt with."""
    waiting, placed = list(waiting), set(fixed)
    while waiting:
        for name in waiting:
            reach = connections(name, footprints, parts, nets, placed, fill_nets)
            if reach:
                break
        else:
            sys.exit(f"these connect to nothing that is placed: {' '.join(waiting)}")
        yield name, reach
        placed.add(name)
        waiting.remove(name)


def furthest_connection(footprint, reach):
    """The longest of the distances from the part's pads to the nearest pad each connects to."""
    return max(min(math.hypot(pad.GetPosition().x - target.x, pad.GetPosition().y - target.y)
                   for _, target in reach[pad.GetNumber()])
               for pad in footprint.Pads() if pad.GetNumber() in reach)


def margins(inner, footprints, parts, nets, fixed, fill_nets, edge_of, room, least):
    """What each part at an edge keeps free around it, and how many parts
    belong to it."""
    owner = {name: name for name in fixed}
    for name, reach in in_order(inner, footprints, parts, nets, fixed, fill_nets):
        votes = collections.Counter(owner[part] for targets in reach.values() for part, _ in targets)
        owner[name] = max(sorted(votes), key=votes.get)
    area, count = collections.Counter(), collections.Counter()
    for name in inner:
        box = keep_out(footprints[name])
        area[owner[name]] += (box[RIGHT] - box[LEFT] + least) * (box[BOTTOM] - box[TOP] + least)
        count[owner[name]] += 1
    margin = {}
    for name in fixed:
        box = keep_out(footprints[name])
        width, height = box[RIGHT] - box[LEFT], box[BOTTOM] - box[TOP]
        free_sides = 2 * (width + height) - (height if edge_of[name] in (LEFT, RIGHT) else width)
        # margin * free_sides + 2 * margin ** 2 = room * area: the band and its two corners.
        margin[name] = max(least, int((math.sqrt(free_sides ** 2 + 8 * room * area[name]) - free_sides) / 4))
    return margin, count


def smallest_outline(blocks, margin, closed, least, extent, largest):
    """The smallest width and height, by area, in which the blocks can be
    put down along their edges, and how far each then slides. extent is the
    width and height the board has, largest the ones the search starts from.

    A block is (edge, [(part, rectangle)], near): parts that move as one,
    each with its rectangle (left, top, right, bottom) measured from the
    board's left and top edge as the board is. A block at the right or the
    bottom edge moves with that edge. near is None for a block that is free
    along its edge; for one that sits level with pads of another part it is
    (the slide that brings it there as the board is, that part's edge), and
    the block has that one place.

    closed holds what a part keeps other parts out of, as {part: [(rectangle
    measured from the left and top of the part's own, the parts kept out)]}.
    least is what two parts at the same edge keep between them.
    """
    at = {name: edge for edge, members, _ in blocks for name, _ in members}

    def moved(block, slide, width, height):
        edge, members, _ = block
        dx = slide if edge in (TOP, BOTTOM) else (width - extent[0] if edge == RIGHT else 0)
        dy = slide if edge in (LEFT, RIGHT) else (height - extent[1] if edge == BOTTOM else 0)
        return [(name, (box[LEFT] + dx, box[TOP] + dy, box[RIGHT] + dx, box[BOTTOM] + dy)) for name, box in members]

    def inside(block, members, width, height):
        return all(block[0] == edge or distance >= margin[name]
                   for name, box in members
                   for edge, distance in ((LEFT, box[LEFT]), (TOP, box[TOP]),
                                          (RIGHT, width - box[RIGHT]), (BOTTOM, height - box[BOTTOM])))

    def let_in(owner, box, name, other):
        return not any(name in kept_out and nearer_than(other, (box[LEFT] + area[LEFT], box[TOP] + area[TOP],
                                                                box[LEFT] + area[RIGHT], box[TOP] + area[BOTTOM]), 0)
                       for area, kept_out in closed.get(owner, ()))

    def apart(members, others):
        return all(max(a[LEFT] - b[RIGHT], b[LEFT] - a[RIGHT], a[TOP] - b[BOTTOM], b[TOP] - a[BOTTOM])
                   >= (least if at[name] == at[other] else margin[name] + margin[other])
                   and let_in(name, a, other, b) and let_in(other, b, name, a)
                   for name, a in members for other, b in others)

    def slides(block, width, height):
        edge, members, near = block
        low, high = (LEFT, RIGHT) if edge in (TOP, BOTTOM) else (TOP, BOTTOM)
        length = width if edge in (TOP, BOTTOM) else height
        first = max(margin[name] - box[low] for name, box in members)
        last = min(length - margin[name] - box[high] for name, box in members)
        candidates = range(-(-first // STEP) * STEP, last + 1, STEP)
        if near:
            # The pads it is level with move with their part's edge.
            level, near_edge = near
            level += width - extent[0] if near_edge == RIGHT else height - extent[1] if near_edge == BOTTOM else 0
            candidates = [level] if first <= level <= last else []
        return [(slide, members_there) for slide in candidates
                for members_there in [moved(block, slide, width, height)] if inside(block, members_there, width, height)]

    def put_down(places):
        """places holds, for each block still to be put down, the places
        along its edge that clear the blocks that are down. Returns how far
        each of those blocks slides, or None when they cannot all be put down."""
        if not places:
            return []
        for slide, members in places[0]:
            left = [[(other_slide, others) for other_slide, others in candidates if apart(members, others)]
                    for candidates in places[1:]]
            if all(left):
                rest = put_down(left)
                if rest is not None:
                    return [slide] + rest
        return None

    def fits(width, height):
        return put_down([slides(block, width, height) for block in blocks])

    if fits(*largest) is None:
        sys.exit("the parts at the edges do not fit in an outline that size with this much room")
    low, height = 0, largest[1]             # no room at low, room at height
    while height - low > STEP:
        middle = (low + height) // 2
        low, height = (low, middle) if fits(largest[0], middle) is not None else (middle, height)
    # A narrower board is never lower: the height only grows as the width shrinks.
    best, width = (largest[0], height), largest[0] - STEP
    while width > 0 and height <= largest[1]:
        if fits(width, height) is None:
            height += STEP
            continue
        if width * height < best[0] * best[1]:
            best = (width, height)
        width -= STEP
    return best, fits(*best)


def main(netlist_path, board_path, room, widest=None):
    parts, nets, class_of_net = read_circuit(netlist_path)
    board = pcbnew.LoadBoard(board_path)
    outline_drawings = [drawing for drawing in board.GetDrawings() if drawing.GetLayer() == pcbnew.Edge_Cuts]
    if len(outline_drawings) != 1 or outline_drawings[0].GetShape() != pcbnew.SHAPE_T_RECTANGLE:
        sys.exit("only an outline that is one rectangle is handled")
    outline = board_outline(board)
    extent = (outline[RIGHT] - outline[LEFT], outline[BOTTOM] - outline[TOP])
    fixed = tomllib.load(open(FIXED_POSITIONS, "rb"))
    antennas = tomllib.load(open(ANTENNAS, "rb"))["antenna"]
    footprints = {footprint.GetReference(): footprint for footprint in board.GetFootprints()}
    fills = [zone for zone in board.Zones() if not zone.GetIsRuleArea()]
    fill_nets = {fill.GetNetname() for fill in fills}
    default_class = board.GetDesignSettings().m_NetSettings.GetDefaultNetclass()
    room_for_a_via = default_class.GetViaDiameter() + 2 * default_class.GetClearance()
    inner = sorted(set(footprints) - set(fixed), key=lambda name: (-footprints[name].GetPadCount(), name))

    # The parts that move as one: a part with an edge, and those the file puts beside it.
    edge_of = {name: EDGES[rule["edge"]] for name, rule in fixed.items() if "edge" in rule}
    # A part the board has at another edge than the file is turned to face the file's, at the distance to the edge it has.
    for name, edge in edge_of.items():
        box = keep_out(footprints[name])
        to_edge = {LEFT: box[LEFT] - outline[LEFT], TOP: box[TOP] - outline[TOP],
                   RIGHT: outline[RIGHT] - box[RIGHT], BOTTOM: outline[BOTTOM] - box[BOTTOM]}
        drawn_at = min(to_edge, key=to_edge.get)
        if drawn_at != edge:
            footprints[name].SetOrientationDegrees(footprints[name].GetOrientationDegrees() + 90 * ((drawn_at - edge) % 4))
            box = keep_out(footprints[name])
            footprints[name].Move(pcbnew.VECTOR2I(*{
                LEFT: (outline[LEFT] + to_edge[drawn_at] - box[LEFT], 0), TOP: (0, outline[TOP] + to_edge[drawn_at] - box[TOP]),
                RIGHT: (outline[RIGHT] - to_edge[drawn_at] - box[RIGHT], 0),
                BOTTOM: (0, outline[BOTTOM] - to_edge[drawn_at] - box[BOTTOM])}[edge]))
    members_of = {name: [name] for name in edge_of}
    for name, rule in fixed.items():
        if "beside" in rule:
            neighbour = footprints[rule["beside"]]
            edge_of[name] = edge_of[rule["beside"]]
            footprints[name].SetOrientationDegrees(neighbour.GetOrientationDegrees())
            footprints[name].SetPosition(neighbour.GetPosition() + beside_offset(rule, edge_of[name]))
            members_of[rule["beside"]].append(name)
    margin, belonging = margins(inner, footprints, parts, nets, fixed, fill_nets, edge_of, room, room_for_a_via)

    # A part that sits near pads of another has one place along its edge: level with them.
    near = {}
    for name, rule in fixed.items():
        if "near" in rule:
            pads = [pad_named(board, pad) for pad in rule["near"]]
            near_edge = edge_of[rule["near"][0].split(".")[0]]
            if (edge_of[name] in (TOP, BOTTOM)) == (near_edge in (TOP, BOTTOM)):
                sys.exit(f"{name} is near pads of a part at its own edge or the one across: not handled")
            to_level = middle([pad.GetPosition() for pad in pads]) - pad_centre(footprints[name])
            near[name] = (to_level.x if edge_of[name] in (TOP, BOTTOM) else to_level.y, near_edge)

    def from_corner(box):
        return (box[LEFT] - outline[LEFT], box[TOP] - outline[TOP], box[RIGHT] - outline[LEFT], box[BOTTOM] - outline[TOP])

    # What an antenna keeps out moves with the antenna's part.
    closed = collections.defaultdict(list)
    for part, area, kept_out in antenna_clearances(board, antennas):
        box = keep_out(footprints[part])
        closed[part].append(((area[LEFT] - box[LEFT], area[TOP] - box[TOP], area[RIGHT] - box[LEFT], area[BOTTOM] - box[TOP]),
                             {name for name in fixed if closed_to(footprints[name], [(part, area, kept_out)], class_of_net)}))

    # The largest first: it has the fewest places.
    blocks = sorted(((edge_of[first], [(name, from_corner(keep_out(footprints[name]))) for name in members], near.get(first))
                     for first, members in members_of.items()),
                    key=lambda block: -sum((box[RIGHT] - box[LEFT]) * (box[BOTTOM] - box[TOP]) for _, box in block[1]))
    # Without a width the outline is no larger than the board is; with one, no wider than it and as tall as it takes:
    # the parts at the edges one below the other is the tallest it gets.
    largest = extent
    if widest is not None:
        largest = (min(extent[0], pcbnew.FromMM(widest)),
                   sum(box[BOTTOM] - box[TOP] + 2 * margin[name] for _, members, _ in blocks for name, box in members))
    new_extent, slides = smallest_outline(blocks, margin, closed, room_for_a_via, extent, largest)
    for (edge, members, _), slide in zip(blocks, slides):
        dx = slide if edge in (TOP, BOTTOM) else (new_extent[0] - extent[0] if edge == RIGHT else 0)
        dy = slide if edge in (LEFT, RIGHT) else (new_extent[1] - extent[1] if edge == BOTTOM else 0)
        for name, _ in members:
            footprints[name].Move(pcbnew.VECTOR2I(dx, dy))

    corners = [(outline[LEFT], outline[TOP]), (outline[LEFT] + new_extent[0], outline[TOP]),
               (outline[LEFT] + new_extent[0], outline[TOP] + new_extent[1]), (outline[LEFT], outline[TOP] + new_extent[1])]
    outline_drawings[0].SetStart(pcbnew.VECTOR2I(*corners[0]))
    outline_drawings[0].SetEnd(pcbnew.VECTOR2I(*corners[2]))
    for fill in fills:
        fill.UnFill()
        fill.Outline().RemoveAllContours()
        fill.Outline().NewOutline()
        for corner in corners:
            fill.Outline().Append(*corner)
    clearances = antenna_clearances(board, antennas)
    draw_antenna_clearances(board, clearances)
    for track in list(board.GetTracks()):
        board.Delete(track)
    pair_lanes = lanes(board)

    # The other parts leave the board and come back one at a time, each beside what it connects to.
    off_the_board = pcbnew.VECTOR2I(outline[LEFT] - 10 * extent[0], outline[TOP])
    for name in inner:
        footprints[name].SetPosition(off_the_board)
    furthest, placed_further = (0, None), []
    further = sorted(((dx, dy) for dx in range(-FURTHER, FURTHER + 1, FURTHER_GRID)
                      for dy in range(-FURTHER, FURTHER + 1, FURTHER_GRID)), key=lambda move: math.hypot(*move))
    for name, reach in in_order(inner, footprints, parts, nets, fixed, fill_nets):
        places = {number: [place for _, place in targets] for number, targets in reach.items()}
        kept_clear = closed_to(footprints[name], clearances, class_of_net) + pair_lanes
        try:
            settle_at_its_connections(board, footprints[name], places, gap=room_for_a_via, closed=kept_clear)
        except NoFreePlace:
            try:
                settle_at_its_connections(board, footprints[name], places, gap=room_for_a_via, moves=further, closed=kept_clear)
            except NoFreePlace:
                sys.exit(f"no free place for {name}")
            placed_further.append(name)
        furthest = max(furthest, (furthest_connection(footprints[name], reach), name))
    # The third argument keeps KiCad from rewriting the project file with the board.
    pcbnew.SaveBoard(board_path, board, True)

    def square_cm(width, height):
        return pcbnew.ToMM(width) * pcbnew.ToMM(height) / 100

    print(f"room {room:g}: {pcbnew.ToMM(extent[0]):.2f} x {pcbnew.ToMM(extent[1]):.2f} mm, {square_cm(*extent):.1f} cm2 "
          f"-> {pcbnew.ToMM(new_extent[0]):.2f} x {pcbnew.ToMM(new_extent[1]):.2f} mm, {square_cm(*new_extent):.1f} cm2")
    for name in sorted(fixed, key=lambda name: (edge_of[name], name)):
        box = from_corner(keep_out(footprints[name]))
        low, high = (LEFT, RIGHT) if edge_of[name] in (TOP, BOTTOM) else (TOP, BOTTOM)
        print(f"  {name:4} at the {EDGE_NAME[edge_of[name]]:6} edge, {pcbnew.ToMM(box[low]):6.1f} to "
              f"{pcbnew.ToMM(box[high]):6.1f} mm along it; {belonging[name]:2} parts belong to it, "
              f"{pcbnew.ToMM(margin[name]):4.1f} mm kept free around it")
    print(f"{len(inner)} parts placed beside what they connect to; "
          f"the furthest pad from its connection: {pcbnew.ToMM(furthest[0]):.1f} mm, on {furthest[1]}")
    if placed_further:
        print(f"no place near their connections, placed further away, to be looked at: {' '.join(placed_further)}")


if __name__ == "__main__":
    if len(sys.argv) not in (4, 5):
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], *(float(number) for number in sys.argv[3:]))
