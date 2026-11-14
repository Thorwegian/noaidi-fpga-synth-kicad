#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""board_from_circuit.py -- bring the board up to the circuit in text.

    scripts/board_from_circuit.py <netlist> <board>

Reads the netlist that circuit/board.py writes and makes the board's parts
and nets the same as the netlist's, moving as little as possible:

  - a part that is not in the netlist leaves the board;
  - a part whose footprint differs gets the netlist's footprint, the middle
    of its pads where the middle of the old pads was, turned the same way;
  - a part that is new is placed where its pads are nearest to the pads
    they connect to in its own block of the circuit (its SubCircuit);
  - a part named in circuit/fixed_positions.toml sits where that file says;
  - every pad gets the net the netlist gives it, and a track on a net that
    has no pad left is removed.

No part enters another's courtyard: one that would is put in the nearest
free place. Tracks are otherwise left alone, so where a footprint has
changed the copper no longer meets the pads; scripts/route.sh lays it anew.

Runs under the system's Python, which has KiCad's pcbnew module.
"""
import math
import os
import sys
import tomllib

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from netlist_summary import kids, parse, val  # noqa: E402

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KICAD_FOOTPRINT_DIR = os.environ.get("KICAD10_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
FIXED_POSITIONS = os.path.join(PROJECT_DIR, "circuit", "fixed_positions.toml")

COURTYARD_GAP = pcbnew.FromMM(0.25)     # kept between two parts' courtyards
GRID = pcbnew.FromMM(0.25)              # the step of the search for a new part's place
REACH = pcbnew.FromMM(20.0)             # how far from its start the search looks
EDGE_STEP = pcbnew.FromMM(0.05)         # the step of a slide along the board's edge
QUARTER_TURNS = (0.0, 90.0, 180.0, 270.0)
LEFT, TOP, RIGHT, BOTTOM = range(4)
EDGES = {"left": LEFT, "top": TOP, "right": RIGHT, "bottom": BOTTOM}


def read_circuit(path):
    """The netlist's parts, as {designator: {value, footprint, lcsc, block}},
    and its nets, as {name: [(designator, pad number), ...]}."""
    root = parse(open(path, encoding="utf-8").read())
    parts = {}
    for component in kids(kids(root, "components")[0], "comp"):
        fields = {val(field, "name"): (field[2] if len(field) > 2 else "")
                  for field in kids(kids(component, "fields")[0], "field")}
        parts[val(component, "ref")] = {
            "value": val(component, "value"),
            "footprint": val(component, "footprint"),
            "lcsc": fields.get("LCSC", ""),
            "block": val(kids(component, "sheetpath")[0], "names"),
        }
    nets = {val(net, "name"): [(val(node, "ref"), val(node, "pin")) for node in kids(net, "node")]
            for net in kids(kids(root, "nets")[0], "net")}
    return parts, nets


def load_footprint(footprint_id):
    library, name = footprint_id.split(":")
    for folder in (PROJECT_DIR, KICAD_FOOTPRINT_DIR):
        library_dir = os.path.join(folder, library + ".pretty")
        if os.path.isdir(library_dir):
            return pcbnew.FootprintLoad(library_dir, name)
    sys.exit(f"no footprint library {library} for {footprint_id}")


def pad_centre(footprint):
    pads = list(footprint.Pads())
    return pcbnew.VECTOR2I(sum(pad.GetPosition().x for pad in pads) // len(pads),
                           sum(pad.GetPosition().y for pad in pads) // len(pads))


def keep_out(footprint):
    """The rectangle (left, top, right, bottom) no other part may enter: the
    courtyard's, or the whole drawing's for a footprint without a courtyard
    (a module on headers)."""
    footprint.BuildCourtyardCaches()
    courtyard = footprint.GetCourtyard(pcbnew.F_CrtYd)
    box = courtyard.BBox() if courtyard.OutlineCount() else footprint.GetBoundingBox(False)
    return (box.GetLeft(), box.GetTop(), box.GetRight(), box.GetBottom())


def too_close(a, b):
    return (a[LEFT] < b[RIGHT] + COURTYARD_GAP and b[LEFT] < a[RIGHT] + COURTYARD_GAP
            and a[TOP] < b[BOTTOM] + COURTYARD_GAP and b[TOP] < a[BOTTOM] + COURTYARD_GAP)


def on_board(box, outline, open_edge):
    """True when the rectangle lies inside the outline. A connector at the
    board's edge reaches over that edge, which is then not checked."""
    return all(open_edge == edge or (box[edge] >= outline[edge] if edge in (LEFT, TOP) else box[edge] <= outline[edge])
               for edge in (LEFT, TOP, RIGHT, BOTTOM))


def board_outline(board):
    """The rectangle (left, top, right, bottom) around the centre lines of
    the board's edge."""
    boxes = []
    for drawing in board.GetDrawings():
        if drawing.GetLayer() == pcbnew.Edge_Cuts:
            box = drawing.GetBoundingBox()
            box.Inflate(-(drawing.GetWidth() // 2))
            boxes.append(box)
    return (min(box.GetLeft() for box in boxes), min(box.GetTop() for box in boxes),
            max(box.GetRight() for box in boxes), max(box.GetBottom() for box in boxes))


def settle(board, footprint, cost, moves, turns=None, open_edge=None):
    """Move the footprint to the free place of lowest cost. moves lists the
    candidates as (dx, dy) from where the footprint is; cost(dx, dy, pads)
    prices one, pads being the footprint's [(number, x, y)] there; turns
    lists the orientations to try, the footprint's own when left out."""
    outline = board_outline(board)
    others = [keep_out(other) for other in board.GetFootprints()
              if other.GetReference() != footprint.GetReference()]
    start = footprint.GetPosition()
    best = None
    for turn in turns or (footprint.GetOrientationDegrees(),):
        footprint.SetOrientationDegrees(turn)
        box = keep_out(footprint)
        pads = [(pad.GetNumber(), pad.GetPosition().x, pad.GetPosition().y) for pad in footprint.Pads()]
        for dx, dy in moves:
            price = cost(dx, dy, [(number, x + dx, y + dy) for number, x, y in pads])
            if best and price >= best[0]:
                continue
            moved = (box[LEFT] + dx, box[TOP] + dy, box[RIGHT] + dx, box[BOTTOM] + dy)
            if on_board(moved, outline, open_edge) and not any(too_close(moved, other) for other in others):
                best = (price, turn, dx, dy)
    if not best:
        sys.exit(f"no free place for {footprint.GetReference()}")
    footprint.SetOrientationDegrees(best[1])
    footprint.SetPosition(pcbnew.VECTOR2I(start.x + best[2], start.y + best[3]))


def displacement(dx, dy, pads):
    return math.hypot(dx, dy)


def main(netlist_path, board_path):
    parts, nets = read_circuit(netlist_path)
    net_of_pad = {pad: name for name, pads in nets.items() for pad in pads}
    fixed = tomllib.load(open(FIXED_POSITIONS, "rb"))
    board = pcbnew.LoadBoard(board_path)
    outline = board_outline(board)

    def describe(footprint):
        position = footprint.GetPosition()
        return (f"{footprint.GetReference():4} {pcbnew.ToMM(position.x):7.2f}, {pcbnew.ToMM(position.y):7.2f} mm "
                f"{footprint.GetOrientationDegrees():4g}°  {footprint.GetFPIDAsString()}")

    # Parts that are not in the circuit leave the board.
    for footprint in list(board.GetFootprints()):
        if footprint.GetReference() not in parts and not footprint.GetAttributes() & pcbnew.FP_BOARD_ONLY:
            print("removed", describe(footprint))
            board.Delete(footprint)

    # A changed footprint replaces the old one where it sat; a new part waits for its place.
    swapped, new = [], []
    for designator in sorted(parts):
        part = parts[designator]
        old = board.FindFootprintByReference(designator)
        footprint = old
        if not old or old.GetFPIDAsString() != part["footprint"]:
            footprint = load_footprint(part["footprint"])
            footprint.SetFPIDAsString(part["footprint"])
            footprint.SetReference(designator)
            if old:
                footprint.SetOrientationDegrees(old.GetOrientationDegrees())
                footprint.SetPosition(footprint.GetPosition() + pad_centre(old) - pad_centre(footprint))
                footprint.SetPath(old.GetPath())
                footprint.SetSheetname(old.GetSheetname())
                footprint.SetSheetfile(old.GetSheetfile())
                board.Delete(old)
            (swapped if old else new).append(footprint)
            board.Add(footprint)
        footprint.SetValue(part["value"])
        if part["lcsc"]:
            footprint.SetField("LCSC", part["lcsc"])
            lcsc = footprint.GetField("LCSC")
            lcsc.SetVisible(False)      # a new field is otherwise printed on the silkscreen
            lcsc.SetLayer(pcbnew.F_Fab)

    # Every pad on the net the circuit gives it; a track whose net has no pad left goes.
    for name in nets:
        if not board.FindNet(name):
            board.Add(pcbnew.NETINFO_ITEM(board, name))
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            name = net_of_pad.get((footprint.GetReference(), pad.GetNumber()))
            if name:
                pad.SetNet(board.FindNet(name))
            else:
                pad.SetNetCode(0)
    nets_with_pads = {pad.GetNetname() for footprint in board.GetFootprints() for pad in footprint.Pads()}
    stale_tracks = [track for track in board.GetTracks() if track.GetNetname() not in nets_with_pads]
    for track in stale_tracks:
        board.Delete(track)

    # The parts whose place is stated.
    waiting = {footprint.GetReference() for footprint in new}
    open_edge_of = {}
    for designator, rule in fixed.items():
        footprint = board.FindFootprintByReference(designator)
        pitch = 0
        if "edge" in rule:
            open_edge_of[designator] = EDGES[rule["edge"]]
            inset = pcbnew.FromMM(rule["edge_line_mm"])
            position = footprint.GetPosition()
            footprint.SetPosition({
                LEFT: pcbnew.VECTOR2I(outline[LEFT] + inset, position.y),
                TOP: pcbnew.VECTOR2I(position.x, outline[TOP] + inset),
                RIGHT: pcbnew.VECTOR2I(outline[RIGHT] - inset, position.y),
                BOTTOM: pcbnew.VECTOR2I(position.x, outline[BOTTOM] - inset),
            }[open_edge_of[designator]])
        else:
            neighbour = board.FindFootprintByReference(rule["beside"])
            open_edge_of[designator] = open_edge_of[rule["beside"]]
            footprint.SetOrientationDegrees(neighbour.GetOrientationDegrees())
            footprint.SetPosition(neighbour.GetPosition())
            pitch = pcbnew.FromMM(rule["pitch_mm"])
        slides = [step for step in range(-2 * REACH, 2 * REACH + 1, EDGE_STEP) if abs(step) >= pitch]
        along_x = open_edge_of[designator] in (TOP, BOTTOM)
        settle(board, footprint, displacement, [(s, 0) if along_x else (0, s) for s in slides],
               open_edge=open_edge_of[designator])
        waiting.discard(designator)

    # A swapped part that now enters a neighbour's courtyard moves the least it can.
    square = sorted(((dx, dy) for dx in range(-REACH, REACH + 1, GRID) for dy in range(-REACH, REACH + 1, GRID)),
                    key=lambda move: math.hypot(*move))
    for footprint in swapped:
        if footprint.GetReference() not in fixed:
            settle(board, footprint, displacement, square)
        print("swapped", describe(footprint))

    # A new part goes where its pads are nearest to the pads they connect to in its own block.
    for footprint in sorted(new, key=lambda f: -f.GetPadCount()):
        designator = footprint.GetReference()
        if designator in waiting:
            reach = {}
            for pad in footprint.Pads():
                name = net_of_pad.get((designator, pad.GetNumber()))
                reach[pad.GetNumber()] = [
                    other_pad.GetPosition()
                    for other, number in nets.get(name, ())
                    if other not in waiting and parts[other]["block"] == parts[designator]["block"]
                    for other_pad in board.FindFootprintByReference(other).Pads() if other_pad.GetNumber() == number]
            reach = {number: targets for number, targets in reach.items() if targets}
            if not reach:
                sys.exit(f"{designator} connects to nothing on the board in its block {parts[designator]['block']}")
            targets = [target for group in reach.values() for target in group]
            footprint.SetPosition(pcbnew.VECTOR2I(sum(t.x for t in targets) // len(targets),
                                                  sum(t.y for t in targets) // len(targets)))

            def distance_to_reach(dx, dy, pads):
                return sum(min(math.hypot(x - target.x, y - target.y) for target in reach[number])
                           for number, x, y in pads if number in reach)

            settle(board, footprint, distance_to_reach, square, turns=QUARTER_TURNS)
            waiting.discard(designator)
        print("added  ", describe(footprint))

    # The third argument keeps KiCad from rewriting the project file with the board.
    pcbnew.SaveBoard(board_path, board, True)
    print(f"{len(stale_tracks)} tracks removed with their nets; "
          f"{len(list(board.GetFootprints()))} parts, {len(nets)} nets")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
