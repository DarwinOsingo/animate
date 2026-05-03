"""
ERAS Seed Script 05 — Character Pose
Blender 5.1 | bpy Python API
Shot type: character_pose
Tags: armature, animation, pose, character, rigging
Usage: blender --background --python seeds/seed_05_character_pose.py
"""
import bpy
import math


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for col in [bpy.data.meshes, bpy.data.armatures, bpy.data.objects]:
        for block in col:
            if block.users == 0:
                col.remove(block)


def add_simple_armature(name: str = "ARM_character", location: tuple = (0.0, 0.0, 0.0)) -> bpy.types.Object:
    """
    Add a simple humanoid armature for character posing.
    Returns the armature object.
    """
    bpy.ops.object.armature_add(location=location)
    arm_obj = bpy.context.active_object
    arm_obj.name = name
    arm_obj.data.name = name + "_data"
    
    # Enter edit mode to create bones
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    arm = arm_obj.data
    
    # Create simple bone structure: root, spine, arm, leg
    bones_data = {
        "root": {"head": (0, 0, 0), "tail": (0, 0, 0.1), "parent": None},
        "spine": {"head": (0, 0, 0.1), "tail": (0, 0, 0.5), "parent": "root"},
        "arm_l": {"head": (0, 0, 0.4), "tail": (-0.3, 0, 0.3), "parent": "spine"},
        "arm_r": {"head": (0, 0, 0.4), "tail": (0.3, 0, 0.3), "parent": "spine"},
        "leg_l": {"head": (0, 0, 0.1), "tail": (-0.1, 0, -0.5), "parent": "root"},
        "leg_r": {"head": (0, 0, 0.1), "tail": (0.1, 0, -0.5), "parent": "root"},
    }
    
    bones_map = {}
    for bone_name, data in bones_data.items():
        edit_bone = arm.edit_bones.new(bone_name)
        edit_bone.head = data["head"]
        edit_bone.tail = data["tail"]
        if data["parent"] and data["parent"] in bones_map:
            edit_bone.parent = bones_map[data["parent"]]
        bones_map[bone_name] = edit_bone
    
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"[ERAS] Armature '{name}' created with {len(bones_data)} bones")
    return arm_obj


def set_pose(arm_obj: bpy.types.Object, pose_name: str = "neutral"):
    """
    Apply a named pose to the armature.
    pose_name: 'neutral', 'offensive', 'defensive', 'relaxed'
    """
    pose_configs = {
        "neutral": {
            "arm_l": {"rotation_euler": (0, 0, math.radians(-90))},
            "arm_r": {"rotation_euler": (0, 0, math.radians(90))},
            "leg_l": {"rotation_euler": (0, 0, 0)},
            "leg_r": {"rotation_euler": (0, 0, 0)},
        },
        "offensive": {
            "arm_l": {"rotation_euler": (math.radians(-45), 0, math.radians(-90))},
            "arm_r": {"rotation_euler": (math.radians(45), 0, math.radians(90))},
            "leg_l": {"rotation_euler": (math.radians(-20), 0, 0)},
            "leg_r": {"rotation_euler": (math.radians(20), 0, 0)},
        },
        "defensive": {
            "arm_l": {"rotation_euler": (math.radians(90), 0, math.radians(-60))},
            "arm_r": {"rotation_euler": (math.radians(90), 0, math.radians(60))},
            "leg_l": {"rotation_euler": (math.radians(-10), 0, 0)},
            "leg_r": {"rotation_euler": (math.radians(10), 0, 0)},
        },
        "relaxed": {
            "arm_l": {"rotation_euler": (0, 0, math.radians(-60))},
            "arm_r": {"rotation_euler": (0, 0, math.radians(60))},
            "leg_l": {"rotation_euler": (0, 0, 0)},
            "leg_r": {"rotation_euler": (0, 0, 0)},
        },
    }
    
    config = pose_configs.get(pose_name, pose_configs["neutral"])
    bpy.ops.object.mode_set(mode='POSE')
    
    for bone_name, transforms in config.items():
        if bone_name in arm_obj.pose.bones:
            pose_bone = arm_obj.pose.bones[bone_name]
            if "rotation_euler" in transforms:
                pose_bone.rotation_euler = transforms["rotation_euler"]
    
    bpy.ops.object.mode_set(mode='OBJECT')
    print(f"[ERAS] Pose '{pose_name}' applied to {arm_obj.name}")


def add_mesh_body(arm_obj: bpy.types.Object, name: str = "MESH_body") -> bpy.types.Object:
    """
    Add a simple mesh body (cube) for visualization.
    """
    bpy.ops.mesh.primitive_cube_add(location=arm_obj.location, size=0.3)
    mesh_obj = bpy.context.active_object
    mesh_obj.name = name
    mesh_obj.scale = (0.3, 0.15, 0.5)
    
    # Parent mesh to armature
    mesh_obj.parent = arm_obj
    mesh_obj.parent_type = 'OBJECT'
    
    print(f"[ERAS] Mesh '{name}' added and parented to {arm_obj.name}")
    return mesh_obj


def main():
    clear_scene()
    
    # Create armature
    arm = add_simple_armature(name="ARM_character", location=(0.0, 0.0, 0.0))
    
    # Apply pose
    set_pose(arm, pose_name="offensive")
    
    # Add mesh body for visualization
    mesh = add_mesh_body(arm, name="MESH_body")
    
    # Configure scene
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 48
    
    print("[ERAS] seed_05_character_pose complete.")
    print(f"[ERAS] Armature: {arm.name}, Mesh: {mesh.name}")


if __name__ == "__main__":
    main()