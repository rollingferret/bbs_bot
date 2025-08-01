# Bleach: Brave Souls 10 Coop Anniversary Bot

Auto co-op quest farming bot for Bleach: Brave Souls 10 Coop Anniversary event.

## Requirements

- Linux (X11)
- Python 3.8+
- Game in windowed mode

## Setup

```bash
# Install system dependencies
sudo apt install python3 python3-pip xdotool

# Install Python dependencies
pip3 install -r requirements.txt

# Add template images to images/ folder
```

## Usage

```bash
python3 bbs_bot.py
```

Press Ctrl+C to stop.

## Templates Needed

Create these template images in `images/` folder:
- `coop_quest.png` - Main co-op button
- `open_coop_quest.png` - Specific quest button  
- `join_coop_quest.png` - Enter room list button
- `search_again.png` - Search again button
- `auto_icon.png` - RED AUTO icon
- `room_rules_valid.png` - White "Room Rules" text
- `close.png` - Blue close/resume button
- `ready_button.png` - Ready button
- `retire.png` - Retire button
- `okay.png` - Okay confirmation button
- `closed_room_coop_quest_menu.png` - Room closed by owner popup
- `ingame_auto_off.png` - In-game auto OFF
- `ingame_auto_on.png` - In-game auto ON
- `tap1.png`, `tap2.png` - Quest completion taps
- `retry.png` - Retry button

Bot finds AUTO rooms with valid rules, handles disconnects, room closures, and loops automatically.

## Known Issues

- **Focus stealing**: Bot steals window focus during clicks, disrupting work
- **Input interference**: Typing/mouse movement during bot actions can break clicks
- **Solutions in progress**: Input buffering or virtual display separation