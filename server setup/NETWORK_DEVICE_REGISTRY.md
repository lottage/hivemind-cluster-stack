# Homelab Network & Device IP Registry

Static DHCP reservations, hardware MAC addresses, service endpoints, and device roles across the homelab network (`192.168.1.0/24`).

---

## 1. Physical Compute Nodes & Hypervisors
| Hostname | Node | IP Address | MAC Address | Hardware / Role |
| :--- | :--- | :--- | :--- | :--- |
| `proxmox-cluster` | Cluster VIP | `192.168.1.245:8006` | `70-20-84-09-7F-91` | Proxmox VE 9.2 Unified Cluster API & GUI |
| `pve` | Node 1 | `192.168.1.229` | — | Intel Core i7-12700K, 32GB RAM, Dual AMD GPUs |
| `bigserv` | Node 2 | `192.168.1.82` | — | Application, Storage & Home Automation Node |

---

## 2. Virtual Machines & Containers (AI Stack & Media)
| Name | Type | IP Address | MAC Address | Port / Web URL | Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `ubu` | VM 102 | `192.168.1.105` | `BC-24-11-94-EA-3C` | `:8001`, `:8002`, `:8003`, `:8765` | Dual GPU Compute (14B, 3B, BGE, MCP) |
| `qdrant` | LXC 117 | `192.168.1.112` | `BC-24-11-66-B7-44` | `:6333/dashboard` | 5-Collection Persistent Vector Brain |
| `homeassistant` | VM 103 | `192.168.1.82` | `02-0E-76-0D-65-4A` | `:8123` | Home Assistant OS (HAOS 17.3) |
| `kavita` | LXC 100 | `192.168.1.124` | `BC-24-11-53-B7-8F` | `:5000` | Digital Manga, Comics & Book Library |
| `jellyfin` | LXC 104 | `192.168.1.180` | `BC-24-11-0D-74-EC` | `:8096` | Media Streaming Server |
| `immich` | LXC 107 | `192.168.1.238` | `BC-24-11-92-9A-D9` | `:9000` | Self-Hosted High-Res Photo & Video Vault |
| `freshrss` | LXC 108 | `192.168.1.212` | `BC-24-11-20-A7-2A` | `:80` | RSS & News Feed Aggregator |
| `prowlarr` | LXC 109 | `192.168.1.125` | `BC-24-11-E4-D0-74` | `:9696` | Indexer & Torrent Manager |
| `sonarr` | LXC 110 | `192.168.1.126` | `BC-24-11-D0-19-BE` | `:8989` | Automated TV Series Management |
| `radarr` | LXC 111 | `192.168.1.127` | `BC-24-11-C2-FD-3C` | `:7878` | Automated Movie Management |
| `lidarr` | LXC 112 | `192.168.1.128` | `BC-24-11-AD-C2-A3` | `:8686` | Automated Music Management |
| `openwebui` | LXC 119 | `192.168.1.108` | `BC-24-11-2F-AE-D4` | `:8080` | Multi-Model Web UI |
| `qbittorrent` | LXC 114 | `192.168.1.169` | `BC-24-11-B0-CA-09` | `:8090` | Automated Torrent Download Client |
| `flaresolverr` | LXC | `192.168.1.159` | `BC-24-11-80-89-BC` | `:8191` | Cloudflare Challenge Solver Proxy |
| `docker` | LXC 105 | `192.168.1.204` | `BC-24-11-85-2C-F2` | `:9443` | Docker & Portainer Container Host |
| `obsidian-live-sync` | LXC 116 | `192.168.1.230` | `BC-24-11-4C-50-5E` | `:5984` | CouchDB Self-Hosted Obsidian LiveSync Server |
| `stonesage` | LXC 120 | `192.168.1.167` | `BC-24-11-40-F0-69` | `:8080` | StoneSage 24/7 Command Cockpit & Automation Server |
| `voice-services` | LXC 121 | `192.168.1.121` | `BC-24-11-32-6E-DB` | `:8200` (STT), `:8300` (TTS), `:10300` (Wyoming STT), `:10200` (Wyoming TTS) | Local Voice Stack: Faster Whisper + Kokoro ONNX + Wyoming Protocol |
| `bhyve-bh1g2` | VM | `192.168.1.87` | `44-67-55-2F-0A-22` | — | FreeBSD / TrueNAS Storage Subsystem |

---

## 3. Smart Home & IoT Hardware
| Device Name | IP Address | MAC Address | Protocol / Integration | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `Nest-Thermostat-9A6E` | `192.168.1.62` | `B4-23-A2-1B-9A-6E` | Matter over Wi-Fi / Google SDM | Living Room HVAC Thermostat |
| `KP125` | `192.168.1.109` | `10-27-F5-8F-36-73` | TP-Link Kasa TCP `:9999` | Smart Plug with Real-time Energy Monitoring |
| `GE_Plug_B0BC` | `192.168.1.17` | `34-13-43-BF-B0-BC` | GE Cync / Google Home | Smart Outlet B0BC |
| `GE_Plug_1FB4` | `192.168.1.111` | `34-13-43-F0-1F-B4` | GE Cync / Google Home | Smart Outlet 1FB4 |
| `GE_Plug_EAF0` | `192.168.1.143` | `34-13-43-BF-EA-F0` | GE Cync / Google Home | Smart Outlet EAF0 |
| `LG_Smart_Dryer2_open` | `192.168.1.56` | `14-7F-67-FD-DB-7C` | LG ThinQ Integration | Smart Laundry Dryer |
| `Petkit_T4` | `192.168.1.10` | `08-3A-8D-BF-50-B8` | Petkit Local / Cloud | Smart Pet Feeder / Water Fountain |

---

## 4. Personal Client Devices & Cockpit Endpoints
| Client Name | IP Address | MAC Address | Hardware | Role |
| :--- | :--- | :--- | :--- | :--- |
| `Austin-s-S25-Ultra` | `192.168.1.178` | `DA-DB-17-7E-58-DD` | Samsung Galaxy S25 Ultra | Primary Mobile Device, Tailscale Cockpit & PWA |
| `Laptop` | `192.168.1.132` | `48-45-E6-4A-DF-BD` | Windows Host | StoneSage Cockpit, Dev Workstation & Antigravity Host |

---

## 5. Network Infrastructure & Gateways
| Device / Label | IP Address | MAC Address | Function |
| :--- | :--- | :--- | :--- |
| `network device` | `192.168.1.7` | `BC-24-11-C3-5F-AE` | Network Switch / Bridge Interface |
| `network device` | `192.168.1.217` | `5C-E7-53-4F-3E-CA` | Wi-Fi Access Point / Router |
| `none-2` | `192.168.1.193` | `08-6A-E5-C4-E0-C2` | Auxiliary Network Device |
