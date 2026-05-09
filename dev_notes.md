# Engineering Log - BBS Bot Version History & Post-Mortem

## Version Evolution: Why they failed & What we learned

| Version | Name | Status | Failure Mode (The "Why") | Lesson Learned |
| :--- | :--- | :--- | :--- | :--- |
| **V2** | Legacy | **Stable** | Slow nested loops. If a popup appeared during a sleep, the bot crashed. | Logic must be reactive, not just a sequence of sleeps. |
| **V3** | Nuclear | **Retired** | Too aggressive. High CPU usage and would "double-click" animations. | Fast is good, but "Momentum" needs to be controlled. |
| **V4-V5**| Prototype| **Retired** | Over-complicated state checks. High overhead for low reliability. | Complexity != Reliability. Keep handlers simple. |
| **V6** | Classic | **Stable** | "Loop Blindness." Watchdog reset too easily; no Orb-safety. | Watchdog must track *Progress*, not just *States*. |
| **V7** | Surgeon | **Failed** | "Atomic Heartbeat" was too rigid. Missed the "flow" of game transitions. | A bot needs to "stare" at animations, not just take one peek. |
| **V8** | Agent | **Failed** | **Resolution Blindness.** Used sub-regions that failed at 806x482. | **Masking is brittle.** Full-window vision is the only way to be resolution-resilient. |
| **V9** | **Sentinel**| **Active** | *Final Production Candidate.* | Combines V6 Speed, V2 Accuracy, and V8 Safety Gates. |

---

## Technical Problem/Solution Log (Deep Dive)

### 1. Vision Discrepancy & Speed
*   **Discovery**: `pyautogui.locate` on a saved file returns different results than `locateOnScreen`. V8 used the slow method, adding 3s of lag.
*   **V9 Fix**: Reverted to **Snapshot-First Vision** using `mss`. One capture per loop, all checks done in-memory (<10ms).

### 2. The "Modal Confusion" Bug
*   **Discovery**: When clicking "Join Room" in the Quest Menu, the bot immediately transitioned to the `SCAN_ROOMS` state. Because the menu takes a second to fade out, the bot's global popup handler would see the menu's red "Close" button, mistake it for an error popup, and click it—accidentally exiting the quest.
*   **V9 Fix**: Implemented the **Modal Gatekeeper**. The bot now stays in the `ENTER_ROOM_LIST` state until the menu physically disappears. While in this state, the generic `close.png` check is physically blocked, making the bot "blind" to the menu's button.

### 3. The "Stuck After Retry" Hang
*   **Discovery**: V9 assumed clicking 'Retry' would always load the 'Join Room' menu. In reality, BBS server lag often dumps the player directly into the room list or lobby. Additionally, the verify timeout was too short (0.8s), causing the click verification to fail if the server lagged, stranding the bot in the `FINISH` state.
*   **V9 Fix**: 
    1. Extended the verify timeout for the Retry button to 5 seconds (`TIMEOUT_ROOM_LIST_LOAD`).
    2. Rewrote `handle_enter_room_list` to act as a Gatekeeper that intelligently routes the bot depending on which screen actually loads (Menu, Room List, or Lobby).

### 4. X11 Click Accuracy on Pop!_OS
*   **Discovery**: V6 calculated click coordinates using `geom.x` / `geom.y`. On Pop!_OS, the OS-level window title bars threw this geometry off, causing the bot to click a few pixels above or below the actual button (failing to hit "Ready" or "Retry").
*   **V9 Fix**: Restored **V2 Physical Math**. The bot now subtracts the raw physical region (`x - self.region[0]`), completely bypassing OS window manager scaling.

### 5. Reward Animation Spam
*   **Discovery**: V9 was clicking the `tap1` and `tap2` rewards incredibly fast, skipping the game's reward animations and sometimes throwing off the state machine.
*   **V9 Fix**: Restored V6's `WAIT_STABILIZE_ANIMATION` pause (0.8s - 1.2s depending on circadian profile) after reward clicks.

### 6. Fast Exits & Session Summaries
*   **Discovery**: A nested `except KeyboardInterrupt` inside the main loop was fighting the outer try/except block, causing a 1-2 second delay when hitting `Ctrl+C` and double-printing the summary.
*   **V9 Fix**: Stripped the inner trap. Exits are now instant and trigger a beautifully formatted CLI summary showing Uptime, Runs, Avg Time, and Disconnects.
