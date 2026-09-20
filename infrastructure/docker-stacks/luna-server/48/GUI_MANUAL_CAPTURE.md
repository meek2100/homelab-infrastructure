# 📊 Manual GUI Network Capture Guide

Follow these instructions to safely pause the automated background capture daemon and transition to a manual debugging session using the Wireshark web interface (`wireshark.secure.theurer.dev`).

---

## 🛑 Step 1: Switch to Manual GUI Mode in Portainer

Because the background `dumpcap` process continuously locks your physical sniffer card interface (`ens19`), you must turn it off before running a manual capture to avoid packet drops and interface conflicts.

1. Open your **Portainer Dashboard**.
2. Navigate to your **Wireshark Stack** and click **Editor**.
3. Locate the `AUTOCAPTURE` variable in the `environment:` block and change it to **`false`**:
   ```yaml
   environment:
     - AUTOCAPTURE=false # SET TO 'true' FOR Headless Capture | SET TO 'false' FOR Pure GUI Mode
   ```
4. Click **Update the Stack** at the bottom of the window. 
   *(The background capture daemon will instantly exit on boot, leaving the `ens19` physical pipe completely free for the GUI).*

---

## 🎛️ Step 2: Configure the Manual GUI Parameters

1. Open your browser and go to: `https://theurer.dev`
2. If a capture session is already running, click the **Red Square** in the top-left toolbar to stop it.
3. Press **`Ctrl + K`** to open the **Capture Options** configuration panel.

### 🔌 Tab A: Input
* **Interface Matrix Grid:** Highlight and select **`ens19`**.
* **Capture Filter Text Box:** Paste your exact loop-prevention filter string:
  ```text
  not host 192.168.40.248 and not port 3000 and not port 3001
  ```

### 💾 Tab B: Output
* **File Input Box:** Type exactly: `/nas-storage/manual_debug.pcapng`
* **Create a new file automatically after...**: Check the box and set it to `100 megabytes`.
* **Use a ring buffer with...**: Check the box and set it to `10 files` *(Limits manual tests so they don't impact your main storage pool).*

### ⚙️ Tab C: Options
* Ensure the **`Run a script after closing each file`** text field box is completely **EMPTY/BLANK**. *(Manual captures bypass the RAM cache and save directly to your OMV network share).*

---

## 🚀 Step 3: Run and Restore Automation

1. Click the green **Start** button at the bottom right of the Capture Options box. Packets will immediately begin scrolling on screen.
2. **To Restore 24/7 Headless Automation Later:** Go back into your **Portainer Stack Editor**, change the variable back to **`AUTOCAPTURE=true`**, and click **Update the Stack**.

