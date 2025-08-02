# Development Notes - BBS Bot

## Project Evolution

### Initial Goal
Auto co-op quest farming bot for Bleach: Brave Souls 10 Coop Anniversary event that can run while user works.

### Core Problem Identified
**Focus stealing during clicks disrupts user workflow**
- Bot must focus game window to ensure reliable clicks
- Focus restoration takes ~0.5-1s, interrupting typing/mouse work
- User input during bot actions can break click sequences

## Solutions Attempted

### 1. Focus Optimization (FAILED)
**Attempt**: Ultra-minimal focus disruption
- Reduced delays, optimized window focus/restore timing
- Added focus restoration to return to user's original window
- **Result**: Still disruptive, clicks became unreliable

**Code tried**:
```python
def simple_click(x, y, description="element"):
    original_focus = get_current_focus()
    focus_game_window()                    # ~0.05s
    pyautogui.click(x, y)                 # Instant
    restore_focus(original_focus)         # Immediate
```

**Reverted**: Focus optimization broke bot reliability

### 2. Virtual Mouse (FAILED)
**Attempt**: xdotool window-relative clicking to avoid focus
- **Result**: Doesn't work with Steam/DRM games
- Steam prevents relative window clicking for security

## Current Focus Solutions Under Consideration

### Option A: Input Buffering with Lock File (RECOMMENDED)
```python
# Bot creates /tmp/bot_clicking during actions
# User runs wrapper that queues input when file exists
# Safe - can't lock out user if bot crashes
```

### Option B: X11 Input Grabbing 
```python
# Grab keyboard/mouse during ~0.5s click sequence
# Risk: Can lock out user if bot crashes
# Requires Ctrl+Alt+F1 recovery
```

### Option C: Virtual Display Separation
```bash
# Run game on :1, user works on :0
Xvfb :1 -screen 0 1920x1080x24 &
DISPLAY=:1 steam  # game runs here
DISPLAY=:0 code   # user works here
```

### Option D: Input Timing Announcements
```python
print("CLICKING IN 3...2...1...") 
# User manually pauses typing for ~0.5s
```

## Technical Discoveries

### Window Management
- `windowactivate` = keyboard focus
- `windowraise` = bring to front visually  
- Both needed for reliable game clicking
- `--sync` flag ensures command completion before proceeding

### Template Matching
- PyAutoGUI with 0.8 confidence works well
- Random clicking within template bounds prevents pixel-perfect detection
- Deduplication needed for overlapping AUTO icon detections

### Error Handling Patterns
- Room unavailable popup → close → retry scan
- Network disconnect → close → continue/restart
- Room owner disconnect → retire → okay → final confirmation → restart
- Room closure by owner → click popup → restart from menu

## State Machine Flow

```
MENU → ENTER_ROOM_LIST → SCAN_ROOMS → READY → CHECK_RUN_START → RUNNING → FINISH
  ↗                         ↗            
Recovery points          Search again
```

### Key Recovery Paths
1. **Room unavailable**: SCAN_ROOMS → SCAN_ROOMS (retry)
2. **Run start timeout**: CHECK_RUN_START → MENU (retire sequence)
3. **Room closure**: CHECK_RUN_START → MENU (popup dismiss)
4. **Network disconnect**: Any state → continue or restart

## Recent Fixes

### Retirement Sequence (Fixed)
**Issue**: Incomplete retirement flow
**Solution**: Added double confirmation
1. Click retire button
2. Click okay confirmation  
3. Click final popup (closed_room_coop_quest_menu.png)
4. Return to MENU state

### Room Closure Detection (Fixed)
**Issue**: Owner closing room wasn't handled
**Solution**: Added detection during CHECK_RUN_START
- Detects closed_room_coop_quest_menu.png popup
- Clicks to dismiss and restarts from MENU

## Templates Required

### Core Navigation
- `coop_quest.png` - Main co-op button
- `open_coop_quest.png` - Specific quest selection
- `join_coop_quest.png` - Enter room list
- `search_again.png` - Refresh room list

### Room Selection  
- `auto_icon.png` - RED AUTO icon (room has auto enabled)
- `room_rules_valid.png` - White "Room Rules" text
- `ready_button.png` - Ready button in lobby

### Error Handling
- `close.png` - Blue close/resume button (multiple contexts)
- `retire.png` - Retire button (leave room)
- `okay.png` - Okay confirmation button
- `closed_room_coop_quest_menu.png` - Room closed/final confirmation popup

### In-Game
- `ingame_auto_off.png` - Auto button OFF (click to enable)
- `ingame_auto_on.png` - Auto button ON (already enabled)
- `tap1.png`, `tap2.png` - Quest completion continues
- `retry.png` - Retry for next run

## Current Status (Ready for Open Source)

### ✅ **Completed Improvements**
- **Template API consistency**: All operations use `locateOnScreen()` returning Box objects
- **Random clicking optimization**: Clicks randomly within template bounds for detection avoidance
- **Auto button reliability**: Center-focused clicking for circular buttons (avoids edge misses)
- **Delay consolidation**: All hardcoded delays moved to named constants at top of file
- **Error handling robustness**: Comprehensive popup detection and recovery paths
- **Code stability**: Fixed all template detection inconsistencies

### 🔄 **Focus Interference Solutions**

**Option A: Virtual Display (Xvfb)** - In Progress
```bash
# Complete isolation approach
Xvfb :2 -screen 0 1920x1080x24 &
DISPLAY=:2 wine game.exe
DISPLAY=:2 python3 bbs_bot.py
```
- **Status**: Xvfb installed, ready for testing
- **Benefit**: Zero interference - bot and work completely isolated
- **Challenge**: Need to verify game renders properly on virtual display

**Option B: Input Buffering** - Designed but not implemented
```python
# Bot creates /tmp/bot_clicking during actions
# System wrapper queues input when lock file exists
```
- **Benefit**: Prevents input interference during click sequences
- **Complexity**: Requires additional system-level input handling

### 📊 **Performance Characteristics**
- **Cycle time**: 2-5 minutes per quest depending on queue times
- **Success rate**: >95% with current optimizations
- **Resource usage**: ~50MB RAM, minimal CPU except during template matching
- **Template matching**: <0.1s per detection operation

### ⚙️ **Technical Debt & Improvements**
- **Monolithic main loop**: 900+ lines, could benefit from state handler extraction
- **Code duplication**: Template detection pattern repeated ~8 times
- **Configuration**: Game path hardcoded, could use config file
- **Documentation**: Templates require manual creation by users

### 🎯 **Next Steps (Optional)**
1. **Test virtual display solution** for complete work isolation
2. **Extract state handler functions** for better code organization  
3. **Add template examples** for easier user setup
4. **Create configuration file** for game paths and settings

## Performance Notes

- Bot runs ~2-5 minute cycles depending on queue times
- Template matching is fast (<0.1s per check)
- Main delays are game loading times and queue waiting
- Focus stealing is only issue preventing work-while-running

## Git History

- `bb0567f` - Working bot before focus experiments
- `4df88c5` - Added okay confirmation for retire
- `252da9b` - Fixed double confirmation retire sequence