# Bleach: Brave Souls Auto Co-op Bot (V5.0)

An advanced, stealth-focused autonomous agent for Bleach: Brave Souls co-op quest farming. V5.0 features a high-performance state-machine architecture, optimized vision system, and reactive interaction logic.

## 🌟 V5.0 Features

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

**Verify Recovery Loop:**
```bash
python3 bbs_bot_v5.py --test-restart
```

**Debug Mode:**
```bash
python3 bbs_bot_v5.py --debug-screenshots
```

## Configuration

All timing profiles and limits are located at the top of `bbs_bot_v5.py` inside the `BotConfiguration` dataclass. Every delay, cooldown, and timeout is fully configurable.
