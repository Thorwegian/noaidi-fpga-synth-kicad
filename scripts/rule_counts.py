#!/usr/bin/env python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""rule_counts.py -- count the findings in kicad-cli's DRC and ERC reports by type.

    rule_counts.py <report.json> ...

Prints one line per report, severity and type, so that two runs can be
compared with diff.
"""
import collections
import json
import os
import sys


def findings(report):
    """The findings of a DRC report (the board's) or an ERC report (per sheet)."""
    yield from report.get("violations", [])
    for sheet in report.get("sheets", []):
        yield from sheet["violations"]
    for item in report.get("unconnected_items", []):
        yield {"severity": item["severity"], "type": "unconnected_items"}
    for item in report.get("schematic_parity", []):
        yield {"severity": item["severity"], "type": "schematic_parity"}


for path in sys.argv[1:]:
    with open(path, encoding="utf-8") as file:
        counts = collections.Counter(
            (finding["severity"], finding["type"]) for finding in findings(json.load(file)))
    name = os.path.splitext(os.path.basename(path))[0]
    for (severity, kind), count in sorted(counts.items()):
        print(f"{name:<18} {severity:<8} {kind:<28} {count}")
    if not counts:
        print(f"{name:<18} no findings")
