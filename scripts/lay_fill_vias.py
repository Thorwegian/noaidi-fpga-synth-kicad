#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""lay_fill_vias.py -- give each surface-mount pad on a fill's net its via, ahead of the autorouter.

    scripts/lay_fill_vias.py <board>

A surface-mount pad on the net of a fill that is on another layer than the
pad needs a via beside it. The router is given such a pad without a net
(scripts/route_board.py) and is free to lay its tracks all around it, so a
via that is looked for after the router has run may find no place. This
script lays the via and the short track to it first, on a board that has
no other tracks than the differential pairs (scripts/lay_pairs.py), and
locks them: the router is given locked copper as wires it has to go
around.

The script removes the board's tracks and vias but the locked ones, and
the locked ones on a fill's net with them, which are its own from the run
before. Then each surface-mount pad whose net has a fill on another layer
gets a track to a via, the pads in the order of their names: a via of its
net that is near and can be reached, or else a new one at the nearest
place that keeps its distance from other copper on every layer
(scripts/join_fills.py's Joiner, which joins what is left after the
router). A pad that finds no place is named; the placement leaves no room
for a via beside it, and KiCad's DRC after the router is the verdict.

Runs under the system's Python, which has KiCad's pcbnew module.
"""
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from join_fills import REACH, Joiner  # noqa: E402


def main(board_path):
    board = pcbnew.LoadBoard(board_path)
    fill_layers = {}
    for fill in board.Zones():
        if not fill.GetIsRuleArea():
            fill_layers.setdefault(fill.GetNetname(), set()).add(fill.GetLayerSet().Seq()[0])
    for track in list(board.GetTracks()):
        if not track.IsLocked() or track.GetNetname() in fill_layers:
            board.Delete(track)

    joiner = Joiner(board)

    def name(pad):
        return f"{pad.GetParentFootprint().GetReference()} pad {pad.GetNumber()} [{pad.GetNetname()}]"

    pads = [pad for pad in joiner.pads
            if not pad.HasHole() and fill_layers.get(pad.GetNetname(), set()) - {pad.GetPrincipalLayer()}]
    shared, joined = 0, set()
    for pad in sorted(pads, key=name):
        # A socket has pads of one net that lie on top of each other: one track joins them all.
        place = (pad.GetNetname(), pad.GetPosition().x, pad.GetPosition().y, pad.GetPrincipalLayer())
        if place in joined:
            continue
        joined.add(place)
        how = joiner.to_via(pad)
        if how is None:
            print(f"no via: {name(pad)}, no clear place for one within {pcbnew.ToMM(REACH):g} mm")
        elif how.startswith("a track to the via"):
            shared += 1
    vias = 0
    for track in board.GetTracks():
        if track.GetNetname() in fill_layers:
            track.SetLocked(True)
            vias += track.Type() == pcbnew.PCB_VIA_T
    # The third argument keeps KiCad from rewriting the project file with the board.
    pcbnew.SaveBoard(board_path, board, True)
    print(f"{len(pads)} surface-mount pads on the nets of fills: {vias} vias laid for them, {shared} of the pads on a via of another")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
