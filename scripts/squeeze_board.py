#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""squeeze_board.py -- place the parts and draw the outline: a cluster around each part at an edge, the clusters packed along the edges.

    scripts/squeeze_board.py <netlist> <board> <room mm> [<widest mm>]

The netlist is the one circuit/board.py writes (board.net).

The parts at the edges are those circuit/fixed_positions.toml names: what a
person plugs into. Each is at the edge the file gives it, at the distance
to an edge that it has on the board, and is free to slide along it; one the
board has at another edge is turned to face the file's. A part the file
puts beside another moves with that one, a part the file puts below,
above, left of or right of another lies wholly on that side of it, and a
part the file puts near pads of another sits level with them. Where the
others sit along their edges on the board that is read plays no role.

No part with a pad of a net class that an antenna is kept clear of
(circuit/antennas.toml) is put inside that antenna's clearance, which
moves with the antenna's part and is drawn on the board where that part
ends up.

Every other part that has one is in the cluster of its hub: the part at an
edge in its block of the circuit (its SubCircuit), or in the nearest block
around that one which has one. Where that block has several parts at an
edge, the hub is the one the part shares the most nets with, the parts
already in that one's cluster counted. A part at the circuit's top level
is in no block and has no hub.

Each cluster is laid out by itself around its hub, before the board has a
size: the largest part first, each at the free place where its pads are
nearest to the pads they connect to on the cluster's parts that are
placed, turned whichever way brings them nearest. A pad's connections are
looked for in the part's own block, and in the whole cluster when the
block has none on that net. A fill is everywhere, so a pad on the net of
a fill counts towards the pads of that net in the part's own block, the
pins it serves, and towards others only for a part that has no other pad
to go by; such a part waits while another of its nets has a part on it
that is still to be placed. So a capacitor is placed by the pins it
serves, after the part that has them, with each of its pads towards its
pin. A part
that finds no place near its connections is looked for one further away,
on a coarser grid. A cluster has walls, which are there before any of its
parts is placed: the board's edge its hub is at, and the room in front of
a part that moves as one with its hub, which is that part's own
cluster's. On its other sides nothing limits it. A part's rectangle is
the one around its courtyard, drawn outline and rule areas
(scripts/board_from_circuit.py's keep_out).

A cluster moves as one. Two clusters at different edges keep room between
their parts, the millimetres given, for the tracks that run between them;
two at the same edge may stand side by side, with room for a via between
their parts; a part keeps room for a via to an edge that is not its hub's.

The script looks for the smallest outline, by area, in which the clusters
can be put down so: it finds the smallest height for the board's width,
then makes the board narrower step by step, raising the height whenever
the clusters no longer fit; for a width and a height it tries the places
along the edges one cluster after the other. The right and the bottom
edge move; the fills follow the outline. The search starts from the
clusters side by side, the widest outline there is, or from the width
given, and the outline is as tall as it takes: the smallest outline is not
the narrowest. Neither bound comes from the board that is read, so the
outline does not depend on how wide that board is.

Of the ways the clusters can be put down in that outline, the script takes
the one in which their connections are shortest, taken together, so that
two of them with many connections are neighbours where the outline allows
it. A connection is a net that joins two clusters; it is measured between
the pads the two have on that net.

A part of a cluster that then lies where a differential pair will run
(scripts/lay_pairs.py's lanes), or in an antenna's clearance that is
closed to it, is placed anew, and the parts without a hub are placed last:
each at the free place where its pads are nearest to the pads they connect
to on the board as it then is.

A part keeps room for a via to every other part: the via of the
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
try:
    import tomllib
except ModuleNotFoundError:     # KiCad's Python on a Mac is 3.9, where tomli stands in
    import tomli as tomllib

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from board_from_circuit import (ANTENNAS, BOTTOM, EDGES, FIXED_POSITIONS, LEFT, RIGHT, TOP, NoFreePlace,  # noqa: E402
                                turn_to_face,
                                antenna_clearances, beside_offset, board_outline, closed_to, draw_antenna_clearances,
                                keep_out, middle, nearer_than, pad_centre, pad_named, read_circuit,
                                settle_at_its_connections)
from lay_pairs import lanes  # noqa: E402

STEP = pcbnew.FromMM(2.0)       # of the search for the outline and for the places along the edges
FURTHER = pcbnew.FromMM(60.0)   # how far from its connections a part is looked for a place when there is none near them
FURTHER_GRID = pcbnew.FromMM(1.0)
FURTHER_MOVES = sorted(((dx, dy) for dx in range(-FURTHER, FURTHER + 1, FURTHER_GRID)
                        for dy in range(-FURTHER, FURTHER + 1, FURTHER_GRID)), key=lambda move: math.hypot(*move))
FAR = pcbnew.FromMM(300.0)      # where the outline lies on the sides that are no wall while a cluster is laid out
EDGE_NAME = {LEFT: "left", TOP: "top", RIGHT: "right", BOTTOM: "bottom"}


def connections(designator, footprints, parts, nets, placed, fill_nets, on_fills_too=True):
    """For each of the part's pads, by number, the pads it connects to on
    the parts that are placed, as [(part, place)]. A pad on the net of a
    fill is given with the pads of that net in the part's own block, which
    are the pins it serves; with the pads of that net anywhere it is given
    only when no pad of the part has another connection, and not at all
    when on_fills_too is false."""
    on_signals, on_fills, on_fills_in_block = {}, {}, {}
    for net, pads in nets.items():
        for number in {number for part, number in pads if part == designator}:
            others = [(part, other) for part, other in pads if part in placed]
            in_block = [(part, other) for part, other in others if parts[part]["block"] == parts[designator]["block"]]
            targets = [(part, pad.GetPosition()) for part, other in in_block or others
                       for pad in footprints[part].Pads() if pad.GetNumber() == other]
            if targets:
                (on_fills if net in fill_nets else on_signals)[number] = targets
                if net in fill_nets and in_block:
                    on_fills_in_block[number] = targets
    return {**on_fills_in_block, **on_signals} if on_signals else (on_fills if on_fills_too else {})


def size(footprint):
    """The area of the part's rectangle."""
    box = keep_out(footprint)
    return (box[RIGHT] - box[LEFT]) * (box[BOTTOM] - box[TOP])


def in_order(waiting, footprints, parts, nets, placed, fill_nets):
    """The parts in the list, one at a time, each with its connections to
    the parts that are placed and to those of the list before it: the first
    in the list that has any. A part that has only the net of a fill to go
    by waits while another of its nets has a part of the list on it, so
    that it is placed by that net once that part is; it is taken all the
    same when no other part of the list can be. Ends when none of those
    left has a connection."""
    waiting, placed = list(waiting), set(placed)

    def has_to_wait(name):
        return any(net not in fill_nets and any(part == name for part, _ in pads)
                   and any(part != name and part in waiting for part, _ in pads) for net, pads in nets.items())

    while waiting:
        for name in waiting:
            reach = connections(name, footprints, parts, nets, placed, fill_nets, on_fills_too=not has_to_wait(name))
            if reach:
                break
        else:
            for name in waiting:
                reach = connections(name, footprints, parts, nets, placed, fill_nets)
                if reach:
                    break
            else:
                return
        yield name, reach
        placed.add(name)
        waiting.remove(name)


def hubs_of(inner, footprints, parts, nets, fill_nets, fixed):
    """For each part that is not at an edge and has one, its hub: the part
    at an edge whose cluster it is in. That is the part at an edge in its
    block of the circuit, or in the nearest block around that one which has
    one. Where that block has several, it is the one the part shares the
    most nets with, counting the parts already in that one's cluster, the
    nets of fills only for a part that no other net decides, and the
    largest of them for a part that no net decides. The circuit's top level
    is no block: a part there, or in a block with no part at an edge in or
    around it, has no hub."""
    at_edge = collections.defaultdict(list)
    for name in fixed:
        at_edge[parts[name]["block"]].append(name)
    hub, undecided = {name: name for name in fixed}, {}
    for name in inner:
        block = parts[name]["block"]
        while block != "/" and block not in at_edge:
            block = block[:block.rstrip("/").rfind("/") + 1]
        if len(at_edge.get(block, ())) == 1:
            hub[name] = at_edge[block][0]
        elif block in at_edge:
            undecided[name] = at_edge[block]
    for counted in (lambda net: net not in fill_nets, lambda net: True):
        on_net = [{part for part, _ in pads} for net, pads in sorted(nets.items()) if counted(net)]
        while True:
            votes = {name: collections.Counter(hub[other] for others in on_net if name in others
                                               for other in others if hub.get(other) in candidates)
                     for name, candidates in undecided.items()}
            decided = {name: max(sorted(found), key=lambda candidate: found[candidate]) for name, found in votes.items() if found}
            if not decided:
                break
            hub.update(decided)
            undecided = {name: candidates for name, candidates in undecided.items() if name not in decided}
    for name, candidates in undecided.items():
        hub[name] = max(sorted(candidates), key=lambda candidate: size(footprints[candidate]))
    return hub


def lay_out_cluster(board, hub, wall, beside_it, members, footprints, parts, nets, fill_nets, gap, closed_to_part):
    """Place the parts of a cluster around its hub, which is where it is:
    the largest first, each at the free place where its pads are nearest to
    the pads they connect to on the cluster's parts that are placed.
    Returns the parts that connect to none of those and are left where they
    are, and the parts that found no place near their connections and were
    placed further away.

    The board's outline is the cluster's wall on the side the hub's edge is
    and lies far away on the others. beside_it lists the parts that move as
    one with the hub: the room in front of each of those is its own
    cluster's, a wall for this one. closed_to_part(name) gives the
    rectangles a part may not enter."""
    across = wall in (TOP, BOTTOM)
    walls = []
    for name in beside_it:
        box = keep_out(footprints[name])
        walls.append((box[LEFT], box[TOP] - FAR, box[RIGHT], box[BOTTOM] + FAR) if across
                     else (box[LEFT] - FAR, box[TOP], box[RIGHT] + FAR, box[BOTTOM]))
    waiting = sorted(members, key=lambda name: (-size(footprints[name]), name))
    placed, placed_further = [], []
    for name, reach in in_order(waiting, footprints, parts, nets, {hub}, fill_nets):
        places = {number: [place for _, place in targets] for number, targets in reach.items()}
        closed = closed_to_part(name) + walls
        try:
            settle_at_its_connections(board, footprints[name], places, gap=gap, closed=closed)
        except NoFreePlace:
            try:
                settle_at_its_connections(board, footprints[name], places, gap=gap, moves=FURTHER_MOVES, closed=closed)
            except NoFreePlace:
                sys.exit(f"no free place for {name} in the cluster of {hub}")
            placed_further.append(name)
        placed.append(name)
    return [name for name in waiting if name not in placed], placed_further


def furthest_connection(footprint, reach):
    """The longest of the distances from the part's pads to the nearest pad each connects to."""
    return max(min(math.hypot(pad.GetPosition().x - target.x, pad.GetPosition().y - target.y)
                   for _, target in reach[pad.GetNumber()])
               for pad in footprint.Pads() if pad.GetNumber() in reach)


def links_between(hub, nets, fill_nets, footprints):
    """The connections between the clusters, one for each net that joins
    two of them, as [(hub, where, other hub, where)]. where is a rectangle
    measured from the left and top of the hub's own: the one around the pads
    its cluster has on that net."""
    links = []
    for net, pads in sorted(nets.items()):
        if net in fill_nets:
            continue
        ends = {}
        for part, number in pads:
            if part not in hub:
                continue
            box = keep_out(footprints[hub[part]])
            place = [pad.GetPosition() for pad in footprints[part].Pads() if pad.GetNumber() == number][0]
            x, y = place.x - box[LEFT], place.y - box[TOP]
            left, top, right, bottom = ends.get(hub[part], (x, y, x, y))
            ends[hub[part]] = (min(left, x), min(top, y), max(right, x), max(bottom, y))
        names = sorted(ends)
        links += [(a, ends[a], b, ends[b]) for index, a in enumerate(names) for b in names[index + 1:]]
    return links


def within(box, where):
    return (box[LEFT] + where[LEFT], box[TOP] + where[TOP], box[LEFT] + where[RIGHT], box[TOP] + where[BOTTOM])


def distance_between(a, b):
    """From one rectangle to another, along the board's two directions."""
    return max(0, a[LEFT] - b[RIGHT], b[LEFT] - a[RIGHT]) + max(0, a[TOP] - b[BOTTOM], b[TOP] - a[BOTTOM])


class Down(list):
    """The parts of a block where the block is put down, as [(part,
    rectangle)], with the block's edge, the rectangle around them all, and
    those of them that are in ruled."""

    def __init__(self, edge, members, ruled):
        super().__init__(members)
        self.edge = edge
        self.around = (min(box[LEFT] for _, box in members), min(box[TOP] for _, box in members),
                       max(box[RIGHT] for _, box in members), max(box[BOTTOM] for _, box in members))
        self.ruled = [(name, box) for name, box in members if name in ruled]


def smallest_outline(blocks, room, closed, order, links, least, extent, largest):
    """The smallest width and height, by area, in which the blocks can be
    put down along their edges, and how far each then slides: of the ways
    they can be put down in that outline, the one in which the links are
    shortest, taken together. extent is the width and height the board has,
    largest the ones the search starts from.

    A block is (edge, [(part, rectangle)], near): parts that move as one,
    each with its rectangle (left, top, right, bottom) measured from the
    board's left and top edge as the board is. A block at the right or the
    bottom edge moves with that edge. near is None for a block that is free
    along its edge; for one that sits level with pads of another part it is
    (the slide that brings it there as the board is, that part's edge), and
    the block has that one place.

    room is what the parts of two blocks at different edges keep between
    them, least what those of two blocks at the same edge keep, and what a
    part keeps to an edge that is not its block's. closed holds what a part
    keeps other parts out of, as {part: [(rectangle measured from the left
    and top of the part's own, the parts kept out)]}. order holds the side
    of another part a part has to be on, as {(part, other part): below,
    above, left_of or right_of}. links is what links_between gives.
    """
    ruled = ({name for pair in order for name in pair} | set(closed)
             | {name for areas in closed.values() for _, kept_out in areas for name in kept_out})
    links_of = collections.defaultdict(list)
    for a, where_a, b, where_b in links:
        links_of[a].append((where_a, b, where_b))
        links_of[b].append((where_b, a, where_a))

    def moved(block, slide, width, height):
        edge, members, _ = block
        dx = slide if edge in (TOP, BOTTOM) else (width - extent[0] if edge == RIGHT else 0)
        dy = slide if edge in (LEFT, RIGHT) else (height - extent[1] if edge == BOTTOM else 0)
        return Down(edge, [(name, (box[LEFT] + dx, box[TOP] + dy, box[RIGHT] + dx, box[BOTTOM] + dy)) for name, box in members],
                    ruled)

    def inside(members, width, height):
        return all(members.edge == edge or distance >= least
                   for edge, distance in ((LEFT, members.around[LEFT]), (TOP, members.around[TOP]),
                                          (RIGHT, width - members.around[RIGHT]), (BOTTOM, height - members.around[BOTTOM])))

    def let_in(owner, box, name, other):
        return not any(name in kept_out and nearer_than(other, (box[LEFT] + area[LEFT], box[TOP] + area[TOP],
                                                                box[LEFT] + area[RIGHT], box[TOP] + area[BOTTOM]), 0)
                       for area, kept_out in closed.get(owner, ()))

    def in_order(name, a, other, b):
        side = order.get((name, other))
        return (side is None or (side == "below" and a[TOP] >= b[BOTTOM]) or (side == "above" and a[BOTTOM] <= b[TOP])
                or (side == "left_of" and a[RIGHT] <= b[LEFT]) or (side == "right_of" and a[LEFT] >= b[RIGHT]))

    def apart(members, others):
        gap = least if members.edge == others.edge else room
        if nearer_than(members.around, others.around, gap) and any(
                nearer_than(a, b, gap) for _, a in members for _, b in others):
            return False
        return all(in_order(name, a, other, b) and let_in(name, a, other, b) and let_in(other, b, name, a)
                   for name, a in members.ruled for other, b in others.ruled)

    def slides(block, width, height):
        edge, members, near = block
        low, high = (LEFT, RIGHT) if edge in (TOP, BOTTOM) else (TOP, BOTTOM)
        length = width if edge in (TOP, BOTTOM) else height
        first = max(least - box[low] for name, box in members)
        last = min(length - least - box[high] for name, box in members)
        candidates = range(-(-first // STEP) * STEP, last + 1, STEP)
        if near:
            # The pads it is level with move with their part's edge.
            level, near_edge = near
            level += width - extent[0] if near_edge == RIGHT else height - extent[1] if near_edge == BOTTOM else 0
            candidates = [level] if first <= level <= last else []
        return [(slide, members_there) for slide in candidates
                for members_there in [moved(block, slide, width, height)] if inside(members_there, width, height)]

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

    def links_to(down, members):
        """How long the links from these parts to the parts that are down are, taken together."""
        return sum(distance_between(within(box, where), within(down[other], other_where))
                   for name, box in members for where, other, other_where in links_of[name] if other in down)

    def with_shortest_links(width, height):
        """How far each block slides in the way of putting them down in which the links are shortest."""
        best = [math.inf, None]

        def put_down_all(places, down, slid, length):
            if not places:
                best[:] = [length, slid]
                return
            for added, slide, members in sorted(((links_to(down, members), slide, members) for slide, members in places[0]),
                                                key=lambda place: place[:2]):
                if length + added >= best[0]:
                    break
                left = [[(other_slide, others) for other_slide, others in candidates if apart(members, others)]
                        for candidates in places[1:]]
                if all(left):
                    put_down_all(left, {**down, **dict(members)}, slid + [slide], length + added)

        put_down_all([slides(block, width, height) for block in blocks], {}, [], 0)
        return best[1]

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
    return best, with_shortest_links(*best)


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
    room = pcbnew.FromMM(room)
    inner = sorted(set(footprints) - set(fixed), key=lambda name: (-size(footprints[name]), name))

    # The parts that move as one: a part with an edge, and those the file puts beside it.
    edge_of = {name: EDGES[rule["edge"]] for name, rule in fixed.items() if "edge" in rule}
    # A part the board has at another edge than the file is turned to face the file's, at the distance to the edge it has.
    for name, edge in edge_of.items():
        footprint = footprints[name]
        if "faces" in fixed[name]:
            turn_to_face(footprint, edge, fixed[name]["faces"])
        box = keep_out(footprint)
        to_edge = {LEFT: box[LEFT] - outline[LEFT], TOP: box[TOP] - outline[TOP],
                   RIGHT: outline[RIGHT] - box[RIGHT], BOTTOM: outline[BOTTOM] - box[BOTTOM]}
        drawn_at = min(to_edge, key=to_edge.get)
        if "edge_line_mm" in fixed[name]:
            # The distance the file states is where the part is placed: the
            # clusters and the outline are worked out around it.
            inset = pcbnew.FromMM(fixed[name]["edge_line_mm"])
            origin = footprint.GetPosition()
            footprint.SetPosition({
                LEFT: pcbnew.VECTOR2I(outline[LEFT] + inset, origin.y),
                TOP: pcbnew.VECTOR2I(origin.x, outline[TOP] + inset),
                RIGHT: pcbnew.VECTOR2I(outline[RIGHT] - inset, origin.y),
                BOTTOM: pcbnew.VECTOR2I(origin.x, outline[BOTTOM] - inset),
            }[edge])
        elif drawn_at != edge:
            footprint.SetOrientationDegrees(footprint.GetOrientationDegrees() + 90 * ((drawn_at - edge) % 4))
            box = keep_out(footprint)
            footprint.Move(pcbnew.VECTOR2I(*{
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

    # Each cluster is laid out with the board to itself, its hub where the board has it: every other part is off the
    # board but those that move as one with the hub, and the outline is far away on the sides that are no wall.
    def draw_outline(rectangle):
        outline_drawings[0].SetStart(pcbnew.VECTOR2I(rectangle[LEFT], rectangle[TOP]))
        outline_drawings[0].SetEnd(pcbnew.VECTOR2I(rectangle[RIGHT], rectangle[BOTTOM]))

    hub = hubs_of(inner, footprints, parts, nets, fill_nets, fixed)
    cluster = collections.defaultdict(list)
    for name in inner:
        if name in hub:
            cluster[hub[name]].append(name)
    off_the_board = pcbnew.VECTOR2I(outline[LEFT] - 10 * extent[0], outline[TOP])
    home = {name: pcbnew.VECTOR2I(footprints[name].GetPosition()) for name in fixed}
    for name in inner:
        footprints[name].SetPosition(off_the_board)
    from_hub, placed_further = {}, []
    for first, group in members_of.items():
        for name in fixed:
            footprints[name].SetPosition(home[name] if name in group else off_the_board)
        clearances = antenna_clearances(board, antennas)
        wide_open = [outline[LEFT] - FAR, outline[TOP] - FAR, outline[RIGHT] + FAR, outline[BOTTOM] + FAR]
        wide_open[edge_of[first]] = outline[edge_of[first]]
        draw_outline(wide_open)
        for name in group:
            without_connection, further = lay_out_cluster(
                board, name, edge_of[name], [other for other in group if other != name], cluster[name], footprints, parts,
                nets, fill_nets, room_for_a_via, lambda part: closed_to(footprints[part], clearances, class_of_net))
            placed_further += further
            for part in without_connection:
                cluster[name].remove(part)
                del hub[part]
        for name in group:
            for part in cluster[name]:
                from_hub[part] = (footprints[part].GetPosition() - home[name], footprints[part].GetOrientationDegrees())
                footprints[part].SetPosition(off_the_board)
    draw_outline(outline)
    for name in fixed:
        footprints[name].SetPosition(home[name])
    for part, (offset, turn) in from_hub.items():
        footprints[part].SetOrientationDegrees(turn)
        footprints[part].SetPosition(home[hub[part]] + offset)
    for first, group in members_of.items():
        group += [part for name in list(group) for part in cluster[name]]
    links = links_between(hub, nets, fill_nets, footprints)

    # The side of another part the file puts a part on, as the board is drawn.
    order = {}
    for name, rule in fixed.items():
        for side, other_side in (("below", "above"), ("above", "below"), ("left_of", "right_of"), ("right_of", "left_of")):
            if side in rule:
                if rule[side] not in fixed:
                    sys.exit(f"{name} is {side} {rule[side]}, which {os.path.basename(FIXED_POSITIONS)} does not name")
                order[name, rule[side]], order[rule[side], name] = side, other_side

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
                             {name for name in hub if closed_to(footprints[name], [(part, area, kept_out)], class_of_net)}))

    # The largest first: it has the fewest places.
    blocks = sorted(((edge_of[first], [(name, from_corner(keep_out(footprints[name]))) for name in members], near.get(first))
                     for first, members in members_of.items()),
                    key=lambda block: -sum((box[RIGHT] - box[LEFT]) * (box[BOTTOM] - box[TOP]) for _, box in block[1]))
    # The outline is as wide and as tall as it takes, and no wider than the width given: the clusters
    # side by side is the widest it gets, one below the other the tallest. Neither is taken from the
    # board that is read, so that a board made from a narrow one is the one made from a wide one.
    side_by_side, one_below_the_other = (-(-sum(max(box[high] for _, box in members) - min(box[low] for _, box in members)
                                                + 2 * room for _, members, _ in blocks) // STEP) * STEP
                                         for low, high in ((LEFT, RIGHT), (TOP, BOTTOM)))
    largest = (side_by_side if widest is None else min(side_by_side, pcbnew.FromMM(widest)), one_below_the_other)
    new_extent, slides = smallest_outline(blocks, room, closed, order, links, room_for_a_via, extent, largest)
    for (edge, members, _), slide in zip(blocks, slides):
        dx = slide if edge in (TOP, BOTTOM) else (new_extent[0] - extent[0] if edge == RIGHT else 0)
        dy = slide if edge in (LEFT, RIGHT) else (new_extent[1] - extent[1] if edge == BOTTOM else 0)
        for name, _ in members:
            footprints[name].Move(pcbnew.VECTOR2I(dx, dy))
    between = collections.defaultdict(list)
    for a, where_a, b, where_b in links:
        between[a, b].append(distance_between(within(keep_out(footprints[a]), where_a), within(keep_out(footprints[b]), where_b)))

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

    # A part of a cluster that lies where a pair will run, or in an antenna's clearance that is closed to it, leaves
    # the board, as the parts without a hub have; they come back one at a time, each beside what it connects to.
    def kept_clear(name):
        return closed_to(footprints[name], clearances, class_of_net) + pair_lanes

    in_the_way = [name for name in from_hub
                  if any(nearer_than(keep_out(footprints[name]), area, 0) for area in kept_clear(name))]
    for name in in_the_way:
        footprints[name].SetPosition(off_the_board)
    waiting = [name for name in inner if name not in from_hub or name in in_the_way]
    placed_last = []
    for name, reach in in_order(waiting, footprints, parts, nets, set(footprints) - set(waiting), fill_nets):
        places = {number: [place for _, place in targets] for number, targets in reach.items()}
        try:
            settle_at_its_connections(board, footprints[name], places, gap=room_for_a_via, closed=kept_clear(name))
        except NoFreePlace:
            try:
                settle_at_its_connections(board, footprints[name], places, gap=room_for_a_via, moves=FURTHER_MOVES,
                                          closed=kept_clear(name))
            except NoFreePlace:
                sys.exit(f"no free place for {name}")
            placed_further.append(name)
        placed_last.append(name)
    if len(placed_last) < len(waiting):
        sys.exit(f"these connect to nothing that is placed: {' '.join(sorted(set(waiting) - set(placed_last)))}")
    furthest = max((furthest_connection(footprints[name], reach), name) for name in inner
                   for reach in [connections(name, footprints, parts, nets, set(footprints) - {name}, fill_nets)])
    # The third argument keeps KiCad from rewriting the project file with the board.
    pcbnew.SaveBoard(board_path, board, True)

    def square_cm(width, height):
        return pcbnew.ToMM(width) * pcbnew.ToMM(height) / 100

    print(f"{pcbnew.ToMM(room):g} mm between clusters: {pcbnew.ToMM(extent[0]):.2f} x {pcbnew.ToMM(extent[1]):.2f} mm, "
          f"{square_cm(*extent):.1f} cm2 -> {pcbnew.ToMM(new_extent[0]):.2f} x {pcbnew.ToMM(new_extent[1]):.2f} mm, "
          f"{square_cm(*new_extent):.1f} cm2")
    for name in sorted(fixed, key=lambda name: (edge_of[name], name)):
        box = from_corner(keep_out(footprints[name]))
        low, high = (LEFT, RIGHT) if edge_of[name] in (TOP, BOTTOM) else (TOP, BOTTOM)
        boxes = [keep_out(footprints[part]) for part in [name] + cluster[name] if part not in in_the_way]
        print(f"  {name:4} at the {EDGE_NAME[edge_of[name]]:6} edge, {pcbnew.ToMM(box[low]):6.1f} to "
              f"{pcbnew.ToMM(box[high]):6.1f} mm along it; {len(cluster[name]):2} parts in its cluster, "
              f"{pcbnew.ToMM(max(b[RIGHT] for b in boxes) - min(b[LEFT] for b in boxes)):5.1f} x "
              f"{pcbnew.ToMM(max(b[BOTTOM] for b in boxes) - min(b[TOP] for b in boxes)):5.1f} mm around it")
    print("connections between the clusters, the most first, and how far apart their ends are:")
    for (a, b), lengths in sorted(between.items(), key=lambda pair: (-len(pair[1]), pair[0])):
        print(f"  {a:4} and {b:4} {len(lengths):2}, {pcbnew.ToMM(sum(lengths) / len(lengths)):5.1f} mm on average")
    print(f"{len(from_hub)} parts placed in the cluster of a part at an edge; "
          f"the furthest pad from its connection: {pcbnew.ToMM(furthest[0]):.1f} mm, on {furthest[1]}")
    if in_the_way:
        print(f"where a pair runs or in an antenna's clearance, placed anew: {' '.join(in_the_way)}")
    without_hub = [name for name in placed_last if name not in in_the_way]
    if without_hub:
        print(f"in no cluster, placed last, beside what they connect to: {' '.join(without_hub)}")
    if placed_further:
        print(f"no place near their connections, placed further away, to be looked at: {' '.join(placed_further)}")


if __name__ == "__main__":
    if len(sys.argv) not in (4, 5):
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], *(float(number) for number in sys.argv[3:]))
