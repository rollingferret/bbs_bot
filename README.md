# Bleach: Brave Souls Auto Co-op Bot (V5.0 'Hollow Engine')

An advanced, stealth-focused autonomous agent for Bleach: Brave Souls co-op quest farming. V5.0 features a high-performance state-machine architecture, optimized vision system, and reactive interaction logic.

## ⚠️ DISCLAIMER - USE AT YOUR OWN RISK

**NO SUPPORT PROVIDED**: This project is released as-is with no warranty, support, or maintenance. The author accepts no responsibility for:
- Account bans or penalties from game publishers
- Terms of Service violations 
- System damage or data loss
- Any other consequences of using this software

**LEGAL WARNING**: Game automation may violate Terms of Service and could result in permanent account bans. Use entirely at your own risk.

## 🌟 V5.0 Key Features

*   **Reactive Interaction Engine:** Combines fire-and-forget clicking with real-time UI polling. It moves at peak human speeds without the sluggishness of traditional bots.
*   **Pure X11 Ghost Clicks:** Uses headless X11 events to click background windows. Includes an aggressive refocus hammer to ensure the terminal remains the active window.
*   **Optimized Vision System:** Throttled popup scanning and single-pass template matching to minimize CPU usage and system lag.
*   **State-Machine Architecture:** Robust state transitions (MENU -> SCAN_ROOMS -> READY -> RUNNING) ensure reliable recovery and long-term stability.
*   **Circadian Rhythm:** Dynamically shifts between `SHIKAI_MAX` (Pro Gamer) and `SHIKAI_NORMAL` (Casual Player) profiles to mimic human behavioral patterns.
*   **Survival Systems:** Automated Steam recovery, 10-minute quest watchdogs, randomized coffee breaks, and a 16-hour hard session limit.

## Requirements

- Linux with X11 (tested on Pop!_OS/Ubuntu)
- Python 3.8+
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
python3 bbs_bot_v5.py
```

## Usage

**Normal Operation:**
```bash
python3 bbs_bot_v5.py
```

**Dry Run Mode (No Clicks):**
```bash
python3 bbs_bot_v5.py --dry-run
```

**Run Unit Tests:**
```bash
python3 test_v5_logic.py
```

**Verify Recovery Loop:**
```bash
python3 bbs_bot_v5.py --test-restart
```

**Debug Mode:**
```bash
python3 bbs_bot_v5.py --debug-screenshots
```

## Template Images

The `images/` folder contains the required UI templates. If the game UI updates or an event changes the banner:
1. Run the game in windowed mode
2. Take a screenshot of the new UI element
3. Crop it tightly (leave no background context if possible)
4. Replace the corresponding PNG file in the `images/` folder.

## Logic Testing

V5 includes a dedicated unit test suite (`test_v5_logic.py`) that validates the bot's core decision-making logic (room matching, icon deduplication, and proximity pairing) without needing the game running. This ensures the "brain" remains accurate after any configuration or code changes.

## Configuration & Tuning

All timing profiles, limits, and delays are located at the top of `bbs_bot_v5.py` inside the `BotConfiguration` dataclass. Every delay, cooldown, and timeout is fully configurable via the `SHIKAI` profiles.

## Known Issues
- **Linux/X11 Only:** Direct memory clicks and background execution rely on Xlib. This will not work natively on Wayland, Windows, or macOS.
- **Resolution Dependent:** If your screen resolution or game scaling changes drastically, the PyAutoGUI confidence templates may fail to match. Keep the window size consistent.
