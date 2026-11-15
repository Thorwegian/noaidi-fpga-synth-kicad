#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""lay_pairs.py -- lay the board's differential pairs as pairs, for the autorouter to work around.

    scripts/lay_pairs.py <board>

For each pair in circuit/pair_paths.toml, removes the tracks and vias of the
pair's two nets and lays two tracks side by side along the path the file
states, on the layer it states: at the width and the gap the nets' class
gives a pair, the path midway between them. The path's corners are cut, so
that a turn is two bends. From each end of the path a track goes to its pad
in one slanted step and then straight on.

A socket has each line of a pair on two pads. The further pad of a net gets
a branch: a track from its middle through the points the file states, to
the net's track or to the net's first pad.

The tracks are locked: scripts/route_board.py leaves a locked track where
it is and gives it to the router as one that stays.

Two tracks on one layer cannot change sides, so the net on the left of the
path has to be the same at both ends. A path that would need a crossing is
refused. So is one whose two tracks would both step the same way to their
pads at an end: side by side they would close in on each other, and the
step belongs in the path.

KiCad's DRC is the judge of what is laid: the clearances, that every pad
is joined, and the rules for a pair in the project's .kicad_dru.

Runs under the system's Python, which has KiCad's pcbnew module.
"""
import os
import sys
import tomllib

import pcbnew

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAIR_PATHS = os.path.join(PROJECT_DIR, "circuit", "pair_paths.toml")

CORNER_CUT_MM = 0.5         # taken off each leg of a corner
SHARP = 0.7                 # a corner is cut when the cosine of its turn is below this: beyond 45 degrees


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


def to_pad(end, heading, pad, name):
    """The points from a track's end at the end of the path to the middle
    of its pad: one slanted step sideways, then straight on."""
    reach = pad - end
    sideways, ahead = along(reach, left_of(heading)), along(reach, heading)
    if ahead < abs(sideways):
        sys.exit(f"{name}: the path ends too near its pads for a slanted step to reach them")
    if abs(sideways) < 1e-6:
        return [pad]
    return [end + abs(sideways) * heading + sideways * left_of(heading), pad]


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


def length_of(points):
    return sum(abs(end - start) for start, end in zip(points, points[1:]))


def with_point(points, point):
    """The line through the points with the point, which lies on it, as one
    of them; None when the point does not lie on the line."""
    for index, (start, end) in enumerate(zip(points, points[1:]), 1):
        if abs(abs(point - start) + abs(end - point) - abs(end - start)) < 1e-6:
            return points[:index] + [point] + points[index:]
    return None


def lay(board, pair):
    name = pair["name"]
    path = with_corners_cut(points_of(pair["path_mm"]))
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
    lines = [beside(path, from_path), beside(path, -from_path)]
    for heading, ends, pads in ((out_of_start, [line[0] for line in lines], start_pads),
                                (out_of_end, [line[-1] for line in lines], end_pads)):
        to_left, to_right = (along(middle(pad) - end, left_of(heading)) for end, pad in zip(ends, pads))
        if to_left * to_right > 1e-9:
            sys.exit(f"{name}: both tracks step the same way from the path's end to "
                     f"{' and '.join(pad.GetParentFootprint().GetReference() + '.' + pad.GetNumber() for pad in pads)}; "
                     f"the path is to end midway between where the two tracks go on")

    def of_the_pair(pad):
        if pad.GetNetname() not in nets:
            sys.exit(f"{name}: a pad on {pad.GetNetname()} is not on one of its nets, {nets[0]} and {nets[1]}")
        return pad

    runs = [(start_pad, to_pad(line[0], out_of_start, middle(start_pad), name)[::-1] + line
             + to_pad(line[-1], out_of_end, middle(end_pad), name))
            for line, start_pad, end_pad in zip(lines, start_pads, end_pads)]
    lengths = [length_of(points) for _, points in runs]
    for branch in pair.get("branch", []):
        pads = [of_the_pair(pad) for pad in pads_of(board, [branch[end] for end in ("from", "to") if end in branch])]
        if len({pad.GetNetname() for pad in pads}) != 1:
            sys.exit(f"{name}: the branch from {branch['from']} to {branch['to']} joins two nets")
        points = with_corners_cut([middle(pads[0])] + points_of(branch["path_mm"])
                                  + [middle(pad) for pad in pads[1:]])
        if len(pads) == 1:
            # The track the branch ends on gets a corner there: the router
            # takes two tracks for joined where their ends meet.
            run = nets.index(pads[0].GetNetname())
            joined = with_point(runs[run][1], points[-1])
            if joined is None:
                sys.exit(f"{name}: the branch from {branch['from']} ends beside the track of {nets[run]}, not on it")
            runs[run] = (runs[run][0], joined)
        runs.append((pads[0], points))

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
