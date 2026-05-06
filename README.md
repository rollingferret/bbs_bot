# Bleach: Brave Souls Auto Co-op Bot (V6.0 'Snapshot Engine')

An advanced, stealth-focused autonomous agent for Bleach: Brave Souls co-op quest farming. V6.0 introduces a high-efficiency vision architecture, robust workspace persistence, and surgical interaction logic.

## ⚠️ DISCLAIMER - USE AT YOUR OWN RISK

**NO SUPPORT PROVIDED**: This project is released as-is with no warranty, support, or maintenance. The author accepts no responsibility for:
- Account bans or penalties from game publishers
- Terms of Service violations 
- System damage or data loss
- Any other consequences of using this software

**LEGAL WARNING**: Game automation may violate Terms of Service and could result in permanent account bans. Use entirely at your own risk.

## 🌟 V6.0 Key Features

*   **High-Efficiency Snapshot Engine:** Captures exactly one game-region screenshot per loop. All surgical checks (Auto, Rewards, Retries) are performed as mathematical offsets in memory, reducing CPU overhead and increasing reaction speed.
*   **Passive Persistence (Workspace Glued):** Automatically forces the game window to be `Sticky` (exists on all desktops) and `Above` (Always on Top). The window follows you silently across workspaces without ever dragging your focus away.
*   **Surgical Auto-Management:** Uses a dual-confidence model (Forgiving Green / Strict Grey) to ensure the Auto button stays ON. It ignores boss-death explosions and flashy special effects that "trick" traditional bots.
*   **Precision Run Counting:** Implements a completion lock that credits exactly one run the moment rewards appear. Verified accurate even during heavy server lag or recovery jumps.
*   **Pure X11 Ghost Clicks:** Uses headless X11 events to click the background game window. Includes an unconditional refocus hammer so you can continue working while the bot plays.
*   **Circadian Rhythm Profiles:** Mimics human focus patterns by shifting between `SHIKAI_MAX` (Focused) and `SHIKAI_NORMAL` (Casual) profiles with Gaussian randomized delays.
*   **Enterprise-Grade Stability:** 100% PEP 8 compliant and Type-Safe (verified via `ruff` and `mypy`). Robust recovery maps and action watchdogs ensure 16+ hours of uninterrupted autonomous play.

## Requirements

- Linux with X11 (tested on Pop!_OS/Ubuntu/Debian)
- Python 3.10+
- Bleach: Brave Souls running in windowed mode
- `wmctrl`, `xdotool`, and `xprop` installed

## Setup

```bash
sudo apt install python3 python3-pip python3-venv xdotool wmctrl x11-utils
git clone https://github.com/rollingferret/bbs_bot.git
cd bbs_bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the Bot
python3 bbs_bot_v6.py
```

## Usage

**Normal Operation:**
```bash
python3 bbs_bot_v6.py
```

**Verify Recovery & Startup:**
```bash
python3 bbs_bot_v6.py --test-restart
```

**Dry Run Mode (Log only, no clicks):**
```bash
python3 bbs_bot_v6.py --dry-run
```

**Run Validation Suite:**
```bash
ruff check bbs_bot_v6.py
python3 -m mypy bbs_bot_v6.py --ignore-missing-imports
python3 test_v5_logic.py
python3 test_v6_sanity.py
```

## Template Images

The `images/` folder contains required UI templates. To update elements:
1. Run the game in windowed mode.
2. The bot will automatically lock the window size and position.
3. Replace existing PNGs with tight, background-free crops of new UI elements if the game updates.

## Configuration

All timing profiles, limits, and vision confidence thresholds are located at the top of `bbs_bot_v6.py` inside the `BotConfiguration` dataclass.

## Known Issues
- **Linux/X11 Only:** Relies on Xlib and X11 properties. Does not support Wayland natively.
- **Privacy:** Debug screenshots (if enabled via `--debug-screenshots`) are strictly bounded to the game window and ignored by Git.
