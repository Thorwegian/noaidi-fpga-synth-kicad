#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""lay_pairs.py -- lay the board's differential pairs as pairs, for the autorouter to work around.

    scripts/lay_pairs.py <board>

For each pair in circuit/pair_paths.toml, removes the tracks and vias of the
pair's two nets and lays two tracks side by side along the pair's path, on
the layer the file states: at the width and the gap the nets' class gives a
pair, the path midway between them. The path's corners are cut, so that a
turn is two bends.

The path is the one the file states. For a pair it states none for, the
script works it out from the pads the circuit joins: straight out of the
first two towards the last two, with a step sideways where the two ends
are not in line. Such a pair goes around nothing; KiCad's DRC says whether
that was right, the rule that keeps a net class away from an antenna among
its rules.

At each end the pair as a whole takes a slanted step onto the line midway
between its two pads, where the path ends beside that line: a socket that
has been moved a little along its edge is still met. From there each track
goes to its pad, in a slanted step of its own where the pads lie further
apart than the tracks.

A socket has each line of a pair on two pads. The further pad of a net gets
a branch: a track from its middle through the points the file states, as
distances from that pad, to the net's first pad, or else on in the
direction of its last stretch until it meets the net's track.

The tracks are locked: scripts/route_board.py leaves a locked track where
it is and gives it to the router as one that stays.

Two tracks on one layer cannot change sides, so the net on the left of the
path has to be the same at both ends. A path that would need a crossing is
refused.

KiCad's DRC is the judge of what is laid: the clearances, that every pad
is joined, and the rules for a pair in the project's .kicad_dru.

Runs under the system's Python, which has KiCad's pcbnew module.
"""
import cmath
import math
import os
import sys
import tomllib

import pcbnew

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAIR_PATHS = os.path.join(PROJECT_DIR, "circuit", "pair_paths.toml")

CORNER_CUT_MM = 0.5         # taken off each leg of a corner
SHARP = 0.7                 # a corner is cut when the cosine of its turn is below this: beyond 45 degrees
STRAIGHT_ON_MM = 0.25       # the pair runs straight for this long after its step onto the pads' line
LEAD_MM = 1.25              # a path the script works out ends this far, and half its pads' spacing, before its pads:
                            # each track's slanted step to its pad needs as far ahead as it goes sideways


# A point, and a direction, is a complex number of millimetres: x + y·j.

def along(vector, direction):
    """How far the vector reaches in the direction (a unit vector)."""
    return (vector * direction.conjugate()).real


def unit(vector):
    return vector / abs(vector)


def left_of(direction):
    """The direction a quarter turn to the left, as KiCad draws the board:
    with y growing downwards."""
    return direction * -1j


def points_of(coordinates):
    return [complex(x, y) for x, y in coordinates]


def length_of(points):
    return sum(abs(end - start) for start, end in zip(points, points[1:]))


def with_corners_cut(points):
    """The line through the points with each corner that turns by more
    than 45 degrees cut off. Where a leg is shorter than two cuts, the cuts
    of its two corners meet in its middle."""
    cut = [points[0]]
    for before, corner, after in zip(points, points[1:], points[2:]):
        if along(unit(corner - before), unit(after - corner)) > SHARP:
            cut.append(corner)
            continue
        for neighbour in (before, after):
            leg = neighbour - corner
            point = corner + unit(leg) * min(CORNER_CUT_MM, abs(leg) / 2)
            if abs(point - cut[-1]) > 1e-6:
                cut.append(point)
    return cut + [points[-1]]


def beside(points, distance):
    """The line that runs the distance to the left of the line through the
    points, its corners where the neighbouring stretches meet."""
    to_left = [left_of(unit(end - start)) for start, end in zip(points, points[1:])]
    corners = [point + distance * (before + after) / (1 + along(before, after))
               for point, before, after in zip(points[1:-1], to_left, to_left[1:])]
    return [points[0] + distance * to_left[0]] + corners + [points[-1] + distance * to_left[-1]]


def sideways_step(end, heading, target, name):
    """The point a slanted step from the end, which heads the given way,
    reaches on the line through the target; None when the end is on it."""
    reach = target - end
    sideways, ahead = along(reach, left_of(heading)), along(reach, heading)
    if ahead < abs(sideways):
        sys.exit(f"{name}: the path ends too near its pads for a slanted step to reach them")
    if abs(sideways) < 1e-6:
        return None
    return end + abs(sideways) * heading + sideways * left_of(heading)


def onto_the_pads_line(path, pads, name):
    """The path, with a slanted step at its end onto the line midway
    between the two pads and a short straight stretch after it, when it
    ends beside that line."""
    heading = unit(path[-1] - path[-2])
    stepped = sideways_step(path[-1], heading, (middle(pads[0]) + middle(pads[1])) / 2, name)
    return path if stepped is None else path + [stepped, stepped + STRAIGHT_ON_MM * heading]


def to_pad(end, heading, pad, name):
    """The points from a track's end at the end of the path to the middle
    of its pad: a slanted step sideways where the pad is not straight
    ahead, then straight on."""
    stepped = sideways_step(end, heading, pad, name)
    return [pad] if stepped is None else [stepped, pad]


def where_met(start, direction, points):
    """Where going from the start in the direction first meets the line
    through the points; None when it does not."""
    def turn(a, b):
        return (a.conjugate() * b).imag

    met = []
    for first, second in zip(points, points[1:]):
        stretch = second - first
        if abs(turn(direction, stretch)) > 1e-9:
            distance = turn(first - start, stretch) / turn(direction, stretch)
            share = turn(first - start, direction) / turn(direction, stretch)
            if distance > 1e-6 and -1e-9 <= share <= 1 + 1e-9:
                met.append(distance)
    return start + min(met) * direction if met else None


def with_point(points, point):
    """The line through the points with the point, which lies on it, as one
    of them."""
    for index, (start, end) in enumerate(zip(points, points[1:]), 1):
        if abs(abs(point - start) + abs(end - point) - abs(end - start)) < 1e-6:
            return points[:index] + [point] + points[index:]
    return points


def pads_of(board, names):
    pads = []
    for name in names:
        designator, _, number = name.partition(".")
        footprint = board.FindFootprintByReference(designator)
        pad = footprint.FindPadByNumber(number) if footprint else None
        if pad is None:
            sys.exit(f"the board has no pad {name}")
        pads.append(pad)
    return pads


def middle(pad):
    return complex(pcbnew.ToMM(pad.GetPosition().x), pcbnew.ToMM(pad.GetPosition().y))


def left_first(pads, end, heading):
    """The two pads, the one that lies further to the left of the heading
    first."""
    return sorted(pads, key=lambda pad: along(middle(pad) - end, left_of(heading)), reverse=True)


def worked_out(board, pair):
    """The path of a pair the file states none for: straight out of its
    first pads and straight into its last. Where the pads at the two ends
    lie in rows the same way, the pair runs straight from the one to the
    other; where the two ends are not in line, it takes a slanted step onto
    the line of its last pads before it reaches them, or, where it is
    further to the side than ahead, a step sideways halfway. Where the rows
    are at a right angle, the pair turns one corner."""
    starts, ends = ([middle(pad) for pad in pads_of(board, pair[end])] for end in ("from", "to"))
    start, end = sum(starts) / 2, sum(ends) / 2
    heading, arriving = left_of(unit(starts[1] - starts[0])), left_of(unit(ends[1] - ends[0]))
    if along(end - start, heading) < 0:
        heading = -heading
    if along(end - start, arriving) < 0:
        arriving = -arriving
    first = start + (abs(starts[1] - starts[0]) / 2 + LEAD_MM) * heading
    last = end - (abs(ends[1] - ends[0]) / 2 + LEAD_MM) * arriving
    ahead, sideways = along(last - first, heading), along(last - first, left_of(heading))
    if abs(along(arriving, heading)) < 1e-6:
        # The rows are at a right angle: out of the first pads, one corner, into the last.
        if ahead < 2 * CORNER_CUT_MM or along(last - first, arriving) < 2 * CORNER_CUT_MM:
            sys.exit(f"{pair['name']}: its two ends are too near each other for a path between them")
        return with_corners_cut([first, first + ahead * heading, last])
    if abs(along(arriving, heading)) < 1 - 1e-6:
        sys.exit(f"{pair['name']}: the pads at its two ends lie neither in line nor at a right angle, so its path has to be stated")
    if ahead < 4 * CORNER_CUT_MM:
        sys.exit(f"{pair['name']}: its two ends are too near each other for a path between them")
    if ahead > abs(sideways) + STRAIGHT_ON_MM + CORNER_CUT_MM:
        return [first, first + (ahead - abs(sideways) - STRAIGHT_ON_MM) * heading]
    return with_corners_cut([first, first + ahead / 2 * heading, last - ahead / 2 * heading, last])


def branch_points(board, branch):
    """The points a branch goes through from its pad: the file's distances,
    which are stated for the part as its footprint is drawn, turned with
    the part."""
    pad = pads_of(board, [branch["from"]])[0]
    turn = cmath.exp(-1j * math.radians(pad.GetParentFootprint().GetOrientationDegrees()))
    return [middle(pad) + offset * turn for offset in [0j] + points_of(branch["offsets_mm"])]


def path_of(board, pair):
    """The line midway between the pair's two tracks, from short of its
    first pads to short of its last."""
    path = with_corners_cut(points_of(pair["path_mm"])) if "path_mm" in pair else worked_out(board, pair)
    path = onto_the_pads_line(path[::-1], pads_of(board, pair["from"]), pair["name"])[::-1]
    return onto_the_pads_line(path, pads_of(board, pair["to"]), pair["name"])


def lanes(board):
    """The rectangles (left, top, right, bottom) the pairs' tracks will lie
    in, with their class's clearance around them, in the board's units: what
    a script that places parts ahead of the pairs keeps free."""
    found = []
    for pair in tomllib.load(open(PAIR_PATHS, "rb"))["pair"]:
        ends = [sum(middle(pad) for pad in pads_of(board, pair[end])) / 2 for end in ("from", "to")]
        lines = [[ends[0]] + path_of(board, pair) + [ends[1]]]
        for branch in pair.get("branch", []):
            lines.append(branch_points(board, branch))
        net_class = board.GetDesignSettings().m_NetSettings.GetEffectiveNetClass(pads_of(board, pair["from"])[0].GetNetname())
        around = pcbnew.ToMM(net_class.GetDiffPairGap() / 2 + net_class.GetDiffPairWidth() + net_class.GetClearance())
        for points in lines:
            for start, end in zip(points, points[1:]):
                found.append(tuple(pcbnew.FromMM(value) for value in (
                    min(start.real, end.real) - around, min(start.imag, end.imag) - around,
                    max(start.real, end.real) + around, max(start.imag, end.imag) + around)))
    return found


def lay(board, pair):
    name = pair["name"]
    path = path_of(board, pair)
    out_of_start, out_of_end = unit(path[0] - path[1]), unit(path[-1] - path[-2])
    # The pad of the track on the path's left first. Looking out of the
    # path's start, the path's left is on the right.
    start_pads = left_first(pads_of(board, pair["from"]), path[0], out_of_start)[::-1]
    end_pads = left_first(pads_of(board, pair["to"]), path[-1], out_of_end)
    nets = [pad.GetNetname() for pad in start_pads]
    if nets != [pad.GetNetname() for pad in end_pads] or nets[0] == nets[1]:
        sys.exit(f"{name}: its two tracks would have to cross between {pair['from']} and {pair['to']}: "
                 f"the pads on the path's left are on {nets[0]} at the start and "
                 f"{end_pads[0].GetNetname()} at the end")

    net_class = board.GetDesignSettings().m_NetSettings.GetEffectiveNetClass(nets[0])
    width, gap = net_class.GetDiffPairWidth(), net_class.GetDiffPairGap()
    from_path = pcbnew.ToMM(width + gap) / 2
    runs = [(start_pad, to_pad(line[0], out_of_start, middle(start_pad), name)[::-1] + line
             + to_pad(line[-1], out_of_end, middle(end_pad), name))
            for line, start_pad, end_pad in zip((beside(path, from_path), beside(path, -from_path)),
                                                start_pads, end_pads)]
    lengths = [length_of(points) for _, points in runs]

    for branch in pair.get("branch", []):
        pads = pads_of(board, [branch[end] for end in ("from", "to") if end in branch])
        if {pad.GetNetname() for pad in pads} - set(nets) or len({pad.GetNetname() for pad in pads}) != 1:
            sys.exit(f"{name}: the branch from {branch['from']} is not on one of its nets, {nets[0]} and {nets[1]}")
        points = branch_points(board, branch)
        if len(pads) == 2:
            points.append(middle(pads[1]))
        else:
            # The track the branch ends on gets a corner there: the router
            # takes two tracks for joined where their ends meet.
            run = nets.index(pads[0].GetNetname())
            met = where_met(points[-2], unit(points[-1] - points[-2]), runs[run][1])
            if met is None:
                sys.exit(f"{name}: the branch from {branch['from']} does not meet the track of {nets[run]}")
            points[-1] = met
            runs[run] = (runs[run][0], with_point(runs[run][1], met))
        runs.append((pads[0], with_corners_cut(points)))

    for track in list(board.GetTracks()):
        if track.GetNetname() in nets:
            board.Delete(track)
    layer = board.GetLayerID(pair["layer"])
    for pad, points in runs:
        for start, end in zip(points, points[1:]):
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(start.real), pcbnew.FromMM(start.imag)))
            track.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(end.real), pcbnew.FromMM(end.imag)))
            track.SetWidth(width)
            track.SetLayer(layer)
            track.SetNet(pad.GetNet())
            track.SetLocked(True)
            board.Add(track)
    print(f"{name}: {nets[0]} {lengths[0]:.2f} mm and {nets[1]} {lengths[1]:.2f} mm from end to end on "
          f"{pair['layer']}, {pcbnew.ToMM(width):g} mm tracks {pcbnew.ToMM(gap):g} mm apart")


def main(board_path):
    board = pcbnew.LoadBoard(board_path)
    for pair in tomllib.load(open(PAIR_PATHS, "rb"))["pair"]:
        lay(board, pair)
    # The third argument keeps KiCad from rewriting the project file with the board.
    pcbnew.SaveBoard(board_path, board, True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
