# Bleach: Brave Souls Auto Co-op Bot

Automation script for Bleach: Brave Souls co-op quest farming. Finds AUTO-enabled rooms, handles errors, loops continuously.

## ⚠️ DISCLAIMER - USE AT YOUR OWN RISK

**NO SUPPORT PROVIDED**: This project is released as-is with no warranty, support, or maintenance. The author accepts no responsibility for:
- Account bans or penalties from game publishers
- Terms of Service violations 
- System damage or data loss
- Any other consequences of using this software

**LEGAL WARNING**: Game automation may violate Terms of Service and could result in permanent account bans. Use entirely at your own risk.

## Requirements

- Linux with X11 (tested on Pop!_OS/Ubuntu)
- Python 3.8+
- Bleach: Brave Souls running in windowed mode
- Game must be visible (bot finds window by title)
- wmctrl - Window management utility

## Setup

```bash
sudo apt install python3 python3-pip python3-venv xdotool wmctrl
git clone https://github.com/yourusername/bbs_bot.git
cd bbs_bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Template images included for current event
python3 bbs_bot.py
```

## Template Images

**Included for 10 Coop Anniversary Event:**

The `images/` folder contains pre-made templates for the current event:
- `coop_quest.png` - Main co-op quest button
- `open_coop_quest.png` - Specific quest selection button  
- `join_coop_quest.png` - "Join" button to enter room list
- `search_again.png` - Search again button in room list
- `auto_icon.png` - RED "AUTO" icon in room list
- `room_rules_valid.png` - White "Room Rules" text
- `close.png` - Blue close/resume button (multiple contexts)
- `ready_button.png` - Ready button in lobby
- `retire.png` - Retire/leave room button
- `okay.png` - Okay confirmation button
- `closed_room_coop_quest_menu.png` - "Room closed" popup
- `ingame_auto_off.png` - In-game AUTO button (OFF state)
- `ingame_auto_on.png` - In-game AUTO button (ON state)  
- `tap1.png`, `tap2.png` - Quest completion continue buttons
- `retry.png` - Retry button after quest

**For Other Events:**
If the UI changes for future events, you'll need to update template images:
1. Run the game in windowed mode
2. Take screenshots of changed UI elements
3. Crop to just the button/icon (tight crop)  
4. Replace the corresponding PNG files in `images/` folder

## How It Works

1. Scans room list for AUTO-enabled rooms with valid rules
2. Joins rooms and handles errors (full rooms, disconnects)
3. Clicks ready and waits for quest to start
4. Enables AUTO in-game if needed
5. Completes quest and retries automatically
6. Loops until stopped (Ctrl+C)

## Configuration

Configurable options at the top of `bbs_bot.py`:

```python
USE_X11_DIRECT_CLICKS = True  # X11 direct clicks (10ms interference)
USE_WMCTRL_ALWAYS_ON_TOP = True  # Keep game window visible
TEMPLATE_FOUND_DELAY = 0.05  # Template detection delay
FOCUS_RESTORE_DELAY = 0.01  # Focus restoration timing
```

## Known Issues

- Linux/X11 only
- Template dependent - breaks if game UI changes
- Requires X11 XTEST extension
- wmctrl compatibility varies by desktop environment (try DevilsPie for reliable window control)

## Current Status

- Runs 30+ consecutive quests unattended
- 2-5 minute cycles, >95% success rate  
- 10ms focus disruption window
- Comprehensive error recovery system

See `dev_notes.md` for technical details.