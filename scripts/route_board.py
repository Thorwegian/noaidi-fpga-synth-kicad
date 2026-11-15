#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""route_board.py -- the board's side of an autorouter run.

    scripts/route_board.py export <board> <design.dsn>
    scripts/route_board.py import <board> <session.ses>

export writes the board for the router as a Specctra design. The board file
is not changed; what the router is given differs from it in four ways:

  - no tracks and vias but the locked ones, which the router is told to
    leave where they are (scripts/lay_pairs.py lays the differential pairs
    and scripts/lay_fill_vias.py the vias of the surface-mount pads on the
    fills' nets, and both lock what they lay), each straight stretch a wire
    of its own: the router lays all of the other tracks;
  - no fills, and the pads of the fills' nets without a net: the router
    lays the signals only and keeps its distance from those pads. Given a
    fill as a plane it leaves connections open, signals among them, and
    given the fills' nets to route it draws them a second time as tracks
    that cut the fills up;
  - an outline drawn in by the board's copper-to-edge clearance, which a
    Specctra design has no rule for.

export prints, for the router's option --router.layers.routable, which of
the copper layers take tracks, from the front to the back: true for a layer
of the type signal, false for one of the type power.

import removes the board's tracks and vias but the locked ones, reads the
router's session in their place, fills the board's fills and saves the
board. A via gets the
hole its net class gives a via of its diameter: the session names the via,
and KiCad's import takes the hole from the net's class whichever via was
used. A track the router made narrower than the board's minimum is widened
to it. scripts/join_fills.py then joins the pads the fills do not reach.

scripts/route.sh runs the two around the router. Runs under the system's
Python, which has KiCad's pcbnew module.
"""
import re
import sys

import pcbnew

# A wire of a Specctra design, on one line: up to its width, the coordinates
# of its corners, and what follows them.
WIRE = re.compile(r"^(\s*\(wire \(path \S+ \d+)((?:\s+-?\d+)+)(\).*)$")


def remove_tracks(board):
    """Remove the tracks and vias the router lays: all but the locked ones."""
    for track in list(board.GetTracks()):
        if not track.IsLocked():
            board.Delete(track)


def one_wire_per_stretch(specctra_path):
    """Write each wire of the design as one wire per straight stretch, the
    wires in the order of their text. KiCad writes tracks that follow on
    each other as one wire through all of their corners, and the router
    takes two wires for joined only where their ends meet. A track that
    ends on such a corner, as a branch of a pair does, the router then
    takes for unjoined: it holds the board for unfinished and leaves out
    its optimiser. The order KiCad writes the wires in differs from one
    save of the board to the next, and the router's result follows its
    input."""
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
    first_wire = next((index for index, line in enumerate(lines) if WIRE.match(line)), len(lines))
    with open(specctra_path, "w", encoding="utf-8") as file:
        file.writelines(lines[:first_wire] + sorted(stretches)
                        + [line for line in lines[first_wire:] if not WIRE.match(line)])


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


def widen_to_minimum(board):
    """The router narrows a track where the going is tight, and by more than
    the board allows. Returns how many segments were widened."""
    minimum = board.GetDesignSettings().m_TrackMinWidth
    narrow = [track for track in board.GetTracks()
              if track.Type() != pcbnew.PCB_VIA_T and track.GetWidth() < minimum]
    for track in narrow:
        track.SetWidth(minimum)
    return len(narrow)


def main(action, board_path, specctra_path):
    board = pcbnew.LoadBoard(board_path)
    if action == "export":
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
        one_wire_per_stretch(specctra_path)
        print(",".join("true" if board.GetLayerType(layer) == pcbnew.LT_SIGNAL else "false"
                       for layer in board.GetEnabledLayers().CuStack()))
    elif action == "import":
        remove_tracks(board)
        if not pcbnew.ImportSpecctraSES(board, specctra_path):
            sys.exit(f"could not read {specctra_path}")
        give_vias_their_holes(board)
        widened = widen_to_minimum(board)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        # The third argument keeps KiCad from rewriting the project file with the board.
        pcbnew.SaveBoard(board_path, board, True)
        tracks = list(board.GetTracks())
        vias = sum(1 for track in tracks if track.Type() == pcbnew.PCB_VIA_T)
        length = sum(track.GetLength() for track in tracks if track.Type() != pcbnew.PCB_VIA_T)
        print(f"{len(tracks) - vias} track segments, {vias} vias, {pcbnew.ToMM(length):.0f} mm of track; "
              f"{widened} segments widened to the minimum track width")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
