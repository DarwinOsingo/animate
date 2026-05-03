"""
ERAS Seed Script 02 — Camera Setup
Blender 5.1 | bpy Python API
Shot type: camera_setup
Tags: camera, focal_length, handheld, position, rotation
Usage: blender --background --python seeds/seed_02_camera.py
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


def add_camera(
    name: str = "CAM_main",
    location: tuple = (0.0, -5.0, 1.7),
    rotation_euler: tuple = (math.radians(90), 0.0, 0.0),
    focal_length: float = 50.0,
    shot_type: str = "medium",
) -> bpy.types.Object:
    """
    Add and configure a camera.
    shot_type: 'wide' | 'medium' | 'close' | 'extreme_close'
    focal lengths: wide=24, medium=50, close=85, extreme_close=135
    """
    focal_map = {
        "wide": 24.0,
        "medium": 50.0,
        "close": 85.0,
        "extreme_close": 135.0,
    }
    focal_length = focal_map.get(shot_type, focal_length)

    bpy.ops.object.camera_add(location=location, rotation=rotation_euler)
    cam_obj = bpy.context.active_object
    cam_obj.name = name
    cam_obj.data.name = name + "_data"
    cam_obj.data.lens = focal_length
    cam_obj.data.clip_start = 0.1
    cam_obj.data.clip_end = 500.0

    # Set as scene camera
    bpy.context.scene.camera = cam_obj
    print(f"[ERAS] Camera '{name}' added — {shot_type} shot, {focal_length}mm")
    return cam_obj


def add_handheld_shake(cam_obj: bpy.types.Object, intensity: float = 0.02):
    """
    Handheld camera shake via baked random keyframes.
    Blender 5.1 removed direct action.fcurves — we bake keyframes instead.
    intensity: 0.01 = subtle, 0.05 = aggressive
    """
    import random
    random.seed(42)  # deterministic so re-runs are consistent

    scene = bpy.context.scene
    base_x = cam_obj.location.x
    base_z = cam_obj.location.z

    for frame in range(scene.frame_start, scene.frame_end + 1, 2):
        scene.frame_set(frame)
        cam_obj.location.x = base_x + random.uniform(-intensity, intensity)
        cam_obj.location.z = base_z + random.uniform(-intensity * 0.5, intensity * 0.5)
        cam_obj.keyframe_insert(data_path="location", index=0, frame=frame)
        cam_obj.keyframe_insert(data_path="location", index=2, frame=frame)

    # Reset to base on frame 1
    scene.frame_set(scene.frame_start)
    print(f"[ERAS] Handheld shake baked — intensity {intensity}")


def main():
    clear_scene()

    cam = add_camera(
        name="CAM_main",
        location=(0.0, -5.0, 1.7),
        rotation_euler=(math.radians(90), 0.0, 0.0),
        shot_type="medium",
    )

    add_handheld_shake(cam, intensity=0.02)

    print("[ERAS] seed_02_camera complete.")
    print(f"[ERAS] Camera: {cam.name}, lens: {cam.data.lens}mm")


if __name__ == "__main__":
    main()