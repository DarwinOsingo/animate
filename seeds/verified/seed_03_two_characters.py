"""
ERAS Seed Script 03 — Two Character Placement
Blender 5.1 | bpy Python API
Shot type: character_placement
Tags: character, positioning, foreground, background, facing, two_character
Usage: blender --background --python seeds/seed_03_two_characters.py
"""
import bpy
import math


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for block_collection in [bpy.data.meshes, bpy.data.cameras, bpy.data.lights]:
        for block in block_collection:
            if block.users == 0:
                block_collection.remove(block)


def add_character_placeholder(
    alias: str,
    location: tuple,
    facing: str = "forward",
    scale: tuple = (1.0, 1.0, 1.0),
) -> bpy.types.Object:
    """
    Add a character placeholder (cube) at position.
    In production, replace with armature import.
    alias:  ERAS alias e.g. 'C1', 'V1'
    facing: 'forward' | 'left' | 'right' | 'backward'
    """
    facing_rotation = {
        "forward":  (0.0, 0.0, 0.0),
        "left":     (0.0, 0.0, math.radians(90)),
        "right":    (0.0, 0.0, math.radians(-90)),
        "backward": (0.0, 0.0, math.radians(180)),
    }
    rotation = facing_rotation.get(facing, (0.0, 0.0, 0.0))

    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.active_object
    obj.name = f"CHAR_{alias}"
    obj.scale = scale
    obj.rotation_euler = rotation

    # Tag with ERAS alias as custom property
    obj["eras_alias"] = alias
    obj["eras_type"] = "character"

    print(f"[ERAS] Character {alias} placed at {location}, facing {facing}")
    return obj


def face_each_other(obj_a: bpy.types.Object, obj_b: bpy.types.Object):
    """Rotate both characters to face each other on Z axis."""
    import mathutils
    dir_a = (mathutils.Vector(obj_b.location) - mathutils.Vector(obj_a.location))
    dir_b = -dir_a
    obj_a.rotation_euler[2] = math.atan2(dir_a.x, -dir_a.y)
    obj_b.rotation_euler[2] = math.atan2(dir_b.x, -dir_b.y)
    print(f"[ERAS] {obj_a.name} and {obj_b.name} facing each other")


def add_camera_for_two_shot(
    subject_a: bpy.types.Object,
    subject_b: bpy.types.Object,
) -> bpy.types.Object:
    """Position camera to frame both characters in a medium two-shot."""
    import mathutils
    midpoint = (
        mathutils.Vector(subject_a.location) +
        mathutils.Vector(subject_b.location)
    ) / 2.0

    cam_location = (midpoint.x, midpoint.y - 4.5, midpoint.z + 1.2)
    bpy.ops.object.camera_add(
        location=cam_location,
        rotation=(math.radians(85), 0.0, 0.0),
    )
    cam = bpy.context.active_object
    cam.name = "CAM_two_shot"
    cam.data.lens = 50.0
    bpy.context.scene.camera = cam
    print(f"[ERAS] Two-shot camera placed at {cam_location}")
    return cam


def main():
    clear_scene()

    # C1 — protagonist, foreground left
    c1 = add_character_placeholder(
        alias="C1",
        location=(-0.8, 0.0, 0.0),
        facing="right",
        scale=(0.5, 0.5, 1.0),
    )

    # V1 — antagonist, foreground right
    v1 = add_character_placeholder(
        alias="V1",
        location=(0.8, 0.0, 0.0),
        facing="left",
        scale=(0.5, 0.5, 1.0),
    )

    face_each_other(c1, v1)
    add_camera_for_two_shot(c1, v1)

    print("[ERAS] seed_03_two_characters complete.")
    print(f"[ERAS] C1 position: {list(c1.location)}")
    print(f"[ERAS] V1 position: {list(v1.location)}")


if __name__ == "__main__":
    main()