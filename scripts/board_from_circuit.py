#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""board_from_circuit.py -- bring the board up to the circuit in text.

    scripts/board_from_circuit.py <netlist> <net classes> <board>

Reads the netlist and the net classes that circuit/board.py writes
(board.net and net_classes.json) and makes the board's parts and nets the
same as the netlist's, moving as little as possible:

  - a part that is not in the netlist leaves the board;
  - a part whose footprint differs gets the netlist's footprint, the middle
    of its pads where the middle of the old pads was, turned the same way;
  - a part that is new is placed where its pads are nearest to the pads
    they connect to in its own block of the circuit (its SubCircuit);
  - a part named in circuit/fixed_positions.toml sits where that file says;
  - every pad gets the net the netlist gives it, and a track on a net that
    has no pad left is removed.

The net classes go into the KiCad project file beside the board: each class
with its widths, clearance and via, and each net that is in one by its name.
A class the circuit does not have leaves the project.

The board gets the copper layers of circuit/layers.toml: a layer without
tracks is of the type power, and each layer has one fill over the whole
board on the net that file gives it. Fills that are already those are left
as they are. A keep-out area that a footprint has on both the front and the
back (the one under the ESP32 module's antenna) is made to hold on the
layers between them too.

No part enters another's courtyard: one that would is put in the nearest
free place. Tracks are otherwise left alone, so where a footprint has
changed the copper no longer meets the pads; scripts/route.sh lays it anew.

Runs under the system's Python, which has KiCad's pcbnew module.
"""
import json
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
LAYERS = os.path.join(PROJECT_DIR, "circuit", "layers.toml")

COURTYARD_GAP = pcbnew.FromMM(0.25)     # kept between two parts' courtyards
GRID = pcbnew.FromMM(0.25)              # the step of the search for a new part's place
REACH = pcbnew.FromMM(20.0)             # how far from its start the search looks
EDGE_STEP = pcbnew.FromMM(0.05)         # the step of a slide along the board's edge
QUARTER_TURNS = (0.0, 90.0, 180.0, 270.0)
LEFT, TOP, RIGHT, BOTTOM = range(4)
EDGES = {"left": LEFT, "top": TOP, "right": RIGHT, "bottom": BOTTOM}
# Every move within REACH on the GRID, the shortest first.
NEARBY = sorted(((dx, dy) for dx in range(-REACH, REACH + 1, GRID) for dy in range(-REACH, REACH + 1, GRID)),
                key=lambda move: math.hypot(*move))


def read_circuit(path):
    """The netlist's parts, as {designator: {value, footprint, lcsc, block}},
    its nets, as {name: [(designator, pad number), ...]}, and the class of
    each net that is in one, as {name: class}."""
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
    class_of_net = {}
    for net in kids(kids(root, "nets")[0], "net"):
        classes = [name for name in val(net, "class").split(",") if name != "Default"]
        if len(classes) > 1:
            sys.exit(f"the net {val(net, 'name')} is in more than one class: {', '.join(classes)}")
        if classes:
            class_of_net[val(net, "name")] = classes[0]
    return parts, nets, class_of_net


def write_net_classes(project_path, classes, class_of_net):
    """Put the circuit's net classes and their nets into the KiCad project
    file. A class keeps what the project has for it beyond the circuit's
    figures (its colours); KiCad gives the lowest priority number the say
    where a net is in several classes, and Default has the highest."""
    missing = sorted((set(class_of_net.values()) | {"Default"}) - set(classes))
    if missing:
        sys.exit(f"the circuit's net classes have no {', '.join(missing)}")
    project = json.load(open(project_path, encoding="utf-8"))
    settings = project["net_settings"]
    in_project = {net_class["name"]: net_class for net_class in settings["classes"]}
    settings["classes"] = []
    for priority, name in enumerate(["Default"] + sorted(set(classes) - {"Default"}), -1):
        net_class = in_project.get(name, {"name": name, "pcb_color": "rgba(0, 0, 0, 0.000)",
                                          "schematic_color": "rgba(0, 0, 0, 0.000)", "tuning_profile": ""})
        net_class.update(classes[name])
        if name != "Default":
            net_class["priority"] = priority
        settings["classes"].append(dict(sorted(net_class.items())))
    settings["netclass_patterns"] = [{"netclass": class_of_net[name], "pattern": name}
                                     for name in sorted(class_of_net)]
    with open(project_path, "w", encoding="utf-8") as file:
        json.dump(project, file, indent=2)
        file.write("\n")


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
    one around the part's courtyard, its outline on the silkscreen and the
    fabrication layer, and its rule areas. A part covers what is under it,
    and a module's outline reaches past its courtyard where the module
    overhangs its pins; in a rule area that keeps the fills out (the one
    under a module's antenna) a pad has no fill to join. For a footprint
    that has none of these, the whole drawing's."""
    footprint.BuildCourtyardCaches()
    courtyard = footprint.GetCourtyard(pcbnew.F_CrtYd)
    boxes = [courtyard.BBox()] if courtyard.OutlineCount() else []
    boxes += [item.GetBoundingBox() for item in footprint.GraphicalItems()
              if item.GetClass() == "PCB_SHAPE" and item.GetLayer() in (pcbnew.F_SilkS, pcbnew.F_Fab)]
    boxes += [area.GetBoundingBox() for area in footprint.Zones() if area.GetIsRuleArea()]
    boxes = boxes or [footprint.GetBoundingBox(False)]
    return (min(box.GetLeft() for box in boxes), min(box.GetTop() for box in boxes),
            max(box.GetRight() for box in boxes), max(box.GetBottom() for box in boxes))


def too_close(a, b, gap):
    return (a[LEFT] < b[RIGHT] + gap and b[LEFT] < a[RIGHT] + gap
            and a[TOP] < b[BOTTOM] + gap and b[TOP] < a[BOTTOM] + gap)


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


def set_layers(board, layers):
    """Give the board the copper layers of circuit/layers.toml and their
    fills. Returns True when the fills were made anew."""
    board.SetCopperLayerCount(len(layers))
    wanted = set()
    for layer in layers:
        number = board.GetLayerID(layer["name"])
        board.SetLayerType(number, pcbnew.LT_SIGNAL if layer["tracks"] else pcbnew.LT_POWER)
        if not board.FindNet(layer["fill"]):
            sys.exit(f"{layer['name']} is filled with {layer['fill']}, which is not a net of the circuit")
        wanted.add((number, layer["fill"]))
    # A footprint drawn for two layers names both of them where it means the board's whole thickness.
    for footprint in board.GetFootprints():
        for area in footprint.Zones():
            if area.GetIsRuleArea() and area.IsOnLayer(pcbnew.F_Cu) and area.IsOnLayer(pcbnew.B_Cu):
                area.SetLayerSet(pcbnew.LSET.AllCuMask(len(layers)))
    fills = list(board.Zones())
    if sorted((fill.GetLayerSet().Seq()[0], fill.GetNetname()) for fill in fills) == sorted(wanted):
        return False
    for fill in fills:
        board.Delete(fill)
    left, top, right, bottom = board_outline(board)
    for number, net in sorted(wanted):
        fill = pcbnew.ZONE(board)
        fill.SetLayer(number)
        fill.SetNet(board.FindNet(net))
        fill.SetZoneName(f"{net} {board.GetLayerName(number)}")
        fill.Outline().NewOutline()
        for x, y in ((left, top), (right, top), (right, bottom), (left, bottom)):
            fill.Outline().Append(x, y)
        fill.SetMinThickness(pcbnew.FromMM(0.25))
        fill.SetThermalReliefGap(pcbnew.FromMM(0.5))
        fill.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.5))
        # Through-hole pads are soldered by hand, and the spokes let the pad be heated.
        fill.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)
        board.Add(fill)
    return True


def settle(board, footprint, cost, moves, turns=None, open_edge=None, gap=COURTYARD_GAP):
    """Move the footprint to the free place of lowest cost. moves lists the
    candidates as (dx, dy) from where the footprint is; cost(dx, dy, pads)
    prices one, pads being the footprint's [(number, x, y)] there; turns
    lists the orientations to try, the footprint's own when left out; gap
    is what the footprint keeps to every other part."""
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
            if on_board(moved, outline, open_edge) and not any(too_close(moved, other, gap) for other in others):
                best = (price, turn, dx, dy)
    if not best:
        sys.exit(f"no free place for {footprint.GetReference()}")
    footprint.SetOrientationDegrees(best[1])
    footprint.SetPosition(pcbnew.VECTOR2I(start.x + best[2], start.y + best[3]))


def displacement(dx, dy, pads):
    return math.hypot(dx, dy)


def settle_at_its_connections(board, footprint, reach, gap=COURTYARD_GAP):
    """Move the footprint to the free place where its pads are nearest to the
    pads they connect to, turned whichever way brings them nearest. reach
    holds, for each of its pads by number, the places of those pads; gap is
    what the footprint keeps to every other part."""
    targets = [target for group in reach.values() for target in group]
    footprint.SetPosition(pcbnew.VECTOR2I(sum(target.x for target in targets) // len(targets),
                                          sum(target.y for target in targets) // len(targets)))

    def distance_to_reach(dx, dy, pads):
        return sum(min(math.hypot(x - target.x, y - target.y) for target in reach[number])
                   for number, x, y in pads if number in reach)

    settle(board, footprint, distance_to_reach, NEARBY, turns=QUARTER_TURNS, gap=gap)


def main(netlist_path, net_classes_path, board_path):
    parts, nets, class_of_net = read_circuit(netlist_path)
    net_of_pad = {pad: name for name, pads in nets.items() for pad in pads}
    fixed = tomllib.load(open(FIXED_POSITIONS, "rb"))
    layers = tomllib.load(open(LAYERS, "rb"))["layer"]
    # KiCad reads the project file when it loads the board.
    write_net_classes(os.path.splitext(board_path)[0] + ".kicad_pro",
                      json.load(open(net_classes_path, encoding="utf-8")), class_of_net)
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
    for name in nets:
        in_kicad = board.FindNet(name).GetNetClassName().split(",")[0]
        if in_kicad != class_of_net.get(name, "Default"):
            sys.exit(f"KiCad has the net {name} in the class {in_kicad}, the circuit in {class_of_net.get(name, 'Default')}")
    new_fills = set_layers(board, layers)
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
            if "edge_line_mm" not in rule:
                continue    # placed by eye: it stays where it is drawn
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
    for footprint in swapped:
        if footprint.GetReference() not in fixed:
            settle(board, footprint, displacement, NEARBY)
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
            settle_at_its_connections(board, footprint, reach)
            waiting.discard(designator)
        print("added  ", describe(footprint))

    # The third argument keeps KiCad from rewriting the project file with the board.
    pcbnew.SaveBoard(board_path, board, True)
    print(f"{len(stale_tracks)} tracks removed with their nets; "
          f"{len(list(board.GetFootprints()))} parts, {len(nets)} nets, "
          f"{len(class_of_net)} of them in {len(set(class_of_net.values()))} classes besides Default; "
          f"{len(layers)} copper layers, their fills {'made anew' if new_fills else 'as they were'}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
