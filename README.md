# Bleach: Brave Souls Auto Co-op Bot

**Personal automation script for Bleach: Brave Souls co-op quest farming. Use at your own risk.**

Automatically finds AUTO-enabled co-op rooms, joins them, handles disconnects, and loops continuously.

## ⚠️ Disclaimer

This is my personal bot that works on my specific setup. No support provided - you'll need to adapt it for your system. Fork and modify as needed.

## Requirements

- **Linux with X11** (tested on Pop!_OS/Ubuntu)
- **Python 3.8+**
- **Bleach: Brave Souls** running in windowed mode via Steam
- **Game path**: Hardcoded for my Steam library - edit the path in `bbs_bot.py` line ~8XX

## Quick Setup

```bash
# Install system dependencies
sudo apt install python3 python3-pip xdotool

# Clone and install
git clone [your-repo-url]
cd bbs_bot
pip3 install -r requirements.txt

# Create template images (see below)
mkdir images
# Take screenshots of each UI element and save as PNG files

# Edit game path in bbs_bot.py for your system
# Run the bot
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

## Known Issues

- **Window focus stealing** - Bot focuses game window for clicks, interrupting work
- **Input interference** - Your mouse/keyboard input during bot actions can break clicks
- **Linux/X11 only** - Won't work on Windows without modification
- **Game path hardcoded** - Edit for your Steam library location
- **Template dependent** - Breaks if game UI changes

## Potential Solutions for Focus Issues

- Run on virtual display (Xvfb) for complete isolation
- Use second monitor dedicated to bot
- Input buffering with lock files
- See `dev_notes.md` for technical details

## License

Use at your own risk. No warranty. Modify freely.