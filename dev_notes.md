# Development Notes - BBS Bot

## Project Overview
Python automation script for Bleach: Brave Souls co-op quest farming. Uses template matching to find AUTO-enabled rooms and handle errors.

## Focus Interference Solution
**Current Implementation**: X11 direct clicks with focus restoration
- 10ms interference window per click
- Focus restored automatically after each click
- Falls back to PyAutoGUI if X11 unavailable

## Template Matching
- Uses PyAutoGUI `locateOnScreen()` with confidence thresholds 0.7-0.95
- Random clicking within template bounds
- Deduplication removes overlapping AUTO icon detections

## Error Recovery
- State recovery function scans all templates to identify current screen
- Maps templates to game states (menu, lobby, in-game)
- Recovers from timeouts, disconnects, room closures
- **Game restart** when stuck on loading screens (no UI elements visible)
- **Startup navigation** sequence: game_start → close_news → coop_1 → coop_2 → MENU
- Only exits on truly unknown screens

## State Machine Flow
MENU → ENTER_ROOM_LIST → SCAN_ROOMS → READY → CHECK_RUN_START → RUNNING → FINISH
                                               ↓ (loading hang)
                                         GAME_STARTUP → MENU
                                   (restart + navigation sequence)

Recovery paths return to appropriate states based on error type.

## Room Selection Algorithm
```python
def match_autos_with_rules(autos, rules, run_count):
    for auto in autos:  # Process AUTO icons sequentially
        # Find closest rule below this AUTO icon
        for rule in rules:
            if rule_y > auto_y and distance < threshold:
                # Return first successful AUTO+Rule match immediately
                return [(auto, closest_rule)]
    return []  # No valid rooms found
```
**Early exit**: Returns immediately after first successful AUTO+Rule pairing

## Current Implementation Status
- Runs 30+ consecutive quests unattended
- 10ms focus interference window with X11 direct clicking
- Comprehensive error recovery prevents overnight crashes
- **Game restart functionality** handles loading screen hangs
- **Startup navigation** automatically returns to farming after restart
- 5 essential dependencies only

## Performance
- 2-5 minute cycles per quest
- 10ms focus interference window
- 50ms template delays
- ~70MB RAM usage

## Architecture Notes
**Current**: Linear state machine with error recovery
**Future recommendation**: Pure polling architecture
```python
# Instead of state tracking, continuously poll templates:
while True:
    if found("retry"): click_retry()
    elif found("join_coop_quest"): click_join_button()
    # Responds to whatever is on screen
```
Pure polling would be simpler and more reliable for game automation.

## Dependencies
- PyAutoGUI - Template matching and screen interaction
- python3-xlib - X11 direct clicking
- xdotool, wmctrl - Window management
- PyGetWindow - Window detection
- Pillow - Image processing

