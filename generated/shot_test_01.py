import bpy
import math
import random

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
    cam = bpy.data.cameras.new(name)
    cam.lens = focal_length
    cam_obj = bpy.data.objects.new(name, cam)
    cam_obj.location = location
    cam_obj.rotation_euler = rotation_euler
    bpy.context.collection.objects.link(cam_obj)
    return cam_obj

def add_character_placeholder(
    alias: str,
    location: tuple,
    facing: str = "forward",
    scale: tuple = (1.0, 1.0, 1.0),
) -> bpy.types.Object:
    obj = bpy.data.objects.new(alias, None)
    obj.location = location
    obj.scale = scale
    obj["eras_alias"] = alias
    obj["eras_type"] = "character"
    bpy.context.collection.objects.link(obj)
    return obj

def add_light(
    name: str = "LIGHT_key",
    location: tuple = (0.0, 0.0, 5.0),
    rotation_euler: tuple = (math.radians(90), 0.0, 0.0),
) -> bpy.types.Object:
    light = bpy.data.lights.new(name, type='POINT')
    light_obj = bpy.data.objects.new(name, light)
    light_obj.location = location
    light_obj.rotation_euler = rotation_euler
    bpy.context.collection.objects.link(light_obj)
    return light_obj

def main():
    print("[ERAS] Starting shot_test_01")
    clear_scene()
    print("[ERAS] Scene cleared")
    
    cam = add_camera(name="CAM_main", location=(0.0, -5.0, 1.7), rotation_euler=(math.radians(90), 0.0, 0.0), focal_length=50.0, shot_type="medium")
    print("[ERAS] Camera added")
    
    char_c1 = add_character_placeholder(alias="CHAR_C1", location=(-1.0, 0.0, 0.0), facing="forward", scale=(1.0, 1.0, 1.0))
    print("[ERAS] Character C1 added")
    
    char_v1 = add_character_placeholder(alias="CHAR_V1", location=(1.0, 0.0, 0.0), facing="forward", scale=(1.0, 1.0, 1.0))
    print("[ERAS] Character V1 added")
    
    light_key = add_light(name="LIGHT_key", location=(0.0, 0.0, 5.0), rotation_euler=(math.radians(90), 0.0, 0.0))
    print("[ERAS] Light added")
    
    bpy.context.scene.render.engine = 'BLENDER_EEVEE'
    print("[ERAS] Render engine set to BLENDER_EEVEE")
    
    bpy.context.scene.render.resolution = (1920, 1080)
    print("[ERAS] Resolution set to 1920x1080")
    
    bpy.context.scene.render.resolution_percentage = 100
    print("[ERAS] Resolution percentage set to 100")
    
    bpy.context.scene.frame_end = 100
    print("[ERAS] Frame end set to 100")
    
    for frame in range(bpy.context.scene.frame_end):
        cam.location = (0.0, -5.0 + random.uniform(-0.1, 0.1), 1.7 + random.uniform(-0.1, 0.1))
        cam.keyframe_insert(data_path="location", frame=frame)
        cam.rotation_euler = (math.radians(90) + random.uniform(-0.01, 0.01), 0.0 + random.uniform(-0.01, 0.01), 0.0 + random.uniform(-0.01, 0.01))
        cam.keyframe_insert(data_path="rotation_euler", frame=frame)
    
    bpy.context.scene.camera = cam
    print("[ERAS] Camera set as active camera")
    
    bpy.ops.render.render(write_still=True)
    print("[ERAS] Rendering complete")

if __name__ == "__main__":
    main()