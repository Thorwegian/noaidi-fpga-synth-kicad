#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""pin_map.py -- docs/pins.md, written from the circuit by board.py: which pin
of which module carries what, the connectors, the test points, and each
part's name in the code."""
import os
import re

from skidl import *

from designators import tag_path
from parts import REPO

MODULES = (
    ("esp32.esp", "the ESP32-S3 module",
     "An HW-678 copy of the ESP32-S3-DevKitC-1 (`docs/esp32s3_hw678.md`). The GPIO number in "
     "the name is the one the firmware uses."),
    ("tang_nano_20k.fpga", "the Tang Nano 20K",
     "The leading number in the name is the FPGA's pin number, the one the gateware's "
     "constraints file uses."),
    ("tang_nano_20k.dac", "the Adafruit PCM510x DAC module", ""),
)


def natural(text):
    return [(0, int(t)) if t.isdigit() else (1, t) for t in re.findall(r"\d+|\D+", str(text))]


def in_use(pin):
    return pin.net is not None and pin.net.name != NC.name


def label(pin):
    part = pin.part
    if len(part.pins) <= 2:
        return part.ref
    if tag_path(part) in [path for path, _, _ in MODULES]:
        return f"{part.ref}.{pin.num} ({pin.name.split('/')[0]})"
    return f"{part.ref}.{pin.num}"


def also_on_net(pin):
    others = sorted((label(p) for p in pin.net.pins if p.part is not pin.part), key=natural)
    if pin.net.drive == POWER:
        return f"supply net, {len(others)} other pin{'s' if len(others) != 1 else ''}"
    return ", ".join(others)


def pin_table(part):
    rows = ["| Pin | Name | Net | Also on the net |", "|---|---|---|---|"]
    pins = sorted(part.pins, key=lambda p: natural(p.num))
    for pin in pins:
        if in_use(pin):
            name = f"`{pin.name}`" if pin.name else ""
            rows.append(f"| {pin.num} | {name} | `{pin.net.name}` | {also_on_net(pin)} |")
    unused = [f"{pin.num} (`{pin.name}`)" if pin.name else str(pin.num)
              for pin in pins if not in_use(pin)]
    if unused:
        rows += ["", "Not connected: " + ", ".join(unused) + "."]
    return rows


def write():
    parts = {part.ref: part for part in default_circuit.parts}
    modules = {tag_path(part): part for part in default_circuit.parts}
    lines = [
        "# Pins and parts",
        "",
        "Which pin of which module carries what, the connectors, the test points, and each",
        "part's name in the code. Written by `circuit/board.py` from the circuit on every",
        "run: change the circuit, not this file.",
        "",
        "## Modules",
    ]
    for path, title, note in MODULES:
        module = modules[path]
        lines += ["", f"### {module.ref}, {title}", ""]
        if note:
            lines += [note, ""]
        lines += pin_table(module)

    lines += ["", "## Connectors, headers and jumpers"]
    for ref in sorted((r for r in parts if r.startswith("J")), key=natural):
        part = parts[ref]
        lines += ["", f"### {ref}, `{'/'.join(part.hiertuple[1:] + (part.tag,))}`", ""]
        lines += pin_table(part)

    lines += ["", "## Test points", "", "| Test point | Net |", "|---|---|"]
    for ref in sorted((r for r in parts if r.startswith("TP")), key=natural):
        lines.append(f"| {ref} | `{parts[ref].pins[0].net.name}` |")

    lines += ["", "## Parts by designator", "",
              "The name in the code is the sheet, the block if the part is in one, and the",
              "part's own name.", "",
              "| Designator | Name in the code | Value |", "|---|---|---|"]
    for ref in sorted((r for r in parts if not r.startswith("TP")), key=natural):
        part = parts[ref]
        lines.append(f"| {ref} | `{'/'.join(part.hiertuple[1:] + (part.tag,))}` | {part.value} |")

    with open(os.path.join(REPO, "docs", "pins.md"), "w", encoding="utf-8") as out:
        out.write("\n".join(lines) + "\n")
