# Bleach: Brave Souls Auto Co-op Bot

An advanced, stealth-focused autonomous agent for Bleach: Brave Souls co-op quest farming on Linux/X11. This project has evolved through 9 generations to achieve a balance between human-like behavior and bulletproof reliability.

## ⚠️ DISCLAIMER - USE AT YOUR OWN RISK

**NO SUPPORT PROVIDED**: This project is released as-is with no warranty, support, or maintenance. The author accepts no responsibility for:
- Account bans or penalties from game publishers
- **Terms of Service (TOS) violations** (Automation is a bannable offense)
- System damage or data loss
- Any other consequences of using this software

**LEGAL WARNING**: Game automation **violates the Terms of Service** of KLab and most game publishers. It will likely result in a permanent account ban if detected. By using this software, you acknowledge that you are solely responsible for any consequences. Use entirely at your own risk.

---

## Project Status & Versions

- **V2 (Legacy)**: Basic functionality. High stability, but slow nested-loop architecture.
- **V6 (Classic)**: The "Proactive" base. Very fast, but prone to logic loops and lacks orb-safety.
- **V8 (Strict Agent)**: Failed experiment with complex screen classification. Too rigid for small resolutions.
- **V9 (Hardened Hybrid)**: **Current Production Candidate.** Combines the speed of V6 with the safety gates and hardened recovery of V8. 

---

## 🌟 Key Features (V9)

*   **Snapshot Architecture**: Captures the screen once per loop and performs all matching in memory (<10ms). Zero lag, zero stutter.
*   **Zero-Latency Refocusing**: Restores window focus in `< 2ms`, allowing the bot to run completely silent while you work in other windows.
*   **Orb Protection (Phase Gates)**: Strictly forbids clicking `okay.png` during live runs. Will never spend your orbs on accidental revives.
*   **Progress-Only Watchdog**: Only resets the hang timer when real quest progress is made. Prevents "Loop Blindness" where other bots would stay stuck in the menu forever.
*   **Resolution-Resilient**: Scans the full game window with no restrictive masking. Works perfectly on small or scaled windows (e.g., 806x482).
*   **Autonomous Search**: No longer waits for timeouts. Proactively refreshes the room list if no valid targets are found.

## Requirements

- **OS**: Linux with X11 (Wayland is not natively supported for direct input).
- **System Tools**: `xdotool`, `wmctrl`, `xprop`, `x11-utils`.
- **Python 3.10+**: Requires `pyautogui`, `pyscreeze`, `python-xlib`, `Pillow`.
- **Game Settings**: Bleach: Brave Souls running in **windowed mode**.

## Setup

```bash
# Install system dependencies
sudo apt install python3 python3-pip python3-venv xdotool wmctrl x11-utils

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

**Run the Production Candidate (V9):**
```bash
python3 bbs_bot_v9.py
```

**Run for Debugging (Includes Screenshots):**
```bash
python3 bbs_bot_v9.py --debug-screenshots
```

**Run for Safety Check (Dry Run):**
```bash
python3 bbs_bot_v9.py --dry-run
```

## Known Issues
- **X11 Only**: Direct memory clicks and focus restoration rely on Xlib.
- **Color Sensitive**: Matching can fail if your OS uses a non-standard color profile (HDR/10-bit). Keep display settings standard.
