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
of R15), so that what has come loose reads off the first lines. Under
each piece but the largest is where it is split from the rest of its net:
the place where its tracks, vias and pads come nearest to those of the
other pieces, as the width of that gap and the pins the copper reaches
first from either side of it; a piece that the board has on another net
than its neighbour is said to be that. A pin of the netlist that has no
pad on the board is named under its net.

Prints the count last. The exit status is 1 when a net is not joined.

Runs under the system's Python, which has KiCad's pcbnew module.
"""
import collections
import math
import re
import sys

import pcbnew

from netlist_summary import read_netlist


def unique_id(item):
    return item.m_Uuid.AsString()


def pin_name(pin):
    return ".".join(pin)


def in_reading_order(name):
    """Sorts R3.1 ahead of R11.1."""
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", name)]


def pieces_of(connectivity, pads):
    """The copper of the pads, grouped by what it joins: a list of pieces,
    each {unique id: item} of the pads, tracks, vias and fills in it."""
    placed, pieces = set(), []
    for pad in pads:
        if unique_id(pad) in placed:
            continue
        piece = {unique_id(item): item.Cast() for item in connectivity.GetConnectedItems(pad)}
        piece[unique_id(pad)] = pad
        placed.update(piece)
        pieces.append(piece)
    return pieces


def ends(item):
    """The points at which copper joins the item: the two ends of a track,
    the middle of a via or a pad. A fill has none: a gap is measured
    between tracks, vias and pads."""
    kind = item.GetClass()
    if kind in ("PCB_TRACK", "PCB_ARC"):
        return [item.GetStart(), item.GetEnd()]
    if kind in ("PCB_VIA", "PAD"):
        return [item.GetPosition()]
    return []


def nearest_approach(piece, others):
    """Where the piece comes nearest to the other pieces of its net, as
    (distance, item of the piece, item of another piece)."""
    return min(((math.hypot(mine.x - theirs.x, mine.y - theirs.y), item, other)
                for item in piece.values() for mine in ends(item)
                for other_piece in others for other in other_piece.values() for theirs in ends(other)),
               key=lambda approach: approach[0])


def first_pads(connectivity, item):
    """The pads the copper reaches first from the item, going from track
    to track."""
    if item.GetClass() == "PAD":
        return [item]
    seen, reached = {unique_id(item)}, [item]
    while reached:
        pads = {unique_id(pad): pad for track in reached for pad in connectivity.GetConnectedPads(track)}
        if pads:
            return list(pads.values())
        further = [track for near in reached for track in connectivity.GetConnectedTracks(near)
                   if unique_id(track) not in seen]
        seen.update(unique_id(track) for track in further)
        reached = further
    return []


def split(connectivity, piece, others, pins_in):
    """In words, what keeps the piece from the other pieces of its net,
    seen from where it comes nearest to them. pins_in names the pins that
    the pads among some items are."""
    gap, item, other = nearest_approach(piece, others)
    if item.GetNetname() != other.GetNetname():
        return (f"on the board this piece is on the net {item.GetNetname() or '(none)'}, "
                f"the copper nearest to it on {other.GetNetname() or '(none)'}")
    between = (f"split from the rest between {' '.join(pins_in(first_pads(connectivity, item)))}"
               f" and {' '.join(pins_in(first_pads(connectivity, other)))}")
    if gap == 0:
        return between + ", one above the other on different layers with nothing joining the layers"
    return between + f", a gap of {pcbnew.ToMM(gap):.2f} mm"


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
                pin_of[unique_id(pad)] = pin

    def pins_in(items):
        """The names of the pins that the pads among the items are."""
        return sorted({pin_name(pin_of[unique_id(item)]) for item in items if item.GetClass() == "PAD"},
                      key=in_reading_order)

    connected_nets = {name: pins for name, pins in nets.items() if len(pins) > 1}
    not_joined = 0
    for name in sorted(connected_nets):
        pins = connected_nets[name]
        without_pad = sorted((pin_name(pin) for pin in pins if pin not in pads_of_pin), key=in_reading_order)
        pieces = pieces_of(connectivity, [pad for pin in pins for pad in pads_of_pin.get(pin, [])])
        pieces.sort(key=lambda piece: (len(pins_in(piece.values())), pins_in(piece.values())))
        if len(pieces) > 1 or without_pad:
            not_joined += 1
            print(f"{name}: its {len(pins)} pins are in {len(pieces)} pieces on the board")
            for piece in pieces:
                print("    " + " ".join(pins_in(piece.values())))
                if piece is not pieces[-1]:
                    print("        " + split(connectivity, piece, [rest for rest in pieces if rest is not piece], pins_in))
            if without_pad:
                print("    no such pad on the board: " + " ".join(without_pad))
    print(f"{len(connected_nets)} nets of more than one pin: {not_joined} not joined by the board's copper")
    sys.exit(1 if not_joined else 0)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
