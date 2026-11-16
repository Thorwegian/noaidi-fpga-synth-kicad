#
#   Copyright © 2026 Thor H. Linløkken <thj@thj.no>
#   License: CERN-OHL-S v2
#
"""enclosure_scene.py -- pictures of the board in a clear acrylic enclosure,
lit by LEDs inside the acrylic, in the dark.

    blender -b --python-exit-code 1 --python scripts/enclosure_scene.py -- \\
        <board.glb> <folder> [width px, default 960] [samples, default 256] [shot ...]

Writes <folder>/enclosure-<shot>.png for each shot named, and for every shot
in SHOTS when none is.

The board is `kicad-cli pcb export glb`'s model of it: metres, the board's
underside at z = 0, each footprint a node named by its designator.
scripts/render_enclosure.sh makes the model and runs this. Needs Blender 4
with Cycles.

The enclosure is a picture's and decides nothing about the one that will be
built (docs/requirements.md leaves it undefined). It is a box of six sheets
around the board's bounding rectangle:

- The walls stand off the board's outline by WALL_CLEARANCE and are not moved
  by a part that reaches further: a part at an edge
  (circuit/fixed_positions.toml) gets an opening through its wall, whether it
  ends short of the wall, in it or beyond it.
- An opening has the outline of the part's mouth, the OPENING_MOUTH_DEPTH of
  it nearest its wall, seen from the wall, with OPENING_MARGIN around it. A
  module's sockets are the solids of its mouth that stand apart, one opening
  each; its own circuit board is not one of them. A mouth that fills the
  ellipse in its bounding rectangle gets a round opening.
- The board stands on four acrylic posts, clear of the base by its longest
  solder pin and UNDERSIDE_CLEARANCE. The board has no mounting holes: the
  posts stand in for whatever will hold it.

The light is path traced from four LEDs, point lights of four colours inside
the lid, one at each corner, and there is no other light in the scene. Three
things make the acrylic show it:

- A sheet's cut edges are matte, as sawn or milled acrylic is, and its faces
  polished: light that travels inside a sheet leaves it at the edges.
- The acrylic scatters a little of the light that passes through it
  (HAZE_DENSITY), so a sheet glows around an LED.
- A shadow ray, the straight line a path tracer draws from a lit point to a
  light, passes through acrylic unbent and loses what a real surface would
  reflect at that angle, all of it beyond the angle of total internal
  reflection. Without this every surface the LEDs light would be lit by
  caustics alone, which a path tracer finds by chance. It is the scene's one
  departure from the path of real light: what the camera sees through the
  acrylic is refracted and reflected in full.
"""
import sys
import tomllib
from dataclasses import dataclass
from math import cos, pi, radians, sin
from pathlib import Path

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

MILLIMETRE = 0.001
UP = Vector((0.0, 0.0, 1.0))

SHEET_THICKNESS = 2.0 * MILLIMETRE
WALL_CLEARANCE = 1.5 * MILLIMETRE       # the board's outline to a wall's inner face
LID_CLEARANCE = 2.0 * MILLIMETRE        # the tallest part to the lid
UNDERSIDE_CLEARANCE = 1.5 * MILLIMETRE  # the longest solder pin to the base
JOINT_GAP = 0.05 * MILLIMETRE           # the film of air where two sheets meet
POST_RADIUS = 2.5 * MILLIMETRE
POST_INSET = 5.0 * MILLIMETRE           # a post's axis from the board's corner

OPENING_MOUTH_DEPTH = 1.0 * MILLIMETRE
OPENING_MARGIN = 1.0 * MILLIMETRE
OPENING_CORNER_RADIUS = 0.8 * MILLIMETRE
OPENING_SMALLEST = 2.0 * MILLIMETRE     # a mouth narrower or lower than this is no socket
MOUTH_PIECES_APART = 1.0 * MILLIMETRE   # pieces of a mouth nearer than this are one socket
ROUND_MOUTH_TOLERANCE = 1.06
WELD_DISTANCE = 0.001 * MILLIMETRE
MODULE_BOARD_FLATNESS = 4.0

ACRYLIC_INDEX_OF_REFRACTION = 1.49
CUT_EDGE_ROUGHNESS = 0.35
HAZE_DENSITY = 12.0                     # scattering per metre of path inside the acrylic

LED_FROM_CORNER = 4.0 * MILLIMETRE      # an LED from each of the two outer faces at its corner
LED_RADIUS = 0.2 * MILLIMETRE
LED_POWER_WATT = 0.2
# One LED in each top corner of the enclosure, by the board's edges that meet
# there, each of its own colour (linear RGB).
LED_COLOURS = {
    ('left', 'top'): (1.0, 0.04, 0.35),      # magenta
    ('right', 'top'): (1.0, 0.42, 0.03),     # amber
    ('left', 'bottom'): (0.0, 0.65, 1.0),    # cyan
    ('right', 'bottom'): (0.22, 0.12, 1.0),  # violet
}
LED_DIE_RADIANCE = 40.0                 # what the camera sees of an LED itself

FLOOR_REFLECTANCE = 0.035
FLOOR_SIZE = 4.0

@dataclass
class Shot:
    """Where the camera stands: its lens on a 36 mm sensor, and the direction
    from the enclosure's middle to it. An azimuth of 0 is towards the board's
    right edge and of 90 towards its top edge."""
    focal_length_mm: float
    azimuth_degrees: float
    elevation_degrees: float


# The pictures that are rendered: the render list, which is Thor's choice of
# views. A shot is named for the edges of the board the camera stands beyond
# and for its height. The wide lens stands near and gives a strong perspective.
SHOTS = {
    'left-bottom-low': Shot(28.0, 215.0, 30.0),
    'right-top-high': Shot(28.0, 35.0, 55.0),
    'bottom-low': Shot(28.0, 260.0, 30.0),
    'left-top-low': Shot(28.0, 125.0, 30.0),
    'right-low': Shot(28.0, 350.0, 30.0),
    'right-high': Shot(28.0, 350.0, 55.0),
}
CAMERA_BACK_OFF = 1.12                  # the distance that fills the frame, times this
ASPECT_RATIO = 3 / 2

FIXED_POSITIONS = Path(__file__).resolve().parent.parent / 'circuit' / 'fixed_positions.toml'


@dataclass
class Box:
    low: Vector
    high: Vector

    @classmethod
    def around(cls, points):
        points = list(points)
        return cls(Vector(min(p[axis] for p in points) for axis in range(3)),
                   Vector(max(p[axis] for p in points) for axis in range(3)))

    def grown(self, sideways, down=0.0, up=0.0):
        return Box(self.low - Vector((sideways, sideways, down)),
                   self.high + Vector((sideways, sideways, up)))

    @property
    def centre(self):
        return (self.low + self.high) / 2

    @property
    def size(self):
        return self.high - self.low

    @property
    def corners(self):
        return [Vector((x, y, z)) for x in (self.low.x, self.high.x)
                for y in (self.low.y, self.high.y) for z in (self.low.z, self.high.z)]

    def reach(self, direction):
        return max(direction.dot(corner) for corner in self.corners)


@dataclass
class Wall:
    """The wall at one edge of the board. A point of it is `along` its length,
    at a height, and `outward` from the board."""
    outward: Vector
    along: Vector
    runs_past_its_neighbours: bool

    def point(self, along, height, outward):
        return self.along * along + UP * height + self.outward * outward


# The edges are the board's as KiCad draws it and circuit/fixed_positions.toml
# names them. KiCad's y axis points down the drawing and the model's up it.
WALLS = {
    'left': Wall(Vector((-1.0, 0.0, 0.0)), Vector((0.0, 1.0, 0.0)), True),
    'right': Wall(Vector((1.0, 0.0, 0.0)), Vector((0.0, 1.0, 0.0)), True),
    'top': Wall(Vector((0.0, 1.0, 0.0)), Vector((1.0, 0.0, 0.0)), False),
    'bottom': Wall(Vector((0.0, -1.0, 0.0)), Vector((1.0, 0.0, 0.0)), False),
}


@dataclass
class Rectangle:
    """A part of a wall: `left` to `right` along it, `bottom` to `top` in height."""
    left: float
    bottom: float
    right: float
    top: float

    @classmethod
    def around(cls, points):
        points = list(points)
        return cls(min(p[0] for p in points), min(p[1] for p in points),
                   max(p[0] for p in points), max(p[1] for p in points))

    @property
    def width(self):
        return self.right - self.left

    @property
    def height(self):
        return self.top - self.bottom

    @property
    def centre(self):
        return ((self.left + self.right) / 2, (self.bottom + self.top) / 2)

    def grown(self, margin):
        return Rectangle(self.left - margin, self.bottom - margin, self.right + margin, self.top + margin)

    def apart_from(self, other):
        return max(self.left - other.right, other.left - self.right,
                   self.bottom - other.top, other.bottom - self.top)


@dataclass
class Opening:
    designator: str
    outline: Rectangle
    is_round: bool

    def profile(self):
        """The opening's outline as a polygon on its wall."""
        centre_along, centre_height = self.outline.centre
        half_width, half_height = self.outline.width / 2, self.outline.height / 2
        if self.is_round:
            return [(centre_along + half_width * cos(angle), centre_height + half_height * sin(angle))
                    for angle in (2 * pi * step / 64 for step in range(64))]
        radius = min(OPENING_CORNER_RADIUS, half_width, half_height)
        polygon = []
        for quadrant, (side_along, side_height) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
            corner_along = centre_along + side_along * (half_width - radius)
            corner_height = centre_height + side_height * (half_height - radius)
            for step in range(9):
                angle = (quadrant + step / 8) * pi / 2
                polygon.append((corner_along + radius * cos(angle), corner_height + radius * sin(angle)))
        return polygon


def designator_of(node):
    """A node's designator: Blender numbers a second node of one name `U1.001`."""
    return node.name.split('.')[0]


def meshes_under(node):
    found = [node] if node.type == 'MESH' else []
    for child in node.children:
        found += meshes_under(child)
    return found


def bounds_of(meshes):
    return Box.around(mesh.matrix_world @ Vector(corner) for mesh in meshes for corner in mesh.bound_box)


def solids_of(mesh_object):
    """The object's solids, each a list of its points. kicad-cli writes every
    surface of a part's CAD model as a piece of mesh of its own: welding the
    points the surfaces share along their edges leaves one connected piece
    for each solid."""
    mesh = bmesh.new()
    mesh.from_mesh(mesh_object.data)
    bmesh.ops.remove_doubles(mesh, verts=mesh.verts, dist=WELD_DISTANCE)
    visited = set()
    solids = []
    for first in mesh.verts:
        if first.index in visited:
            continue
        visited.add(first.index)
        pending, solid = [first], []
        while pending:
            vertex = pending.pop()
            solid.append(mesh_object.matrix_world @ vertex.co)
            for edge in vertex.link_edges:
                neighbour = edge.other_vert(vertex)
                if neighbour.index not in visited:
                    visited.add(neighbour.index)
                    pending.append(neighbour)
        solids.append(solid)
    mesh.free()
    return solids


def is_circuit_board(solid):
    """A module's own board, with what its model has made one solid with it:
    a plate, MODULE_BOARD_FLATNESS times as wide and as long as it is thick."""
    size = Box.around(solid).size
    return min(size.x, size.y) >= MODULE_BOARD_FLATNESS * size.z


def edges_of_parts():
    """Each part at an edge with the edge it is at, from the constraints the
    board is placed to. A part `beside` another is at that part's edge."""
    constraints = tomllib.loads(FIXED_POSITIONS.read_text())

    def edge_of(designator):
        constraint = constraints[designator]
        if 'edge' in constraint:
            return constraint['edge']
        return edge_of(constraint['beside']) if 'beside' in constraint else None

    return {designator: edge_of(designator) for designator in constraints if edge_of(designator)}


def openings_for(designator, meshes, wall):
    """The openings a part needs in its wall: one for each piece of its mouth."""
    solids = [solid for mesh in meshes for solid in solids_of(mesh) if not is_circuit_board(solid)]
    reach = max(wall.outward.dot(point) for solid in solids for point in solid)
    pieces = []
    for solid in solids:
        on_the_wall = [(wall.along.dot(point), point.z) for point in solid
                       if reach - wall.outward.dot(point) <= OPENING_MOUTH_DEPTH]
        if on_the_wall:
            pieces.append(on_the_wall)
    merged = True
    while merged:
        merged = False
        for first in range(len(pieces)):
            for second in range(first + 1, len(pieces)):
                if Rectangle.around(pieces[first]).apart_from(
                        Rectangle.around(pieces[second])) <= MOUTH_PIECES_APART:
                    pieces[first] += pieces.pop(second)
                    merged = True
                    break
            if merged:
                break
    openings = []
    for piece in pieces:
        mouth = Rectangle.around(piece)
        if min(mouth.width, mouth.height) < OPENING_SMALLEST:
            continue
        centre_along, centre_height = mouth.centre
        fills_its_ellipse = all(
            ((along - centre_along) / (mouth.width / 2)) ** 2
            + ((height - centre_height) / (mouth.height / 2)) ** 2 <= ROUND_MOUTH_TOLERANCE
            for along, height in piece)
        openings.append(Opening(designator, mouth.grown(OPENING_MARGIN), fills_its_ellipse))
    return sorted(openings, key=lambda opening: opening.outline.left)


def acrylic(name, roughness):
    """Clear acrylic with a surface of the given roughness: see the heading
    for the haze and for what a shadow ray does."""
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes, link = material.node_tree.nodes, material.node_tree.links.new
    surface = nodes['Principled BSDF']
    surface.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    surface.inputs['Transmission Weight'].default_value = 1.0
    surface.inputs['IOR'].default_value = ACRYLIC_INDEX_OF_REFRACTION
    surface.inputs['Roughness'].default_value = roughness

    reflected = nodes.new('ShaderNodeFresnel')
    reflected.inputs['IOR'].default_value = ACRYLIC_INDEX_OF_REFRACTION
    transmitted = nodes.new('ShaderNodeMath')
    transmitted.operation = 'SUBTRACT'
    transmitted.inputs[0].default_value = 1.0
    link(reflected.outputs['Fac'], transmitted.inputs[1])
    straight_through = nodes.new('ShaderNodeBsdfTransparent')
    link(transmitted.outputs['Value'], straight_through.inputs['Color'])

    ray = nodes.new('ShaderNodeLightPath')
    by_kind_of_ray = nodes.new('ShaderNodeMixShader')
    link(ray.outputs['Is Shadow Ray'], by_kind_of_ray.inputs['Fac'])
    link(surface.outputs['BSDF'], by_kind_of_ray.inputs[1])
    link(straight_through.outputs['BSDF'], by_kind_of_ray.inputs[2])

    haze = nodes.new('ShaderNodeVolumeScatter')
    haze.inputs['Density'].default_value = HAZE_DENSITY
    output = nodes['Material Output']
    link(by_kind_of_ray.outputs['Shader'], output.inputs['Surface'])
    link(haze.outputs['Volume'], output.inputs['Volume'])
    return material


def object_from(name, mesh, materials, collection):
    data = bpy.data.meshes.new(name)
    bmesh.ops.recalc_face_normals(mesh, faces=mesh.faces)
    mesh.to_mesh(data)
    mesh.free()
    for material in materials:
        data.materials.append(material)
    made = bpy.data.objects.new(name, data)
    collection.objects.link(made)
    return made


POLISHED, CUT = 0, 1    # a sheet's material slots: its faces and its cut edges


def sheet(name, box, materials, collection):
    """A sheet of acrylic that fills the box: polished on its two faces, cut on its edges."""
    mesh = bmesh.new()
    bmesh.ops.create_cube(mesh, size=1.0)
    bmesh.ops.scale(mesh, vec=box.size, verts=mesh.verts)
    bmesh.ops.translate(mesh, vec=box.centre, verts=mesh.verts)
    mesh.normal_update()
    through = min(range(3), key=lambda axis: box.size[axis])
    for face in mesh.faces:
        face.material_index = POLISHED if abs(face.normal[through]) > 0.5 else CUT
    return object_from(name, mesh, materials, collection)


def cutter(name, wall, inner_face, openings, materials, collection):
    """What is cut out of a wall: each opening's profile, through the sheet and beyond both faces."""
    mesh = bmesh.new()
    for opening in openings:
        profile = opening.profile()
        inside = [mesh.verts.new(wall.point(along, height, inner_face - SHEET_THICKNESS))
                  for along, height in profile]
        outside = [mesh.verts.new(wall.point(along, height, inner_face + 2 * SHEET_THICKNESS))
                   for along, height in profile]
        mesh.faces.new(inside)
        mesh.faces.new(outside)
        for corner in range(len(profile)):
            following = (corner + 1) % len(profile)
            mesh.faces.new((inside[corner], inside[following], outside[following], outside[corner]))
    for face in mesh.faces:
        face.material_index = CUT
    made = object_from(name, mesh, materials, collection)
    made.hide_render = True
    return made


def post(name, foot, height, materials, collection):
    mesh = bmesh.new()
    bmesh.ops.create_cone(mesh, cap_ends=True, segments=48, radius1=POST_RADIUS, radius2=POST_RADIUS,
                          depth=height)
    bmesh.ops.translate(mesh, vec=foot + UP * (height / 2), verts=mesh.verts)
    return object_from(name, mesh, materials, collection)


def led_light(name, colour):
    light = bpy.data.lights.new(name, 'POINT')
    light.energy = LED_POWER_WATT
    light.color = colour
    light.shadow_soft_size = LED_RADIUS
    return light


def led_die(name, colour):
    """The LED as the camera sees it, directly or through polished acrylic: a
    point light has no surface to look at. The die lights nothing: place_leds
    hides it from every ray but the camera's and the mirrored and refracted."""
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes, link = material.node_tree.nodes, material.node_tree.links.new
    glow = nodes.new('ShaderNodeEmission')
    glow.inputs['Color'].default_value = (*colour, 1.0)
    glow.inputs['Strength'].default_value = LED_DIE_RADIANCE
    link(glow.outputs['Emission'], nodes['Material Output'].inputs['Surface'])
    material.cycles.emission_sampling = 'NONE'
    mesh = bmesh.new()
    bmesh.ops.create_icosphere(mesh, subdivisions=2, radius=LED_RADIUS)
    data = bpy.data.meshes.new(name)
    mesh.to_mesh(data)
    mesh.free()
    data.materials.append(material)
    return data


def place_leds(outside, collection):
    """An LED in the middle of the lid's thickness at each of its corners."""
    height = outside.high.z - SHEET_THICKNESS / 2
    for (side, end), colour in LED_COLOURS.items():
        position = Vector((
            outside.low.x + LED_FROM_CORNER if side == 'left' else outside.high.x - LED_FROM_CORNER,
            outside.high.y - LED_FROM_CORNER if end == 'top' else outside.low.y + LED_FROM_CORNER,
            height))
        name = f'LED, {end} {side}'
        light = bpy.data.objects.new(name, led_light(name, colour))
        die = bpy.data.objects.new(f'{name}, die', led_die(f'{name}, die', colour))
        die.visible_shadow = False
        die.visible_diffuse = False
        die.visible_volume_scatter = False
        for made in (light, die):
            made.location = position
            collection.objects.link(made)


def build_enclosure(root, collection):
    """The enclosure around the imported board. Returns the box it fills."""
    board = bounds_of([child for child in root.children if child.type == 'MESH'])
    everything = bounds_of(meshes_under(root))
    inside = Box(Vector((board.low.x - WALL_CLEARANCE, board.low.y - WALL_CLEARANCE,
                         everything.low.z - UNDERSIDE_CLEARANCE)),
                 Vector((board.high.x + WALL_CLEARANCE, board.high.y + WALL_CLEARANCE,
                         everything.high.z + LID_CLEARANCE)))
    outside = inside.grown(SHEET_THICKNESS, down=SHEET_THICKNESS, up=SHEET_THICKNESS)
    materials = [acrylic('Acrylic, polished face', 0.0), acrylic('Acrylic, cut edge', CUT_EDGE_ROUGHNESS)]

    sheet('Base', Box(outside.low, Vector((outside.high.x, outside.high.y, inside.low.z))),
          materials, collection)
    sheet('Lid', Box(Vector((outside.low.x, outside.low.y, inside.high.z)), outside.high),
          materials, collection)
    for corner in ((board.low.x + POST_INSET, board.low.y + POST_INSET),
                   (board.low.x + POST_INSET, board.high.y - POST_INSET),
                   (board.high.x - POST_INSET, board.low.y + POST_INSET),
                   (board.high.x - POST_INSET, board.high.y - POST_INSET)):
        post('Post', Vector((corner[0], corner[1], inside.low.z + JOINT_GAP)),
             board.low.z - inside.low.z - JOINT_GAP, materials[:1], collection)

    parts = {}
    for child in root.children:
        if child.type != 'MESH':
            parts.setdefault(designator_of(child), []).extend(meshes_under(child))
    openings = {name: [] for name in WALLS}
    for designator, edge in edges_of_parts().items():
        openings[edge] += openings_for(designator, parts[designator], WALLS[edge])

    place_leds(outside, collection)
    floor_height, lid_height = inside.low.z + JOINT_GAP, inside.high.z - JOINT_GAP
    for name, wall in WALLS.items():
        inner_face = board.reach(wall.outward) + WALL_CLEARANCE
        if wall.runs_past_its_neighbours:
            along_low, along_high = wall.along.dot(outside.low), wall.along.dot(outside.high)
        else:
            along_low = wall.along.dot(inside.low) + JOINT_GAP
            along_high = wall.along.dot(inside.high) - JOINT_GAP
        made = sheet(f'Wall, {name}',
                     Box.around((wall.point(along_low, floor_height, inner_face),
                                 wall.point(along_high, lid_height, inner_face + SHEET_THICKNESS))),
                     materials, collection)
        if openings[name]:
            cut = made.modifiers.new('Openings', 'BOOLEAN')
            cut.operation = 'DIFFERENCE'
            cut.solver = 'EXACT'
            cut.object = cutter(f'Openings, {name}', wall, inner_face, openings[name], materials, collection)
        print(f'wall {name}: {len(openings[name])} openings')
        for opening in openings[name]:
            outline = opening.outline
            print('    %-4s %-5s %5.1f x %4.1f mm, its middle %5.1f mm above the board' % (
                opening.designator, 'round' if opening.is_round else 'slot',
                outline.width / MILLIMETRE, outline.height / MILLIMETRE,
                (outline.centre[1] - board.high.z) / MILLIMETRE))
    print('enclosure %.1f x %.1f x %.1f mm outside' % tuple(outside.size / MILLIMETRE))
    return outside


def lay_floor(height, collection):
    material = bpy.data.materials.new('Floor')
    material.use_nodes = True
    surface = material.node_tree.nodes['Principled BSDF']
    surface.inputs['Base Color'].default_value = (FLOOR_REFLECTANCE,) * 3 + (1.0,)
    surface.inputs['Roughness'].default_value = 1.0
    surface.inputs['Specular IOR Level'].default_value = 0.0
    mesh = bmesh.new()
    bmesh.ops.create_grid(mesh, x_segments=1, y_segments=1, size=FLOOR_SIZE / 2)
    floor = object_from('Floor', mesh, [material], collection)
    floor.location.z = height
    return floor


def aim_camera(scene, subject, name, shot):
    """The scene's camera for a shot: it looks at the subject's middle from
    the shot's direction, as near as holds all of it, then backed off."""
    lens = bpy.data.cameras.new(name)
    lens.lens = shot.focal_length_mm
    camera = bpy.data.objects.new(name, lens)
    scene.collection.objects.link(camera)
    scene.camera = camera
    azimuth, elevation = radians(shot.azimuth_degrees), radians(shot.elevation_degrees)
    towards_camera = Vector((cos(elevation) * cos(azimuth), cos(elevation) * sin(azimuth), sin(elevation)))
    camera.rotation_euler = towards_camera.to_track_quat('Z', 'Y').to_euler()
    camera.location = subject.centre + towards_camera
    bpy.context.view_layer.update()
    coordinates = [coordinate for corner in subject.corners for coordinate in corner]
    location, _ = camera.camera_fit_coords(bpy.context.evaluated_depsgraph_get(), coordinates)
    distance = (location - subject.centre).dot(towards_camera)
    camera.location = location + towards_camera * distance * (CAMERA_BACK_OFF - 1.0)
    lens.clip_start = 0.01
    lens.clip_end = 10.0
    # A near, wide lens draws the subject's near end larger than its far end,
    # and its outline is no longer about the middle of the frame. The lens is
    # shifted, as a view camera's is, until the same room is left on both
    # sides and above and below: the perspective stays as it is.
    bpy.context.view_layer.update()
    in_frame = [world_to_camera_view(scene, camera, corner) for corner in subject.corners]
    middle_across = (min(point.x for point in in_frame) + max(point.x for point in in_frame)) / 2
    middle_up = (min(point.y for point in in_frame) + max(point.y for point in in_frame)) / 2
    lens.shift_x = middle_across - 0.5
    lens.shift_y = (middle_up - 0.5) / ASPECT_RATIO


def set_up_render(scene, width, samples):
    scene.render.engine = 'CYCLES'
    cycles = scene.cycles
    cycles.device = 'CPU'
    cycles.samples = samples
    cycles.use_adaptive_sampling = False
    cycles.use_denoising = False
    cycles.max_bounces = 24
    cycles.transmission_bounces = 24
    cycles.glossy_bounces = 8
    cycles.diffuse_bounces = 4
    cycles.volume_bounces = 2
    cycles.transparent_max_bounces = 32
    # The light an LED sends out through the acrylic is carried by the shadow
    # rays. A refracted path that happens upon the LED would bring it again.
    cycles.caustics_refractive = False
    cycles.sample_clamp_indirect = 4.0
    scene.render.resolution_x = width
    scene.render.resolution_y = round(width / ASPECT_RATIO)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.world = bpy.data.worlds.new('Dark')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.0


def main():
    arguments = sys.argv[sys.argv.index('--') + 1:]
    board_path, folder = arguments[0], Path(arguments[1]).resolve()
    width = int(arguments[2]) if len(arguments) > 2 else 960
    samples = int(arguments[3]) if len(arguments) > 3 else 256
    names = arguments[4:] or list(SHOTS)
    unknown = [name for name in names if name not in SHOTS]
    if unknown:
        sys.exit(f'no shot named {", ".join(unknown)}: the shots are {", ".join(SHOTS)}')

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    bpy.ops.import_scene.gltf(filepath=board_path)
    root = next(node for node in scene.objects if node.parent is None)
    enclosure = build_enclosure(root, scene.collection)
    lay_floor(enclosure.low.z - JOINT_GAP, scene.collection)
    set_up_render(scene, width, samples)
    for name in names:
        aim_camera(scene, enclosure, name, SHOTS[name])
        scene.render.filepath = str(folder / f'enclosure-{name}.png')
        bpy.ops.render.render(write_still=True)
        print('picture', scene.render.filepath, scene.render.resolution_x, 'x', scene.render.resolution_y,
              'at', samples, 'samples')


if __name__ == '__main__':
    main()
