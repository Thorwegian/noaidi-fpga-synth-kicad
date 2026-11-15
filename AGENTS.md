# Rules

- Git policies: Agents have GitHub accounts. `gh` access tokens and SSH keys are set up in their home directories. Agents pay attention to what is going on at GitHub as they work: new comments and notifications on the issues and pull requests they are working on. Agents *always* liveblog their progress directly to the comments sections of the GitHub issues and pull requests they are working on. Issue relations live in GitHub's fields, never in prose, and the relation is the parent: an issue belongs to the family whose goal it serves, and two issues that belong together share a parent rather than referring to each other. Before opening an issue the agent looks for its family among the open parents (`gh issue list --state open --label meta`, then a search on the topic, `gh issue list --state open --search "<words>"`), and an agent-opened issue has, at creation, its labels and its parent (`gh api -X POST repos/<r>/issues/<parent>/sub_issues -F sub_issue_id=<id>`, the id from `gh api repos/<r>/issues/<n> --jq .id`). Only when no open issue is its parent does the agent open the parent first (labelled `meta`, the family's home: a body stating the goal and the rule, never a list of its children). The one other relation is the dependency, for an issue that cannot be worked before another lands (`gh api -X POST repos/<r>/issues/<n>/dependencies/blocked_by -F issue_id=<id>`); it states the order of work, not kinship. The field is the only place a relation lives: `gh issue view` prints `parent:`, `sub-issues:`, `blocked-by:` and `blocking:` in every issue's header, so "see #n", "sibling of #n", "parent: #n" or "blocked by #n" written in a body or a comment is noise when it agrees with the field and a lie once the issue is re-parented. The body may say why the issue belongs to its family when the titles do not make it plain; that is a sentence about the design, not a link. A PR's relation to its issue is `Fixes #n` in the PR body. When an agent pull request is approved, the agent must remove the branch it created for it.

- Pull requests are drafts against `main`, opened as soon as the change exists; what was run and what it gave lands on them as comments. The base is never another pull request's branch: a pull request merged into a side branch does not reach `main` (#14, the circuit in text, went that way and needed #17 to carry it across). Work that needs an unmerged pull request branches from its head, is still opened against `main`, and says in its body that it contains the other's commits until that one is merged. Agents never commit to `main`, mark a pull request ready or merge one. Before pushing to a pull request's branch again, check its state: it may have been merged meanwhile.

- An issue states a problem, not a symptom. A problem found while working on another issue gets its own issue at once.

- Time-consuming tasks (3D renders, anything that runs for more than a minute) are run in the background.

## Decisions and evidence

- The specification comes first. `docs/requirements.md` says what the board has to do, and a requirement that changes, changes there before the design does. A decision is recorded in the requirements or in its issue's body. It becomes a change to the design when Thor asks for the change.

- The design's intent is read before it is asked about: from the netlist, the parts, and the modules' own schematics in `docs/thirdparty/`. A question goes to Thor only for what those do not answer.

- A finding that Thor questions is discussed in the chat first. Documents and issues are rewritten once the answer is agreed, and with what was agreed.

- A finding states where it is (file, sheet, designator, pin), the evidence taken from the files that day, the arithmetic in full, and whether it has any electrical effect. A value that is within its specification is called acceptable in the first sentence.

- A figure is measured, taken from a named document (file, section or table, page), or labelled as a bound or a guess. Catalogue stock and prices, and the fab's limits, are fetched the day they are quoted.

- Sources are not equal, and a claim says which kind it rests on. A part's data sheet is the authority on its limits and ratings; its test circuit states the conditions those limits are measured under and is not an application circuit. The maker's application notes and the standard for a bus (the MIDI specification, USB) are the authority on how a part or a bus is used. The published schematic of a product that a reputable vendor ships in volume is evidence of what works in practice. Hobby write-ups and forum posts are anecdote: they say where to look, and settle nothing. A fab's or a distributor's blog is vendor copy and is labelled as such. When sources disagree, the stronger one wins. A proposal that goes against what the manufacturers recommend says why, and "it is already drawn" is not a reason.

- Dimensions are *never* taken from a photo. They come from the vendor's drawing, the data sheet, the footprint, or a measurement made with the part in hand. Photos are for reading labels and markings.

- A picture an agent looks at to reach a conclusion (a render, a crop of a schematic or a data sheet, a photo) is sent to the chat with the conclusion.

## Files

- The root folder holds the KiCad project, the README, this file and the licence, nothing else. Scripts go in `scripts/`, documents in `docs/`, vendor documents in `docs/thirdparty/`, the circuit in text in `circuit/`.

- Vendor documents are fetched from the link in the symbol's Datasheet field, so that each is the document its symbol names. A part that enters the design brings its data sheet in the same pull request.

- Generated files are not committed: netlists, renders and logs go under `build/`, which is ignored. The one exception is `docs/pins.md`. The README's pictures are hosted on the website and regenerated by `scripts/render.sh`.

- The KiCad project holds the board and has no schematic: the circuit is in `circuit/`, and the board is never updated from a schematic in the KiCad GUI. The project's own symbols are in `noaidi-fpga-synth.kicad_sym`, which the circuit in text reads.

- KiCad files that were edited as text have not been opened in the KiCad GUI, and the pull request says so.

## The circuit

- The circuit in text (`circuit/`) leads. It holds the circuit with the parts chosen for fabrication, and the board follows it by script: `scripts/board_from_circuit.py` sets the board's parts, nets and net classes, and `scripts/route.sh` lays the copper and puts the designators where they can be read (`scripts/place_designators.py`). A net's class is stated in `circuit/net_classes.py`, a fixed position in `circuit/fixed_positions.toml`, and the copper layers with the fill of each in `circuit/layers.toml`. No track is laid on the net of a fill: the fill joins its pads, and `scripts/join_fills.py` the ones it does not reach. The net class table in the KiCad project file is not edited by hand. A change to the circuit is made in `circuit/`, and is done when the board has been brought up to it and routed, `scripts/check.sh` exits 0, and the regenerated `docs/pins.md` is committed with it. A change to a footprint the board uses is done when `scripts/route.sh` has been run on the board and its result is committed with it: the router is given each part's outline and name. The counts the script prints for KiCad's DRC are the same as on `main`, type for type, or the pull request explains the difference.

- Agents place and route the board. Thor states where the parts a person interacts with sit: the connectors at the board's edge, lights, buttons. Every other position, and the copper, is the agent's to decide, from the fab's limits, the parts' data sheets and the makers' application notes. A layout is judged by KiCad's DRC and `scripts/check.sh`, never by a router's own report, and then by looking at the copper, which shows what the DRC has no rule for. `scripts/layout_pictures.py` makes the pictures: the agent looks at every tile of the board before it reports the layout, and the layout reaches Thor as the whole-board picture and its quarters, with its counts (track segments, vias, track length, DRC findings by type, missing connections) beside those of the layout it replaces.

- SKiDL's SVG and the KiCad schematic it generates are not used for this board: neither draws it legibly. Agents use Mermaid.js for diagrams and Matplotlib for graphs.

- A part has a descriptive name in the code (`cc1_pulldown`) and a regular designator on the board (`R13`). The descriptive name is also the part's `tag`. A new part takes the next free number; existing designators are not renumbered, and a gap stays a gap.

- A net that crosses sheets is defined once, in `circuit/global_nets.py`, and imported. Every net a person may want to probe has a name. A circuit that appears twice is written once, as a function that takes its nets as arguments.

- Pins are addressed by name: the FPGA's by the symbol's names, which begin with the FPGA's pin number (`27_IOB8A`), the number the gateware's constraints use; the ESP32's by GPIO number. Unused pins are marked as not connected.

- `docs/pins.md` is written by `circuit/board.py` and *never* edited by hand. A change to the circuit is committed together with the change it makes to that file.

- A change to what a module's pin does is a change for the gateware or the firmware as well: its issue in Thorwegian/noaidi-fpga-synth is opened in the same turn.

- Apply principles of universal design to what a person touches: connectors of one kind carry their signals in one order (both I2C headers read ground, clock, data), and what is printed on the board agrees with the documents.

## Parts and the fab

- JLCPCB fabricates the board and places the surface-mount parts. The modules, the DIN and RCA sockets and the pin headers are through-hole and soldered by hand (`docs/requirements.md`, How it is made).

- JLCPCB's published limits are the authority on the design rules, and a layout never undercuts one. The figures that apply to every object are in the board setup (`noaidi-fpga-synth.kicad_pro`); the fab's limits for component holes, which are wider than its limits for vias, are rules in `noaidi-fpga-synth.kicad_dru`. Where the fab's minimum is the edge of its process the layout stays above it: a track and its spacing are 0.2 mm, twice the fab's minimum, 0.4 mm on the supply nets and 0.3 mm on the USB data pair (`circuit/net_classes.py`), and a track narrows to 0.15 mm only where it has to pass between pins.

- Chip parts are 0805 on KiCad's hand-solder footprints (the ones named `..._HandSolder`), so that a board can be repaired by hand, and come from JLCPCB's basic library where it has the value. A part that JLCPCB places carries its LCSC number in the symbol's `LCSC` field.

- Agents *never* order anything, and never upload files to a fab or a distributor. They prepare the files with `scripts/fab_files.py`; Thor uploads them and orders.

- What an order costs is estimated with `scripts/cost_estimate.py`, not by hand. The price of the bare boards and of each shipping method is read from JLCPCB's quote page (https://cart.jlcpcb.com/quote) with the values the script prints typed in: the page gives them without a sign-in, and nothing is put in a cart. The estimate is posted on its issue as one comment, and is made anew when the layer count, the board's size, the quantity or a placed part changes.

## Code and documents

- Agents write elegant and highly structured code at a senior developer level.

- Variable names *must* be descriptive and use industry standard textbook terminology.

- Always look for dead code, duplicates, similar code in two places that could live in one and inconsistent code patterns, and bring these to the attention of the user.

- Agents *must* update comments and docs so they match the design before *every* commit. A document changes in the same pull request as the number or the rule it states.

- Files in the repository document *state*: what the design is and why it is so. They never say what something was before, what it replaced, or when and by whom it changed. Change is recorded where it happens: in the chat, the issue, the pull request and the commit message, and Git keeps the log. The only file that lists changes is one that is a changelog by name.

- The README is for a person who wants to know what the board is. The routines of developing it go in `scripts/` as scripts and in this file as rules, not in the README.

- All source files shall carry the following copyright notice:

```
Copyright © 2026 Thor H. Linløkken <thj@thj.no>
License: CERN-OHL-S v2
```

# Division of labour

Thor decides, solders the through-hole parts and places the order. JLCPCB fabricates and places the surface-mount parts. Agents work headless: the circuit in text, placement and routing, the checks, candidates for parts, the documents.

The top agent is Claude Fable, with DeepSeek V4 Flash as the fallback. Subagents run on DeepSeek V4 Flash.

A subagent's output is delivered to the lead agent, never to a commit or a PR. The lead agent verifies before acting on it.

# Finding your feet

- **The words:** the *base board* is this board, which sits at the bottom of the enclosure; the *front panel board* is the later one it will power and talk to. A *module* is a bought board that sits on headers: the Tang Nano 20K, the ESP32-S3 board, the DAC. The *lab jig* is the lab's set of connections to the board for the automated tests, among them the modules' USB ports and the LED into the optical capture. The *circuit in text* is `circuit/`, and a *sheet* is one of its four files (`usb`, `esp32`, `tang_nano_20k`, `test_points`); the *board* is `noaidi-fpga-synth.kicad_pcb`, which the scripts make from the circuit in text. A *designator* is a part's name on the board (`R13`). The synth repository's `docs/glossary.md` defines the project's other terms.
- **The board:** `README.md` (what is on it, the files, the build tools); `docs/requirements.md` is what the board has to do and is the reference the design is checked against; `docs/pins.md` (which pin of which module carries what, the connectors, the test points, each part's name in the code); `docs/esp32s3_hw678.md` (the ESP32-S3 boards in hand, which stand in for Espressif's ESP32-S3-DevKitC-1: same pins, same footprint); `docs/thirdparty/` (the vendors' drawings, schematics and data sheets).
- **The work:** the goal is issue #5, labelled `meta`: get the board fabricated at JLCPCB, so development moves onto it. Its sub-issues are the open work. Closed issue #1 is an earlier agent's review of the schematic; its claims are not the agreed state.
- **For those who know the gateware:** the circuit in text is the RTL and `global_nets.py` its package; a block written as a function is a module with ports; the netlist comparison is the equivalence check; the fixed positions (edge connectors, outline, mounting holes) are the constraints file; a SPICE bench is a simulation bench; layout is place and route, and DRC is its timing report; `docs/pins.md` is the debug symbols.
- **The tools:** `kicad-cli` (KiCad 10), `pdftoppm` (poppler-utils) and `java` (25, for the autorouter) come from the system's packages, and so does the Python that has KiCad's `pcbnew` module and Pillow (`/usr/bin/python3`), which the scripts that read the board file run under; the other Python tools (SKiDL among them) live in a virtual environment built from `scripts/requirements.txt`. `scripts/check.sh` is the one command to run after a change; its exit code is 0 when the circuit in text passes its rule check, the board agrees with it and no print on the board is nearer a pad than JLCPCB's 0.15 mm (KiCad's DRC does not measure that distance; `scripts/silkscreen_clearance.py` does). The README lists the scripts, and each says in its heading what it does and needs. Everything generated lands under `build/`.
- **Two machines:** the cloud box (thj.no) holds this repository and runs everything headless: `kicad-cli`, the circuit in text, the checks, the renders. It has no KiCad GUI and no board. Thor's edits arrive on `main`, so pull before reading the design. The main checkout rests on `main` and is only ever pulled. Every session's work, a one-line docs pull request included, happens in its own worktree (`git worktree add ~/wt/wt-<issue> -b <branch> main`), which holds its own `build/`. The Python environment is built once, in the main checkout's `.venv/`, and serves every worktree: `source ~/noaidi-fpga-synth-kicad/.venv/bin/activate`. The session that made a worktree removes it when its pull request merges.
