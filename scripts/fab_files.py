#!/usr/bin/python3
#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""fab_files.py -- the files JLCPCB's order page takes, from the board.

    scripts/fab_files.py [--out <folder>] <board>

Writes into build/fab/, or into the folder given:

  gerbers.zip    one Gerber file for each copper layer, solder mask,
                 silkscreen and paste layer and for the board's edge, and
                 the drill files for plated and for unplated holes;
  bom.csv        the parts JLCPCB places, one line for each LCSC number;
  placement.csv  where each of those parts sits, and how it is turned.

The Gerber and drill settings are the ones JLCPCB asks for
(https://jlcpcb.com/help/article/how-to-generate-gerber-and-drill-files-in-kicad-9):
Protel file name extensions, by which JLCPCB tells the layers apart and
counts the inner ones, the extended X2 format, drill files in Excellon with
millimetres, decimal zeros and absolute origin, plated and unplated holes
in separate files. The columns of the two lists are the ones of
https://jlcpcb.com/help/article/how-to-generate-the-bom-and-centroid-file-from-kicad.

JLCPCB places the parts that have an LCSC number, which is the footprint's
field `LCSC`. A part without one is soldered by hand and is in neither list.

A position is the footprint's own, in millimetres from the same origin as
the Gerber files, with y upwards. JLCPCB's library holds some packages
turned against KiCad's footprint for them. The rotations to add are those
of the Fabrication Toolkit, the KiCad plugin JLCPCB's article recommends
(https://github.com/bennymeg/Fabrication-Toolkit, plugins/transformations.csv);
the script fetches that table into build/tools/ and checks it against a
SHA-256. Whether a part sits right on its pads shows in the placement
preview of JLCPCB's order page and nowhere before it.

The board file is not changed.
"""
import argparse
import collections
import csv
import hashlib
import os
import re
import subprocess
import sys
import urllib.request
import zipfile

import pcbnew

TURNS_COMMIT = "038cd1ddbe36c1e013aa3b4f284b0326cc4bdb77"
TURNS_URL = f"https://raw.githubusercontent.com/bennymeg/Fabrication-Toolkit/{TURNS_COMMIT}/plugins/transformations.csv"
TURNS_SHA256 = "f02b3353de29331b1b740cc0bf9da11157bc9a9803f6ddb264e30b4ca8f1e6d1"
TURNS_FILE = "build/tools/jlcpcb-rotations.csv"
OTHER_LAYERS = ["F.Mask", "B.Mask", "F.Silkscreen", "B.Silkscreen", "F.Paste", "B.Paste", "Edge.Cuts"]


def turns():
    """The Fabrication Toolkit's table as [(pattern, degrees)]."""
    if not os.path.exists(TURNS_FILE):
        os.makedirs(os.path.dirname(TURNS_FILE), exist_ok=True)
        with urllib.request.urlopen(TURNS_URL) as answer, open(TURNS_FILE, "wb") as file:
            file.write(answer.read())
    with open(TURNS_FILE, "rb") as file:
        if hashlib.sha256(file.read()).hexdigest() != TURNS_SHA256:
            sys.exit(f"{TURNS_FILE} is not the table this script was written against")
    with open(TURNS_FILE, encoding="utf-8", newline="") as file:
        return [(row["Regex To Match"], float(row["Rotation"])) for row in csv.DictReader(file)]


def run(*command):
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode:
        sys.exit(f"{' '.join(command)}\n{done.stdout}{done.stderr}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="build/fab")
    parser.add_argument("board")
    arguments = parser.parse_args()
    out = arguments.out
    plots = os.path.join(out, "gerbers")
    os.makedirs(plots, exist_ok=True)
    for name in os.listdir(plots):
        os.remove(os.path.join(plots, name))

    board = pcbnew.LoadBoard(arguments.board)
    copper = [board.GetLayerName(layer) for layer in board.GetEnabledLayers().CuStack()]
    run("kicad-cli", "pcb", "export", "gerbers", "--output", plots + "/", "--layers", ",".join(copper + OTHER_LAYERS),
        "--subtract-soldermask", "--check-zones", arguments.board)
    run("kicad-cli", "pcb", "export", "drill", "--output", plots + "/", "--format", "excellon",
        "--drill-origin", "absolute", "--excellon-units", "mm", "--excellon-zeros-format", "decimal",
        "--excellon-oval-format", "alternate", "--excellon-separate-th", arguments.board)
    # KiCad also writes a job file, which is no part of what JLCPCB asks for.
    plotted = sorted(name for name in os.listdir(plots) if not name.endswith(".gbrjob"))
    with zipfile.ZipFile(os.path.join(out, "gerbers.zip"), "w", zipfile.ZIP_DEFLATED) as archive:
        for name in plotted:
            archive.write(os.path.join(plots, name), name)

    table = turns()
    lines = collections.defaultdict(list)
    placements, turned = [], []
    for footprint in sorted(board.GetFootprints(), key=lambda footprint: natural(footprint.GetReference())):
        number = footprint.GetFieldText("LCSC") if footprint.HasField("LCSC") else ""
        if not number:
            continue
        designator = footprint.GetReference()
        package = str(footprint.GetFPID().GetLibItemName())
        lines[(number, footprint.GetValue(), package)].append(designator)
        add = next((degrees for pattern, degrees in table if re.search(pattern, package)), 0.0)
        if add:
            turned.append(designator)
        position = footprint.GetPosition()
        placements.append((designator, f"{pcbnew.ToMM(position.x):.4f}", f"{-pcbnew.ToMM(position.y):.4f}",
                           "bottom" if footprint.IsFlipped() else "top",
                           f"{(footprint.GetOrientationDegrees() + add) % 360:g}"))

    with open(os.path.join(out, "bom.csv"), "w", encoding="utf-8", newline="") as file:
        rows = csv.writer(file)
        rows.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (number, value, package), designators in sorted(lines.items(), key=lambda line: natural(line[1][0])):
            rows.writerow([value, ",".join(designators), package, number])
    with open(os.path.join(out, "placement.csv"), "w", encoding="utf-8", newline="") as file:
        rows = csv.writer(file)
        rows.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        rows.writerows(placements)

    print(f"gerbers.zip: {len(plotted)} files: {' '.join(plotted)}")
    print(f"bom.csv: {len(placements)} parts in {len(lines)} lines")
    print(f"placement.csv: {len(placements)} parts, {sum(1 for row in placements if row[3] == 'bottom')} of them on the back; "
          f"turned for JLCPCB's library: {' '.join(turned) or 'none'}")


def natural(designator):
    """J9 before J14."""
    letters, digits = re.match(r"(\D*)(\d*)", designator).groups()
    return letters, int(digits or 0)


if __name__ == "__main__":
    main()
