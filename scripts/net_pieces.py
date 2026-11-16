#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""net_pieces.py -- does the board's copper join the pins of each net of the netlist?

    scripts/net_pieces.py <netlist> <board>

scripts/netlist_summary.py compares the netlist with the net each pad of
the board is assigned to. This compares it with the copper: for every net
of the netlist, the pins that the board's tracks, vias and fills (as the
board file stores them) join to one another.

A net whose pins the copper leaves in more than one piece is printed with
its pieces, the smallest first, each as the pins it holds (R15.1 is pin 1
of R15), so that what has come loose reads off the first lines. A pin of
the netlist that has no pad on the board is named under its net.

Prints the count last. The exit status is 1 when a net is not joined.

Runs under the system's Python, which has KiCad's pcbnew module.
"""
import collections
import re
import sys

import pcbnew

from netlist_summary import read_netlist


def pin_name(pin):
    return ".".join(pin)


def in_reading_order(name):
    """Sorts R3.1 ahead of R11.1."""
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", name)]


def pieces_of(connectivity, pads, pin_of):
    """The pads grouped by the copper that joins them: a list of pieces,
    each the names of the pins its pads are. pin_of gives the pin of every
    pad of the board by the pad's unique id."""
    placed, pieces = set(), []
    for pad in pads:
        if pad.m_Uuid.AsString() in placed:
            continue
        joined = {item.m_Uuid.AsString() for item in connectivity.GetConnectedItems(pad) if item.GetClass() == "PAD"}
        joined.add(pad.m_Uuid.AsString())
        placed.update(joined)
        pieces.append(sorted({pin_name(pin_of[pad_id]) for pad_id in joined}, key=in_reading_order))
    return sorted(pieces, key=lambda piece: (len(piece), piece))


def main(netlist_path, board_path):
    _, nets = read_netlist(netlist_path)
    board = pcbnew.LoadBoard(board_path)
    connectivity = board.GetConnectivity()
    pads_of_pin, pin_of = collections.defaultdict(list), {}
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if pad.IsOnCopperLayer():
                pin = (footprint.GetReference(), pad.GetNumber())
                pads_of_pin[pin].append(pad)
                pin_of[pad.m_Uuid.AsString()] = pin

    connected_nets = {name: pins for name, pins in nets.items() if len(pins) > 1}
    not_joined = 0
    for name in sorted(connected_nets):
        pins = connected_nets[name]
        without_pad = sorted((pin_name(pin) for pin in pins if pin not in pads_of_pin), key=in_reading_order)
        pieces = pieces_of(connectivity, [pad for pin in pins for pad in pads_of_pin.get(pin, [])], pin_of)
        if len(pieces) > 1 or without_pad:
            not_joined += 1
            print(f"{name}: its {len(pins)} pins are in {len(pieces)} pieces on the board")
            for piece in pieces:
                print("    " + " ".join(piece))
            if without_pad:
                print("    no such pad on the board: " + " ".join(without_pad))
    print(f"{len(connected_nets)} nets of more than one pin: {not_joined} not joined by the board's copper")
    sys.exit(1 if not_joined else 0)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
