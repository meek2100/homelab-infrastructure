# Dell Precision 5520 Dual-GPU & Power Reconfiguration

This runbook guides executing the automated setup script on `pve` (`192.168.1.250`).
It includes pre-emptive **Linux Kernel 7.0+ compatibility patches** (`__vm_flags`, `in_irq()`, and `VMA_LOCK_OFFSET`) for the NVIDIA DKMS module (`nvidia-current 550.xx`) and hooks directly into the Debian package post-install lifecycle to ensure clean completion.

---

## 🚀 Single Execution Command

Run this single command from your terminal:

```bash
ssh root@192.168.1.250 'bash -s' < /home/agentsvc/repos/homelab-infrastructure/mcp/homelab/scripts/reconfigure-pve-gpu-power.sh
```

---

## 🔍 Verification Commands (Run on `pve` post-execution)

```bash
# Verify DKMS module status
dkms status

# Verify NVIDIA driver and Quadro M1200
nvidia-smi

# Verify Intel QuickSync VA-API hardware driver
vainfo

# Verify kernel drivers bound to both GPUs
lspci -nnk | grep -E -A2 'VGA|3D'
```
