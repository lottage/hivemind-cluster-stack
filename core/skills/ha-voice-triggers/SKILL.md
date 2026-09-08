# HA Voice Sentence Trigger Deployer

name: ha-voice-triggers
description: Deploy and manage comprehensive Home Assistant conversation sentence triggers for instant local voice control of all known devices. Covers lamps, lights, floodlights, thermostat, TV, watering, litter box, Echo DND, and scene automations.

---

## Overview

This skill deploys HA `conversation` platform triggers that match **before** the LLM processes, providing instant (<0.2s) device control without GPU cost. Each trigger maps a natural language command directly to an HA service call with a spoken response.

## When to Use

- Adding voice control for a new device
- Rebuilding all sentence triggers after a fresh HA install
- Expanding trigger phrases for better speech recognition coverage
- Auditing which devices have voice control

## Architecture

```
Voice Command → Wyoming Whisper STT → HA Assist Pipeline
                                         ↓
                              conversation trigger match?
                             ╱                            ╲
                          YES                              NO
                           ↓                                ↓
                    Run automation                   Forward to LLM
                    (instant, <0.2s)              (3B worker, ~0.8s)
```

### Design Principles

1. **Instant local matching** — HA's `prefer_local_intents: true` catches exact sentence matches before GPU inference
2. **Redundant phrasing** — Each device has 5-9 trigger variants covering natural speech patterns ("turn on the X", "X on", "switch on the X", etc.)
3. **Bulk controls** — "All lamps on", "all lights off", "all floodlights on", "all outside lights off"
4. **Spoken confirmation** — Every automation uses `set_conversation_response` for TTS feedback

## Dependencies

- Home Assistant at `http://127.0.0.1:8123` with a valid long-lived access token
- `conversation` platform triggers (built into HA Core)
- Wyoming Whisper STT + Piper TTS on LXC 121 (`127.0.0.1`)
- Python 3.10+ (stdlib only: `json`, `urllib.request`)

## Quick Start

### Full Deployment (62 automations, 375 triggers)

```bash
python deploy_all_triggers.py
```

### Adding a New Device

1. Find the entity ID via HA REST API or the MCP `home_assistant_entities` tool
2. Add a new block to the `AUTOMATIONS` list in `deploy_all_triggers.py`:

```python
AUTOMATIONS.append({
    'id': 'stonesage_<device>_on',
    'alias': '<Device Name> On',
    'description': 'Voice: turn on <device>',
    'mode': 'single',
    'trigger': [{'platform': 'conversation', 'command': [
        'turn on the <device>',
        'turn on <device>',
        '<device> on',
    ]}],
    'condition': [],
    'action': [
        {'action': '<domain>.turn_on', 'target': {'entity_id': '<domain>.<entity>'}},
        {'set_conversation_response': '<Device> is now on.'}
    ]
})
```

3. Re-run `python deploy_all_triggers.py` — existing automations are updated in-place

## Device Coverage Matrix

| Category | Devices | Entity Domain | Triggers |
|:---|:---|:---|---:|
| Lamps | Living Room, Hallway, Bedroom | `switch` | 30 |
| Bulk Lamps | All 3 lamps | `switch` | 12 |
| TV Lights | Govee H6098 backlight | `light` | 18 |
| Floodlights | Kitchen, Driveway, Back Yard, Side Yard | `light` | 46 |
| Bulk Floodlights | All 4 cameras | `light` | 18 |
| Porch Lights | Front porch string lights | `switch` | 16 |
| All Lights | Lamps + TV + Porch | `switch` + `light` | 12 |
| TV Power | Living Room TV | `remote` | 10 |
| Thermostat Temps | 65°F – 78°F (14 presets) | `climate` | 84 |
| Thermostat Modes | Cool, Heat, Off, Auto | `climate` | 30 |
| Watering Zones | Handheld, Garden, Side Yard, Back Yard | `valve` | 40 |
| Bulk Watering | All 4 zones | `valve` | 12 |
| Litter Box | PETKIT PuraMax scoop | `button` | 6 |
| Echo DND | All 3 Echo devices | `switch` | 8 |
| Bedtime Scene | All lights + TV + thermostat 68° | mixed | 7 |
| Movie Night | Dim lights + TV on + thermostat 70° | mixed | 7 |
| Laundry Alerts | LG Dryer + Washer (state-based) | `notify` | 0 (state) |
| **TOTAL** | | | **375** |

## Excluded Devices (and Why)

| Device | Reason |
|:---|:---|
| `switch.luna_s_feeder` | Vacation-only smart switch, no voice use case |
| `switch.server` | **NEVER toggle** — powers the compute cluster |
| Camera settings switches | ~100+ config switches, not user-facing commands |
| PETKIT config switches | Internal settings (auto-clean timers, notifications) |
| Echo announcement/comms switches | Mostly unavailable, not useful for voice |

## Safety Rules

- **`switch.server` is NEVER included** in any bulk "all switches" or "all lights" commands
- **`switch.luna_s_feeder` is excluded** from bulk lamp controls per user directive
- Thermostat range is bounded to 65-78°F to prevent extreme settings
- Destructive operations require explicit user approval

## Troubleshooting

### Trigger not matching
- Check the exact transcription from Wyoming Whisper — run `verify_triggers.py` to test
- HA conversation triggers are **case-insensitive** but require exact phrase match
- Add more variants to the `command` list to catch speech recognition variations

### Device state shows "unknown" or "unavailable"
- Cync/GE plugs require LAN Bridge connectivity — check integration health
- TVs in deep sleep drop WiFi — use `remote.turn_on` not `media_player.turn_on`

## Files

- `deploy_all_triggers.py` — Main deployment script (62 automations, 375 triggers)
- `verify_triggers.py` — Test trigger matching via HA conversation API
- `SKILL.md` — This file
