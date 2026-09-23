#!/usr/bin/env python3
"""
PVE Hardware Watchdog & Out-of-Band Power Cycler (Fencing Daemon)
Runs 24/7 on Node 2 (LXC 120 'stonesage' @ 192.168.1.167 on bigserv).

Monitors Node 1 ('pve' @ 192.168.1.229) and compute VM 102 ('ubu' @ 192.168.1.105)
using a triangulated multi-vector probing matrix. When 100% frozen/unresponsive
for >= 120 continuous seconds, power-cycles the TP-Link Kasa KP125 smart plug ('Server' @ 192.168.1.109)
via local TCP :9999 (8-second off duration to discharge motherboard/PSU capacitors).
"""

import os
import sys
import time
import socket
import struct
import json
import ssl
import signal
import logging
import argparse
import subprocess
import urllib.request
import urllib.error
from datetime import datetime

# Default Network Topology Configuration
PVE_HOST_IP = "192.168.1.229"        # Physical Node 1 (pve)
PVE_SSH_PORT = 22
VM102_IP = "192.168.1.105"           # Dual AMD GPU compute host VM (ubu)
VM102_SSH_PORT = 22
GATEWAY_IP = "192.168.1.217"         # Local AP/gateway for self-sanity check
FALLBACK_DNS = "1.1.1.1"             # External internet sanity check

KASA_PLUG_IP = "192.168.1.109"       # KP125(US) 'Server' plug
KASA_PORT = 9999

PROXMOX_API_URL = "https://192.168.1.245:8006"
PROXMOX_TOKEN = os.environ.get("PVE_TOKEN", "")  # "PVEAPIToken=USER@pam!TOKENID=SECRET" via /etc/stonesage/secrets.env

HASS_URL = "http://192.168.1.82:8123"
HASS_TOKEN = os.environ.get("HASS_TOKEN", "")
if not HASS_TOKEN:
    import sys as _sys
    print("WARNING: HASS_TOKEN is not set (expected in /etc/stonesage/secrets.env); Home Assistant calls will fail.", file=_sys.stderr)

# Watchdog Invariants & Timings
PROBE_INTERVAL_SEC = 10              # Probe every 10 seconds
HOLD_DOWN_SEC = 120                  # Must remain dead for 120 consecutive seconds (12 checks)
COOLDOWN_SEC = 600                   # 10-minute lockout after power cycling
POWER_OFF_DURATION_SEC = 8           # 8-second off window to discharge ATX power supply capacitors
MAX_CYCLES_PER_HOUR = 2              # Hard anti-loop ceiling

LOG_FILE = "/var/log/pve_watchdog.log"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Watchdog] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("pve_watchdog")


# ==============================================================================
# 1. TP-Link Kasa Local Protocol (Port 9999 XOR)
# ==============================================================================

def kasa_encrypt(string: str) -> bytes:
    key = 171
    result = bytearray(struct.pack('>I', len(string)))
    for i in string.encode():
        a = key ^ i
        key = a
        result.append(a)
    return bytes(result)


def kasa_decrypt(data: bytes) -> str:
    key = 171
    result = []
    for i in data[4:]:
        a = key ^ i
        key = i
        result.append(a)
    return bytes(result).decode(errors="replace")


def kasa_send_command(ip: str, port: int, cmd_dict: dict, timeout: float = 3.0) -> dict:
    payload = json.dumps(cmd_dict)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((ip, port))
    s.send(kasa_encrypt(payload))
    data = b''
    while True:
        chunk = s.recv(2048)
        if not chunk:
            break
        data += chunk
        if len(data) >= 4:
            length = struct.unpack('>I', data[:4])[0]
            if len(data) >= 4 + length:
                break
    s.close()
    return json.loads(kasa_decrypt(data))


def kasa_get_info(ip: str = KASA_PLUG_IP, port: int = KASA_PORT) -> dict:
    try:
        res = kasa_send_command(ip, port, {"system": {"get_sysinfo": {}}})
        sysinfo = res.get("system", {}).get("get_sysinfo", {})
        return {
            "ok": True,
            "alias": sysinfo.get("alias"),
            "model": sysinfo.get("model"),
            "relay_state": sysinfo.get("relay_state"),
            "rssi": sysinfo.get("rssi")
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def kasa_set_relay(state: int, ip: str = KASA_PLUG_IP, port: int = KASA_PORT) -> bool:
    try:
        res = kasa_send_command(ip, port, {"system": {"set_relay_state": {"state": state}}})
        err_code = res.get("system", {}).get("set_relay_state", {}).get("err_code", -1)
        return err_code == 0
    except Exception as e:
        logger.error(f"Failed to set Kasa relay to {state}: {e}")
        return False


def execute_power_cycle(off_seconds: int = POWER_OFF_DURATION_SEC, dry_run: bool = False) -> bool:
    """Executes the physical power cycle sequence."""
    if dry_run:
        logger.warning(f"DRY-RUN: Would send RELAY OFF to {KASA_PLUG_IP}, sleep {off_seconds}s, and RELAY ON.")
        return True

    logger.critical(f"EXECUTE: Turning smart plug '{KASA_PLUG_IP}' OFF for {off_seconds}s...")
    if not kasa_set_relay(0):
        logger.error("Failed to turn smart plug OFF! Aborting cycle.")
        return False

    time.sleep(off_seconds)

    logger.critical(f"EXECUTE: Turning smart plug '{KASA_PLUG_IP}' back ON...")
    if not kasa_set_relay(1):
        logger.critical("Failed to turn smart plug back ON! Retrying once after 2s...")
        time.sleep(2)
        kasa_set_relay(1)

    # Verify relay state
    info = kasa_get_info()
    if info.get("ok") and info.get("relay_state") == 1:
        logger.info("CONFIRMED: Smart plug relay is ON and power is restored to pve.")
        return True
    else:
        logger.critical(f"WARNING: Smart plug verification returned unexpected state: {info}")
        return False


# ==============================================================================
# 2. Multi-Vector Probing Engine
# ==============================================================================

def probe_ping(ip: str, timeout: float = 1.0) -> bool:
    """Sends 1 ICMP echo request using system ping."""
    try:
        res = subprocess.run(
            ["ping", "-c", "1", "-W", str(int(timeout) or 1), ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout + 0.5
        )
        return res.returncode == 0
    except Exception:
        return False


def probe_tcp(host: str, port: int, timeout: float = 1.5) -> bool:
    """Probes whether a TCP socket handshake succeeds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def probe_proxmox_pve_node(timeout: float = 2.0) -> dict:
    """Queries Proxmox cluster status for node 'pve'."""
    url = f"{PROXMOX_API_URL}/api2/json/nodes/pve/status"
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"Authorization": PROXMOX_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            data = json.loads(r.read().decode())
            uptime = data.get("data", {}).get("uptime", 0)
            return {"ok": True, "status": "online" if uptime > 0 else "unknown", "uptime": uptime}
    except urllib.error.HTTPError as e:
        # If node is offline, API returns 500 or 504
        return {"ok": False, "status": "offline", "http_code": e.code}
    except Exception as e:
        return {"ok": False, "status": "unreachable", "error": str(e)}


def check_self_network_health() -> bool:
    """Verifies that bigserv itself has a working network connection."""
    if probe_ping(GATEWAY_IP, timeout=1.0):
        return True
    if probe_ping(FALLBACK_DNS, timeout=1.5):
        return True
    return False


def send_home_assistant_notification(title: str, message: str):
    """Dispatches a persistent notification to Home Assistant OS."""
    try:
        url = f"{HASS_URL}/api/services/persistent_notification/create"
        payload = json.dumps({"title": title, "message": message, "notification_id": "pve_watchdog_fencing"}).encode()
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Authorization": f"Bearer {HASS_TOKEN}", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=3.0) as r:
            pass
        logger.info("Dispatched notification to Home Assistant.")
    except Exception as e:
        logger.warning(f"Failed to deliver Home Assistant notification: {e}")


# ==============================================================================
# 3. Main Watchdog Loop
# ==============================================================================

class PVEHardwareWatchdog:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.running = True
        self.failure_streak_seconds = 0
        self.cooldown_until = 0
        self.cycle_timestamps = []

        signal.signal(signal.SIGINT, self._handle_exit)
        signal.signal(signal.SIGTERM, self._handle_exit)

    def _handle_exit(self, signum, frame):
        logger.info(f"Received signal {signum}. Gracefully stopping watchdog daemon.")
        self.running = False

    def probe_cluster(self) -> dict:
        """Executes one multi-vector probe matrix."""
        # 1. Self Sanity
        self_ok = check_self_network_health()
        if not self_ok:
            return {"self_ok": False, "alive": True, "reason": "Self network unverified"}

        # 2. Probe PVE Host
        pve_ping = probe_ping(PVE_HOST_IP)
        pve_ssh = probe_tcp(PVE_HOST_IP, PVE_SSH_PORT)

        # 3. Probe VM 102
        vm_ping = probe_ping(VM102_IP)
        vm_ssh = probe_tcp(VM102_IP, VM102_SSH_PORT)

        # 4. Probe Cluster API
        pve_api = probe_proxmox_pve_node()
        api_online = pve_api.get("status") == "online"

        # If ANY vector is responding, the node is considered alive
        alive = pve_ping or pve_ssh or vm_ping or vm_ssh or api_online

        return {
            "self_ok": True,
            "alive": alive,
            "pve_ping": pve_ping,
            "pve_ssh": pve_ssh,
            "vm_ping": vm_ping,
            "vm_ssh": vm_ssh,
            "api_online": api_online,
            "pve_api_raw": pve_api
        }

    def run(self):
        mode_label = "DRY-RUN (Simulated)" if self.dry_run else "LIVE EXECUTION (Armed)"
        logger.info("==================================================================")
        logger.info(f"  PVE Hardware Watchdog Daemon Started [{mode_label}]")
        logger.info(f"  Target: pve ({PVE_HOST_IP}) & VM 102 ({VM102_IP})")
        logger.info(f"  Smart Plug: KP125 'Server' ({KASA_PLUG_IP}:{KASA_PORT})")
        logger.info(f"  Threshold: {HOLD_DOWN_SEC}s continuous dead hold-down timer")
        logger.info(f"  Cooldown: {COOLDOWN_SEC}s post-reboot lockout")
        logger.info("==================================================================")

        # Initial check of smart plug
        plug_info = kasa_get_info()
        if plug_info.get("ok"):
            logger.info(f"Smart plug verified: Alias='{plug_info['alias']}', State={plug_info['relay_state']}")
        else:
            logger.error(f"WARNING: Cannot communicate with smart plug: {plug_info.get('error')}")

        while self.running:
            now = time.time()

            # Check if in cooldown period
            if now < self.cooldown_until:
                rem = int(self.cooldown_until - now)
                logger.debug(f"Watchdog in post-reboot cooldown grace period ({rem}s remaining)...")
                time.sleep(PROBE_INTERVAL_SEC)
                continue

            res = self.probe_cluster()

            if not res.get("self_ok"):
                logger.warning(f"Self network probe failed. Pausing trigger: {res.get('reason')}")
                self.failure_streak_seconds = 0
                time.sleep(PROBE_INTERVAL_SEC)
                continue

            if res["alive"]:
                if self.failure_streak_seconds > 0:
                    logger.info(f"Node 1 recovered after {self.failure_streak_seconds}s of failure. Streak reset to 0.")
                self.failure_streak_seconds = 0
            else:
                self.failure_streak_seconds += PROBE_INTERVAL_SEC
                logger.warning(
                    f"[CONFIRMED DEAD] All vectors unreachable (pve_ping={res['pve_ping']}, "
                    f"pve_ssh={res['pve_ssh']}, vm_ping={res['vm_ping']}, vm_ssh={res['vm_ssh']}, "
                    f"api_online={res['api_online']}). Dead duration: {self.failure_streak_seconds}s / {HOLD_DOWN_SEC}s"
                )

                # Check if hold-down duration threshold is met
                if self.failure_streak_seconds >= HOLD_DOWN_SEC:
                    # Check rate limits
                    hour_ago = now - 3600
                    self.cycle_timestamps = [t for t in self.cycle_timestamps if t > hour_ago]

                    if len(self.cycle_timestamps) >= MAX_CYCLES_PER_HOUR:
                        logger.critical(
                            f"SAFETY LOCKOUT: Exceeded {MAX_CYCLES_PER_HOUR} power cycles in the last hour! "
                            "Halting automated power cycles to prevent hardware flap. Manual intervention required."
                        )
                        send_home_assistant_notification(
                            "🚨 PVE Watchdog SAFETY LOCKOUT",
                            f"Node 1 has exceeded {MAX_CYCLES_PER_HOUR} automated power cycles in 1 hour. Automated fencing suspended."
                        )
                        self.cooldown_until = now + 1800  # Pause for 30 minutes
                        self.failure_streak_seconds = 0
                        continue

                    logger.critical(
                        f"⚡ 100% DEAD TRIGGER CONFIRMED: Node 1 dead for {self.failure_streak_seconds}s continuously! "
                        "Initiating out-of-band power cycle on KP125 'Server'..."
                    )

                    success = execute_power_cycle(POWER_OFF_DURATION_SEC, dry_run=self.dry_run)
                    self.cycle_timestamps.append(now)
                    self.failure_streak_seconds = 0
                    self.cooldown_until = now + COOLDOWN_SEC

                    log_msg = (
                        f"Node 1 ('pve' {PVE_HOST_IP}) was confirmed frozen for {HOLD_DOWN_SEC}s. "
                        f"Power-cycled KP125 plug '{KASA_PLUG_IP}' (8s discharge). "
                        f"10-minute boot cooldown active."
                    )
                    send_home_assistant_notification(
                        "⚡ PVE Hardware Watchdog Triggered",
                        log_msg
                    )

            time.sleep(PROBE_INTERVAL_SEC)


# ==============================================================================
# 4. Entrypoint & CLI Diagnostic Flags
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="PVE Out-of-Band Hardware Fencing Watchdog")
    parser.add_argument("--dry-run", action="store_true", help="Simulate power cycles without altering relay state")
    parser.add_argument("--test-plug", action="store_true", help="Probe KP125 plug info and exit")
    parser.add_argument("--test-probes", action="store_true", help="Run one full multi-vector cluster probe and exit")
    parser.add_argument("--test-cycle", action="store_true", help="Execute an immediate 8s test power cycle on the smart plug")
    args = parser.parse_args()

    if args.test_plug:
        info = kasa_get_info()
        print(json.dumps(info, indent=2))
        sys.exit(0 if info.get("ok") else 1)

    if args.test_probes:
        wd = PVEHardwareWatchdog(dry_run=True)
        res = wd.probe_cluster()
        print(json.dumps(res, indent=2))
        sys.exit(0)

    if args.test_cycle:
        confirm = input(f"Are you sure you want to test power cycling '{KASA_PLUG_IP}' (8 seconds OFF)? [y/N]: ")
        if confirm.lower() == "y":
            ok = execute_power_cycle(POWER_OFF_DURATION_SEC, dry_run=False)
            print("Cycle result:", "SUCCESS" if ok else "FAILED")
            sys.exit(0 if ok else 1)
        else:
            print("Aborted.")
            sys.exit(0)

    watchdog = PVEHardwareWatchdog(dry_run=args.dry_run)
    watchdog.run()


if __name__ == "__main__":
    main()
