# Bleach: Brave Souls Auto Co-op Bot (V3.30 'Nuclear Grade')

An advanced, stealth-focused autonomous agent for Bleach: Brave Souls co-op quest farming. V3.30 features a highly optimized background engine with "Zero-Latency" refocusing, dynamic psychological profiles (Circadian Rhythm), and 100% procedural verification.

## ⚠️ DISCLAIMER - USE AT YOUR OWN RISK

**NO SUPPORT PROVIDED**: This project is released as-is with no warranty, support, or maintenance. The author accepts no responsibility for:
- Account bans or penalties from game publishers
- Terms of Service violations 
- System damage or data loss
- Any other consequences of using this software

**LEGAL WARNING**: Game automation may violate Terms of Service and could result in permanent account bans. Use entirely at your own risk.

## 🌟 V3.30 Key Features

*   **Circadian Rhythm (Stealth Profiles):** The bot dynamically shifts between `SHIKAI_MAX` (a sweaty, aggressive grinder reacting in 0.28s) and `SHIKAI_NORMAL` (a casual player watching Netflix reacting in 0.35s) every few hours. This creates a messy, human-like statistical curve on the server side, making it virtually impossible for anti-cheat heuristics to distinguish from human stamina.
*   **Zero-Latency Refocusing:** Uses direct Xlib memory calls to restore window focus in `< 2ms`. The bot is completely silent and will never steal your taskbar focus or drop a keystroke while you are working in another window.
*   **33fps (0.03s) Awareness:** The internal engine polls the screen 33 times per second, allowing the bot to react the instant an animation completes.
*   **Positive Verification Gates:** The bot never "guesses" if a click worked. It uses multi-frame stability checks (`find_stable_image`) to avoid clicking ghost animations, and will stare at the screen until it verifies a positive anchor (like the Retire button) before assuming a lobby join was successful.
*   **Persistent Quest Watchdog:** A background timer tracks the total duration of a quest loop. If a single run takes longer than 10 minutes (due to silent network drops or fully zombified game clients), the bot automatically hard-restarts the game from Steam.
*   **Coffee Breaks:** Every 25-45 runs, the bot takes a random 2 to 8-minute AFK break.

## Requirements

- Linux with X11 (tested on Pop!_OS/Ubuntu)
- Python 3.8+
- Bleach: Brave Souls running in windowed mode
- Game must be visible on the screen (bot finds window by title)
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

# Run the Nuclear Grade Bot
python3 bbs_bot_v3.py
```

## Usage

**Normal Operation (Background Farming):**
```bash
python3 bbs_bot_v3.py
```
Starts the bot and automatically attaches to the running game instance. It will seamlessly swap profiles and run until the 16-hour session limit is hit.

**Test Recovery Sequence:**
```bash
python3 bbs_bot_v3.py --test-restart
```
Force-kills the game upon startup to verify the Steam relaunch and automated recovery sequences are working on your machine.

**Debug Mode:**
```bash
python3 bbs_bot_v3.py --debug-screenshots
```
Saves a screenshot to `screenshots/` every time the bot transitions to a new state. Useful if the bot is getting stuck on a new event screen.

## Template Images

The `images/` folder contains the required UI templates. If the game UI updates or an event changes the banner:
1. Run the game in windowed mode
2. Take a screenshot of the new UI element
3. Crop it tightly (leave no background context if possible)
4. Replace the corresponding PNG file in the `images/` folder.

## Configuration & Tuning

All timing profiles, limits, and delays are located at the very top of `bbs_bot_v3.py` inside the `BotConfiguration` dataclass.

If you wish to change how aggressive the bot is, modify the `CIRCADIAN_PROFILES` dictionary. You can tune the cognitive reaction delays, transition speeds, and post-run breather times to your exact preferences.

## Known Issues
- **Linux/X11 Only:** Direct memory clicks and focus restoration rely on Xlib. This will not work on Wayland natively or Windows/macOS.
- **Resolution Dependent:** If your screen resolution or game scaling changes drastically, the PyAutoGUI confidence templates may fail to match. Keep the window size consistent.
