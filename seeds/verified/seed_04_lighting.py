"""
ERAS Seed Script 04 — Three-Point Lighting Rig
Blender 5.1 | bpy Python API
Shot type: lighting_rig
Tags: lighting, three_point, key_light, fill_light, rim_light, mood
Usage: blender --background --python seeds/seed_04_lighting.py
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


def add_light(
    name: str,
    light_type: str,
    location: tuple,
    rotation_euler: tuple,
    energy: float,
    color: tuple = (1.0, 1.0, 1.0),
    radius: float = 0.5,
) -> bpy.types.Object:
    """
    Add a light to the scene.
    light_type: 'POINT' | 'SUN' | 'SPOT' | 'AREA'
    """
    bpy.ops.object.light_add(
        type=light_type,
        location=location,
        rotation=rotation_euler,
    )
    light_obj = bpy.context.active_object
    light_obj.name = name
    light_obj.data.name = name + "_data"
    light_obj.data.energy = energy
    light_obj.data.color = color

    if light_type in ('POINT', 'SPOT'):
        light_obj.data.shadow_soft_size = radius
    elif light_type == 'AREA':
        light_obj.data.size = radius * 2

    print(f"[ERAS] Light '{name}' ({light_type}) — energy {energy}, color {color}")
    return light_obj


def three_point_rig(
    subject_location: tuple = (0.0, 0.0, 0.0),
    mood: str = "neutral",
) -> dict:
    """
    Standard three-point lighting rig centered on subject.
    mood: 'neutral' | 'dramatic' | 'warm' | 'cold' | 'dusk'
    Returns dict of light objects.
    """
    mood_config = {
        "neutral": {
            "key_color":  (1.0, 0.98, 0.95),
            "fill_color": (0.9, 0.95, 1.0),
            "rim_color":  (1.0, 1.0, 1.0),
            "key_energy": 800, "fill_energy": 200, "rim_energy": 400,
        },
        "dramatic": {
            "key_color":  (1.0, 0.85, 0.7),
            "fill_color": (0.2, 0.2, 0.4),
            "rim_color":  (0.8, 0.9, 1.0),
            "key_energy": 1200, "fill_energy": 80, "rim_energy": 600,
        },
        "warm": {
            "key_color":  (1.0, 0.85, 0.6),
            "fill_color": (1.0, 0.7, 0.4),
            "rim_color":  (1.0, 0.9, 0.7),
            "key_energy": 700, "fill_energy": 250, "rim_energy": 350,
        },
        "cold": {
            "key_color":  (0.7, 0.85, 1.0),
            "fill_color": (0.5, 0.6, 0.9),
            "rim_color":  (0.8, 0.9, 1.0),
            "key_energy": 700, "fill_energy": 200, "rim_energy": 500,
        },
        "dusk": {
            "key_color":  (1.0, 0.5, 0.2),
            "fill_color": (0.3, 0.2, 0.5),
            "rim_color":  (0.9, 0.6, 0.3),
            "key_energy": 600, "fill_energy": 150, "rim_energy": 800,
        },
    }
    cfg = mood_config.get(mood, mood_config["neutral"])
    sx, sy, sz = subject_location

    key = add_light(
        name="LIGHT_key",
        light_type="AREA",
        location=(sx - 2.5, sy - 2.0, sz + 3.0),
        rotation_euler=(math.radians(60), 0.0, math.radians(-40)),
        energy=cfg["key_energy"],
        color=cfg["key_color"],
        radius=1.5,
    )
    fill = add_light(
        name="LIGHT_fill",
        light_type="AREA",
        location=(sx + 2.0, sy - 1.5, sz + 1.5),
        rotation_euler=(math.radians(45), 0.0, math.radians(50)),
        energy=cfg["fill_energy"],
        color=cfg["fill_color"],
        radius=2.0,
    )
    rim = add_light(
        name="LIGHT_rim",
        light_type="SPOT",
        location=(sx + 1.0, sy + 3.0, sz + 2.5),
        rotation_euler=(math.radians(-45), 0.0, math.radians(160)),
        energy=cfg["rim_energy"],
        color=cfg["rim_color"],
        radius=0.3,
    )

    print(f"[ERAS] Three-point rig complete — mood: {mood}")
    return {"key": key, "fill": fill, "rim": rim}


def main():
    clear_scene()

    lights = three_point_rig(
        subject_location=(0.0, 0.0, 0.0),
        mood="dramatic",
    )

    print("[ERAS] seed_04_lighting complete.")
    for role, obj in lights.items():
        print(f"[ERAS] {role}: {obj.name} at {list(obj.location)}")


if __name__ == "__main__":
    main()