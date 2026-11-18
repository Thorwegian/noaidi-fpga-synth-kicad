#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""board_from_circuit.py -- bring the board up to the circuit in text.

    scripts/board_from_circuit.py <netlist> <net classes> <board> [fresh]

Reads the netlist and the net classes that circuit/board.py writes
(board.net and net_classes.json) and makes the board's parts and nets the
same as the netlist's, moving as little as possible. With fresh it reads no
board at all: it builds one from the netlist and the rule files, in a
nominal rectangle that scripts/place_parts.py then draws the outline
around.

  - a part that is not in the netlist leaves the board;
  - a part whose footprint differs gets the netlist's footprint, the middle
    of its pads where the middle of the old pads was, turned the same way;
  - a part that is new is placed where its pads are nearest to the pads
    they connect to in its own block of the circuit (its SubCircuit);
  - a part named in circuit/fixed_positions.toml sits where that file says,
    and the parts that connect to nothing but that part move with it;
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

Around each antenna of circuit/antennas.toml the board gets a rule area
named "Antenna clearance", on every copper layer: the antenna's area in its
part's footprint, wider by the distance that file states. The area closes
nothing by itself, so copper is laid and filled in it as anywhere; the rule
of that name in the project's .kicad_dru says which nets may not lie in it.

No part enters another's courtyard, and no part with a pad of a net class
that an antenna is kept clear of enters that antenna's clearance: one that
would is put in the nearest free place. Tracks are otherwise left alone, so
where a footprint has changed or a part has moved the copper no longer
meets the pads; scripts/route.sh lays it anew.

Runs under the system's Python, which has KiCad's pcbnew module.
"""
import collections
import json
import math
import os
import sys
try:
    import tomllib
except ModuleNotFoundError:     # KiCad's Python on a Mac is 3.9, where tomli stands in
    import tomli as tomllib

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from netlist_summary import kids, parse, val  # noqa: E402

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KICAD_FOOTPRINT_DIR = os.environ.get("KICAD10_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
FIXED_POSITIONS = os.path.join(PROJECT_DIR, "circuit", "fixed_positions.toml")
LAYERS = os.path.join(PROJECT_DIR, "circuit", "layers.toml")
ANTENNAS = os.path.join(PROJECT_DIR, "circuit", "antennas.toml")
FAB = os.path.join(PROJECT_DIR, "circuit", "fab.toml")
ANTENNA_CLEARANCE = "Antenna clearance"     # the name the rule in the .kicad_dru knows the areas by

COURTYARD_GAP = pcbnew.FromMM(0.25)     # kept between two parts' courtyards
GRID = pcbnew.FromMM(0.25)              # the step of the search for a new part's place
REACH = pcbnew.FromMM(20.0)             # how far from its start the search looks
EDGE_STEP = pcbnew.FromMM(0.05)         # the step of a slide along the board's edge
QUARTER_TURNS = (0.0, 90.0, 180.0, 270.0)
NOMINAL_MM = 1200.0                     # the room a fresh board is built in: the longest side any fab takes, both ways round
LEFT, TOP, RIGHT, BOTTOM = range(4)
EDGES = {"left": LEFT, "top": TOP, "right": RIGHT, "bottom": BOTTOM}

# The side of a part a person plugs into, as its footprint is drawn, and the
# direction of the board's edges. The turn comes first: a part is turned to
# the edge the fixed positions give it before it is placed anywhere, since
# the edge it happens to be drawn near on the board says nothing about which
# way its opening points.
FACING = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}
TOWARD_EDGE = {LEFT: (-1, 0), RIGHT: (1, 0), TOP: (0, -1), BOTTOM: (0, 1)}


def turn_to_face(footprint, edge, faces):
    """Turn a footprint so that the side it is plugged into faces the board
    edge it is at, through a quarter turn at most from where it is drawn."""
    x, y = FACING[faces]
    want = TOWARD_EDGE[edge]
    for quarter in range(4):
        angle = math.radians(quarter * 90)
        turned = (round(x * math.cos(angle) + y * math.sin(angle)),
                  round(-x * math.sin(angle) + y * math.cos(angle)))
        if turned == want:
            footprint.SetOrientationDegrees(quarter * 90)
            return
    raise ValueError(f"{footprint.GetReference()} faces {faces}, which no quarter turn puts at {edge}")


class NoFreePlace(Exception):
    """A part has no free place among the moves it was given. Its text is the part's designator."""


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
    return middle([pad.GetPosition() for pad in footprint.Pads()])


def middle(points):
    return pcbnew.VECTOR2I(sum(point.x for point in points) // len(points),
                           sum(point.y for point in points) // len(points))


def pad_named(board, name):
    """The pad that designator.pad names."""
    designator, number = name.split(".")
    footprint = board.FindFootprintByReference(designator)
    pads = [pad for pad in footprint.Pads() if pad.GetNumber() == number] if footprint else []
    if not pads:
        sys.exit(f"no pad {name} on the board")
    return pads[0]


def rectangle(box):
    return (box.GetLeft(), box.GetTop(), box.GetRight(), box.GetBottom())


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


def nearer_than(a, b, gap):
    return (a[LEFT] < b[RIGHT] + gap and b[LEFT] < a[RIGHT] + gap
            and a[TOP] < b[BOTTOM] + gap and b[TOP] < a[BOTTOM] + gap)


def antenna_clearances(board, antennas):
    """What circuit/antennas.toml keeps clear, as [(part, rectangle, net
    classes)]: the rectangle around the antenna's area in the part's
    footprint, wider by the file's distance on every side."""
    clearances = []
    for antenna in antennas:
        footprint = board.FindFootprintByReference(antenna["part"])
        areas = [area for area in footprint.Zones() if area.GetZoneName() == antenna["area"]] if footprint else []
        if not areas:
            sys.exit(f"{antenna['part']} has no rule area named {antenna['area']}")
        box = areas[0].GetBoundingBox()
        box.Inflate(pcbnew.FromMM(antenna["clear_mm"]))
        clearances.append((antenna["part"], rectangle(box), set(antenna["net_classes"])))
    return clearances


def draw_antenna_clearances(board, clearances):
    """Make the board's rule areas named ANTENNA_CLEARANCE the clearances'
    rectangles, on every copper layer. Areas that are already those are left
    as they are."""
    copper = pcbnew.LSET.AllCuMask(board.GetCopperLayerCount())
    drawn = [area for area in board.Zones() if area.GetIsRuleArea() and area.GetZoneName() == ANTENNA_CLEARANCE]
    if (sorted(rectangle(area.GetBoundingBox()) for area in drawn) == sorted(box for _, box, _ in clearances)
            and all(list(area.GetLayerSet().Seq()) == list(copper.Seq()) for area in drawn)):
        return
    for area in drawn:
        board.Delete(area)
    for _, (left, top, right, bottom), _ in clearances:
        area = pcbnew.ZONE(board)
        area.SetIsRuleArea(True)
        area.SetZoneName(ANTENNA_CLEARANCE)
        area.SetLayerSet(copper)
        # What may not lie in the area is for the rule in the .kicad_dru to say: it knows the nets.
        for close in (area.SetDoNotAllowTracks, area.SetDoNotAllowVias, area.SetDoNotAllowPads,
                      area.SetDoNotAllowZoneFills, area.SetDoNotAllowFootprints):
            close(False)
        area.Outline().NewOutline()
        for x, y in ((left, top), (right, top), (right, bottom), (left, bottom)):
            area.Outline().Append(x, y)
        board.Add(area)


def closed_to(footprint, clearances, class_of_net):
    """The antenna clearances the footprint may not enter: those kept clear
    of a net class one of its pads is in."""
    classes = {class_of_net.get(pad.GetNetname(), "Default") for pad in footprint.Pads() if pad.GetNetname()}
    return [box for part, box, kept_out in clearances
            if part != footprint.GetReference() and kept_out & classes]


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


def draw_nominal_outline(board):
    """A rectangle for the board to be built in, before anything is placed:
    the placing reads no size from it, and draws the board's own outline
    afterwards."""
    rectangle = pcbnew.PCB_SHAPE(board)
    rectangle.SetShape(pcbnew.SHAPE_T_RECTANGLE)
    rectangle.SetLayer(pcbnew.Edge_Cuts)
    rectangle.SetWidth(pcbnew.FromMM(0.1))
    rectangle.SetStart(pcbnew.VECTOR2I(0, 0))
    rectangle.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(NOMINAL_MM), pcbnew.FromMM(NOMINAL_MM)))
    board.Add(rectangle)


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
    fills = [zone for zone in board.Zones() if not zone.GetIsRuleArea()]
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


def settle(board, footprint, cost, moves, turns=None, open_edge=None, gap=COURTYARD_GAP, closed=()):
    """Move the footprint to the free place of lowest cost. moves lists the
    candidates as (dx, dy) from where the footprint is; cost(dx, dy, pads)
    prices one, pads being the footprint's [(number, x, y)] there; turns
    lists the orientations to try, the footprint's own when left out; gap
    is what the footprint keeps to every other part; closed lists the
    rectangles the footprint may not enter."""
    outline = board_outline(board)
    others = [keep_out(other) for other in board.GetFootprints()
              if other.GetReference() != footprint.GetReference()]
    start = footprint.GetPosition()
    # A tie is broken by the place itself, not by the order the candidates came
    # in: the first is the place nearest the top left corner of the board, and
    # the angle nearest the one the footprint is drawn at. Otherwise the same
    # part in the same surroundings would land somewhere else when it was moved
    # here from a different place.
    best = None
    for turn in turns or (footprint.GetOrientationDegrees(),):
        facing = abs((turn + 180) % 360 - 180)
        footprint.SetOrientationDegrees(turn)
        box = keep_out(footprint)
        pads = [(pad.GetNumber(), pad.GetPosition().x, pad.GetPosition().y) for pad in footprint.Pads()]
        for dx, dy in moves:
            price = cost(dx, dy, [(number, x + dx, y + dy) for number, x, y in pads])
            if best is not None and price > best[0][0]:
                continue
            moved = (box[LEFT] + dx, box[TOP] + dy, box[RIGHT] + dx, box[BOTTOM] + dy)
            if (on_board(moved, outline, open_edge) and not any(nearer_than(moved, other, gap) for other in others)
                    and not any(nearer_than(moved, area, 0) for area in closed)):
                key = (price, facing, moved[TOP], moved[LEFT])
                if best is None or key < best[0]:
                    best = (key, turn, dx, dy)
    if not best:
        raise NoFreePlace(footprint.GetReference())
    footprint.SetOrientationDegrees(best[1])
    footprint.SetPosition(pcbnew.VECTOR2I(start.x + best[2], start.y + best[3]))


def displacement(dx, dy, pads):
    return math.hypot(dx, dy)


def beside_offset(rule, edge):
    """From a part to the one a rule of circuit/fixed_positions.toml puts
    beside it: the rule's pitch along the edge, to the side the rule names
    as a person facing that edge from outside the board sees it."""
    pitch = pcbnew.FromMM(rule["pitch_mm"])
    step = -pitch if (rule["side"] == "left") == (edge in (BOTTOM, LEFT)) else pitch
    return pcbnew.VECTOR2I(step, 0) if edge in (TOP, BOTTOM) else pcbnew.VECTOR2I(0, step)


def near_moves(footprint, reach, rings=3):
    """The places worth trying for a part, as (dx, dy) from where it is:
    each that puts one of its pads on one of the pads it connects to, and
    the ones a step or two around that, out to rings. The square of places
    NEARBY covers gives the same answer for a part whose pads are wanted on
    their connections, at many times the cost of looking where they meet."""
    moves = set()
    for pad in footprint.Pads():
        here = pad.GetPosition()
        for target in reach.get(pad.GetNumber(), ()):
            across, up = target.x - here.x, target.y - here.y
            for ring in range(rings + 1):
                for along in range(-ring, ring + 1):
                    for other in range(-(ring - abs(along)), ring - abs(along) + 1):
                        moves.add((across + along * GRID, up + other * GRID))
    return sorted(moves)


def settle_at_its_connections(board, footprint, reach, gap=COURTYARD_GAP, moves=None, closed=()):
    """Move the footprint to the free place where its pads are nearest to the
    pads they connect to, turned whichever way brings them nearest. reach
    holds, for each of its pads by number, the places of those pads; gap is
    what the footprint keeps to every other part; moves lists the places
    tried, as (dx, dy) from where the footprint is, those near its
    connections when left out; closed lists the rectangles the footprint may
    not enter."""
    targets = [target for group in reach.values() for target in group]
    footprint.SetPosition(pcbnew.VECTOR2I(sum(target.x for target in targets) // len(targets),
                                          sum(target.y for target in targets) // len(targets)))

    def distance_to_reach(dx, dy, pads):
        return sum(min(math.hypot(x - target.x, y - target.y) for target in reach[number])
                   for number, x, y in pads if number in reach)

    settle(board, footprint, distance_to_reach, near_moves(footprint, reach) if moves is None else moves,
           turns=QUARTER_TURNS, gap=gap, closed=closed)


def build_skeleton(netlist_path, board_path):
    """A board with every part of the netlist on it and every pad on its net,
    the parts spread out and the fixed ones on their lines: what a run beside
    the project file reads, so that the nets come back with the classes the
    circuit gives them. A board made in this process keeps the classes of a
    process that never read the project, and a net with no pad on it does not
    survive the file."""
    parts, nets, _ = read_circuit(netlist_path)
    fixed = tomllib.load(open(FIXED_POSITIONS, "rb"))
    net_of_pad = {pad: name for name, pads in nets.items() for pad in pads}
    board = pcbnew.NewBoard(board_path)
    draw_nominal_outline(board)
    for name in nets:
        board.Add(pcbnew.NETINFO_ITEM(board, name))
    footprints = {}
    for designator in sorted(parts):
        footprint = load_footprint(parts[designator]["footprint"])
        footprint.SetFPIDAsString(parts[designator]["footprint"])
        footprint.SetReference(designator)
        board.Add(footprint)
        footprints[designator] = footprint
        for pad in footprint.Pads():
            name = net_of_pad.get((designator, pad.GetNumber()))
            if name:
                pad.SetNet(board.FindNet(name))
    # A part at an edge on its line, each further along its edge than the one
    # before, the others in a row each: nothing is where another part's place
    # has to be found.
    along = collections.Counter({LEFT: pcbnew.FromMM(10.0), TOP: pcbnew.FromMM(10.0),
                                 RIGHT: pcbnew.FromMM(10.0), BOTTOM: pcbnew.FromMM(10.0)})
    loose = 0
    nominal = pcbnew.FromMM(NOMINAL_MM)
    for designator in sorted(footprints):
        footprint = footprints[designator]
        rule = fixed.get(designator, {})
        if "edge" in rule and "edge_line_mm" in rule:
            edge = EDGES[rule["edge"]]
            if "faces" in rule:
                turn_to_face(footprint, edge, rule["faces"])
            inset = pcbnew.FromMM(rule["edge_line_mm"])
            footprint.SetPosition({
                LEFT: pcbnew.VECTOR2I(inset, along[edge]),
                TOP: pcbnew.VECTOR2I(along[edge], inset),
                RIGHT: pcbnew.VECTOR2I(nominal - inset, along[edge]),
                BOTTOM: pcbnew.VECTOR2I(along[edge], nominal - inset),
            }[edge])
            box = keep_out(footprint)
            if edge in (LEFT, RIGHT):
                footprint.Move(pcbnew.VECTOR2I(0, along[edge] - box[TOP]))
                along[edge] = box[BOTTOM] + (along[edge] - box[TOP]) + pcbnew.FromMM(10.0)
            else:
                footprint.Move(pcbnew.VECTOR2I(along[edge] - box[LEFT], 0))
                along[edge] = box[RIGHT] + (along[edge] - box[LEFT]) + pcbnew.FromMM(10.0)
        else:
            # Well clear of the edges, where the fixed parts are, and of each
            # other: a part with no place of its own must not take one.
            footprint.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(NOMINAL_MM / 2 + 18.0 * (loose % 8)),
                                                  pcbnew.FromMM(40.0 + 18.0 * (loose // 8))))
            loose += 1
    pcbnew.SaveBoard(board_path, board, True)


def main(netlist_path, net_classes_path, board_path):
    parts, nets, class_of_net = read_circuit(netlist_path)
    net_of_pad = {pad: name for name, pads in nets.items() for pad in pads}
    fixed = tomllib.load(open(FIXED_POSITIONS, "rb"))
    layers = tomllib.load(open(LAYERS, "rb"))["layer"]
    antennas = tomllib.load(open(ANTENNAS, "rb"))["antenna"]
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
    clearances = antenna_clearances(board, antennas)
    draw_antenna_clearances(board, clearances)
    nets_with_pads = {pad.GetNetname() for footprint in board.GetFootprints() for pad in footprint.Pads()}
    stale_tracks = [track for track in board.GetTracks() if track.GetNetname() not in nets_with_pads]
    for track in stale_tracks:
        board.Delete(track)

    def followers(designator):
        """The parts that connect to nothing but this part, the nets of the
        fills aside: a socket's pull-down resistors."""
        fill_nets = {layer["fill"] for layer in layers}
        parts_of_net = [{part for part, _ in pads} for name, pads in nets.items() if name not in fill_nets]
        found = []
        for other in sorted(set(parts) - set(fixed)):
            connected = set().union(*(joined for joined in parts_of_net if other in joined)) - {other}
            if connected == {designator}:
                found.append(board.FindFootprintByReference(other))
        return found

    # The parts whose place is stated. What connects to nothing but such a part moves with it.
    waiting = {footprint.GetReference() for footprint in new}
    open_edge_of = {}
    for designator, rule in fixed.items():
        footprint = board.FindFootprintByReference(designator)
        if "edge" in rule and "faces" in rule:
            turn_to_face(footprint, EDGES[rule["edge"]], rule["faces"])
        start = footprint.GetPosition()
        slides = range(-2 * REACH, 2 * REACH + 1, EDGE_STEP)
        if "edge" in rule:
            open_edge_of[designator] = EDGES[rule["edge"]]
            if "edge_line_mm" not in rule:
                continue    # placed by eye: it stays where it is drawn
            inset = pcbnew.FromMM(rule["edge_line_mm"])
            along = start
            if "near" in rule:
                along = start + middle([pad_named(board, name).GetPosition() for name in rule["near"]]) - pad_centre(footprint)
            footprint.SetPosition({
                LEFT: pcbnew.VECTOR2I(outline[LEFT] + inset, along.y),
                TOP: pcbnew.VECTOR2I(along.x, outline[TOP] + inset),
                RIGHT: pcbnew.VECTOR2I(outline[RIGHT] - inset, along.y),
                BOTTOM: pcbnew.VECTOR2I(along.x, outline[BOTTOM] - inset),
            }[open_edge_of[designator]])
        else:
            neighbour = board.FindFootprintByReference(rule["beside"])
            open_edge_of[designator] = open_edge_of[rule["beside"]]
            offset = beside_offset(rule, open_edge_of[designator])
            footprint.SetOrientationDegrees(neighbour.GetOrientationDegrees())
            footprint.SetPosition(neighbour.GetPosition() + offset)
            # The pitch is the least: further from its neighbour, never nearer.
            slides = range(0, 2 * REACH + 1, EDGE_STEP) if offset.x + offset.y > 0 else range(0, -2 * REACH - 1, -EDGE_STEP)
        along_x = open_edge_of[designator] in (TOP, BOTTOM)
        settle(board, footprint, displacement, [(s, 0) if along_x else (0, s) for s in slides],
               open_edge=open_edge_of[designator], closed=closed_to(footprint, clearances, class_of_net))
        waiting.discard(designator)
        moved_by = footprint.GetPosition() - start
        if moved_by.x or moved_by.y:
            print("moved  ", describe(footprint))
            for follower in followers(designator):
                follower.SetPosition(follower.GetPosition() + moved_by)
                settle(board, follower, displacement, NEARBY, closed=closed_to(follower, clearances, class_of_net))
                print("moved  ", describe(follower))

    # A swapped part that now enters a neighbour's courtyard moves the least it can.
    for footprint in swapped:
        if footprint.GetReference() not in fixed:
            settle(board, footprint, displacement, NEARBY, closed=closed_to(footprint, clearances, class_of_net))
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
            settle_at_its_connections(board, footprint, reach, closed=closed_to(footprint, clearances, class_of_net))
            waiting.discard(designator)
        print("added  ", describe(footprint))

    # The third argument keeps KiCad from rewriting the project file with the board.
    pcbnew.SaveBoard(board_path, board, True)
    print(f"{len(stale_tracks)} tracks removed with their nets; "
          f"{len(list(board.GetFootprints()))} parts, {len(nets)} nets, "
          f"{len(class_of_net)} of them in {len(set(class_of_net.values()))} classes besides Default; "
          f"{len(layers)} copper layers, their fills {'made anew' if new_fills else 'as they were'}; "
          f"{len(board.Zones())} zones on the board as it is saved")


if __name__ == "__main__":
    if len(sys.argv) not in (4, 5):
        sys.exit(__doc__)
    netlist, classes, board_file = sys.argv[1:4]
    if len(sys.argv) == 5:
        # fresh: the board comes from the circuit and the rule files. The
        # skeleton is written here and read by a run of this script in a new
        # process, which is what brings the nets back with their classes.
        _, _, class_of_net = read_circuit(netlist)
        write_net_classes(os.path.splitext(board_file)[0] + ".kicad_pro",
                          json.load(open(classes, encoding="utf-8")), class_of_net)
        build_skeleton(netlist, board_file)
        os.execv(sys.executable, [sys.executable, os.path.abspath(__file__), netlist, classes, board_file])
    try:
        main(netlist, classes, board_file)
    except NoFreePlace as part:
        sys.exit(f"no free place for {part}")
