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

A pin on the no-connect net has no line, as in SKiDL's own netlist.
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
    for code, net in enumerate(sorted(circuit.get_nets(), key=lambda net: str(net.name)), 1):
        classes = ",".join(reversed(net.netclasses.by_priority()))
        lines += ["    (net", f'      (code "{code}")', f"      (name {quoted(net.name)})", f"      (class {quoted(classes)})"]
        lines += [f"      (node (ref {quoted(pin.part.ref)}) (pin {quoted(pin.num)}))" for pin in sorted(net.pins, key=str)]
        lines[-1] += ")"
    lines[-1] += "))"
    with open(path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")
