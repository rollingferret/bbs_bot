# Engineering Log - BBS Bot Version History & Post-Mortem

## Version Evolution: Why they failed & What we learned

| Version | Name | Status | Failure Mode (The "Why") | Lesson Learned |
| :--- | :--- | :--- | :--- | :--- |
| **V2** | Legacy | **Stable** | Slow nested loops. If a popup appeared during a sleep, the bot crashed. | Logic must be reactive, not just a sequence of sleeps. |
| **V3** | Nuclear | **Retired** | Too aggressive. High CPU usage and would "double-click" animations. | Fast is good, but "Momentum" needs to be controlled. |
| **V4-V5**| Prototype| **Retired** | Over-complicated state checks. High overhead for low reliability. | Complexity != Reliability. Keep handlers simple. |
| **V6** | Classic | **Stable** | "Loop Blindness." Watchdog reset too easily; no Orb-safety (clicked OK anywhere). | Watchdog must track *Progress*, not just *States*. |
| **V7** | Surgeon | **Failed** | "Atomic Heartbeat" was too rigid. It missed the "flow" of game transitions. | A bot needs to "stare" at animations, not just take one peek. |
| **V8** | Agent | **Failed** | **Resolution Blindness.** Used sub-regions that failed at 806x482. Too strict (95% conf). | **Masking is brittle.** Full-window vision is the only way to be resolution-resilient. |
| **V9** | **Hardened**| **Active** | *Current Production Candidate.* | Combines V6 Momentum with V8 Safety Gates. |

---

## Technical Problem/Solution Log (Deep Dive)

### 1. Vision Discrepancy & Speed
*   **Discovery**: `pyautogui.locate` on a saved file returns different results than `locateOnScreen`. V8 used the slow method, adding 3s of lag.
*   **V9 Fix**: Reverted to **Snapshot-First Vision**. One capture per loop, all checks done in-memory (<10ms).

### 2. Accidental "Create Room" Entry
*   **Discovery**: V6 would click coordinates for a room even if the list shifted. If the "Create" button moved under the mouse, it clicked it.
*   **V9 Fix**: 
    1.  **JOIN_PENDING State**: Immediately stops clicking the list after one snatch attempt.
    2.  **`verify_anchor="auto"`**: Before the physical click, the bot re-scans for the "Auto" icon. If it's gone, the click is aborted.

### 3. The "Orb-Vampire" Bug
*   **Discovery**: In V2-V6, the bot would click `okay.png` anywhere. If you died in a run, it would spend Orbs to revive.
*   **V9 Fix**: **Phase-Gated Safety**. The `can_click` logic blocks `okay` clicks unless the bot is in `SCAN_ROOMS` or a verified `RETIREMENT`. 

### 4. Watchdog "Fake Progress"
*   **Discovery**: Bots were resetting their "Hang Timer" just by seeing the Menu. This meant they could loop `Menu -> Error -> Menu` for 10 hours without restarting.
*   **V9 Fix**: Watchdog timer only resets when a run is **Actually Started** (`entered_running`) or **Completed** (`run_completed`).

### 5. UI "State Thrashing"
*   **Discovery**: Bots were jumping between states faster than the game could animate (e.g. `FINISH -> RECOVERY -> FINISH`).
*   **V9 Fix**: **`is_screen_stable`**. The bot verifies the pixels have stopped moving for 100ms before it trusts a transition to a new screen.
