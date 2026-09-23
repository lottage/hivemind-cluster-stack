# PVE Out-of-Band Hardware Fencing Watchdog Guide

Automated hardware watchdog and smart-plug power cycler running 24/7 on **Node 2 (`bigserv` / LXC 120 `stonesage` @ `192.168.1.167`)** to monitor **Node 1 (`pve` @ `192.168.1.229`)** and resolve kernel/PCIe driver freeze conditions without manual intervention.

---

## 1. System Architecture & Role Division

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 NODE 2: bigserv (24/7 Out-of-Band Observer)                 │
│                   LXC 120 (stonesage @ 192.168.1.167)                       │
│                                                                             │
│   • Service: pve-watchdog.service (Systemd Daemon)                          │
│   • Script:  /opt/pve-watchdog/pve_hardware_watchdog.py                     │
│   • Probing Matrix (Every 10s):                                             │
│       [1] Self-Sanity Check (Gateway 192.168.1.217 / DNS 1.1.1.1)          │
│       [2] pve Physical Host Ping (192.168.1.229)                            │
│       [3] pve Physical Host SSH Port 22 (:22 TCP)                           │
│       [4] VM 102 Compute Host Ping (192.168.1.105)                          │
│       [5] VM 102 Compute Host SSH Port 22 (:22 TCP)                         │
│       [6] Proxmox Cluster Corosync API (:8006 node/pve/status)              │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
            If 100% Unreachable for    │ Local TCP Port 9999 (TP-Link XOR)
            >= 120 Continuous Seconds  │ (Sub-10ms, No Cloud, No HA Dependency)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 SMART POWER OUTLET: TP-Link Kasa KP125(US)                  │
│                     IP: 192.168.1.109:9999 (Alias: 'Server')                │
│                                                                             │
│   1. Relay OFF (0) -> Cuts 120V AC input to pve                             │
│   2. Sleep 8 Seconds -> Full discharge of ATX power supply capacitors       │
│   3. Relay ON (1) -> Restores AC power                                      │
│   4. Motherboard BIOS ("Restore on AC Power Loss") boots pve immediately    │
│   5. 10-Minute Lockout -> Suppresses cycles while BIOS POST / OS boots      │
│   6. Dispatches persistent notification to Home Assistant OS (:8123)        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. The 5 "100% For Sure" Failsafe Invariants

To guarantee the watchdog **never** falsely power-cycles a live server that is undergoing heavy computation, mmap caching, or an intentional reboot, it enforces:

1. **Multi-Vector Triangulation**:
   All three layers (physical host ping/SSH, compute VM ping/SSH, and Proxmox cluster corosync telemetry) must report completely dead simultaneously. If **any single probe succeeds**, the node is treated as alive.
2. **Self-Sanity Gateway Guard**:
   Before evaluating Node 1, `bigserv` verifies its own network connection against the local gateway (`192.168.1.217`) and internet DNS (`1.1.1.1`). If `bigserv` loses network, the failure streak immediately resets.
3. **120-Second Continuous Hold-Down Timer**:
   Transient network drops or regular OS reboots (~45–60s) will never trigger the relay. All targets must remain 100% unresponsive across **12 consecutive 10-second cycles**.
4. **Anti-Flapping & Rate Limiting**:
   - **10-Minute Cooldown**: Post-cycle grace period during which the smart plug will not be touched under any circumstances.
   - **Rate Limit**: Maximum 2 power cycles per hour. If a machine fails to recover after cycling, it enters `SAFETY LOCKOUT` requiring physical inspection.
5. **Capacitor Discharge Timing (8 Seconds)**:
   Modern ATX power supplies hold standby charge for 3–5 seconds. The 8-second off-window ensures the power rail drops to 0V so the motherboard detects genuine power loss and triggers the BIOS power-on policy.

---

## 3. Operational Commands & Maintenance

### Check Service Status on `stonesage` (LXC 120):
```bash
ssh root@192.168.1.167 "systemctl status pve-watchdog.service"
```

### View Live Watchdog Journal:
```bash
ssh root@192.168.1.167 "journalctl -u pve-watchdog.service -f"
```

### Run Multi-Vector Probe Diagnostics (Dry-Run):
```bash
ssh root@192.168.1.167 "python3 /opt/pve-watchdog/pve_hardware_watchdog.py --test-probes"
```

### Probe Smart Plug Info:
```bash
ssh root@192.168.1.167 "python3 /opt/pve-watchdog/pve_hardware_watchdog.py --test-plug"
```

### Restart / Reload Watchdog:
```bash
ssh root@192.168.1.167 "systemctl restart pve-watchdog.service"
```

---

## 4. Source Files

- Local Workspace Source: [`server setup/watchdog/pve_hardware_watchdog.py`](file:///c:/Users/johna/OneDrive/Documents/.ai/server%20setup/watchdog/pve_hardware_watchdog.py)
- Systemd Unit: [`server setup/watchdog/pve-watchdog.service`](file:///c:/Users/johna/OneDrive/Documents/.ai/server%20setup/watchdog/pve-watchdog.service)
- Automated Deployment Script: [`server setup/watchdog/deploy_watchdog.ps1`](file:///c:/Users/johna/OneDrive/Documents/.ai/server%20setup/watchdog/deploy_watchdog.ps1)
