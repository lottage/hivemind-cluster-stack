# Obsidian Self-Hosted LiveSync: Homelab Cluster Integration Guide

This guide documents how **Self-Hosted LiveSync** (obsidian-livesync) is deployed and configured to synchronize your personal knowledge vault across your Windows laptop, Samsung Galaxy S25 Ultra, and the StoneSage tertiary backup vault via the dedicated CouchDB cluster instance.

---

## 1. Active Infrastructure & Endpoints

| Component | Location / Host | IP / Endpoint | Role |
| :--- | :--- | :--- | :--- |
| **CouchDB Sync Server** | LXC 116 (igserv) | http://192.168.1.230:5984 | 24/7 Central Replication Server (CouchDB v3.5.2) |
| **Primary Vault** | Laptop | C:\Users\johna\OneDrive\Documents\obsidian | Main knowledge base & daily driver |
| **Mobile Vault** | Samsung Galaxy S25 Ultra | Obsidian Android App (192.168.1.178) | Mobile capture & notes |
| **Tertiary Backup Vault** | StoneSage Cockpit | c:\Users\johna\OneDrive\Documents\.ai\StoneSage\vault_backup | Zero-delete archival vault with git micro-commits |

---

## 2. Vault Configuration Status

### Tertiary Vault (StoneSage/vault_backup)
- **Plugin Installed**: Self-hosted LiveSync (v1.0.24) installed in .obsidian/plugins/obsidian-livesync/.
- **Enabled in Config**: .obsidian/community-plugins.json configured with ["obsidian-livesync"].
- **Preconfigured Settings**:
  - couchDB_URI: http://192.168.1.230:5984
  - deviceAndVaultName: StoneSage-Tertiary
  - 	rashInsteadDelete: 	rue (Enforces Zero-Delete protection)
  - syncOnSave: 	rue
  - syncOnStart: 	rue
- **Obsidian Registered**: Registered in C:\Users\johna\AppData\Roaming\obsidian\obsidian.json so you can open it directly from the Obsidian vault switcher.

---

## 3. How to Connect All Devices

You can synchronize your devices using **CouchDB (Recommended for Homelab)** or **P2P Sync**:

### Method A: Centralized Sync via Local CouchDB (192.168.1.230:5984)
*Benefits: Instant continuous background replication, works whenever any device touches your Wi-Fi or Tailscale without needing the other device powered on.*

1. **In Obsidian (on Laptop or Phone)**:
   - Open **Settings** -> **Community Plugins** -> **Self-hosted LiveSync** options (gear icon).
   - Under **General Settings**:
     - Set **Remote type** to CouchDB.
     - **URI**: http://192.168.1.230:5984
     - **User**: Your CouchDB admin username (created when LXC 116 was deployed).
     - **Password**: Your CouchDB admin password.
     - **Database Name**: e.g., obsidian-vault.
2. **Initialize Database**:
   - Click **Check Connectivity** -> Once connected, click **Test & Create Database**.
3. **Replication Settings**:
   - Toggle **LiveSync** to ON.
   - Toggle **Sync on Save** and **Sync on Start** to ON.
4. **On Other Devices (e.g. S25 Ultra & StoneSage Vault)**:
   - In Self-hosted LiveSync settings, click **Copy Setup URI** on the first device.
   - On the second device, click **Setup with URI** and paste the encrypted string.

---

### Method B: Direct P2P Sync (Current Phone-to-Laptop Setup)
*Benefits: Zero server configuration required, encrypted end-to-end between active devices.*

1. In your primary vault, open **Self-hosted LiveSync** settings.
2. In the **P2P Sync** section:
   - Click **Show QR Code / Copy Setup URI**.
3. In your other vault or device:
   - Open **Self-hosted LiveSync** -> Click **Import Setup URI** or scan QR code.
   - Enter your sync passphrase.
4. Changes will stream directly between your devices in real-time.

---

## 4. StoneSage Cockpit Integration

Within StoneSage (http://127.0.0.1:8080):
- **Obsidian Tab**: Displays all files and notes in the tertiary vault.
- **Save Note**: Updates trigger automated git micro-commits.
- **Delete Note**: Intercepted by the Zero-Delete engine and saved into _archive/<note>.<timestamp>.tombstone.
- **Embed in Brain**: 1-click embeds notes into Qdrant (192.168.1.112:6333) so your 14B Coordinator and 3B Worker can answer questions based on your notes!
