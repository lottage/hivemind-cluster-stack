import os
#!/usr/bin/env python3
"""
Deploy comprehensive sentence triggers for ALL known controllable devices.
Uses HA conversation platform triggers for instant local matching (<0.2s).
"""

import json
import urllib.request

TOKEN = os.environ.get("HASS_TOKEN", "YOUR_HA_LONG_LIVED_ACCESS_TOKEN")
HA_URL = 'http://127.0.0.1:8123'
HEADERS = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}

def ha_post(path, data):
    req = urllib.request.Request(f'{HA_URL}{path}', data=json.dumps(data).encode(), headers=HEADERS, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

AUTOMATIONS = []

# === INDIVIDUAL LAMPS (on/off) ===
LAMPS = {
    'living_room_lamp': ('switch.living_room_lamp', 'Living Room Lamp', ['living room lamp', 'the living room lamp']),
    'hallway_lamp':     ('switch.hallway_lamp',     'Hallway Lamp',     ['hallway lamp', 'the hallway lamp', 'hall lamp', 'the hall lamp']),
    'bedroom_lamp':     ('switch.bedroom_lamp',     'Bedroom Lamp',     ['bedroom lamp', 'the bedroom lamp', 'bedroom light', 'the bedroom light']),
}
for key, (entity, name, variants) in LAMPS.items():
    for action, verb, state_word in [('turn_on', 'turn on', 'on'), ('turn_off', 'turn off', 'off')]:
        cmds = []
        for v in variants:
            cmds.append(f'{verb} {v}')
            cmds.append(f'{v} {state_word}')
        cmds.append(f'switch {state_word} {variants[0]}')
        AUTOMATIONS.append({
            'id': f'stonesage_{key}_{state_word}',
            'alias': f'{name} {state_word.title()}',
            'description': f'Voice: {verb} {name.lower()}',
            'mode': 'single',
            'trigger': [{'platform': 'conversation', 'command': cmds}],
            'condition': [],
            'action': [
                {'action': f'switch.{action}', 'target': {'entity_id': entity}},
                {'set_conversation_response': f'{name} is now {state_word}.'}
            ]
        })

# === ALL LAMPS (bulk) ===
ALL_LAMP_IDS = [v[0] for v in LAMPS.values()]
for action, verb, state_word in [('turn_on', 'turn on', 'on'), ('turn_off', 'turn off', 'off')]:
    AUTOMATIONS.append({
        'id': f'stonesage_all_lamps_{state_word}',
        'alias': f'All Lamps {state_word.title()}',
        'description': f'Voice: {verb} all lamps',
        'mode': 'single',
        'trigger': [{'platform': 'conversation', 'command': [
            f'{verb} all the lamps', f'{verb} all lamps', f'all lamps {state_word}',
            f'{verb} every lamp', f'lamps {state_word}', f'{verb} the lamps',
        ]}],
        'condition': [],
        'action': [
            {'action': f'switch.{action}', 'target': {'entity_id': ALL_LAMP_IDS}},
            {'set_conversation_response': f'All lamps are now {state_word}.'}
        ]
    })

# === TV LIGHTS (on/off/dim) ===
TV_LIGHT = 'light.living_room_living_room_tv_lights'
AUTOMATIONS.append({
    'id': 'stonesage_tv_lights_on', 'alias': 'TV Lights On', 'description': 'Voice: turn on TV lights', 'mode': 'single',
    'trigger': [{'platform': 'conversation', 'command': [
        'turn on the tv lights', 'turn on tv lights', 'tv lights on',
        'turn on the backlight', 'backlight on', 'turn on the tv backlight',
    ]}], 'condition': [],
    'action': [
        {'action': 'light.turn_on', 'target': {'entity_id': TV_LIGHT}, 'data': {'brightness_pct': 100}},
        {'set_conversation_response': 'TV lights are on at full brightness.'}
    ]
})
AUTOMATIONS.append({
    'id': 'stonesage_tv_lights_off', 'alias': 'TV Lights Off', 'description': 'Voice: turn off TV lights', 'mode': 'single',
    'trigger': [{'platform': 'conversation', 'command': [
        'turn off the tv lights', 'turn off tv lights', 'tv lights off',
        'turn off the backlight', 'backlight off', 'turn off the tv backlight',
    ]}], 'condition': [],
    'action': [
        {'action': 'light.turn_off', 'target': {'entity_id': TV_LIGHT}},
        {'set_conversation_response': 'TV lights are off.'}
    ]
})
AUTOMATIONS.append({
    'id': 'stonesage_tv_lights_dim', 'alias': 'TV Lights Dim', 'description': 'Voice: dim TV lights', 'mode': 'single',
    'trigger': [{'platform': 'conversation', 'command': [
        'dim the tv lights', 'dim tv lights', 'tv lights dim',
        'dim the backlight', 'lower the tv lights', 'tv lights low',
    ]}], 'condition': [],
    'action': [
        {'action': 'light.turn_on', 'target': {'entity_id': TV_LIGHT}, 'data': {'brightness_pct': 20}},
        {'set_conversation_response': 'TV lights dimmed to 20%.'}
    ]
})

# === FLOODLIGHTS (on/off, each + bulk) ===
FLOODS = {
    'kitchen':  ('light.kitchen_living_room_floodlight_timed',   'Kitchen Floodlight',  ['flood light', 'flood lights', 'the flood light', 'the flood lights', 'kitchen floodlight', 'kitchen flood light', 'kitchen living room flood light', 'kitchen living room floodlight']),
    'driveway': ('light.driveway_front_door_floodlight_timed',   'Driveway Floodlight', ['driveway light', 'the driveway light', 'front door light', 'the front door light', 'driveway floodlight', 'the driveway floodlight']),
    'backyard': ('light.back_yard_floodlight_timed',             'Back Yard Floodlight',['back yard light', 'the back yard light', 'backyard light', 'the backyard light', 'backyard floodlight', 'the backyard floodlight']),
    'sideyard': ('light.side_yard_floodlight_timed',             'Side Yard Floodlight',['side yard light', 'the side yard light', 'side yard floodlight', 'the side yard floodlight']),
}
for key, (entity, name, variants) in FLOODS.items():
    for verb, state_word in [('turn on', 'on'), ('turn off', 'off')]:
        cmds = [f'{verb} {v}' for v in variants] + [f'{variants[0]} {state_word}']
        AUTOMATIONS.append({
            'id': f'stonesage_{key}_floodlight_{state_word}',
            'alias': f'{name} {state_word.title()}', 'description': f'Voice: {verb} {name.lower()}', 'mode': 'single',
            'trigger': [{'platform': 'conversation', 'command': cmds}], 'condition': [],
            'action': [
                {'action': f'light.turn_{state_word}', 'target': {'entity_id': entity}},
                {'set_conversation_response': f'{name} is now {state_word}.'}
            ]
        })

ALL_FLOOD_IDS = [v[0] for v in FLOODS.values()]
for verb, state_word in [('turn on', 'on'), ('turn off', 'off')]:
    AUTOMATIONS.append({
        'id': f'stonesage_all_floodlights_{state_word}',
        'alias': f'All Floodlights {state_word.title()}', 'description': f'Voice: {verb} all floodlights', 'mode': 'single',
        'trigger': [{'platform': 'conversation', 'command': [
            f'{verb} all the floodlights', f'{verb} all floodlights', f'all floodlights {state_word}',
            f'{verb} all the flood lights', f'all flood lights {state_word}', f'{verb} all outside lights',
            f'all outside lights {state_word}', f'{verb} the outside lights', f'{verb} every floodlight',
        ]}], 'condition': [],
        'action': [
            {'action': f'light.turn_{state_word}', 'target': {'entity_id': ALL_FLOOD_IDS}},
            {'set_conversation_response': f'All four floodlights are now {state_word}.'}
        ]
    })

# === PORCH STRING LIGHTS (on/off) ===
PORCH = 'switch.front_porch_front_porch_front_porch_lights'
for verb, action, state_word in [('turn on', 'turn_on', 'on'), ('turn off', 'turn_off', 'off')]:
    AUTOMATIONS.append({
        'id': f'stonesage_porch_lights_{state_word}',
        'alias': f'Porch Lights {state_word.title()}', 'description': f'Voice: {verb} porch lights', 'mode': 'single',
        'trigger': [{'platform': 'conversation', 'command': [
            f'{verb} the porch lights', f'{verb} porch lights', f'porch lights {state_word}',
            f'{verb} the string lights', f'string lights {state_word}', f'{verb} the front porch lights',
            f'front porch lights {state_word}', f'{verb} front porch lights',
        ]}], 'condition': [],
        'action': [
            {'action': f'switch.{action}', 'target': {'entity_id': PORCH}},
            {'set_conversation_response': f'Front porch string lights are now {state_word}.'}
        ]
    })

# === ALL LIGHTS (everything: lamps + TV lights + porch) ===
ALL_SW = [v[0] for v in LAMPS.values()] + [PORCH]
for verb, state_word in [('turn on', 'on'), ('turn off', 'off')]:
    action_list = [
        {'action': f'switch.turn_{state_word}', 'target': {'entity_id': ALL_SW}},
        {'action': f'light.turn_{state_word}', 'target': {'entity_id': TV_LIGHT}},
    ]
    if state_word == 'on':
        action_list[1]['data'] = {'brightness_pct': 100}
    AUTOMATIONS.append({
        'id': f'stonesage_all_lights_{state_word}',
        'alias': f'All Lights {state_word.title()}', 'description': f'Voice: {verb} all lights', 'mode': 'single',
        'trigger': [{'platform': 'conversation', 'command': [
            f'{verb} all the lights', f'{verb} all lights', f'all lights {state_word}',
            f'lights {state_word}', f'{verb} every light', f'{verb} the lights',
        ]}], 'condition': [],
        'action': action_list + [{'set_conversation_response': f'All lights are now {state_word}.'}]
    })

# === TV POWER (on/off) ===
for verb, action, state_word in [('turn on', 'turn_on', 'on'), ('turn off', 'turn_off', 'off')]:
    AUTOMATIONS.append({
        'id': f'stonesage_tv_{state_word}',
        'alias': f'TV {state_word.title()}', 'description': f'Voice: {verb} TV', 'mode': 'single',
        'trigger': [{'platform': 'conversation', 'command': [
            f'{verb} the tv', f'{verb} tv', f'tv {state_word}',
            f'{verb} the television', f'switch {state_word} the tv',
        ]}], 'condition': [],
        'action': [
            {'action': f'remote.{action}', 'target': {'entity_id': 'remote.living_room_tv'}},
            {'set_conversation_response': f'TV is powering {state_word}.'}
        ]
    })

# === THERMOSTAT — temperature presets 65-78 ===
for temp in range(65, 79):
    AUTOMATIONS.append({
        'id': f'stonesage_thermostat_set_{temp}',
        'alias': f'Set Thermostat to {temp}', 'description': f'Voice: set thermostat to {temp}', 'mode': 'single',
        'trigger': [{'platform': 'conversation', 'command': [
            f'set the thermostat to {temp}', f'set thermostat to {temp}',
            f'set it to {temp} degrees', f'set the temperature to {temp}',
            f'make it {temp} degrees', f'set the house to {temp}',
        ]}], 'condition': [],
        'action': [
            {'action': 'climate.set_temperature', 'target': {'entity_id': 'climate.nest_thermostat'}, 'data': {'temperature': temp}},
            {'set_conversation_response': f'Thermostat set to {temp} degrees.'}
        ]
    })

# === THERMOSTAT MODES ===
HVAC_MODES = {
    'cool': (['set the thermostat to cool', 'set thermostat to cool', 'turn on the ac', 'turn on the air conditioning', 'turn on ac', 'cool the house', 'start cooling'], 'cool'),
    'heat': (['set the thermostat to heat', 'set thermostat to heat', 'turn on the heat', 'turn on the heater', 'turn on heat', 'heat the house', 'warm the house', 'warm it up', 'start heating'], 'heat'),
    'off':  (['turn off the thermostat', 'turn off thermostat', 'thermostat off', 'turn off the ac', 'turn off ac', 'turn off the heat', 'turn off heat', 'stop heating', 'stop cooling'], 'off'),
    'auto': (['set the thermostat to auto', 'set thermostat to auto', 'thermostat auto', 'set the thermostat to automatic'], 'heat_cool'),
}
for mode_name, (cmds, hvac_mode) in HVAC_MODES.items():
    AUTOMATIONS.append({
        'id': f'stonesage_thermostat_{mode_name}',
        'alias': f'Thermostat {mode_name.title()} Mode', 'description': f'Voice: thermostat {mode_name}', 'mode': 'single',
        'trigger': [{'platform': 'conversation', 'command': cmds}], 'condition': [],
        'action': [
            {'action': 'climate.set_hvac_mode', 'target': {'entity_id': 'climate.nest_thermostat'}, 'data': {'hvac_mode': hvac_mode}},
            {'set_conversation_response': f'Thermostat is now in {mode_name} mode.'}
        ]
    })

# === WATERING ZONES (on/off + bulk) ===
WATER_ZONES = {
    'handheld':  ('valve.front_of_house_hoses_handheld_zone',  'Handheld',  ['the handheld hose', 'handheld zone', 'the handheld']),
    'garden':    ('valve.front_of_house_hoses_garden_zone',    'Garden',    ['the garden hose', 'garden zone', 'the garden']),
    'side_yard': ('valve.front_of_house_hoses_side_yard_zone', 'Side Yard', ['the side yard water', 'side yard zone']),
    'back_yard': ('valve.front_of_house_hoses_back_yard_zone', 'Back Yard', ['the back yard water', 'back yard zone', 'the backyard water']),
}
for zone_key, (entity, nice, variants) in WATER_ZONES.items():
    for verb, valve_action, state_word in [('turn on', 'open_valve', 'on'), ('turn off', 'close_valve', 'off')]:
        cmds = [f'{verb} {v}' for v in variants]
        if verb == 'turn on':
            cmds.append(f'water the {nice.lower()}')
            cmds.append(f'start the {nice.lower()}')
        else:
            cmds.append(f'stop watering the {nice.lower()}')
        AUTOMATIONS.append({
            'id': f'stonesage_water_{zone_key}_{state_word}',
            'alias': f'Water {nice} {"On" if state_word == "on" else "Off"}',
            'description': f'Voice: {verb} {nice} watering', 'mode': 'single',
            'trigger': [{'platform': 'conversation', 'command': cmds}], 'condition': [],
            'action': [
                {'action': f'valve.{valve_action}', 'target': {'entity_id': entity}},
                {'set_conversation_response': f'{nice} watering zone is now {"open" if state_word == "on" else "closed"}.'}
            ]
        })

ALL_VALVES = [v[0] for v in WATER_ZONES.values()]
AUTOMATIONS.append({
    'id': 'stonesage_water_all_on', 'alias': 'All Watering On', 'description': 'Voice: all watering on', 'mode': 'single',
    'trigger': [{'platform': 'conversation', 'command': [
        'turn on all the water', 'water the whole yard', 'water everything',
        'turn on all zones', 'start watering', 'turn on all sprinklers',
    ]}], 'condition': [],
    'action': [
        {'action': 'valve.open_valve', 'target': {'entity_id': ALL_VALVES}},
        {'set_conversation_response': 'All four watering zones are now open.'}
    ]
})
AUTOMATIONS.append({
    'id': 'stonesage_water_all_off', 'alias': 'All Watering Off', 'description': 'Voice: all watering off', 'mode': 'single',
    'trigger': [{'platform': 'conversation', 'command': [
        'turn off all the water', 'stop watering', 'turn off all zones',
        'stop all sprinklers', 'turn off all sprinklers', 'water off',
    ]}], 'condition': [],
    'action': [
        {'action': 'valve.close_valve', 'target': {'entity_id': ALL_VALVES}},
        {'set_conversation_response': 'All watering zones are now closed.'}
    ]
})

# === LITTER BOX (scoop) ===
AUTOMATIONS.append({
    'id': 'stonesage_litterbox_clean', 'alias': 'Litter Box Clean', 'description': 'Voice: scoop litter box', 'mode': 'single',
    'trigger': [{'platform': 'conversation', 'command': [
        'clean the litter box', 'clean litter box', 'scoop the litter box',
        "clean luna's litter box", 'clean the cat box', 'scoop the cat box',
    ]}], 'condition': [],
    'action': [
        {'action': 'button.press', 'target': {'entity_id': 'button.petkit_puramax_scoop'}},
        {'set_conversation_response': 'Starting a scoop cycle on the PuraMax litter box.'}
    ]
})

# === ECHO DO NOT DISTURB (on/off) ===
ECHO_DND = ['switch.bathroom_echo_dot_do_not_disturb', 'switch.kitchen_echo_show_8_do_not_disturb', 'switch.kitchen_echo_dot_do_not_disturb']
for verb, action, state_word in [('turn on', 'turn_on', 'on'), ('turn off', 'turn_off', 'off')]:
    desc_verb = 'enable' if state_word == 'on' else 'disable'
    AUTOMATIONS.append({
        'id': f'stonesage_echo_dnd_{state_word}',
        'alias': f'Echo DND {state_word.title()}', 'description': f'Voice: {desc_verb} DND', 'mode': 'single',
        'trigger': [{'platform': 'conversation', 'command': [
            f'do not disturb {state_word}', f'{verb} do not disturb',
            f'{desc_verb} do not disturb', f'{"silence" if state_word == "on" else "unmute"} the echos',
        ]}], 'condition': [],
        'action': [
            {'action': f'switch.{action}', 'target': {'entity_id': ECHO_DND}},
            {'set_conversation_response': f'Do Not Disturb {desc_verb}d on all Echo devices.'}
        ]
    })

# === SCENE: BEDTIME LOCKDOWN ===
AUTOMATIONS.append({
    'id': 'stonesage_bedtime_lockdown', 'alias': 'Bedtime Routine', 'description': 'Voice bedtime lockdown', 'mode': 'single',
    'trigger': [
        {'platform': 'conversation', 'command': [
            'goodnight', 'bedtime', "it's bedtime", 'good night',
            'time for bed', 'going to bed', 'going to sleep',
        ]},
        {'platform': 'state', 'entity_id': 'input_boolean.bedtime_lockdown', 'to': 'on'},
    ], 'condition': [],
    'action': [
        {'action': 'switch.turn_off', 'target': {'entity_id': ALL_SW}},
        {'action': 'light.turn_off', 'target': {'entity_id': TV_LIGHT}},
        {'action': 'remote.turn_off', 'target': {'entity_id': 'remote.living_room_tv'}},
        {'action': 'climate.set_temperature', 'target': {'entity_id': 'climate.nest_thermostat'}, 'data': {'temperature': 68}},
        {'action': 'input_boolean.turn_off', 'target': {'entity_id': 'input_boolean.bedtime_lockdown'}},
        {'set_conversation_response': 'Goodnight! All lights and TV are off, thermostat set to 68 degrees.'}
    ]
})

# === SCENE: MOVIE NIGHT ===
AUTOMATIONS.append({
    'id': 'stonesage_movie_night', 'alias': 'Movie Night Mode', 'description': 'Voice movie night', 'mode': 'single',
    'trigger': [
        {'platform': 'conversation', 'command': [
            'movie night', 'movie time', 'cinema mode', 'start movie night',
            'living room layout', 'turn on the living room layout', 'turn on living room layout',
        ]},
        {'platform': 'state', 'entity_id': 'input_boolean.movie_night_mode', 'to': 'on'},
    ], 'condition': [],
    'action': [
        {'action': 'switch.turn_off', 'target': {'entity_id': ['switch.living_room_lamp', 'switch.hallway_lamp']}},
        {'action': 'light.turn_on', 'target': {'entity_id': TV_LIGHT}, 'data': {'brightness_pct': 20}},
        {'action': 'climate.set_temperature', 'target': {'entity_id': 'climate.nest_thermostat'}, 'data': {'temperature': 70}},
        {'action': 'remote.turn_on', 'target': {'entity_id': 'remote.living_room_tv'}},
        {'action': 'input_boolean.turn_off', 'target': {'entity_id': 'input_boolean.movie_night_mode'}},
        {'set_conversation_response': 'Movie night! Lights dimmed, TV is on, thermostat set to 70.'}
    ]
})

# === LAUNDRY ALERTS ===
for appliance, entity, msg in [
    ('dryer', 'input_boolean.lg_dryer_cycle', 'The laundry in the dryer is finished.'),
    ('washer', 'input_boolean.lg_washer_cycle', 'The washing machine has completed its cycle.'),
]:
    AUTOMATIONS.append({
        'id': f'stonesage_lg_{appliance}_alert', 'alias': f'LG {appliance.title()} Finished Voice Alert',
        'description': f'{appliance.title()} cycle complete alert', 'mode': 'single',
        'trigger': [{'platform': 'state', 'entity_id': entity, 'from': 'on', 'to': 'off'}],
        'condition': [],
        'action': [
            {'action': 'notify.kitchen_echo_show_8_announce', 'data': {'message': msg, 'title': f'{appliance.title()} Complete'}},
            {'action': 'notify.kitchen_echo_dot_announce', 'data': {'message': msg, 'title': f'{appliance.title()} Complete'}},
        ]
    })

# ============================================================================
# DEPLOY
# ============================================================================
def main():
    print(f'Deploying {len(AUTOMATIONS)} automations to Home Assistant...\n')
    success = fail = 0
    for auto in AUTOMATIONS:
        status, body = ha_post(f'/api/config/automation/config/{auto["id"]}', auto)
        tag = '[OK] ' if status in (200, 201) else f'[ERR {status}]'
        print(f'  {tag} {auto["id"]:55s} {auto["alias"]}')
        if status in (200, 201):
            success += 1
        else:
            fail += 1
            print(f'        -> {body[:200]}')

    print(f'\nDeployed: {success}/{len(AUTOMATIONS)} OK, {fail} failed')
    print('\nReloading automation engine...')
    s, _ = ha_post('/api/services/automation/reload', {})
    print(f'  {"[OK]" if s in (200,201) else f"[ERR {s}]"} Automations reloaded')

    trigger_count = sum(
        len(t.get('command', []))
        for a in AUTOMATIONS for t in a.get('trigger', [])
        if t.get('platform') == 'conversation'
    )
    print(f'\n=== DEPLOYMENT SUMMARY ===')
    print(f'  Total automations:  {len(AUTOMATIONS)}')
    print(f'  Sentence triggers:  {trigger_count}')
    print(f'  Device categories:  Lamps (3+bulk), TV Lights (on/off/dim),')
    print(f'                      Floodlights (4+bulk), Porch Lights,')
    print(f'                      TV Power, Thermostat (14 temps + 4 modes),')
    print(f'                      Watering (4 zones+bulk), Litter Box,')
    print(f'                      Echo DND, Scenes, Laundry Alerts')

if __name__ == '__main__':
    main()
