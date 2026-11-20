# Rules

- Git policies:
  - Agents have GitHub accounts. `gh` access tokens and SSH keys are set up in their home directories.
  - Agents read GitHub through GraphQL queries in preference to REST calls.
  - On the issues and pull requests they are working on, agents watch for new comments and notifications and *always* liveblog their progress in the comments.
  - Issues form a tree, read as a Makefile: a sub-issue is a prerequisite of its parent, and the issue to work on has no open sub-issues.
  - Sub-issues of one parent are independent of each other.
  - `blocked_by` is only for a prerequisite that several issues share.
  - GitHub allows one parent and eight levels.
  - An issue has its labels and its parent at creation; a parent with no work of its own is labelled `meta`.
  - Issue relations live in GitHub's fields, never in prose.
  - An issue states a problem, not a symptom. A problem found while working on another issue gets its own issue at once.
  - An issue's title says in plain words what is wrong and who notices.
  - A PR's relation to its issue is `Fixes #n` in the PR body.
  - Pull requests are drafts against `main`, opened as soon as the change exists; what was run and what it gave lands on them as comments.
  - A pull request's base is *never* another pull request's branch.
  - Agents *never* commit to `main`, mark a pull request ready or merge one.
  - Before pushing to a pull request's branch again, the agent checks its state: it may have been merged meanwhile.
  - When an agent pull request is approved, the agent must remove the branch it created for it.

- Triaging:
  - When checking GitHub, propose issues to quick fix, rerank, reparent, consolidate, update or close.
  - An issue ranks by how much, and how often, it annoys a keyboard player. A bug that can cause systemic faults ranks above a mild annoyance; what the typical keyboard player's audio gear already does ranks low.
  - A new sub-issue is ranked among its siblings by how critical it is, the most critical first.

- Time-consuming tasks (3D renders, anything that runs for more than a minute) are run in the background.

- Every session's work, a one-line docs PR included, happens in its own worktree, *never* in a shared one. The checkouts rest on `main` and are only ever pulled.

- Thor's edits arrive on `main`: pull before reading the design.

- 3D renders are made on the Mac. Every job on the Mac is started with `nice -n 20`. Before a render on its GPU the agent reads the Mac's memory (`vm_stat`), and starts none while another program holds several GB.

## Decisions and evidence

- The specification comes first. `docs/requirements.md` says what the board has to do, and a requirement that changes, changes there before the design does.

- A decision is recorded in the requirements or in its issue's body. It becomes a change to the design when Thor asks for the change.

- The design's intent is read before it is asked about: from the netlist, the parts, and the modules' own schematics in `docs/thirdparty/`.

- A finding that Thor questions is discussed in the chat first. Documents and issues are rewritten once the answer is agreed.

- A finding states where it is (file, sheet, designator, pin), the evidence taken from the files that day, the arithmetic in full, and whether it has any electrical effect. A value that is within its specification is called acceptable in the first sentence.

- A figure is measured, taken from a named document (file, section or table, page), or labelled as a bound or a guess. Catalogue stock and prices, and the fab's limits, are fetched the day they are quoted.

- Sources are not equal, and a claim says which kind it rests on:
  - A part's data sheet is the authority on its limits and ratings. Its test circuit is not an application circuit.
  - The maker's application notes and the standard for a bus (the MIDI specification, USB) are the authority on how a part or a bus is used.
  - The published schematic of a product that a reputable vendor ships in volume is evidence of what works in practice.
  - Hobby write-ups and forum posts are anecdote.
  - A fab's or a distributor's blog is vendor copy and is labelled as such.
  - When sources disagree, the stronger one wins. A proposal that goes against what the manufacturers recommend says why, and "it is already drawn" is not a reason.

- Dimensions are *never* taken from a photo.

- A picture an agent looks at to reach a conclusion (a render, a crop of a schematic or a data sheet, a photo) is sent to the chat with the conclusion.

## Files

- The root folder holds the KiCad project, the README, this file and the licence, nothing else. Scripts go in `scripts/`, documents in `docs/`, vendor documents in `docs/thirdparty/`, the circuit in text in `circuit/`.

- Vendor documents are fetched from the link in the symbol's Datasheet field. A part that enters the design brings its data sheet in the same pull request.

- Generated files are not committed: they go under `build/`, which is ignored. The exceptions are `docs/pins.md` and the README's pictures.

- The README's pictures live in `docs/images/`.

- KiCad files that were edited as text have not been opened in the KiCad GUI, and the pull request says so.

## The circuit and the board

- The board is edited in KiCad, and the circuit in text (`circuit/`) is held against it: the netlist that `circuit/board.py` writes is right when KiCad's File > Import > Netlist, set to "Link footprints using reference designators", proposes no change to the board. KiCad is the authority on that.

- The KiCad project has no schematic, and the board is never updated from one in the KiCad GUI.

- The KiCad project file is the authority on the design rules. Scripts read them off the board and carry no copy of their own: a clearance, a width, a via size or an annular ring written into a script is a defect.

- JLCPCB's published limits are the authority behind the design rules, and a layout never undercuts one. Where the fab's minimum is the edge of its process the layout stays above it.

- A pull request that changes the board gives the counts of KiCad's DRC beside those of `main`, type for type, and explains a difference.

- A part has a descriptive name in the code (`cc1_pulldown`), which is also its `tag`, and a regular designator on the board (`R13`). A new part takes the next free number; existing designators are not renumbered, and a gap stays a gap.

- A net that crosses sheets is defined once, in `circuit/global_nets.py`, and imported. Every net a person may want to probe has a name. A circuit that appears twice is written once, as a function that takes its nets as arguments.

- Pins are addressed by name: the FPGA's by the symbol's names, which begin with the FPGA's pin number (`27_IOB8A`), the number the gateware's constraints use; the ESP32's by GPIO number. Unused pins are marked as not connected.

- `docs/pins.md` is written by `circuit/board.py` and *never* edited by hand. A change to the circuit is committed together with the change it makes to that file.

- A change to what a module's pin does is a change for the gateware or the firmware as well: its issue in Thorwegian/noaidi-fpga-synth is opened in the same turn.

- Apply principles of universal design to what a person touches: connectors of one kind carry their signals in one order, and what is printed on the board agrees with the documents.

- Agents use Mermaid.js for diagrams and Matplotlib for graphs. SKiDL's SVG and the KiCad schematic it generates are not used.

## Parts and the fab

- JLCPCB fabricates the board and places the surface-mount parts. The modules, the DIN and RCA sockets and the pin headers are through-hole and soldered by hand.

- Chip parts are 0805 on KiCad's hand-solder footprints (the ones named `..._HandSolder`), and come from JLCPCB's basic library where it has the value.

- A part that JLCPCB places carries its LCSC number in the symbol's `LCSC` field.

- Agents *never* order anything, and never upload files to a fab or a distributor. They prepare the files with `scripts/fab_files.py`; Thor uploads them and orders.

- What an order costs is estimated with `scripts/cost_estimate.py`, not by hand. The estimate is posted on its issue as one comment, and is made anew when the layer count, the board's size, the quantity or a placed part changes.

## Code and documents

- Agents write elegant and highly structured code at a senior developer level.

- Variable names *must* be descriptive and use industry standard textbook terminology.

- Agents *always* look for and fix dead code, code that lives in two places and could live in one, and inconsistent code patterns.

- Agents *must* update comments and docs so they match the design before *every* commit. A document changes in the same pull request as the number or the rule it states.

- Files in the repository document *state*: what the design is and why it is so. They never say what something was before, what it replaced, or when and by whom it changed. Change is recorded where it happens: in the chat, the issue, the pull request and the commit message, and Git keeps the log. The only file that lists changes is one that is a changelog by name.

- The README is for a person who wants to know what the board is. The routines of developing it go in `scripts/` as scripts and in this file as rules, not in the README.

- All source files shall carry the following copyright notice:

```
Copyright © 2026 Thor H. Linløkken <thj@thj.no>
License: CERN-OHL-S v2
```

# Finding your feet

## The words

- The *base board* is this board, which sits at the bottom of the enclosure. The *front panel board* is the later one it will power and talk to.
- A *module* is a bought board that sits on headers: the Tang Nano 20K, the ESP32-S3 board, the DAC.
- The *lab jig* is the lab's set of connections to the board for the automated tests.
- The *circuit in text* is `circuit/`, and a *sheet* is one of its four files (`usb`, `esp32`, `tang_nano_20k`, `test_points`).
- The *board* is `noaidi-fpga-synth.kicad_pcb`.
- A *designator* is a part's name on the board (`R13`).
- The synth repository's `docs/glossary.md` defines the project's other terms.
- For those who know the gateware: the circuit in text is the RTL and `global_nets.py` its package; a block written as a function is a module with ports; the netlist comparison is the equivalence check; a SPICE bench is a simulation bench; layout is place and route, and DRC is its timing report; `docs/pins.md` is the debug symbols.

## The board

- `README.md`: what is on it, the files, the build tools.
- `docs/requirements.md`: what the board has to do, and the reference the design is checked against.
- `docs/pins.md`: which pin of which module carries what, the connectors, the test points, each part's name in the code.
- `docs/esp32s3_hw678.md`: the ESP32-S3 boards in hand, which stand in for Espressif's ESP32-S3-DevKitC-1.
- `docs/thirdparty/`: the vendors' drawings, schematics and data sheets.
- `noaidi-fpga-synth.kicad_pcb`: the board. Thor lays it out by hand in KiCad.
- `noaidi-fpga-synth.kicad_pro` and `noaidi-fpga-synth.kicad_dru`: the design rules. The second names the row of JLCPCB's capability page each figure comes from.
- `noaidi-fpga-synth.kicad_sym` and `noaidi-fpga-synth.pretty/`: the project's own symbols and footprints.
- The goal is issue #5: get the board fabricated at JLCPCB, so development moves onto it.

## The tools

- `README.md` lists the scripts and the build tools. Each script says in its heading what it does and needs.
- `scripts/netlist_import.py` holds the circuit in text against the board, without running KiCad.
- The scripts that read the board file run under the system's Python (`/usr/bin/python3`), which has KiCad's `pcbnew` module. The other Python tools live in the main checkout's `.venv/`, which serves every worktree.
- Everything generated lands under `build/`.

## Two machines

- The cloud box (thj.no): this repository, where the agent lives. No KiCad GUI, no board.
- The Mac (`ssh -p 23456 hermes@home.thj.no`): an M2 Pro with a GPU, and the machine Thor works at.
  - The agent's account there has no administrator rights. Its home is `/Volumes/Media/Hermes`, with a clone of this repository in `~/noaidi-fpga-synth-kicad`.
  - `kicad-cli` and `blender` come from Homebrew, which is Thor's to run.
  - The render scripts render on the machine they are started on, so a render is started in the Mac's clone over SSH and the picture fetched from its `build/` (#114).
- Worktrees live under `~/wt` on the cloud box: `git worktree add ~/wt/wt-<issue> -b <branch> main`. A worktree holds its own `build/`.
