---
name: blender-3d-modeler
description: Procedural 3D modeling, mesh editing, Cycles raytracing, and interactive GLB export for autonomous agents driving the LXC 127 Blender compute engine (:8095/:9876).
---

# Blender 3D Modeler: Autonomous Agent Protocol

This skill guides autonomous agents in procedurally generating 3D models, editing meshes, setting up lighting and cameras, raytracing photorealistic preview stills, and exporting interactive `.glb` assets using the local cluster's headless Blender 4.0.2 compute engine on LXC 127 (`192.168.1.248`).

## 1. Dual-Mode Sampling Invariant
When rendering preview stills or exporting final models:
- **Fast Draft Mode (`samples=16`)**: Use during initial mesh shaping, topology adjustments, and iterative layout checks. Renders in **~1.8 seconds** with Cycles CPU without denoising.
- **Master High-Res Mode (`samples=64`)**: Use for final customer-facing presentations, portfolio exports, and fine lighting/reflection audits. Renders in **~6–8 seconds** with clean soft shadows.

## 2. Safe Geometry & Python (`bpy`) Rules
In Blender 4.0.2, always follow these rules when writing procedural Python scripts:
1. **Never Look Up Nodes by Name**: Node names are localized. Look up shader nodes by RNA type:
   ```python
   bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
   ```
2. **Principled BSDF 4.0 Inputs**:
   - Base Color: `bsdf.inputs["Base Color"].default_value = (R, G, B, 1.0)`
   - Roughness: `bsdf.inputs["Roughness"].default_value = 0.4`
   - Metallic: `bsdf.inputs["Metallic"].default_value = 0.0`
   - Emission: In Blender 4.0, use `bsdf.inputs["Emission Color"]` and `bsdf.inputs["Emission Strength"]`.
3. **Always Smooth Shading & Bevel**: For organic or hard-surface models, apply `bpy.ops.object.shade_smooth()` and add a subtle Bevel modifier to prevent razor-sharp CG edges.
4. **Apply Transforms Before Export**: Always apply rotation and scale before GLB export to prevent distortion in WebGL:
   ```python
   bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
   ```

## 3. Standard Camera & 3-Point Lighting Setup
Always provide clear directional definition:
- **Key Light**: High angle, 45° offset, warm tone (`color=(1.0, 0.95, 0.9)`, `energy=500–800W`).
- **Fill / Rim Light**: Opposite side, cooler tone (`color=(0.6, 0.8, 1.0)`, `energy=200–300W`).
- **Ground Shadow Plane**: Add a subtle matte ground plane or contact shadow caster.

## 4. MCP Tool Orchestration Lifecycle
To build a 3D model:
1. `blender_reset_scene()`: Clean existing geometry.
2. `blender_execute_code(code=..., render_preview=True, samples=16)`: Build base mesh and check fast draft render.
3. `blender_get_scene_info()`: Confirm object count, dimensions, and vertex bounds.
4. `blender_execute_code(...)`: Add secondary details, materials, and refine shapes.
5. `blender_export_glb(model_name=..., title=..., agent_creator=..., samples=64)`: Raytrace master 64-sample still and export interactive GLB.
6. Present the model to the user with the rendered image preview and the interactive `.glb` URL (`http://192.168.1.248:8095/api/v1/assets/models/{name}.glb`).
