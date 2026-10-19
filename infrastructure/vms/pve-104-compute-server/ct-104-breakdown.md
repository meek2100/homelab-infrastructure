# 🖥️ Detailed Container & Service Breakdown: `compute-server` (`pve` CT 104)

* **Host Proxmox Node**: `pve` (`192.168.1.250`)
* **Target Container**: `CT 104` (`compute-server`)
* **IP Address**: `192.168.40.246/24` (VLAN 40)
* **OS**: Debian GNU/Linux 12 (bookworm) LXC Unprivileged Container
* **Compute Allocation**: 4 vCPUs, 8 GB RAM, 32 GB NVMe Rootfs

---

## ⚡ Hardware Acceleration & Dual-GPU Mappings

1. **Intel HD Graphics P630 (QuickSync VA-API)**:
   * Device mappings: `/dev/dri/card0`, `/dev/dri/renderD128` (major 226)
   * Driver: `iHD` driver supporting HEVC Main10, H.264, VP8/VP9, and JPEG hardware transcode
   * Consumer: **Plex Media Server** (`:32400`)

2. **NVIDIA Quadro M1200 Mobile (4GB VRAM)**:
   * Host Driver: `580.178.04` (Linux Kernel 7.0.14-24-pve)
   * Device mappings: `/dev/nvidia0`, `/dev/nvidiactl`, `/dev/nvidia-uvm`, `/dev/nvidia-uvm-tools`, `/dev/nvidia-caps/*` (majors 195, 505, 508)
   * Libraries: Host bind mount `/usr/lib/x86_64-linux-gnu/nvidia/current` linked into `/usr/lib/x86_64-linux-gnu/`
   * Consumer: **Ollama Local AI Inference** (`:11434`) via CUDA 12

---

## 🚀 Active Services & Port Matrix

| Service | Port | Endpoint / URL | Purpose | Backend Runtime |
| :--- | :---: | :--- | :--- | :--- |
| **Plex Media Server** | `32400/tcp` | `http://192.168.40.246:32400` | Media streaming & hardware transcode | Docker / Native |
| **Ollama AI Engine** | `11434/tcp` | `http://192.168.40.246:11434` | Local LLM & embedding inference | systemd (`ollama.service`) |
| **Open WebUI** | `3000/tcp` | `http://192.168.40.246:3000` | Web chat & local document RAG | Docker (`open-webui`) |
| **SSH Server** | `22/tcp` | `meek2100@192.168.40.246` | Remote administration | OpenSSH (`proxmox_ed25519`) |

---

## 🤖 Deployed LLM & Embedding Roster

| Model Name | Parameter Size | Disk Footprint | VRAM Context Cap | Primary Role |
| :--- | :---: | :---: | :---: | :--- |
| **`qwen2.5:3b-instruct`** | 3.1B | 1.84 GB | 4096 tokens | Primary assistant & daily briefings |
| **`llama3.2:3b`** | 3.2B | 1.93 GB | 4096 tokens | Conversational co-pilot & writing |
| **`deepseek-r1:1.5b`** | 1.5B | 1.07 GB | Dynamic | Deep reasoning & logic problems |
| **`qwen2.5-coder:1.5b`** | 1.5B | 940 MB | Dynamic | Code review, shell & YAML syntax |
| **`llama3.2:1b`** | 1.2B | 1.26 GB | Dynamic | Ultra-fast home automation / notifications |
| **`nomic-embed-text`** | 137M | 262 MB | 8192 tokens | Document search & Second Brain RAG |

---

## 🔒 Security & Secrets Hygiene

* **Access Identity**: User `meek2100` (UID 1000) with passwordless `sudo` in `/etc/sudoers.d/meek2100`.
* **SSH Key**: Public key `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHQ0qHGWnCbwaRbPf1Nlx+iMTw4+9sKHlOD5+em/bkED dtheurer@011PRD-HKWJBK3`.
* **Zero-Cloud Privacy**: In-cluster local inference only; zero external cloud LLM dependencies.
