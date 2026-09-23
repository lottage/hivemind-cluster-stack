# Citadel 3D: Multi-Tier Procedural Micro-Worlds & Workstation Deck

Citadel 3D is a lightweight, zero-binary-asset 3D spatial interface for the StoneSage sovereign AI cluster. It visualizes sovereign AI agents working in high-fidelity procedural architectural environments with real-time HUD telemetry.

---

## 1. Features & Architecture

- **Zero External Assets**: All 3D geometry is procedurally generated using Three.js (r128). All textures (parquet, marble, circuit traces, stone bricks, frost) are generated dynamically on HTML5 canvases via `texture_generator.js`.
- **5 High-Fidelity Environments**:
  1. **Victorian Greenhouse**: Curved iron trusses, double-glazed transparent canopy, multi-tier planter boxes, tropical plants, and polished marble tiles.
  2. **Modern Industrial Loft**: Double-height open space, mezzanine lounge, spiral/straight exact parametric staircases, and herringbone parquet.
  3. **Gothic Manor**: Pointed rib vaults, stained glass tracery, antique mahogany bookcases, and warm flickering candelabra lighting.
  4. **Arctic Research Outpost**: Geodesic dome exterior, insulated sub-zero floor tiles, frosted observation portals, and tundra terrain.
  5. **Cyberpunk Den**: Subterranean hacker sanctum, glowing neon light tubing, server rack stacks, and holographic circuit floor.
- **Parametric Architectural Invariants**:
  - **Exact Staircases (`createExactStaircase`)**: Perfectly anchors steps between floor levels:
    $$\text{Riser} = \frac{\text{height}}{N}, \quad \text{Tread} = \frac{\text{depth}}{N}$$
    Steps are grouped in a single base-aligned pivot group so compound parent rotations cleanly line up with mezzanine openings.
- **Agent Inspector HUD**:
  - Click any 3D agent avatar in the scene to open a floating retro Windows 95 inspector window.
  - Displays agent ID, assigned model, active reasoning task, and token throughput.
- **Ambient Audio Synthesizer**:
  - Procedural sound generator using the Web Audio API (gentle rain on glass, server fan hum, wind howl, crackling fireplace) with mute toggle.

---

## 2. Directory Layout

```
citadel3d/
├── index.html               # Main viewport, HUD modal, environment dropdown
├── app.js                   # Scene graph orchestrator, camera controls, agent updates
├── texture_generator.js     # HTML5 Canvas procedural texture generators
├── environments/
│   ├── greenhouse.js        # Victorian conservatory geometry & lighting
│   ├── modern_loft.js       # Industrial loft & mezzanine geometry
│   ├── gothic_manor.js      # Stone vaulting & stained glass geometry
│   ├── arctic_camp.js       # Geodesic dome & frost terrain geometry
│   └── cyberpunk_den.js     # Neon tubes, server racks & glowing circuits
└── vendor/
    ├── three.min.js         # Three.js r128 (local bundle)
    └── OrbitControls.js     # Orbit navigation controls
```

---

## 3. Usage & Deployment

### Local Development:
Served automatically by the StoneSage backend:
```
http://localhost:8080/citadel3d/
```

### Production Homelab Deployment:
Deployed on Node 2 (`bigserv` / LXC 120 `stonesage` @ `192.168.1.167`):
```
http://192.168.1.167:8080/citadel3d/
```

### Controls:
- **Orbit**: Left Click + Drag
- **Pan**: Right Click + Drag (or Shift + Left Click)
- **Zoom**: Mouse Wheel
- **Select Environment**: Dropdown menu at bottom of screen, or keyboard keys `1`–`5`.
- **Inspect Agent**: Click directly on an agent avatar in 3D space.
