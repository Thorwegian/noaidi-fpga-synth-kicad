#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""lay_fill_vias.py -- join each surface-mount pad on a fill's net to its fill and to the pad beside it, in the room the autorouter leaves.

    scripts/lay_fill_vias.py <board> <netlist>

The netlist is the one circuit/board.py writes (board.net).

A surface-mount pad on the net of a fill that is on another layer than the
pad needs a via beside it. The router is given such a pad without a net
(scripts/route_board.py) and lays its tracks past it, so the via goes down
where the router has left room: this script runs after scripts/route.sh has
read the router's result back.

Two pads that the placement has put side by side for each other are
joined by a track as well, pad to pad: a bypass capacitor and the supply
and ground pins it serves, whose way to each other is otherwise down a
via, through a fill and up another. Such a pad gets a track to the nearest
pad of its net on its layer, on another part of its block of the circuit
(its SubCircuit), where that pad is no further than NEAR: straight, or in
two stretches where the pads are neither in line nor at 45 degrees. The
rule goes by nets, blocks and distance; it names no kind of part.

The script removes its own copper from the run before, which is locked and
on a fill's net. Then the tracks from pad to pad are laid, and each
surface-mount pad whose net has a fill on another layer gets a track to a
via, the pads
in the order of their names: a via of its net that is near and can be
reached, or else a new one at the nearest place that keeps its distance
from other copper on every layer (scripts/join_fills.py's Joiner, which
joins what is left after the router). A pad that finds no place for a
via is named; the placement leaves no room for one beside it, and KiCad's
DRC after the router is the verdict. So is a pad whose track to the pad
beside it has no clear way.

Runs under the system's Python, which has KiCad's pcbnew module.
"""
import math
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from board_from_circuit import read_circuit  # noqa: E402
from join_fills import REACH, Joiner  # noqa: E402

NEAR = pcbnew.FromMM(6.0)   # how far apart two pads of one block on a fill's net get a track from the one to the other


def main(board_path, netlist_path):
    parts, _, _ = read_circuit(netlist_path)
    board = pcbnew.LoadBoard(board_path)
    fill_layers = {}
    for fill in board.Zones():
        if not fill.GetIsRuleArea():
            fill_layers.setdefault(fill.GetNetname(), set()).add(fill.GetLayerSet().Seq()[0])
    for track in list(board.GetTracks()):
        if track.IsLocked() and track.GetNetname() in fill_layers:
            board.Delete(track)

    joiner = Joiner(board)

    def part_of(pad):
        return pad.GetParentFootprint().GetReference()

    def name(pad):
        return f"{part_of(pad)} pad {pad.GetNumber()} [{pad.GetNetname()}]"

    def place(pad):
        return (pad.GetNetname(), pad.GetPosition().x, pad.GetPosition().y, pad.GetPrincipalLayer())

    def apart(pad, other):
        return math.hypot(pad.GetPosition().x - other.GetPosition().x, pad.GetPosition().y - other.GetPosition().y)

    pads = [pad for pad in joiner.pads
            if not pad.HasHole() and fill_layers.get(pad.GetNetname(), set()) - {pad.GetPrincipalLayer()}]
    between = set()
    for pad in sorted(pads, key=name):
        beside = sorted((apart(pad, other), name(other), other) for other in joiner.pads
                        if other.GetNetname() == pad.GetNetname() and other.IsOnLayer(pad.GetPrincipalLayer())
                        and part_of(other) != part_of(pad)
                        and parts[part_of(other)]["block"] == parts[part_of(pad)]["block"] and apart(pad, other) <= NEAR)
        if not beside or frozenset((place(pad), place(beside[0][2]))) in between:
            continue
        if joiner.join_pads(pad, beside[0][2]) is None:
            print(f"no track: {name(pad)} to {name(beside[0][2])}, {pcbnew.ToMM(beside[0][0]):.1f} mm away, no clear way")
        else:
            print(f"track: {name(pad)} to {name(beside[0][2])}, {pcbnew.ToMM(beside[0][0]):.1f} mm away")
            between.add(frozenset((place(pad), place(beside[0][2]))))
    shared, joined = 0, set()
    for pad in sorted(pads, key=name):
        # A socket has pads of one net that lie on top of each other: one track joins them all.
        if place(pad) in joined:
            continue
        joined.add(place(pad))
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
    print(f"{len(pads)} surface-mount pads on the nets of fills: {vias} vias laid for them, {shared} of the pads on a via of another; "
          f"{len(between)} tracks from a pad to the pad beside it")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
