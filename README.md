# BBS Bot V7 "The Surgeon"

Autonomous agent for Bleach: Brave Souls on Linux/X11.

## Architecture: Atomic Heartbeat

V7 replaces the nested-loop logic of V6 with a strictly serial execution flow. Every loop pass performs exactly one sequence:
1. **Snapshot**: Capture one frame of the game window.
2. **Global Priority**: Check for popups (Disconnect, Room Full, News).
3. **State Logic**: Check for state-specific anchors (Menu, Room List, Scan, Quest).
4. **Action & Return**: If an action (click) is taken, the bot immediately restarts the loop.

This ensures zero "double-dipping" or decision-making on stale pixels.

## Technical Specifications

* **Vision**: Single snapshot per heartbeat. Enforces `haystack` usage for all sub-checks to minimize CPU.
* **Focus Reclaim**: Captures active window ID before clicks and restores focus/activation via `xdotool` immediately after.
* **Window Shielding**: Uses `wmctrl` for sticky/above properties. Uses `xprop` to detect `IconicState` (minimized) and issues `windowraise` only when the window is hidden from the snapshot engine.
* **Recovery**: 16-point anchor map for 100% parity with V6 recovery capabilities.

## Requirements

* Python 3.10+
* `pyautogui`, `pyscreeze`, `python-xlib`, `Pillow`
* System: `xdotool`, `wmctrl`, `xprop`
* OS: Linux (X11)
