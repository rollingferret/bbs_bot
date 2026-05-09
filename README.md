# Bleach: Brave Souls Auto Co-op Bot (BBS Sentinel)

An advanced, stealth-focused autonomous agent for Bleach: Brave Souls co-op quest farming on Linux/X11. This project has evolved through 9 generations to achieve a balance between human-like behavior, blistering speed, and bulletproof reliability.

## ⚠️ DISCLAIMER - USE AT YOUR OWN RISK

**NO SUPPORT PROVIDED**: This project is released as-is with no warranty, support, or maintenance. The author accepts no responsibility for:
- Account bans or penalties from game publishers
- **Terms of Service (TOS) violations** (Automation is a bannable offense)
- System damage or data loss
- Any other consequences of using this software

**LEGAL WARNING**: Game automation **violates the Terms of Service** of KLab and most game publishers. It will likely result in a permanent account ban if detected. By using this software, you acknowledge that you are solely responsible for any consequences. Use entirely at your own risk.

---

## 🌟 Key Features (V9.39)

*   **Fast & Silent Xlib Engine**: Uses root-relative Xlib injection. The bot clicks without moving your physical mouse cursor and restores focus to your active window in `<20ms`. You can work entirely uninterrupted while it farms.
*   **V2 Coordinate Accuracy**: Calculates click offsets using `self.region[0]` (physical screen space) rather than OS-level `geom` to perfectly bypass Pop!_OS titlebar scaling.
*   **Modal Gatekeeper**: Intelligently handles the "Select a Room Type" menu. It physically forbids clicking generic "Close" buttons while in the quest menu to prevent accidental quest exiting.
*   **Intelligent Retry Handling**: Understands that clicking 'Retry' can lead to 3 different states (the menu, the room list, or directly into the lobby) and adapts instantly.
*   **Orb Protection**: Strictly forbids clicking `okay.png` during live runs. Will never spend your orbs on accidental revives.
*   **Hard Watchdog**: Features a 5-minute AFK host timeout and a 5-minute absolute stuck timeout. If the game crashes, the bot will kill the process and relaunch it via Steam.
*   **Alignment Mode**: Run with `--alignment-mode` to save visual snapshots of exactly what the bot saw immediately before making a click decision.

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
python3 bbs_bot_v9.py
```

**Allow Fallback Auto Rooms:**
*(If no strict matching rooms are found, it will join any valid auto room)*
```bash
python3 bbs_bot_v9.py --allow-all-auto-rooms
```

**Run for Debugging (Alignment Mode):**
*(Saves the last 10 pre-click snapshots to `alignment_audit/`)*
```bash
python3 bbs_bot_v9.py --allow-all-auto-rooms --alignment-mode
```

## Known Issues
- **X11 Only**: Direct memory clicks and focus restoration rely on Xlib.
- **Color Sensitive**: Matching can fail if your OS uses a non-standard color profile (HDR/10-bit). Keep display settings standard.