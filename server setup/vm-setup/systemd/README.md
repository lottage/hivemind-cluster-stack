# VM 102 systemd units

Copied from the live `/etc/systemd/system/` on VM 102 (192.168.1.105) on 2026-09-23 at 13:40, after GPU layout A
was installed. Top level = enabled and running. `disabled/` = installed on the VM but disabled
(Assembly Hall, the Ornith 35B MoE and the ROCm variants).

- GPUs are pinned with `Environment=GGML_VK_VISIBLE_DEVICES` (0 = RX 6750 XT, 1 = RX 6600). With that set,
  `--device Vulkan0` means "first visible device", not the 6750.
- `cluster-mcp.service` reads `HASS_URL`/`HASS_TOKEN` from `/etc/stonesage/secrets.env` (root, 600). No secrets in these files.
- To change a unit, start from the live copy (`systemctl cat <unit>`), not these files, then copy the result back
  here. See the `homelab-deploy` skill.
