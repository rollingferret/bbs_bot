# BBS Quest Bot - V7.2 (Field Build)

Technical interaction script for automated quest loops in Bleach: Brave Souls.

## System Description
Script-based autonomous agent utilizing a state-machine architecture. Focus is on resource efficiency and workspace persistence during long-duration runs.

## Operational Theory (The "How")

### 1. Vision Cycle (Snapshot Engine)
*   **Method:** Performs a single `pyautogui.screenshot(region=self.region)` at the start of each 100ms loop.
*   **Reason:** Eliminates CPU spikes caused by multiple full-screen scans. All UI checks (Auto, Rewards, Retry) use mathematical pixel-offsets from this single memory buffer.

### 2. Focus & Persistence (Sword & Shield)
*   **Shield (Passive):** Uses `wmctrl` to force `sticky` and `above` flags. The window follows the user across all workspaces silently.
*   **Sword (Active):** Monitors `WM_STATE` and `_NET_WM_DESKTOP`. If the window is minimized or loses stickiness, the bot re-applies the flags. 
*   **Politeness:** Replaced `windowactivate` with `windowraise` to prevent the Window Manager from stealing the user's workspace.

### 3. Auto-Management (Dual Gate)
*   **Logic:** Prioritizes the Green (ON) state check at 0.85 confidence. If Green is detected, the check exits. 
*   **Security:** Only attempts a click if the Grey (OFF) state is confirmed at 0.995 confidence. This prevents "Flash Bugs" from boss animations disabling Auto.

### 4. Run Counting (Cycle Lock)
*   **Mechanism:** Uses a `_run_counted` boolean lock.
*   **Validation:** Triggered by the first detection of any finish anchor (`tap1`, `tap2`, or `retry`). Lock clears only upon successful lobby entry (`READY`).

## System Requirements
- Linux / X11 (Pop!_OS, Ubuntu, Debian)
- Python 3.10+
- `wmctrl`, `xdotool`, `xprop`

## Installation & Calibration

```bash
# Dependencies
sudo apt install python3-pip python3-venv xdotool wmctrl x11-utils

# Environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Execution
python3 bbs_bot_v6.py
```

## Maintenance & Testing
Run these commands to verify system integrity before long sessions:
*   `ruff check bbs_bot_v6.py`: Style/PEP8 validation.
*   `python3 -m mypy bbs_bot_v6.py --ignore-missing-imports`: Type-safety audit.
*   `python3 test_v5_logic.py`: Brain/Matching unit tests.
*   `python3 test_v6_sanity.py`: X11 loop boot-check.

## File Manifest
*   `bbs_bot_v6.py`: Main control logic and state machine.
*   `images/`: UI template library.
*   `screenshots/`: Local debug output (excluded from git).
*   `dev_notes.md`: Architectural evolution and low-level technical log.
