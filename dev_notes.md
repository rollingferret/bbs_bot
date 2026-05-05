# Development Notes - BBS Bot (V5 'Hollow Engine')

## Architectural Evolution
The bot has evolved through several major paradigms:
*   **V2 (The Slug):** Procedural architecture with hardcoded `time.sleep()` calls (e.g., 3-5 seconds per action). Extremely stable focus management but far too slow.
*   **V3 (The Ghost):** "Fire and forget" interaction logic running at 10fps. Incredibly fast but prone to outrunning game animations, missing clicks, and failing recovery loops due to lack of state awareness.
*   **V4 (The Stealth Engine):** Introduced the robust Dictionary-Mapped State Machine and Circadian rhythms. However, it suffered from "Verification Bottlenecking" (waiting synchronously for UI changes) and high CPU usage from excessive scanning.
*   **V5.7 (The Hollow Engine):** The definitive synthesis. Uses V4's State Machine shell, V3's reactive pacing, and V2's focus stability.

## Core V5 Technologies

### 1. Reactive Interaction (`smart_click`)
V5 abandons synchronous verification. The `smart_click` method performs exactly one sequence:
`Locate -> Wait (Cognitive Delay) -> Gaussian Click -> V2 Refocus Hammer -> Return`
If a `verify_key` is provided, it watches the UI for a maximum of 1.0s. If the UI flips, it returns `True`. If the UI doesn't flip, it returns `False` immediately, allowing the 20fps main loop to re-evaluate and retry on the next tick. This prevents the bot from ever "stalling" while staring at a button.

### 2. Focus Management (The V2 Hammer)
V5 utilizes a hybrid "Ghost + Hammer" approach to solve GNOME/Pop!_OS focus stealing:
1.  **Ghost Click:** X11 events are sent directly to the background game window via `Xlib` without moving the OS cursor or activating the window.
2.  **The Hammer:** Immediately after the click, the bot sleeps for exactly `0.02s` (to allow GNOME to process any focus-stealing requests from the game engine/Wine), and then fires an unconditional `windowactivate --sync [TERMINAL] windowraise [TERMINAL]`. This ensures the user's terminal remains perfectly on top, allowing for seamless multitasking.
3.  **Title Targeting:** Window properties (Sticky, Always on Top) are enforced every 5 seconds using `wmctrl -r "Bleach: Brave Souls"`. By verifying the process ID and `WM_CLASS` during discovery, this ensures browser tabs (YouTube/Reddit) are never accidentally hijacked.

### 3. Vision Optimization (CPU Throttling)
To prevent the "vision lag" seen in V4:
*   `find_image` performs a single `locateOnScreen` pass. A 2nd pass (confidence - 0.05) is only triggered if the first fails, providing forgiveness for slow fades without doubling CPU load on successful hits.
*   `handle_global_popups` is throttled to run only once every `0.5s` (`POLL_POPUP`). This frees up massive CPU cycles for the core 20fps state machine.

### 4. Circadian Rhythms (Human Emulation)
The bot's timing is entirely driven by `SHIKAI` profiles in the `BotConfiguration` dataclass.
*   **SHIKAI_MAX:** ~380ms total cognitive reaction time. Mimics an elite, focused player.
*   **SHIKAI_NORMAL:** ~550ms total cognitive reaction time. Mimics a casual player watching Netflix.
All delays pass through a Gaussian math function (`random.gauss`) influenced by a `fatigue_modifier` that slowly oscillates on a 30-minute Sine wave. This ensures no two clicks are ever mathematically identical, masking the bot from heuristic anti-cheat detection.

### 5. Closed-Loop Recovery
The bot is "Unkillable" for overnight runs:
*   If stuck for 10 minutes (`TIMEOUT_QUEST_MAX`), it force-kills `BleachBraveSouls.exe` and restarts via Steam.
*   It updates its internal `self.region` every 0.05s, even during startup, ensuring it tracks the game window if it resizes or shifts across monitors.
*   If it encounters an unknown screen, it enters `RECOVERY` and scans a dictionary of 16 global anchors. The moment it recognizes an anchor (e.g., `search_again`), it "teleports" its state machine to the correct handler, eliminating the need for hardcoded "Back" button navigation.