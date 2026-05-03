"""
ERAS Seed Script 08 — Full Shot Template
Blender 5.1 | bpy Python API
Shot type: full_shot
Tags: full_shot, camera, lighting, characters, two_character, medium, dramatic
Usage: blender --background --python seeds/seed_08_full_shot.py

This is the canonical full-shot template Phi-4 will pattern-match against.
It combines: scene init, camera, two characters, three-point lighting, render config.
All components follow ERAS alias conventions.
"""
import bpy
import math
import os
import mathutils


# ── Registry snapshot (injected by pipeline at runtime) ──────────────────────
# In production this comes from the ERAS entity registry.
# Hardcoded here for seed verification.
REGISTRY = {
    "C1": {
        "alias": "C1", "type": "character",
        "position": "foreground_left", "facing": "right",
        "stance": "offensive", "scale": (0.5, 0.5, 1.0),
    },
    "V1": {
        "alias": "V1", "type": "character",
        "position": "foreground_right", "facing": "left",
        "stance": "defensive", "scale": (0.5, 0.5, 1.0),
    },
    "BG1": {
        "alias": "BG1", "type": "background",
        "lighting_mood": "dramatic",
    },
}

SHOT = {
    "alias": "shot_008",
    "type": "confrontation",
    "camera_type": "medium",
    "camera_style": "handheld",
    "frame_start": 1,
    "frame_end": 48,
    "output_path": "/tmp/eras_renders/shot_008_",
}
# ─────────────────────────────────────────────────────────────────────────────


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for col in [bpy.data.meshes, bpy.data.cameras, bpy.data.lights, bpy.data.armatures]:
        for block in col:
            if block.users == 0:
                col.remove(block)


def configure_render(shot: dict):
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.frame_start = shot["frame_start"]
    scene.frame_end   = shot["frame_end"]
    scene.render.filepath = shot["output_path"]
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode  = 'RGBA'
    scene.render.film_transparent = True
    scene.eevee.taa_render_samples = 64
    os.makedirs(os.path.dirname(shot["output_path"]), exist_ok=True)
    print(f"[ERAS] Render configured — {scene.render.resolution_x}x{scene.render.resolution_y}, "
          f"frames {scene.frame_start}-{scene.frame_end}")


def place_character(entry: dict) -> bpy.types.Object:
    position_map = {
        "foreground_left":   (-0.8, 0.0, 0.0),
        "foreground_right":  (0.8,  0.0, 0.0),
        "background_left":   (-1.5, 2.0, 0.0),
        "background_right":  (1.5,  2.0, 0.0),
        "center":            (0.0,  0.0, 0.0),
    }
    facing_map = {
        "right":    math.radians(90),
        "left":     math.radians(-90),
        "forward":  0.0,
        "backward": math.radians(180),
    }
    loc = position_map.get(entry.get("position", "center"), (0.0, 0.0, 0.0))
    rot_z = facing_map.get(entry.get("facing", "forward"), 0.0)

    bpy.ops.mesh.primitive_cube_add(location=loc)
    obj = bpy.context.active_object
    obj.name = f"CHAR_{entry['alias']}"
    obj.scale = entry.get("scale", (0.5, 0.5, 1.0))
    obj.rotation_euler = (0.0, 0.0, rot_z)
    obj["eras_alias"] = entry["alias"]
    obj["eras_type"]  = "character"
    print(f"[ERAS] {entry['alias']} placed at {loc}, facing {entry.get('facing')}")
    return obj


def setup_camera(shot: dict, subjects: list) -> bpy.types.Object:
    focal_map = {"wide": 24.0, "medium": 50.0, "close": 85.0, "extreme_close": 135.0}
    focal = focal_map.get(shot["camera_type"], 50.0)

    # Frame midpoint of all subjects
    if subjects:
        mid = sum((mathutils.Vector(s.location) for s in subjects), mathutils.Vector()) / len(subjects)
    else:
        mid = mathutils.Vector((0, 0, 0))

    cam_loc = (mid.x, mid.y - 5.0, mid.z + 1.5)
    bpy.ops.object.camera_add(
        location=cam_loc,
        rotation=(math.radians(87), 0.0, 0.0),
    )
    cam = bpy.context.active_object
    cam.name = "CAM_main"
    cam.data.lens = focal
    cam.data.clip_start = 0.1
    cam.data.clip_end = 500.0
    bpy.context.scene.camera = cam

    # Handheld shake — baked keyframes (Blender 5.1 compatible)
    if shot.get("camera_style") == "handheld":
        import random
        random.seed(42)
        scene = bpy.context.scene
        base_x, base_z = cam.location.x, cam.location.z
        for frame in range(scene.frame_start, scene.frame_end + 1, 2):
            scene.frame_set(frame)
            cam.location.x = base_x + random.uniform(-0.02, 0.02)
            cam.location.z = base_z + random.uniform(-0.01, 0.01)
            cam.keyframe_insert(data_path="location", index=0, frame=frame)
            cam.keyframe_insert(data_path="location", index=2, frame=frame)
        scene.frame_set(scene.frame_start)

    print(f"[ERAS] Camera '{cam.name}' — {shot['camera_type']} {focal}mm, style: {shot['camera_style']}")
    return cam


def setup_lighting(mood: str = "dramatic"):
    mood_configs = {
        "dramatic": {
            "key":  {"energy": 1200, "color": (1.0, 0.85, 0.7)},
            "fill": {"energy": 80,   "color": (0.2, 0.2, 0.4)},
            "rim":  {"energy": 600,  "color": (0.8, 0.9, 1.0)},
        },
        "neutral": {
            "key":  {"energy": 800,  "color": (1.0, 0.98, 0.95)},
            "fill": {"energy": 200,  "color": (0.9, 0.95, 1.0)},
            "rim":  {"energy": 400,  "color": (1.0, 1.0,  1.0)},
        },
    }
    cfg = mood_configs.get(mood, mood_configs["neutral"])

    lights = [
        ("LIGHT_key",  "AREA",  (-2.5, -2.0, 3.0), (math.radians(60), 0, math.radians(-40)), cfg["key"]),
        ("LIGHT_fill", "AREA",  ( 2.0, -1.5, 1.5), (math.radians(45), 0, math.radians(50)),  cfg["fill"]),
        ("LIGHT_rim",  "SPOT",  ( 1.0,  3.0, 2.5), (math.radians(-45),0, math.radians(160)), cfg["rim"]),
    ]
    for name, ltype, loc, rot, lcfg in lights:
        bpy.ops.object.light_add(type=ltype, location=loc, rotation=rot)
        l = bpy.context.active_object
        l.name = name
        l.data.energy = lcfg["energy"]
        l.data.color  = lcfg["color"]
        print(f"[ERAS] Light '{name}' ({ltype}) energy={lcfg['energy']}")


def main():
    clear_scene()
    configure_render(SHOT)

    # Place characters from registry
    chars = []
    for alias, entry in REGISTRY.items():
        if entry["type"] == "character":
            chars.append(place_character(entry))

    # Camera framing all characters
    cam = setup_camera(SHOT, chars)

    # Lighting from BG mood
    bg_mood = REGISTRY.get("BG1", {}).get("lighting_mood", "neutral")
    setup_lighting(mood=bg_mood)

    print("\n[ERAS] seed_08_full_shot complete.")
    print(f"[ERAS] Shot: {SHOT['alias']} | Camera: {cam.name} | Characters: {[c.name for c in chars]}")
    print(f"[ERAS] Engine: {bpy.context.scene.render.engine}")
    print(f"[ERAS] Output: {bpy.context.scene.render.filepath}")


if __name__ == "__main__":
    main()