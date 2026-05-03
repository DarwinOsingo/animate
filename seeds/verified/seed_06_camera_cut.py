"""
ERAS Seed Script 06 — Camera Cut
Blender 5.1 | bpy Python API
Shot type: camera_cut
Tags: camera, cut, multi_camera, scene, marker, switch
Usage: blender --background --python seeds/seed_06_camera_cut.py
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
    name: str,
    location: tuple,
    rotation_euler: tuple,
    focal_length: float = 50.0,
) -> bpy.types.Object:
    bpy.ops.object.camera_add(location=location, rotation=rotation_euler)
    cam = bpy.context.active_object
    cam.name = name
    cam.data.name = name + "_data"
    cam.data.lens = focal_length
    cam.data.clip_start = 0.1
    cam.data.clip_end = 500.0
    print(f"[ERAS] Camera '{name}' at {location}, {focal_length}mm")
    return cam


def add_camera_cut(
    scene: bpy.types.Scene,
    cam_obj: bpy.types.Object,
    frame: int,
):
    """
    Add a timeline marker that switches to cam_obj at the given frame.
    This is Blender's native camera cut mechanism.
    """
    scene.timeline_markers.new(name=f"cut_{cam_obj.name}_f{frame}", frame=frame)
    marker = next(
        m for m in scene.timeline_markers
        if m.name == f"cut_{cam_obj.name}_f{frame}"
    )
    marker.camera = cam_obj
    print(f"[ERAS] Camera cut to '{cam_obj.name}' at frame {frame}")


def main():
    clear_scene()

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 48

    # Camera A — wide establishing shot
    cam_a = add_camera(
        name="CAM_wide",
        location=(0.0, -8.0, 2.0),
        rotation_euler=(math.radians(85), 0.0, 0.0),
        focal_length=24.0,
    )

    # Camera B — close shot
    cam_b = add_camera(
        name="CAM_close",
        location=(-0.5, -2.5, 1.6),
        rotation_euler=(math.radians(88), 0.0, math.radians(-5)),
        focal_length=85.0,
    )

    # Set initial camera
    scene.camera = cam_a

    # Cut from CAM_wide at frame 1 to CAM_close at frame 25
    add_camera_cut(scene, cam_a, frame=1)
    add_camera_cut(scene, cam_b, frame=25)

    print("[ERAS] seed_06_camera_cut complete.")
    print(f"[ERAS] Cut schedule: CAM_wide f1 → CAM_close f25")
    print(f"[ERAS] Total frames: {scene.frame_start} - {scene.frame_end}")


if __name__ == "__main__":
    main()