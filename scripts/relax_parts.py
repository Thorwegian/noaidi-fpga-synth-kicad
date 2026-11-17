#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""relax_parts.py -- relax the parts into an arrangement: a spring on every
connection, the courtyards pushed apart, and the parts at the edges pinned to
their lines.

    scripts/relax_parts.py <board> <out board> [<steps>]

Reads the board scripts/board_from_circuit.py builds, with the parts where
that run left them, and moves them by the forces on them: every pair of pads
on one net pulls its two parts together, held apart by the parts' own
rectangles. A part at an edge of circuit/fixed_positions.toml does not leave
its line and slides along it only; the parts the file puts beside another
move as one with it.

The result is an arrangement, not a packing: it is where the parts want to
be, and scripts/place_parts.py's settle makes it legal. Nothing about it is
random, and the same board gives the same arrangement.
"""
import math
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from board_from_circuit import EDGES, FIXED_POSITIONS, LAYERS, board_outline, keep_out, turn_to_face  # noqa: E402

import tomllib  # noqa: E402

SPRING = 1.0            # a newton per millimetre a connection is out of its length
REST_MM = 2.0           # how long a connection wants to be
PUSH = 4.0              # how hard two rectangles push when they overlap, per mm of it
STEP_MM = 0.6           # the most a part moves in one step
STEPS = 400
SETTLED_MM = 0.02       # when nothing moves further than this, it is done


def springs_of(board, fill_nets):
    """[(part, pad offset, part, pad offset)]: every pair of pads on one net on
    two parts, as the offset of each pad from its part's origin. A net the
    copper is filled with joins every part on it and pulls none of them."""
    nets = {}
    for footprint in board.GetFootprints():
        origin = footprint.GetPosition()
        for pad in footprint.Pads():
            name = pad.GetNetname()
            if not name or name in fill_nets:
                continue
            place = pad.GetPosition()
            nets.setdefault(name, []).append((footprint.GetReference(), place.x - origin.x,
                                              place.y - origin.y, place))
    springs = []
    for name, pads in sorted(nets.items()):
        for i, (part_a, ax, ay, a) in enumerate(pads):
            for part_b, bx, by, b in pads[i + 1:]:
                if part_a != part_b:
                    springs.append((part_a, ax, ay, part_b, bx, by))
    return springs


def boxes_of(board):
    return {footprint.GetReference(): keep_out(footprint) for footprint in board.GetFootprints()}


def overlap(a, b, gap):
    """How far two rectangles have to be moved apart, as (dx, dy) for the
    first one, and which way is the shorter way out."""
    across = min(a[2], b[2]) - max(a[0], b[0]) + gap
    up = min(a[3], b[3]) - max(a[1], b[1]) + gap
    if across <= 0 or up <= 0:
        return 0.0, 0.0
    if across < up:
        return (across if (a[0] + a[2]) < (b[0] + b[2]) else -across), 0.0
    return 0.0, (up if (a[1] + a[3]) < (b[1] + b[3]) else -up)


def main(board_path, out_path, steps=STEPS):
    fixed = tomllib.load(open(FIXED_POSITIONS, "rb"))
    board = pcbnew.LoadBoard(board_path)
    outline = board_outline(board)
    footprints = {footprint.GetReference(): footprint for footprint in board.GetFootprints()}
    fill_nets = {layer["fill"] for layer in tomllib.load(open(LAYERS, "rb"))["layer"]}
    springs = springs_of(board, fill_nets)
    pinned = {}
    for name, rule in fixed.items():
        if name not in footprints:
            continue
        if "edge" in rule and "edge_line_mm" in rule:
            if "faces" in rule:
                turn_to_face(footprints[name], EDGES[rule["edge"]], rule["faces"])
            pinned[name] = EDGES[rule["edge"]]
        elif "beside" in rule and rule["beside"] in footprints:
            pinned[name] = "beside"

    for step in range(steps):
        push = {name: [0.0, 0.0] for name in footprints}
        for part_a, ax, ay, part_b, bx, by in springs:
            a, b = footprints[part_a].GetPosition(), footprints[part_b].GetPosition()
            dx, dy = (b.x - a.x) + (bx - ax), (b.y - a.y) + (by - ay)
            length = math.hypot(dx, dy) or 1.0
            pull = SPRING * (length - pcbnew.FromMM(REST_MM)) / length
            push[part_a][0] += pull * dx
            push[part_a][1] += pull * dy
            push[part_b][0] -= pull * dx
            push[part_b][1] -= pull * dy
        boxes = boxes_of(board)
        names = sorted(boxes)
        for i, one in enumerate(names):
            for other in names[i + 1:]:
                dx, dy = overlap(boxes[one], boxes[other], 0)
                if dx or dy:
                    push[one][0] += PUSH * dx
                    push[one][1] += PUSH * dy
                    push[other][0] -= PUSH * dx
                    push[other][1] -= PUSH * dy
        moved = 0.0
        for name, footprint in footprints.items():
            fx, fy = push[name]
            if name in pinned:
                edge = pinned[name]
                if edge in (EDGES["left"], EDGES["right"]):
                    fx = 0.0
                else:
                    fy = 0.0
            size = math.hypot(fx, fy)
            if size < 1e-9:
                continue
            travel = min(STEP_MM, size)
            dx, dy = fx / size * travel, fy / size * travel
            footprint.Move(pcbnew.VECTOR2I(pcbnew.FromMM(dx), pcbnew.FromMM(dy)))
            moved = max(moved, abs(dx) + abs(dy))
        if moved < SETTLED_MM:
            print(f"settled after {step + 1} steps")
            break
    else:
        print(f"{steps} steps")

    # The parts the file moves as one keep their places together.
    for name, edge in pinned.items():
        if edge == "beside":
            footprint, neighbour = footprints[name], footprints[fixed[name]["beside"]]
            footprint.SetOrientationDegrees(neighbour.GetOrientationDegrees())
            footprint.SetPosition(neighbour.GetPosition())

    pcbnew.SaveBoard(out_path, board, True)
    length = sum(math.hypot((footprints[b].GetPosition().x + bx) - (footprints[a].GetPosition().x + ax),
                            (footprints[b].GetPosition().y + by) - (footprints[a].GetPosition().y + ay))
                 for a, ax, ay, b, bx, by in springs)
    boxes = boxes_of(board)
    names = sorted(boxes)
    clashing = sum(1 for i, one in enumerate(names) for other in names[i + 1:]
                   if overlap(boxes[one], boxes[other], 0) != (0.0, 0.0))
    print(f"{len(springs)} connections, {length / 1e6:.0f} mm of them in all, "
          f"{clashing} pairs of parts still on each other, {len(pinned)} parts pinned")
    print(f"saved {out_path}")


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], *(int(number) for number in sys.argv[3:]))
