"""
ERAS Seed Script 01 — Scene Init & Headless Render Config
Blender 5.1 | bpy Python API
Usage: blender --background --python seed_01_scene_init.py
"""

import bpy
import os


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    for block_collection in [
        bpy.data.meshes,
        bpy.data.cameras,
        bpy.data.lights,
    ]:
        for data_block in block_collection:
            if data_block.users == 0:
                block_collection.remove(data_block)


def configure_render(output_path: str, frame_start: int = 1, frame_end: int = 24):
    scene = bpy.context.scene

    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100

    scene.frame_start = frame_start
    scene.frame_end = frame_end
    scene.frame_set(frame_start)

    scene.render.filepath = output_path
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.film_transparent = True


def configure_eevee():
    scene = bpy.context.scene
    eevee = scene.eevee
    eevee.taa_render_samples = 64


def main():
    output_dir = "/tmp/eras_renders"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "shot_")

    clear_scene()
    configure_render(output_path=output_path, frame_start=1, frame_end=24)
    configure_eevee()

    print("[ERAS] Scene init complete.")
    print(f"[ERAS] Engine: {bpy.context.scene.render.engine}")
    print(f"[ERAS] Resolution: {bpy.context.scene.render.resolution_x}x{bpy.context.scene.render.resolution_y}")
    print(f"[ERAS] Output: {bpy.context.scene.render.filepath}")
    print(f"[ERAS] Frames: {bpy.context.scene.frame_start} - {bpy.context.scene.frame_end}")


if __name__ == "__main__":
    main()