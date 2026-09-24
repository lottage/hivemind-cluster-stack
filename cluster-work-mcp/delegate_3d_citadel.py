"""
Delegation Orchestrator for 3D Citadel & Physical Kanban Project.
Dispatches coding tasks across cluster models (Coordinator :8001, Worker :8002, Ally Z1 :1234)
using calibrated sampling parameters to maximize code synthesis success.
"""

import os
import sys
import json
import time

from cluster_client import ClusterClient

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "StoneSage", "frontend", "citadel3d"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

client = ClusterClient()

def extract_code_block(text: str, default_ext: str = "js") -> str:
    """Extracts code from markdown code fences if present."""
    if f"```{default_ext}" in text:
        return text.split(f"```{default_ext}")[1].split("```")[0].strip()
    elif "```javascript" in text:
        return text.split("```javascript")[1].split("```")[0].strip()
    elif "```" in text:
        return text.split("```")[1].split("```")[0].strip()
    return text.strip()

def run_delegation():
    print("=== Delegating 3D Citadel Coding Tasks Across Cluster ===")
    
    # 1. Health Probe
    health = client.health_check()
    print(f"Cluster Health: {json.dumps(health, indent=2)}")

    total_tokens_generated = 0
    total_cloud_tokens_saved = 0
    start_all = time.time()

    # --- TASK 1: PROCEDURAL 3D MODELS (Coordinator :8001) ---
    print("\n--- Dispatching Task 1: Procedural 3D Character & Prop Models to Coordinator (:8001) ---")
    prompt_task1 = """
You are a Principal Three.js Graphics Architect.
Create a production-ready ES module 'procedural_models.js' for an isometric 3D Multi-Agent Citadel.
Requirements:
1. createWorkerCharacter(options = {}):
   - options: { color: 0x2563eb, hasHardHat: true, hardHatColor: 0xfacc15, hasClipboard: false, hasMegaphone: false, isSitting: false, agentId: 'agent-1' }
   - Builds a stylized low-poly human worker using Three.js Groups and primitives (BoxGeometry, CylinderGeometry, SphereGeometry).
   - Hierarchical structure with pivotable parts stored on character.userData:
     * head, torso, leftArm, rightArm, leftLeg, rightLeg, hardHat, accessory
   - CRITICAL FOR TOUCH: Attach an invisible bounding cylinder/box with radius 1.2 and height 2.5 on character.userData.hitbox with userData.isAgentHitbox = true and userData.agentId = options.agentId to ensure touch-friendly 48px+ tap targets.
2. createScissorLift(options = {}):
   - Wheeled platform cart with scissor crossing X-trusses and railed top basket that can elevate/lower via a setElevation(y) method on the returned group.
3. createStepladder(height = 3):
   - Low-poly A-frame stepladder with wooden/metallic rungs.
4. createComputerDesk(options = {}):
   - Desk table with dual glowing CRT/flat screens, keyboard, chair, and desk lamp.
5. createMemoryMonolith(options = {}):
   - Glowing translucent crystalline pillar (representing Qdrant vector memory) with pulsing emissive shader/material.

Return ONLY clean, complete, fully working JavaScript ES module code (export functions). Do not use external asset loaders; all geometry must be procedural Three.js primitives.
"""
    t0 = time.time()
    res1 = client.execute_model(
        model_target="coordinator",
        prompt=prompt_task1,
        preset="precise_code",
        temperature=0.20,
        min_p=0.08,
        max_tokens=3500
    )
    code1 = extract_code_block(res1.get("content", ""))
    path1 = os.path.join(OUTPUT_DIR, "procedural_models.js")
    with open(path1, "w", encoding="utf-8") as f:
        f.write(code1)
    perf1 = res1.get("performance", {})
    total_tokens_generated += perf1.get("completion_tokens", 0)
    total_cloud_tokens_saved += perf1.get("cloud_tokens_saved", 0)
    print(f"   -> procedural_models.js saved ({len(code1)} chars, {perf1.get('tokens_per_second')} tok/s, saved {perf1.get('cloud_tokens_saved')} tokens)")

    # --- TASK 2: 3D KANBAN TRACK & CARDS (Coordinator :8001) ---
    print("\n--- Dispatching Task 2: 3D Physical Kanban System to Coordinator (:8001) ---")
    prompt_task2 = """
You are a Principal Three.js Systems Architect.
Create an ES module 'kanban_board3d.js' for a physical 3D Kanban system in an isometric multi-tier world.
Requirements:
1. class KanbanBoard3D:
   - constructor(scene, options = {}):
     * Creates 3 horizontal suspension cables (steel wires with metallic material) for columns: 'TO_DO', 'DOING', 'DONE'.
     * Position columns side-by-side or stacked in tiers with signposts / placards ('TO DO', 'DOING / REASONING', 'DONE / VERIFIED').
     * Creates a basket at the bottom of the 'DONE' track for archived completed cards.
   - addTaskCard(taskData):
     * taskData: { id, title, type: 'code'|'test'|'reasoning'|'hypothesis'|'mating', status: 'TO_DO', agentId: null }
     * Color code cards: Green for code, Blue for test, Orange for architecture, Purple for mating/agent blend.
     * Card mesh: BoxGeometry with canvas texture or front-facing canvas drawing card title and status icon.
     * CRITICAL FOR TOUCH: Large touch hit target (width: 1.8, height: 1.2, depth: 0.1) with userData.isKanbanCard = true, userData.taskId = taskData.id.
     * Pins card to the cable with a wooden/metal clothespin mesh.
   - moveCardToStatus(cardId, newStatus):
     * Smoothly animates (lerps) card along cable to the new column position over 0.8s.
     * If newStatus === 'DOING', activates pulsing electric glow edge.
     * If newStatus === 'DONE', flashes gold, stamps a green checkmark/seal, and enables drop-to-basket animation on complete.
   - update(delta, time):
     * Updates card hover oscillations and glow pulses.
   - getInteractiveObjects():
     * Returns array of card hitboxes and column placards for raycasting touch events.

Return ONLY clean, complete, fully working JavaScript ES module code (export class KanbanBoard3D).
"""
    res2 = client.execute_model(
        model_target="coordinator",
        prompt=prompt_task2,
        preset="precise_code",
        temperature=0.20,
        min_p=0.08,
        max_tokens=3000
    )
    code2 = extract_code_block(res2.get("content", ""))
    path2 = os.path.join(OUTPUT_DIR, "kanban_board3d.js")
    with open(path2, "w", encoding="utf-8") as f:
        f.write(code2)
    perf2 = res2.get("performance", {})
    total_tokens_generated += perf2.get("completion_tokens", 0)
    total_cloud_tokens_saved += perf2.get("cloud_tokens_saved", 0)
    print(f"   -> kanban_board3d.js saved ({len(code2)} chars, {perf2.get('tokens_per_second')} tok/s, saved {perf2.get('cloud_tokens_saved')} tokens)")

    # --- TASK 3: SKELETAL ANIMATION ENGINE (Worker :8002) ---
    print("\n--- Dispatching Task 3: Procedural Skeletal Animations to Worker (:8002) ---")
    prompt_task3 = """
You are a High-Speed Game Physics & Animation Engineer.
Create an ES module 'animations.js' for procedural hierarchical animations of low-poly character meshes in Three.js.
Requirements:
1. Animation State Controller:
   - Each agent has an animation state: 'idle', 'walking', 'typing', 'celebrating', 'dizzy', 'megaphone', 'climbing'.
   - agent.userData.animState = 'idle'
   - agent.userData.animTimer = 0.0
2. Implement procedural updates for each state:
   - animateIdle(agent, delta, time): Gentle breathing torso scale, subtle head look-around.
   - animateWalking(agent, delta, time): Alternating arm and leg swings (sin/cos on rotation.x), slight body bounce.
   - animateTyping(agent, delta, time): Rapid alternate tapping of leftArm and rightArm forward/down, head looking at desk screen.
   - animateCelebrate(agent, delta, time): Both arms thrust upward (rotation.z / rotation.x), jumping up and down (position.y hop).
   - animateDizzy(agent, delta, time): Stumbling torso wobble, head rolling in circle, spawn/update circling yellow stars or question marks around hard hat.
   - animateMegaphone(agent, delta, time): Right arm raised with megaphone pointing toward camera (rotation angle matching camera vector), head tilted up, megaphone pulsing slightly.
3. updateAgentAnimation(agent, delta, time):
   - Dispatches to appropriate state function based on agent.userData.animState.
4. triggerAgentEvent(agent, eventName):
   - eventName: 'TASK_COMPLETE' -> switches to celebrate for 3.5s, then returns to previous state.
   - eventName: 'STUCK_LOOP' -> switches to dizzy for 5.0s with smoke puff particles.
   - eventName: 'USER_INPUT_NEEDED' -> switches to megaphone until acknowledged.
   - eventName: 'AGENT_MATING' -> moves toward partner, plays handshake / celebratory particle burst.

Return ONLY clean, complete JavaScript ES module code (export functions).
"""
    res3 = client.execute_model(
        model_target="worker",
        prompt=prompt_task3,
        preset="high_speed_utility",
        temperature=0.15,
        min_p=0.10,
        max_tokens=2500
    )
    code3 = extract_code_block(res3.get("content", ""))
    path3 = os.path.join(OUTPUT_DIR, "animations.js")
    with open(path3, "w", encoding="utf-8") as f:
        f.write(code3)
    perf3 = res3.get("performance", {})
    total_tokens_generated += perf3.get("completion_tokens", 0)
    total_cloud_tokens_saved += perf3.get("cloud_tokens_saved", 0)
    print(f"   -> animations.js saved ({len(code3)} chars, {perf3.get('tokens_per_second')} tok/s, saved {perf3.get('cloud_tokens_saved')} tokens)")

    # --- TASK 4: TOUCH-FRIENDLY AGENT INSPECTOR HUD (Coordinator / Ally) ---
    print("\n--- Dispatching Task 4: Touch-Friendly Agent Inspector HUD to Coordinator (:8001) ---")
    prompt_task4 = """
You are a Senior Frontend UI & Audio Engineer.
Create an ES module 'agent_inspector_hud.js' for an interactive, touch-friendly HUD modal overlay in the 3D Citadel.
Requirements:
1. Touch-Friendly Ergonomics:
   - All tap buttons MUST have min-height: 48px, min-width: 48px, padding: 12px 16px, large legible retro-beveled buttons.
   - Safe margins for thumbs on mobile devices.
2. Inspector Panels:
   - Panel Header: Agent Name, Role Badge, Assigned Hardware Node (Coordinator :8001 / Worker :8002 / Ally Z1 :1234), Status Badge, Close [X] button.
   - Real-Time Reasoning Trace Viewport:
     * Dark terminal styling (`#0a0f1d`), monospace font.
     * Streams live reasoning tokens (<think> traces) with auto-scroll.
     * Speed and token counter badges (`tok/s`, `total_tokens`, `cloud_tokens_saved`).
   - Long-Term Task Queue List:
     * Vertical list of past, active, and queued tasks with progress indicators.
   - Command Console:
     * Large touch-friendly input text box.
     * [⚡ Send Directive] button (min 48px height).
     * [🎙️ Voice Direct] push-to-talk microphone button that records audio and sends to LXC 121 Whisper STT (http://192.168.1.121:8200).
     * [🔊 Read Out Loud] button that calls LXC 121 Kokoro TTS (http://192.168.1.121:8300) and plays audio response.
     * [🚨 Breakout Nudge] button calling agent-nudge out-of-band intervention.
3. Methods:
   - openInspector(agentData): Displays modal, binds live telemetry.
   - closeInspector(): Hides modal.
   - appendReasoningToken(token): Appends token to live streaming view.
   - updateTaskQueue(tasks): Refreshes the task list.

Return ONLY clean, complete JavaScript ES module code (export class AgentInspectorHUD).
"""
    res4 = client.execute_model(
        model_target="coordinator",
        prompt=prompt_task4,
        preset="precise_code",
        temperature=0.20,
        min_p=0.08,
        max_tokens=3000
    )
    code4 = extract_code_block(res4.get("content", ""))
    path4 = os.path.join(OUTPUT_DIR, "agent_inspector_hud.js")
    with open(path4, "w", encoding="utf-8") as f:
        f.write(code4)
    perf4 = res4.get("performance", {})
    total_tokens_generated += perf4.get("completion_tokens", 0)
    total_cloud_tokens_saved += perf4.get("cloud_tokens_saved", 0)
    print(f"   -> agent_inspector_hud.js saved ({len(code4)} chars, {perf4.get('tokens_per_second')} tok/s, saved {perf4.get('cloud_tokens_saved')} tokens)")

    elapsed_total = round(time.time() - start_all, 1)
    print(f"\n=== All 4 Core Modules Successfully Synthesized by Local Cluster! ===")
    print(f"Total Local Tokens Generated: {total_tokens_generated}")
    print(f"Total Cloud Tokens Saved: {total_cloud_tokens_saved}")
    print(f"Total Execution Time: {elapsed_total}s")

if __name__ == "__main__":
    run_delegation()
