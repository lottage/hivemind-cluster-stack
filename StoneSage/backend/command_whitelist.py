"""
StoneSage Command & Action Whitelist Engine
Establishes strict security, safety bounds, and execution whitelists for common use cases:
1. Home Assistant: climate/HVAC control, lighting, switches, automations, scenes.
2. Coding & Development: compilers, runtimes, linters, test runners, git, and safe shell utilities.
3. Projects & Workspaces: safe workspace directory scoping, file inspection.
4. Natural Language Action Parsing: intent extraction with whitelist validation for chat.
"""

import os
import re
import shlex
from typing import Dict, Any, List, Tuple, Optional

# ==============================================================================
# 1. HOME ASSISTANT WHITELIST & GUARDRAILS
# ==============================================================================

# Allowed Home Assistant service domains and services
HA_ALLOWED_SERVICES: Dict[str, List[str]] = {
    "climate": ["set_temperature", "set_hvac_mode", "set_preset_mode"],
    "light": ["turn_on", "turn_off", "toggle"],
    "switch": ["turn_on", "turn_off", "toggle"],
    "automation": ["trigger", "turn_on", "turn_off"],
    "scene": ["turn_on"],
    "homeassistant": ["turn_on", "turn_off", "toggle"],
    "select": ["select_option"],
    "button": ["press"],
}

# Verified default entities for Austin's estate
HA_VERIFIED_ENTITIES = {
    "climate": ["climate.nest_thermostat"],
    "light": [
        "light.back_yard_floodlight_timed",
        "light.side_yard_floodlight_timed",
        "light.driveway_front_door_floodlight_timed"
    ],
    "switch": [
        "switch.kitchen_living_room",
        "switch.kitchen_living_room_led",
        "switch.yard_driveway_front_door_preset_patrol_mode",
        "switch.kitchen_kitchen_living_room_preset_patrol_mode"
    ]
}

# Blocked entity substrings (destructive actions, security credentials, reboots)
HA_BLOCKED_ENTITY_SUBSTRINGS = [
    "format_sd",
    "reboot",
    "factory_reset",
    "firmware",
    "password",
    "security_status",
    "token"
]

# Safe temperature range in Fahrenheit (protects HVAC equipment and home)
MIN_SAFE_TEMP_F = 60.0
MAX_SAFE_TEMP_F = 85.0


def validate_ha_action(domain: str, service: str, service_data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Validates a Home Assistant service call against strict domain, service, entity,
    and parameter safety whitelists.
    Returns: (is_allowed, reason_or_message, sanitized_service_data)
    """
    domain = (domain or "").strip().lower()
    service = (service or "").strip().lower()
    data = dict(service_data or {})

    # 1. Domain & Service Whitelist Check
    if domain not in HA_ALLOWED_SERVICES:
        return False, f"Domain '{domain}' is not in the allowed Home Assistant whitelist.", data

    if service not in HA_ALLOWED_SERVICES[domain]:
        return False, f"Service '{service}' is not permitted for domain '{domain}'. Allowed: {HA_ALLOWED_SERVICES[domain]}", data

    # 2. Entity Whitelist & Sanitization Check
    entity_id = data.get("entity_id", "")
    if isinstance(entity_id, list):
        entity_id = entity_id[0] if entity_id else ""
    entity_id = str(entity_id).strip().lower()

    if entity_id:
        for blocked in HA_BLOCKED_ENTITY_SUBSTRINGS:
            if blocked in entity_id:
                return False, f"Entity '{entity_id}' contains blocked substring '{blocked}'.", data

    # 3. Domain-Specific Parameter Validation
    if domain == "climate" and service == "set_temperature":
        target = data.get("temperature")
        if target is None:
            # Check target_temp_high/low if present
            target = data.get("target_temp_high") or data.get("target_temp_low")
        if target is None:
            return False, "set_temperature requires a 'temperature' parameter.", data

        try:
            temp_f = float(target)
        except (ValueError, TypeError):
            return False, f"Invalid temperature value: '{target}'.", data

        if temp_f < MIN_SAFE_TEMP_F or temp_f > MAX_SAFE_TEMP_F:
            return False, (f"Requested temperature {temp_f}°F is outside the safe residential whitelist bounds "
                           f"({MIN_SAFE_TEMP_F}°F to {MAX_SAFE_TEMP_F}°F)."), data

        # Default entity to Nest thermostat if omitted
        if not entity_id:
            entity_id = "climate.nest_thermostat"
            data["entity_id"] = entity_id

        data["temperature"] = round(temp_f, 1)

    return True, "Action approved by Home Assistant whitelist.", data


# ==============================================================================
# 2. CODING & TERMINAL COMMAND WHITELIST
# ==============================================================================

# Allowed command base names / binaries
ALLOWED_BINARIES = {
    # Compilers, Runtimes & Interpreters
    "python", "python3", "py", "node", "npm", "npx", "pnpm", "yarn",
    "cargo", "rustc", "go", "tsc", "deno", "bun",
    # Testing, Linting & Formatting
    "pytest", "unittest", "ruff", "black", "flake8", "eslint", "prettier", "mypy", "bandit",
    # Version Control
    "git",
    # Package Management
    "pip", "pip3", "uv",
    # Filesystem & Inspection
    "ls", "dir", "cat", "head", "tail", "grep", "find", "findstr",
    "wc", "pwd", "echo", "diff", "mkdir", "tree", "type", "touch", "cp", "mv",
    # Network, Diagnostics & Homelab Services
    "curl", "wget", "jq", "ping", "systemctl", "journalctl", "uptime", "free", "df", "ps"
}

# Subcommands explicitly allowed for systemctl (read-only + safe service restarts)
ALLOWED_SYSTEMCTL_ACTIONS = {
    "status", "is-active", "is-enabled", "restart"
}
ALLOWED_SYSTEMCTL_SERVICES = {
    "stonesage", "stonesage.service",
    "cluster-mcp", "cluster-mcp.service",
    "wildlife-sentry", "wildlife-sentry.service"
}

# Hard blacklist of dangerous shell commands / destructive patterns
DANGEROUS_COMMAND_PATTERNS = [
    r"\brm\s+-[rf]*\s+[\/\\]",                 # rm -rf / or rm -rf \
    r"\brm\s+-[rf]*\s+\*",                     # rm -rf *
    r"\brmdir\s+\/s\s+\/q\s+[c-zC-Z]:\\",       # Windows rmdir /s /q C:\
    r"\bmkfs\b",                               # Format partition
    r"\bfdisk\b",                              # Partition tool
    r"\bdd\s+if=",                             # Raw block overwrite
    r"\bshutdown\b",                           # Node shutdown
    r"\binit\s+0\b",                           # Shutdown
    r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;",   # Fork bomb
    r"\bchmod\s+-[rR]*\s+777\s+[\/\\]",        # chmod -R 777 /
    r"\bchown\s+-[rR]*\s+[\/\\]",              # chown -R /
    r"\bdrop\s+database\b",                    # Database destruction
    r"\btruncate\s+table\b",                   # Table destruction
]


def validate_terminal_command(command_str: str, cwd: str = "", allowed_roots: Optional[List[str]] = None) -> Tuple[bool, str]:
    """
    Validates a shell/terminal command against coding binaries, safety bounds,
    and filesystem scope.
    Returns: (is_allowed, reason)
    """
    cmd = (command_str or "").strip()
    if not cmd:
        return False, "Command string cannot be empty."

    # 1. Dangerous Pattern Blacklist Check
    for pattern in DANGEROUS_COMMAND_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return False, f"Command contains forbidden destructive pattern matching '{pattern}'."

    # 2. Extract base binary
    # Handle PowerShell command chains or pipe splits safely
    # Extract first token
    parts = cmd.split(None, 1)
    base_token = parts[0].strip().strip('"').strip("'").lower()
    
    # Strip path prefix (e.g. /usr/bin/git -> git, C:\Python313\python.exe -> python)
    base_name = os.path.basename(base_token).lower()
    if base_name.endswith(".exe"):
        base_name = base_name[:-4]

    # Handle directory navigation builtins
    if base_name in ("cd", "chdir", "set-location"):
        return True, "Directory navigation permitted."

    # 3. Whitelist check on binary
    if base_name not in ALLOWED_BINARIES:
        return False, f"Binary '{base_name}' is not in the StoneSage coding and diagnostics whitelist."

    # 4. Systemctl scope check
    if base_name == "systemctl":
        cmd_tokens = cmd.split()[1:]
        if not cmd_tokens:
            return False, "systemctl requires a subcommand (e.g. status, is-active)."
        subcmd = cmd_tokens[0].lower()
        if subcmd not in ALLOWED_SYSTEMCTL_ACTIONS:
            return False, f"systemctl action '{subcmd}' is not permitted. Allowed: {ALLOWED_SYSTEMCTL_ACTIONS}"
        if subcmd == "restart":
            # Must be one of the permitted cluster services
            target_svc = cmd_tokens[1].lower() if len(cmd_tokens) > 1 else ""
            if target_svc not in ALLOWED_SYSTEMCTL_SERVICES:
                return False, f"Restarting service '{target_svc}' is not permitted. Allowed: {ALLOWED_SYSTEMCTL_SERVICES}"

    # 5. Working Directory Scoping Check (if allowed_roots supplied)
    if allowed_roots and cwd:
        abs_cwd = os.path.abspath(cwd).lower()
        matched = any(abs_cwd.startswith(os.path.abspath(r).lower()) for r in allowed_roots)
        if not matched:
            return False, f"Execution path '{cwd}' is outside authorized workspace roots."

    return True, "Command approved by coding and development whitelist."


# ==============================================================================
# 3. CHAT INTENT PARSER & ACTION EXTRACTOR
# ==============================================================================

# Regex patterns for natural language Home Assistant commands
CLIMATE_TEMP_PATTERNS = [
    r"(?:set|change|turn|make|adjust|cool|heat|lower|raise)\s+(?:the\s+)?(?:thermostat|temp|temperature|ac|heat|house|climate)?\s*(?:to\s+)?(\d{2}(?:\.\d)?)\s*(?:degrees|deg|°|f)?\b",
    r"(\d{2}(?:\.\d)?)\s*(?:degrees|deg|°|f)?\s*(?:on\s+the\s+thermostat|for\s+the\s+temp)",
]

LIGHT_PATTERNS = [
    (r"(?:turn|switch)\s+on\s+(?:the\s+)?(.*?(?:light|floodlight|lamp).*)", "turn_on"),
    (r"(?:turn|switch)\s+off\s+(?:the\s+)?(.*?(?:light|floodlight|lamp).*)", "turn_off"),
    (r"(?:turn|switch)\s+(.*?(?:light|floodlight|lamp).*)\s+on", "turn_on"),
    (r"(?:turn|switch)\s+(.*?(?:light|floodlight|lamp).*)\s+off", "turn_off"),
]


def extract_whitelisted_chat_action(user_text: str) -> Optional[Dict[str, Any]]:
    """
    Parses conversational user prompt for actionable smart home intents,
    validates against the whitelist, and returns an executable action dictionary.
    Returns None if no actionable or whitelisted intent is present.
    """
    text = (user_text or "").strip().lower()

    # 1. Climate / Thermostat Target Temperature
    for pattern in CLIMATE_TEMP_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            temp_str = match.group(1)
            try:
                temp_val = float(temp_str)
                # Verify safe temperature bounds
                is_valid, msg, s_data = validate_ha_action(
                    domain="climate",
                    service="set_temperature",
                    service_data={"entity_id": "climate.nest_thermostat", "temperature": temp_val}
                )
                if is_valid:
                    return {
                        "category": "home_assistant",
                        "domain": "climate",
                        "service": "set_temperature",
                        "service_data": s_data,
                        "description": f"Set Nest Thermostat to {temp_val}°F"
                    }
            except Exception:
                pass

    # 2. Lighting Controls
    for pattern, srv in LIGHT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            target_str = match.group(1).strip()
            # Match against known lights
            entity_id = None
            if "back" in target_str or "yard" in target_str:
                entity_id = "light.back_yard_floodlight_timed"
            elif "side" in target_str:
                entity_id = "light.side_yard_floodlight_timed"
            elif "driveway" in target_str or "front" in target_str:
                entity_id = "light.driveway_front_door_floodlight_timed"

            if entity_id:
                is_valid, msg, s_data = validate_ha_action(
                    domain="light",
                    service=srv,
                    service_data={"entity_id": entity_id}
                )
                if is_valid:
                    return {
                        "category": "home_assistant",
                        "domain": "light",
                        "service": srv,
                        "service_data": s_data,
                        "description": f"{srv.replace('_', ' ').title()} {entity_id}"
                    }

    return None
