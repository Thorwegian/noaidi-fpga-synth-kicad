#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""route_board.py -- the board's side of an autorouter run.

    scripts/route_board.py export <board> <design.dsn>
    scripts/route_board.py import <board> <session.ses>

export writes the board for the router as a Specctra design. The board file
is not changed; what the router is given differs from it in three ways:

  - no tracks and vias: the router lays all of the copper;
  - no copper pours: the router then draws a track to every pad, the pads of
    the poured nets among them, so that no pad depends on a pour's thermal
    spokes for its connection;
  - an outline drawn in by the board's copper-to-edge clearance, which a
    Specctra design has no rule for.

import removes the board's tracks and vias, reads the router's session in
their place, fills the pours again and saves the board. A via gets the hole
its net class gives a via of its diameter: the session names the via, and
KiCad's import takes the hole from the net's class whichever via was used.
A track the router made narrower than the board's minimum is widened to it.
The pours join through-hole pads by thermal reliefs, which is what lets a
pad be heated when it is soldered by hand, and surface-mount pads solidly.

scripts/route.sh runs the two around the router. Runs under the system's
Python, which has KiCad's pcbnew module.
"""
import sys

import pcbnew


def remove_tracks(board):
    for track in list(board.GetTracks()):
        board.Delete(track)


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
        for pour in list(board.Zones()):
            board.Delete(pour)
        draw_outline_in(board)
        if not pcbnew.ExportSpecctraDSN(board, specctra_path):
            sys.exit(f"could not write {specctra_path}")
    elif action == "import":
        remove_tracks(board)
        if not pcbnew.ImportSpecctraSES(board, specctra_path):
            sys.exit(f"could not read {specctra_path}")
        give_vias_their_holes(board)
        widened = widen_to_minimum(board)
        for pour in board.Zones():
            pour.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)
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
