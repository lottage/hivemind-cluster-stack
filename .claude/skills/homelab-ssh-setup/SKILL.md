---
name: homelab-ssh-setup
description: >-
  Generate, configure, and deploy secure passwordless SSH Ed25519 key pairs from Windows
  to Linux homelab hosts, Proxmox VE nodes, and VMs (e.g. Ubuntu VM 127.0.0.1).
  Use whenever the user or agent needs passwordless remote access, automated file sync (SCP/rsync),
  or secure remote command execution without exposing credentials in chat or scripts.
---

# Homelab Passwordless SSH Key Setup

This skill provides the standard operating procedure for configuring secure, passwordless SSH key authentication from a Windows workstation to remote Linux hosts, Proxmox VE hypervisors, and VMs.

## Why SSH Keys Over Passwords
- **Zero Plaintext Exposure**: Passwords never touch chat transcripts, shell history, or automation scripts.
- **Uninterrupted Automation**: Scripts like `sync_to_pve.ps1` and background agents can SCP/SSH without prompting for user interaction.
- **Cryptographic Strength**: Modern Ed25519 keys offer superior security and faster handshakes than legacy RSA.

---

## Standard Procedure

### Step 1: Check for Existing Keys
In Windows PowerShell, check if an Ed25519 key pair already exists:
```powershell
Test-Path "$HOME\.ssh\id_ed25519.pub"
```
If `True`, skip to **Step 3**.

---

### Step 2: Generate Ed25519 Key Pair
Generate a high-security key pair with an empty passphrase for automated non-interactive tasks:
```powershell
ssh-keygen -t ed25519 -f "$HOME\.ssh\id_ed25519" -N '""'
```
This generates:
- Private key: `C:\Users\<user>\.ssh\id_ed25519` (keep secret!)
- Public key: `C:\Users\<user>\.ssh\id_ed25519.pub`

---

### Step 3: Deploy Public Key to Remote Host
On Windows, `ssh-copy-id` is often unavailable by default. Deploy the public key using this cross-platform PowerShell pipe:

```powershell
# Syntax: type <pubkey> | ssh <user>@<host> "<commands>"
type "$HOME\.ssh\id_ed25519.pub" | ssh <username>@127.0.0.1 "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

*Note: The user will be prompted for the remote account password exactly once during this step.*

---

### Step 4: Verify Passwordless Connection
Test that authentication succeeds without prompting:
```powershell
ssh -o BatchMode=yes <username>@127.0.0.1 "echo '[SUCCESS] Passwordless SSH is active!'"
```
If the command prints the success message without prompting for a password, setup is complete.

---

### Step 5: (Optional) Create Host Shortcut in SSH Config
To avoid typing IP addresses and usernames, add an entry to `$HOME\.ssh\config`:

```text
Host pve-ubu
    HostName 127.0.0.1
    User <username>
    IdentityFile ~/.ssh/id_ed25519

Host bigserv-haos
    HostName 127.0.0.1
    Port 22222
    User root
    IdentityFile ~/.ssh/id_ed25519
```

Test shortcut:
```powershell
ssh pve-ubu
```

---

## Automation Helper Script

For 1-click deployment, run:
[`scripts/setup_ssh.ps1`](./scripts/setup_ssh.ps1)
