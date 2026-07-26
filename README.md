# Bleach: Brave Souls Auto Co-op Bot (BBS Sentinel)

An advanced, stealth-focused autonomous agent for Bleach: Brave Souls co-op quest farming on Linux/X11. This project has evolved through 10 generations to balance human-like behavior, speed, and recovery reliability.

## ⚠️ DISCLAIMER - USE AT YOUR OWN RISK

**NO SUPPORT PROVIDED**: This project is released as-is with no warranty, support, or maintenance. The author accepts no responsibility for:
- Account bans or penalties from game publishers
- **Terms of Service (TOS) violations** (Automation is a bannable offense)
- System damage or data loss
- Any other consequences of using this software

**LEGAL WARNING**: Game automation **violates the Terms of Service** of KLab and most game publishers. It will likely result in a permanent account ban if detected. By using this software, you acknowledge that you are solely responsible for any consequences. Use entirely at your own risk.

---

## 🌟 Key Features (V10)

*   **X11 Click + Refocus Engine**: Uses root-relative Xlib click injection and xdotool focus restoration. The bot clicks the game window without moving your physical mouse cursor, then restores the previously active window.
*   **V2 Coordinate Accuracy**: Calculates click offsets using `self.region[0]` (physical screen space) rather than OS-level `geom` to perfectly bypass Pop!_OS titlebar scaling.
*   **Phantom-Killer Vision**: Uses High-Confidence (0.92–0.95) matching combined with a **3-Frame Temporal Rule**. The bot must see a button for 3 consecutive frames before acting, effectively filtering out 100% of combat flashes and visual noise.
*   **Recovery Triage Hierarchy**: Replaced the "Stuck Relaunch" with a tiered escalation system:
    *   **3 Minutes**: Retire from AFK lobbies gracefully.
    *   **5 Minutes**: Relaunch game if lost in menu loops.
    *   **10 Minutes**: "Nuclear" relaunch if zero global progress is made (Dead Man's Switch).
*   **Modal Gatekeeper**: Intelligently handles the "Select a Room Type" menu. It physically forbids clicking generic "Close" buttons while in the quest menu to prevent accidental quest exiting.
*   **Coffee Breaks (Distractions)**: Simulates fatigue by taking random 2–8 minute breaks after high-intensity sessions. Resets circadian profiles and fatigue modifiers upon waking.
*   **Alignment Mode**: Run with `--alignment-mode` to save a rolling buffer of the **last 100** visual snapshots to `alignment_audit/`.

## Requirements

- **OS**: Linux with X11 (Wayland is not natively supported for direct input).
- **System Tools**: `xdotool`, `wmctrl`, `xprop`, `ps`, `pkill`.
- **Python 3.10+**: Requires `mss`, `pyautogui`, `pyscreeze`, `python-xlib`, `Pillow`.
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

**Run the Sentinel (Normal Mode):**
```bash
python3 bbs_bot_v10.py
```

**Allow Fallback Auto Rooms:**
*(If no strict matching rooms are found, it will join any valid auto room)*
```bash
python3 bbs_bot_v10.py --allow-all-auto-rooms
```

**Run for Debugging (Alignment Mode):**
*(Saves a rolling buffer of visual snapshots to `alignment_audit/`)*
```bash
python3 bbs_bot_v10.py --allow-all-auto-rooms --alignment-mode
```

## Known Issues
- **X11 Only**: Click injection and focus restoration rely on X11 tools/APIs.
- **Color Sensitive**: Matching can fail if your OS uses a non-standard color profile (HDR/10-bit). Keep display settings standard.
