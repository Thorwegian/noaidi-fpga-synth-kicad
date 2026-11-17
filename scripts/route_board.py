#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""route_board.py -- the board's side of an autorouter run.

    scripts/route_board.py export <board> <design.dsn>
    scripts/route_board.py import <board> <session.ses>
    scripts/route_board.py widen <board>
    scripts/route_board.py clear <board>

clear removes every track and via from the board, so that a run starts from
its pads and the copper the run before laid does not carry into it.

export writes the board for the router as a Specctra design. The board file
is not changed; what the router is given differs from it in four ways:

  - no tracks and vias but the locked ones, which the router is told to
    leave where they are (scripts/lay_pairs.py lays the differential pairs
    and locks them), each straight stretch a wire of its own: the router
    lays all of the other tracks;
  - no fills, and the pads of the fills' nets without a net: the router
    lays the signals only and keeps its distance from those pads. Given a
    fill as a plane it leaves connections open, signals among them, and
    given the fills' nets to route it draws them a second time as tracks
    that cut the fills up;
  - an outline drawn in by the board's copper-to-edge clearance, which a
    Specctra design has no rule for.

The structure rule states the tightest width and clearance of the net
classes, where KiCad writes the default class's two figures; a net's class
carries its own. The vias the router may use are the classes' ones, and it
has no rule for an annular ring, so a via padded to the fab's ring is the
only way that limit reaches it. The fab's floors are the limits KiCad's DRC
holds the routed board to.

export prints, for the router's option --router.layers.routable, which of
the copper layers take tracks, from the front to the back: true for a layer
of the type signal, false for one of the type power.

import removes the board's tracks and vias but the locked ones, reads the
router's session in their place, fills the board's fills and saves the
board. A via gets the
hole its net class gives a via of its diameter: the session names the via,
and KiCad's import takes the hole from the net's class whichever via was
used. scripts/join_fills.py then joins the pads the fills do not reach.

widen runs after those joins, which need room a wider track would take: a
track the router made narrower than its net class's width is widened to
that width where the wider copper still clears every other net on its
layer, and the ones that cannot be are printed with the pad beside them.

scripts/route.sh runs the four around the router. Runs under the system's
Python, which has KiCad's pcbnew module.
"""
import re
import sys

import pcbnew

# A wire of a Specctra design, on one line: up to its width, the coordinates
# of its corners, and what follows them. A coordinate that is not a whole
# micrometre is written with decimals.
WIRE = re.compile(r"^(\s*\(wire \(path \S+ \d+)((?:\s+-?\d+(?:\.\d+)?)+)(\).*)$")
# A via that is on the board, on one line: its padstack, where it is, its net.
VIA = re.compile(r"^\s*\(via \S+\s+-?\d+(?:\.\d+)?\s+-?\d+(?:\.\d+)?\s+\(net ")


def remove_tracks(board):
    """Remove the tracks and vias the router lays: all but the locked ones."""
    for track in list(board.GetTracks()):
        if not track.IsLocked():
            board.Delete(track)


def one_wire_per_stretch(specctra_path):
    """Write each wire of the design as one wire per straight stretch, the
    wires and the vias in the order of their text. KiCad writes tracks that
    follow on each other as one wire through all of their corners, and the
    router takes two wires for joined only where their ends meet. A track
    that ends on such a corner, as a branch of a pair does, the router then
    takes for unjoined: it holds the board for unfinished and leaves out
    its optimiser. The order KiCad writes the wires and the vias in differs
    from one save of the board to the next, and the router's result follows
    its input."""
    with open(specctra_path, encoding="utf-8") as file:
        lines = file.readlines()
    stretches = []
    for line in lines:
        wire = WIRE.match(line)
        if wire:
            coordinates = wire.group(2).split()
            corners = list(zip(coordinates[::2], coordinates[1::2]))
            stretches += [f"{wire.group(1)}  {start_x} {start_y}  {end_x} {end_y}{wire.group(3)}\n"
                          for (start_x, start_y), (end_x, end_y) in zip(corners, corners[1:])]
    vias = [line for line in lines if VIA.match(line)]
    first = next((index for index, line in enumerate(lines) if WIRE.match(line) or VIA.match(line)), len(lines))
    with open(specctra_path, "w", encoding="utf-8") as file:
        file.writelines(lines[:first] + sorted(stretches) + sorted(vias)
                        + [line for line in lines[first:] if not WIRE.match(line) and not VIA.match(line)])


def state_the_design_floors(specctra_path, board):
    """Write the tightest width and clearance of the board's net classes into
    the design's structure rule, which is the one place the format has for a
    figure that applies to every object. KiCad writes the default class's two
    figures there; the tightest of all of them is the floor the router is to
    work to, and the fab's own floors are what KiCad's DRC checks the result
    against, not what the router is asked to route at."""
    classes = list(board.GetAllNetClasses().values())
    width = round(min(net_class.GetTrackWidth() for net_class in classes) / 1000)
    clearance = round(min(net_class.GetClearance() for net_class in classes) / 1000)
    with open(specctra_path, encoding="utf-8") as file:
        text = file.read()
    start = text.find("(structure")
    end = text.find("(placement")
    block = text[start:end]
    block = re.sub(r"\(width \d+\)", f"(width {width})", block, count=1)
    block = re.sub(r"\(clearance \d+\)(?!\s*\(type)", f"(clearance {clearance})", block, count=1)
    with open(specctra_path, "w", encoding="utf-8") as file:
        file.write(text[:start] + block + text[end:])


def draw_outline_in(board):
    """Make the board's outline smaller by the copper-to-edge clearance on
    every side."""
    outline = [drawing for drawing in board.GetDrawings() if drawing.GetLayer() == pcbnew.Edge_Cuts]
    if len(outline) != 1 or outline[0].GetShape() != pcbnew.SHAPE_T_RECTANGLE:
        sys.exit("only an outline that is one rectangle is handled")
    rectangle = outline[0]
    clearance = board.GetDesignSettings().m_CopperEdgeClearance
    start, end = rectangle.GetStart(), rectangle.GetEnd()
    left, right = sorted((start.x, end.x))
    top, bottom = sorted((start.y, end.y))
    rectangle.SetStart(pcbnew.VECTOR2I(left + clearance, top + clearance))
    rectangle.SetEnd(pcbnew.VECTOR2I(right - clearance, bottom - clearance))


def give_vias_their_holes(board):
    hole_of_diameter = {net_class.GetViaDiameter(): net_class.GetViaDrill()
                        for net_class in board.GetAllNetClasses().values()}
    for track in board.GetTracks():
        if track.Type() == pcbnew.PCB_VIA_T:
            track.SetDrill(hole_of_diameter[track.GetWidth(pcbnew.F_Cu)])


def widen_to_class(board):
    """Widen each track to its net class's width, then put back the width of
    every widened track that no longer clears its neighbours, until nothing
    changes: a track widened after its neighbour was checked cannot leave
    the two too near each other.

    Returns the tracks that are still narrower than their class."""
    settings = board.GetDesignSettings().m_NetSettings
    floor = board.GetDesignSettings().m_TrackMinWidth
    copper = list(board.GetTracks()) + [pad for footprint in board.GetFootprints()
                                        for pad in footprint.Pads()]

    def target_of(track):
        return max(floor, settings.GetEffectiveNetClass(track.GetNetname()).GetTrackWidth())

    # A neighbour that is too near does not intersect the track's own box: the
    # box is grown by the widest clearance any class asks for before the search.
    reach = int(max(net_class.GetClearance()
                    for net_class in board.GetAllNetClasses().values()))

    def clashes(track):
        net_class = settings.GetEffectiveNetClass(track.GetNetname())
        shape = track.GetEffectiveShape(track.GetLayer())
        box = track.GetBoundingBox()
        box.Inflate(reach)
        for other in copper:
            if other is track or other.GetNetname() == track.GetNetname():
                continue
            if not other.GetBoundingBox().Intersects(box):
                continue
            other_layer = track.GetLayer()
            if other.Type() != pcbnew.PCB_VIA_T:
                if other.GetLayer() != other_layer:
                    continue
                other_layer = other.GetLayer()
            gap = max(net_class.GetClearance(),
                      settings.GetEffectiveNetClass(other.GetNetname()).GetClearance())
            if shape.Collide(other.GetEffectiveShape(other_layer), gap):
                return True
        return False

    was = []
    for track in board.GetTracks():
        if track.Type() == pcbnew.PCB_VIA_T or track.GetWidth() >= target_of(track):
            continue
        was.append((track, track.GetWidth()))
        track.SetWidth(target_of(track))
    changed = True
    while changed:
        changed = False
        for track, width in was:
            if track.GetWidth() > width and clashes(track):
                track.SetWidth(width)
                changed = True
    return [track for track, width in was if track.GetWidth() < target_of(track)]


def main(action, board_path, specctra_path=None):
    board = pcbnew.LoadBoard(board_path)
    if action == "clear":
        for track in list(board.GetTracks()):
            board.Delete(track)
        # The third argument keeps KiCad from rewriting the project file with the board.
        pcbnew.SaveBoard(board_path, board, True)
        print("every track and via removed")
    elif action == "export":
        remove_tracks(board)
        fill_nets = {fill.GetNetname() for fill in board.Zones() if not fill.GetIsRuleArea()}
        for fill in list(board.Zones()):
            board.Delete(fill)
        for footprint in board.GetFootprints():
            for pad in footprint.Pads():
                if pad.GetNetname() in fill_nets:
                    pad.SetNetCode(0)
        draw_outline_in(board)
        if not pcbnew.ExportSpecctraDSN(board, specctra_path):
            sys.exit(f"could not write {specctra_path}")
        state_the_design_floors(specctra_path, board)
        one_wire_per_stretch(specctra_path)
        print(",".join("true" if board.GetLayerType(layer) == pcbnew.LT_SIGNAL else "false"
                       for layer in board.GetEnabledLayers().CuStack()))
    elif action == "import":
        remove_tracks(board)
        if not pcbnew.ImportSpecctraSES(board, specctra_path):
            sys.exit(f"could not read {specctra_path}")
        give_vias_their_holes(board)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        # The third argument keeps KiCad from rewriting the project file with the board.
        pcbnew.SaveBoard(board_path, board, True)
        tracks = list(board.GetTracks())
        vias = sum(1 for track in tracks if track.Type() == pcbnew.PCB_VIA_T)
        length = sum(track.GetLength() for track in tracks if track.Type() != pcbnew.PCB_VIA_T)
        print(f"{len(tracks) - vias} track segments, {vias} vias, {pcbnew.ToMM(length):.0f} mm of track")
    elif action == "widen":
        narrow = widen_to_class(board)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pcbnew.SaveBoard(board_path, board, True)
        print(f"{len(narrow)} segments stay narrower than their net class")
        settings = board.GetDesignSettings().m_NetSettings
        for track in narrow:
            middle = track.GetStart() + (track.GetEnd() - track.GetStart()) / 2
            beside = min((((pad.GetPosition() - middle).EuclideanNorm(), f"{pad.GetParentFootprint().GetReference()} pad {pad.GetNumber()}")
                          for footprint in board.GetFootprints() for pad in footprint.Pads()), default=None)
            if beside:
                print(f"  {track.GetNetname()}: {pcbnew.ToMM(track.GetWidth()):.2f} mm where the class is "
                      f"{pcbnew.ToMM(settings.GetEffectiveNetClass(track.GetNetname()).GetTrackWidth()):.2f}, "
                      f"beside {beside[1]}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
