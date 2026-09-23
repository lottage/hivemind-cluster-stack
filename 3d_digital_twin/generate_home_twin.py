#!/usr/bin/env python3
"""
Procedural 3D Digital Twin Generator - 120 Sams Way, Murphy, NC
Generates a complete architectural 3D model from the exact dimensioned floorplan:
- Dimension: ~1,074 sq ft (34' x 32' footprint)
- Rooms: Living Room (211 sq ft), Kitchen (188 sq ft), Bedroom 1 (162 sq ft),
         Bedroom 2 (154 sq ft), Bathroom 1 (73.6 sq ft), Bathroom 2 (39.8 sq ft),
         Office Nooks, Closets, Hallway.
- Architectural cutaway walls with door openings.
- Styled floors with distinct PBR materials per room.
- Kitchen island with barstools, perimeter counters, bathroom vanities, tubs, beds, desks.
- Isometric 3D camera setup and warm lighting.
- Exports to .blend, .glb, and renders a beauty preview.
"""

import os
import sys
import math

try:
    import bpy
    import mathutils
except ImportError:
    print("Run inside Blender: blender -b -P generate_home_twin.py")
    sys.exit(1)

# Measurement Conversion
FEET = 0.3048
INCH = 0.0254

def ft_in(ft, inch=0.0):
    return ft * FEET + inch * INCH

WALL_HEIGHT = 1.35   # Architectural cutaway height (4.4 ft) for dashboard overview
WALL_THICK_EXT = ft_in(0, 6.0)   # 6-inch exterior wall (0.152m)
WALL_THICK_INT = ft_in(0, 4.5)   # 4.5-inch interior wall (0.114m)
DOOR_WIDTH = ft_in(2, 8.0)       # 32-inch standard interior door
DOOR_HEIGHT = 1.35               # Cut down for cutaway visibility

OUTPUT_DIR = os.path.abspath(os.path.dirname(__file__))
BLEND_PATH = os.path.join(OUTPUT_DIR, "sams_way_120.blend")
GLB_PATH = os.path.join(OUTPUT_DIR, "sams_way_120.glb")
PREVIEW_PATH = os.path.join(OUTPUT_DIR, "sams_way_120_preview.png")

# --- MATERIAL FACTORY ---
def get_or_create_material(name, base_color, roughness=0.4, metallic=0.0):
    mat = bpy.data.materials.get(name)
    if not mat:
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        bsdf = nodes.get("Principled BSDF")
        if bsdf:
            if "Base Color" in bsdf.inputs:
                bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
            if "Roughness" in bsdf.inputs:
                bsdf.inputs["Roughness"].default_value = roughness
            if "Metallic" in bsdf.inputs:
                bsdf.inputs["Metallic"].default_value = metallic
    return mat

# --- PRIMITIVE HELPERS ---
def create_box(name, x, y, z, width, depth, height, material=None, collection=None):
    """Creates an axis-aligned box with bottom anchored at z."""
    bpy.ops.mesh.primitive_cube_add(
        size=1.0,
        location=(x + width / 2.0, y + depth / 2.0, z + height / 2.0)
    )
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (width, depth, height)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        obj.data.materials.append(material)
    if collection and collection != bpy.context.scene.collection:
        collection.objects.link(obj)
        bpy.context.scene.collection.objects.unlink(obj)
    return obj

def create_floor_slab(name, x, y, width, depth, material, collection):
    """Creates a thin floor plane at z=0."""
    return create_box(f"Floor_{name}", x, y, 0.0, width, depth, 0.02, material=material, collection=collection)

def create_wall(name, x, y, width, depth, height=WALL_HEIGHT, material=None, collection=None):
    return create_box(f"Wall_{name}", x, y, 0.02, width, depth, height, material=material, collection=collection)

# --- SCENE SETUP ---
def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def setup_collections():
    collections = {}
    for name in ["Floors", "Walls", "Kitchen", "Bathrooms", "Furniture", "Lighting", "Cameras"]:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
        collections[name] = col
    return collections

def build_materials():
    return {
        "wall_ext": get_or_create_material("Mat_Wall_Exterior", (0.28, 0.32, 0.35), roughness=0.8),
        "wall_int": get_or_create_material("Mat_Wall_Interior", (0.92, 0.92, 0.90), roughness=0.7),
        "wood_floor": get_or_create_material("Mat_Hardwood_Floor", (0.58, 0.42, 0.28), roughness=0.35),
        "tile_bath": get_or_create_material("Mat_Bathroom_Tile", (0.85, 0.88, 0.90), roughness=0.2),
        "kitchen_tile": get_or_create_material("Mat_Kitchen_Stone", (0.75, 0.74, 0.72), roughness=0.3),
        "counter_top": get_or_create_material("Mat_Quartz_Counter", (0.95, 0.95, 0.96), roughness=0.15),
        "cabinet_wood": get_or_create_material("Mat_Cabinet_Charcoal", (0.15, 0.16, 0.18), roughness=0.5),
        "fabric_sofa": get_or_create_material("Mat_Sofa_Fabric", (0.22, 0.28, 0.35), roughness=0.85),
        "bed_sheet": get_or_create_material("Mat_Bed_Linen", (0.90, 0.90, 0.92), roughness=0.8),
        "wood_furniture": get_or_create_material("Mat_Walnut", (0.35, 0.22, 0.14), roughness=0.4),
        "porcelain_white": get_or_create_material("Mat_Porcelain", (0.98, 0.98, 0.98), roughness=0.1),
        "glass": get_or_create_material("Mat_Glass", (0.9, 0.95, 1.0), roughness=0.1),
    }

def generate_digital_twin():
    print("=== Generating 3D Digital Twin for 120 Sams Way ===")
    clear_scene()
    cols = setup_collections()
    mats = build_materials()

    # --- KEY ARCHITECTURAL COORDINATES (meters) ---
    W_LEFT = ft_in(15, 2.8)          # 4.643m
    L_TOTAL = ft_in(31, 7.9)         # 9.649m
    L_KITCHEN = ft_in(14, 0.0)       # 4.267m
    L_LIVING = L_TOTAL - L_KITCHEN   # ~5.382m

    W_BATH1 = ft_in(5, 10.0)         # 1.778m
    L_BATH1 = ft_in(12, 11.7)        # 3.955m
    W_HALL = ft_in(8, 5.8)           # 2.586m
    L_HALL = ft_in(5, 5.9)           # 1.674m
    W_BATH2 = ft_in(5, 2.6)          # 1.590m
    L_BATH2 = ft_in(7, 7.6)          # 2.327m
    L_CLOSET2 = ft_in(3, 11.0)       # 1.194m

    W_BED1 = ft_in(12, 5.8)          # 3.805m
    L_BED1 = L_BATH1                 # 3.955m
    W_BED2 = ft_in(12, 11.3)         # 3.945m
    L_BED2 = ft_in(11, 10.5)         # 3.620m
    W_CLOSET1 = ft_in(6, 2.2)        # 1.885m
    W_OTHER2 = ft_in(3, 2.0)         # 0.965m

    X_0 = 0.0
    X_MID = W_LEFT                   # 4.643m
    X_RIGHT_B1 = X_MID + W_BATH1     # 6.421m
    X_RIGHT_B2 = X_MID + W_BATH2     # 6.233m
    X_MAX = X_RIGHT_B1 + W_BED1      # ~10.226m

    Y_0 = 0.0
    Y_B2_DIV = L_CLOSET2             # 1.194m
    Y_HALL_START = L_CLOSET2 + L_BATH2 # 3.521m
    Y_HALL_END = Y_HALL_START + L_HALL # ~5.195m
    Y_B1_START = Y_HALL_END          # ~5.195m
    Y_MAX = L_TOTAL                  # 9.649m

    # 1. FLOORS (Room Slabs)
    create_floor_slab("LivingRoom", X_0, L_KITCHEN, W_LEFT, L_LIVING, mats["wood_floor"], cols["Floors"])
    create_floor_slab("Kitchen", X_0, Y_0, W_LEFT, L_KITCHEN, mats["kitchen_tile"], cols["Floors"])
    create_floor_slab("Bathroom1", X_MID, Y_B1_START, W_BATH1, L_BATH1, mats["tile_bath"], cols["Floors"])
    create_floor_slab("Bedroom1", X_RIGHT_B1, Y_B1_START, W_BED1, L_BED1, mats["wood_floor"], cols["Floors"])
    create_floor_slab("Hallway", X_MID, Y_HALL_START, W_HALL, L_HALL, mats["wood_floor"], cols["Floors"])
    create_floor_slab("Closet1", X_MID + W_HALL, Y_HALL_START, W_CLOSET1, L_HALL, mats["wood_floor"], cols["Floors"])
    create_floor_slab("Bathroom2", X_MID, Y_B2_DIV, W_BATH2, L_BATH2, mats["tile_bath"], cols["Floors"])
    create_floor_slab("Closet2", X_MID, Y_0, W_BATH2, L_CLOSET2, mats["wood_floor"], cols["Floors"])
    create_floor_slab("Bedroom2", X_RIGHT_B2, Y_0, W_BED2, L_BED2, mats["wood_floor"], cols["Floors"])

    # 2. EXTERIOR WALLS
    wt = WALL_THICK_EXT
    create_wall("Ext_West", X_0 - wt, Y_0, wt, L_TOTAL, material=mats["wall_ext"], collection=cols["Walls"])
    create_wall("Ext_South_Kitchen", X_0, Y_0 - wt, W_LEFT, wt, material=mats["wall_ext"], collection=cols["Walls"])
    create_wall("Ext_South_Bed2", X_MID, Y_0 - wt, X_MAX - X_MID, wt, material=mats["wall_ext"], collection=cols["Walls"])
    create_wall("Ext_East", X_MAX, Y_0 - wt, wt, L_TOTAL + wt, material=mats["wall_ext"], collection=cols["Walls"])
    create_wall("Ext_North_Bed1", X_RIGHT_B1, Y_MAX, W_BED1 + wt, wt, material=mats["wall_ext"], collection=cols["Walls"])
    create_wall("Ext_North_Bath1", X_MID, Y_MAX, W_BATH1, wt, material=mats["wall_ext"], collection=cols["Walls"])
    create_wall("Ext_North_Living", X_0, Y_MAX, W_LEFT, wt, material=mats["wall_ext"], collection=cols["Walls"])

    # 3. INTERIOR WALLS
    wi = WALL_THICK_INT
    # Spine wall
    create_wall("Spine_North", X_MID, Y_B1_START, wi, L_BATH1, material=mats["wall_int"], collection=cols["Walls"])
    create_wall("Spine_South", X_MID, Y_0, wi, Y_HALL_START, material=mats["wall_int"], collection=cols["Walls"])

    door_gap = ft_in(2, 8.0)
    create_wall("Bath1_Bed1_Wall", X_RIGHT_B1, Y_B1_START + door_gap, wi, L_BATH1 - door_gap, material=mats["wall_int"], collection=cols["Walls"])
    create_wall("Bath1_Hall_Wall", X_MID, Y_B1_START, W_BATH1, wi, material=mats["wall_int"], collection=cols["Walls"])
    create_wall("Bed1_South_Wall", X_RIGHT_B1, Y_B1_START, W_BED1, wi, material=mats["wall_int"], collection=cols["Walls"])
    create_wall("Bed2_North_Wall", X_RIGHT_B2, Y_HALL_START, W_BED2, wi, material=mats["wall_int"], collection=cols["Walls"])
    create_wall("Bath2_Bed2_Wall", X_RIGHT_B2, Y_B2_DIV, wi, L_BATH2, material=mats["wall_int"], collection=cols["Walls"])
    create_wall("Bath2_Closet2_Wall", X_MID, Y_B2_DIV, W_BATH2, wi, material=mats["wall_int"], collection=cols["Walls"])

    # 4. KITCHEN FIXTURES
    island_w = ft_in(3, 8.0)
    island_d = ft_in(6, 6.0)
    island_x = X_0 + (W_LEFT - island_w) / 2.0
    island_y = Y_0 + ft_in(5, 0.0)
    create_box("Kitchen_Island_Base", island_x, island_y, 0.0, island_w, island_d, 0.88, material=mats["cabinet_wood"], collection=cols["Kitchen"])
    create_box("Kitchen_Island_Top", island_x - 0.05, island_y - 0.05, 0.88, island_w + 0.10, island_d + 0.25, 0.04, material=mats["counter_top"], collection=cols["Kitchen"])
    
    for i, offset_y in enumerate([0.5, 1.4]):
        create_box(f"Barstool_{i+1}", island_x + island_w + 0.08, island_y + offset_y, 0.0, 0.40, 0.40, 0.65, material=mats["wood_furniture"], collection=cols["Kitchen"])

    counter_depth = 0.65
    create_box("Kitchen_South_Counters", X_0 + 0.3, Y_0, 0.0, ft_in(14, 0.0), counter_depth, 0.90, material=mats["cabinet_wood"], collection=cols["Kitchen"])
    create_box("Kitchen_South_Top", X_0 + 0.3, Y_0, 0.90, ft_in(14, 0.0), counter_depth + 0.03, 0.04, material=mats["counter_top"], collection=cols["Kitchen"])

    create_box("Fridge", X_MID - 0.90, Y_0 + 0.8, 0.0, 0.85, 0.85, 1.80, material=mats["wall_ext"], collection=cols["Kitchen"])
    create_box("Range_Stove", X_MID - 0.75, Y_0 + 2.0, 0.0, 0.70, 0.75, 0.92, material=mats["cabinet_wood"], collection=cols["Kitchen"])

    # 5. BATHROOM FIXTURES
    create_box("Bath1_Double_Vanity", X_MID + wi, Y_B1_START + 0.3, 0.0, 0.60, 1.80, 0.85, material=mats["cabinet_wood"], collection=cols["Bathrooms"])
    create_box("Bath1_Vanity_Top", X_MID + wi, Y_B1_START + 0.3, 0.85, 0.62, 1.82, 0.03, material=mats["porcelain_white"], collection=cols["Bathrooms"])
    create_box("Bath1_Toilet", X_MID + wi, Y_B1_START + 2.4, 0.0, 0.50, 0.65, 0.45, material=mats["porcelain_white"], collection=cols["Bathrooms"])
    create_box("Bath1_Toilet_Tank", X_MID + wi, Y_B1_START + 2.4, 0.45, 0.25, 0.65, 0.40, material=mats["porcelain_white"], collection=cols["Bathrooms"])
    create_box("Bath1_Tub", X_MID + wi, Y_MAX - 1.0, 0.0, W_BATH1 - wi*2, 0.95, 0.55, material=mats["porcelain_white"], collection=cols["Bathrooms"])

    create_box("Bath2_Vanity", X_MID + wi, Y_B2_DIV + 1.2, 0.0, 0.55, 0.90, 0.85, material=mats["cabinet_wood"], collection=cols["Bathrooms"])
    create_box("Bath2_Toilet", X_MID + wi, Y_B2_DIV + 0.4, 0.0, 0.50, 0.65, 0.45, material=mats["porcelain_white"], collection=cols["Bathrooms"])
    create_box("Bath2_Tub", X_MID + wi, Y_B2_DIV - 0.05, 0.0, W_BATH2 - wi*2, 0.80, 0.50, material=mats["porcelain_white"], collection=cols["Bathrooms"])

    # 6. FURNITURE
    bed1_x = X_MAX - 2.20
    bed1_y = Y_B1_START + (L_BED1 - 2.0) / 2.0
    create_box("Bed1_Frame", bed1_x, bed1_y, 0.0, 2.10, 2.05, 0.35, material=mats["wood_furniture"], collection=cols["Furniture"])
    create_box("Bed1_Mattress", bed1_x + 0.05, bed1_y + 0.05, 0.35, 2.00, 1.95, 0.30, material=mats["bed_sheet"], collection=cols["Furniture"])
    create_box("Bed1_Headboard", bed1_x + 2.05, bed1_y, 0.0, 0.10, 2.05, 1.10, material=mats["wood_furniture"], collection=cols["Furniture"])
    create_box("Bed1_Nightstand_L", bed1_x + 1.5, bed1_y - 0.60, 0.0, 0.50, 0.50, 0.60, material=mats["wood_furniture"], collection=cols["Furniture"])
    create_box("Bed1_Nightstand_R", bed1_x + 1.5, bed1_y + 2.10, 0.0, 0.50, 0.50, 0.60, material=mats["wood_furniture"], collection=cols["Furniture"])

    bed2_x = X_MAX - 2.20
    bed2_y = Y_0 + (L_BED2 - 1.7) / 2.0
    create_box("Bed2_Frame", bed2_x, bed2_y, 0.0, 2.10, 1.65, 0.35, material=mats["wood_furniture"], collection=cols["Furniture"])
    create_box("Bed2_Mattress", bed2_x + 0.05, bed2_y + 0.05, 0.35, 2.00, 1.55, 0.28, material=mats["bed_sheet"], collection=cols["Furniture"])

    sofa_x = X_0 + 0.8
    sofa_y = L_KITCHEN + 1.2
    create_box("Sofa_Main", sofa_x, sofa_y, 0.0, 1.0, 2.4, 0.75, material=mats["fabric_sofa"], collection=cols["Furniture"])
    create_box("Sofa_Chaise", sofa_x + 1.0, sofa_y, 0.0, 1.2, 0.95, 0.45, material=mats["fabric_sofa"], collection=cols["Furniture"])
    create_box("Coffee_Table", sofa_x + 1.3, sofa_y + 1.0, 0.0, 0.85, 0.85, 0.40, material=mats["wood_furniture"], collection=cols["Furniture"])
    create_box("TV_Console", X_MID - 0.50, L_KITCHEN + 1.5, 0.0, 0.45, 1.80, 0.50, material=mats["wood_furniture"], collection=cols["Furniture"])
    create_box("TV_Screen", X_MID - 0.20, L_KITCHEN + 1.7, 0.75, 0.08, 1.40, 0.80, material=mats["wall_ext"], collection=cols["Furniture"])

    create_box("Desk_Office_1", X_0 + 0.2, Y_MAX - 0.9, 0.0, 1.40, 0.75, 0.75, material=mats["wood_furniture"], collection=cols["Furniture"])
    create_box("Desk_Office_2", X_MID - 1.6, Y_MAX - 0.9, 0.0, 1.40, 0.75, 0.75, material=mats["wood_furniture"], collection=cols["Furniture"])

    # 7. LIGHTING
    world = bpy.context.scene.world
    if not world:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.94, 0.96, 0.98, 1.0)
        bg.inputs["Strength"].default_value = 0.85

    room_lights = [
        ("Light_Living", X_0 + W_LEFT/2.0, L_KITCHEN + L_LIVING/2.0, 2.2, 80.0),
        ("Light_Kitchen", X_0 + W_LEFT/2.0, L_KITCHEN/2.0, 2.2, 90.0),
        ("Light_Bed1", X_RIGHT_B1 + W_BED1/2.0, Y_B1_START + L_BED1/2.0, 2.2, 70.0),
        ("Light_Bed2", X_RIGHT_B2 + W_BED2/2.0, Y_0 + L_BED2/2.0, 2.2, 70.0),
        ("Light_Bath1", X_MID + W_BATH1/2.0, Y_B1_START + L_BATH1/2.0, 2.0, 50.0),
        ("Light_Bath2", X_MID + W_BATH2/2.0, Y_B2_DIV + L_BATH2/2.0, 2.0, 40.0),
        ("Light_Hall", X_MID + W_HALL/2.0, Y_HALL_START + L_HALL/2.0, 2.0, 40.0),
    ]
    for l_name, lx, ly, lz, power in room_lights:
        light_data = bpy.data.lights.new(name=l_name, type='POINT')
        light_data.energy = power
        light_data.color = (1.0, 0.92, 0.82)
        light_obj = bpy.data.objects.new(name=l_name, object_data=light_data)
        light_obj.location = (lx, ly, lz)
        cols["Lighting"].objects.link(light_obj)

    sun_data = bpy.data.lights.new(name="Sun_Architectural", type='SUN')
    sun_data.energy = 2.5
    sun_data.color = (1.0, 0.97, 0.92)
    sun_obj = bpy.data.objects.new(name="Sun_Architectural", object_data=sun_data)
    sun_obj.location = (5.0, -5.0, 10.0)
    sun_obj.rotation_euler = (math.radians(50), math.radians(15), math.radians(-35))
    cols["Lighting"].objects.link(sun_obj)

    # 8. CAMERAS
    # Primary Isometric Overview Camera
    cam_data = bpy.data.cameras.new("Cam_Isometric")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 15.0
    cam_obj = bpy.data.objects.new("Cam_Isometric", cam_data)
    cam_obj.location = (-6.0, -6.0, 10.0)
    cam_obj.rotation_euler = (math.radians(54.7), 0, math.radians(-45.0))
    cols["Cameras"].objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj

    # 9. RENDER SETTINGS & BEAUTY PREVIEW
    scene = bpy.context.scene
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 64
    scene.cycles.use_denoising = False

    # 10. SAVE .BLEND & EXPORT .GLB
    print(f"Saving .blend to {BLEND_PATH}...")
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)

    print(f"Exporting GLB to {GLB_PATH}...")
    bpy.ops.export_scene.gltf(
        filepath=GLB_PATH,
        export_format='GLB',
        use_selection=False,
        export_apply=True,
        export_yup=True
    )
    glb_size_mb = os.path.getsize(GLB_PATH) / (1024 * 1024)
    print(f"Exported {GLB_PATH} ({glb_size_mb:.2f} MB)")

    # 11. RENDER PREVIEW IMAGE
    print(f"Rendering beauty preview to {PREVIEW_PATH}...")
    scene.render.filepath = PREVIEW_PATH
    scene.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)
    print(f"Preview rendered to {PREVIEW_PATH}!")

if __name__ == "__main__":
    generate_digital_twin()
