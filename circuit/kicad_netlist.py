#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""kicad_netlist.py -- the netlist, as KiCad's PCB editor takes it without
proposing a change to the board.

The board is edited in KiCad, and its File > Import > Netlist is what the
circuit in text is held against: the netlist is right when that dialog,
linking footprints by reference designator, lists no change. So the netlist
states what the board's footprints hold, and nothing they do not:

  - each part's designator, value and footprint;
  - the fields the circuit gives a part, which is its LCSC number. KiCad
    compares every field of the netlist with the footprint's, and leaves a
    field that only the footprint has as it is;
  - "exclude from BOM", "exclude from position files" and "do not place",
    for a part the circuit marks so;
  - each net by its name, with its pins and its classes.

It has no sheet path and no tstamps: the footprints hold no link to a
symbol, and KiCad would write the netlist's into every one of them. It has
no pin types: KiCad copies those onto the pads without listing it. SKiDL's
own generate_netlist() writes all three, and a tag and a source line as
fields of every part.

A pin the circuit leaves unconnected, or marks as not connected, is written
as a net of its own named unconnected-(<ref>-Pad<pin>), which is what
eeschema writes for a pin that ends up alone in its net. KiCad's importer
warns about every numbered pad on copper that the netlist says nothing
about, so the netlist says something about these. A pad with no pin in the
circuit at all keeps that warning: the two DIN jacks' footprints have
MNT1 and MNT2, which the symbol Connector:DIN-5_180degree does not.
"""
from skidl import *

PROPERTIES = ("dnp", "exclude_from_bom", "exclude_from_pos_files")


def quoted(text):
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def write(path):
    circuit = default_circuit
    circuit.merge_net_names()
    circuit.check_for_empty_footprints()
    circuit.check_tags()
    lines = ['(export (version "E")', "  (design", '    (source "circuit/board.py")', '    (tool "SKiDL"))',
             "  (components"]
    for part in sorted(circuit.parts, key=lambda part: str(part.ref)):
        lines += ["    (comp", f"      (ref {quoted(part.ref)})", f"      (value {quoted(part.value)})",
                  f"      (footprint {quoted(part.footprint)})"]
        if part.fields:
            lines.append("      (fields")
            lines += [f"        (field (name {quoted(name)}) {quoted(text)})" for name, text in part.fields.items()]
            lines[-1] += ")"
        lines += [f"      (property (name {quoted(name)}))" for name in PROPERTIES if getattr(part, name, False)]
        lines[-1] += ")"
    lines[-1] += ")"
    lines.append("  (nets")
    for net in circuit.get_nets():
        net.netclasses = "Default"
    nets = [(str(net.name), ",".join(reversed(net.netclasses.by_priority())), list(net.pins))
            for net in circuit.get_nets()]
    nets += [(f"unconnected-({pin.part.ref}-Pad{pin.num})", "Default", [pin]) for pin in circuit.NC.pins]
    for code, (name, classes, pins) in enumerate(sorted(nets, key=lambda net: net[0]), 1):
        lines += ["    (net", f'      (code "{code}")', f"      (name {quoted(name)})", f"      (class {quoted(classes)})"]
        lines += [f"      (node (ref {quoted(pin.part.ref)}) (pin {quoted(pin.num)}))" for pin in sorted(pins, key=str)]
        lines[-1] += ")"
    lines[-1] += "))"
    with open(path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")
