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

## Setup

```bash
sudo apt install python3 python3-pip python3-venv xdotool
git clone https://github.com/yourusername/bbs_bot.git
cd bbs_bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create template images (see below)
mkdir images
python3 bbs_bot.py
```

## Template Images Required

**You must create these yourself by taking screenshots:**

Create `images/` folder with these files:
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

**How to create templates:**
1. Run the game in windowed mode
2. Take screenshots of each UI element using your screenshot tool
3. Crop to just the button/icon (tight crop)
4. Save as PNG in `images/` folder with exact names above

## How It Works

1. **Scans room list** for AUTO-enabled rooms with valid rules
2. **Joins rooms** and handles errors (full rooms, disconnects)
3. **Clicks ready** and waits for quest to start
4. **Enables AUTO** in-game if needed
5. **Completes quest** and retries automatically
6. **Loops forever** until you stop it (Ctrl+C)

## Configuration

The bot has several configurable options at the top of `bbs_bot.py`:

### Focus Restoration (NEW!)
```python
RESTORE_FOCUS_AND_MOUSE = False  # Set to True to reduce focus stealing
```
- **True**: Bot restores your window focus and mouse position after each click (less disruptive)
- **False**: Bot leaves focus on game window (better performance, more disruptive)

### Timing Constants
- `INGAME_AUTO_STABILITY_DELAY = 0.5` - Extra delay before clicking ingame auto button
- `TEMPLATE_FOUND_DELAY = 0.2` - Stability delay after finding templates
- `ROOM_LOAD_TIMEOUT = 5` - Max time to wait for room list loading
- And many more timing controls for fine-tuning

## Known Issues

- **Focus stealing** - Bot must focus game window for reliable clicking. Use `RESTORE_FOCUS_AND_MOUSE = True` to minimize disruption
- **Typing interference** - When bot steals focus, your keystrokes may go to game instead of terminal
- **Linux/X11 only** - Won't work on Windows without modification  
- **Template dependent** - Breaks if game UI changes

## Current Status

- **Stable**: Runs 30+ consecutive quests unattended
- **Performance**: 2-5 minute cycles, >95% success rate
- **Focus restoration**: NEW atomic timing minimizes keystroke interference to ~0.05s windows

## Recent Updates

- ✅ **Focus restoration system** - Optional window focus and mouse position restoration
- ✅ **Atomic timing optimization** - Minimized interference window to ~0.05s during clicks
- ✅ **Performance improvements** - Combined xdotool calls, reduced subprocess overhead
- ✅ **Configurable ingame auto delay** - Improved reliability for auto button clicking
- ✅ **Virtual environment support** - Clean dependency management

## Future Improvements

- **Code refactoring**: Extract repeated template detection patterns
- **State handler functions**: Break 1000+ line main loop into readable functions  
- **Alternative input isolation**: Explore Xephyr nested X server for complete isolation
- **Configuration file**: Move timing constants to external config

See `dev_notes.md` for technical details and solution research.