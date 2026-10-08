#!/bin/sh
# ExecStartPre for the llama-server units on VM 102 (installed as /usr/local/bin/wait-for-gpus.sh).
# At boot the units can start before amdgpu has brought every GPU up; llama-server then finds no Vulkan
# device and silently runs on the CPU (2026-09-24: coordinator at 0.8 tok/s instead of 42).
# Waits until Vulkan lists as many AMD devices as there are AMD display controllers on the PCI bus.
# Deliberately no hardware names: the count comes from the bus.
want=$(grep -l '^0x03' /sys/bus/pci/devices/*/class 2>/dev/null | while read -r f; do
  d=${f%/class}; [ "$(cat "$d/vendor")" = 0x1002 ] && echo x; done | wc -l)
[ "$want" -gt 0 ] || exit 0
i=0
while [ $i -lt 90 ]; do
  have=$(GGML_VK_VISIBLE_DEVICES= vulkaninfo --summary 2>/dev/null | grep -c 'driverName *= *radv')
  [ "$have" -ge "$want" ] && exit 0
  i=$((i + 1)); sleep 1
done
echo "wait-for-gpus: only $have of $want AMD GPUs visible to Vulkan after 90 s" >&2
exit 1
