# Mechanical Audit: V6 Stable vs V7 "The Surgeon"

This document provides a mechanical trace of the data flow, shape, and logic comparing the last stable build (`v6_last_stable.py`) to the fully repaired V7 (`bbs_bot_v7.py`).

## 1. Architecture & Data Shape

### V6 Stable (Nested Loop Engine)
* **Shape**: Deeply nested, state-bound loops.
* **Data Flow**: `run()` loop -> Takes Snapshot -> Passes to Handler -> Handler takes *new* internal snapshots while waiting for UI changes -> Returns control to `run()`.
* **The Flaw**: The bot could execute multiple clicks based on a single initial condition without re-evaluating global priorities (like disconnects).

### V7 (Atomic Heartbeat)
* **Shape**: Flat, strictly serial state machine.
* **Data Flow**: `run()` loop -> Takes ONE Snapshot -> Checks Global Popups -> Passes to Handler -> Handler makes ONE decision -> Returns boolean `True` (Action Taken) or `False` (No Action) -> Loop instantly restarts.
* **The Fix**: The bot is forced to look at the screen freshly after every single click, preventing "stale pixel" clicks.

---

## 2. Path Traces

### A. The "Happy Path" (Entering a Room & Finishing)

#### V6 Stable Flow:
1. `handle_scan_rooms`: Finds room. Clicks "Snatch".
2. **Safety Bubble**: Enters a 6-second `while` loop. Waits for "Ready" button to appear.
3. If "Ready" appears, clicks it, transitions to `CHECK_RUN_START`.
4. In `handle_finish`: Finds "tap1". Clicks it. Hard sleeps for `WAIT_STABILIZE_ANIMATION` (0.8s) to prevent double-clicking.
5. Resets `quest_watchdog`.

#### V7 Flow:
1. `handle_scan_rooms`: Finds room. Clicks "Snatch" inside `smart_click`.
2. **Safety Bubble (Restored)**: `smart_click` uses `TIMEOUT_VERIFY_UI` (0.7s) to wait for the UI to physically change before returning.
3. Sets `_snatch_pending = True` (The Lock). Returns `True`.
4. Loop restarts. Next snapshot sees "Ready" button. `handle_ready` clicks it.
5. In `handle_finish`: Finds "tap1". Clicks it using `smart_click` with `verify_key="tap1"`. `smart_click` bubbles for 0.7s waiting for the tap button to disappear.
6. If the click succeeds, it explicitly resets `quest_watchdog`. Returns `True`. Loop restarts.

**Verdict**: V7 accurately mirrors V6 Stable's pacing using `smart_click`'s verify logic and the new `_snatch_pending` lock, while remaining 100% faithful to the Atomic Architecture.

---

### B. The "Sad Path" (Room Full / Unavailable)

#### V6 Stable Flow:
1. `handle_scan_rooms`: Clicks "Snatch". Enters 6-second `while` loop.
2. The "Room Full" popup appears. The internal loop detects it using `find_image("closed_room_coop_quest_menu")`.
3. Clicks "Close Room Full". Transitions to `MENU`.

#### V7 Flow:
1. `handle_scan_rooms`: Clicks "Snatch". Sets `_snatch_pending = True`. Returns `True`. Loop Restarts.
2. Next snapshot is taken. The "Room Full" popup is on screen.
3. **Global Priority**: `handle_global_popups` runs *first*. It detects the "Room Full" popup (`closed_room_coop_quest_menu`).
4. It clicks the dismiss button. Transitions to `MENU`. Returns `True`. Loop Restarts.

**Verdict**: V7 is technically superior here. It doesn't rely on the `SCAN_ROOMS` handler to know how to dismiss popups. The global handler catches it immediately. The `_snatch_pending` flag safely resets on the transition to `MENU`.

---

### C. The "Recovery Path" (Watchdogs & Freezes)

#### V6 Stable Flow:
* **The Watchdog**: Initialized at launch. Reset only when finishing a quest (tapping rewards), taking a distraction break, or transitioning back to `MENU`.
* **The Limit**: If 10 minutes pass without the bot seeing the `MENU` or finishing a quest, it assumes a hard freeze (e.g., stuck on a black loading screen) and runs `recover_game()`.

#### V7 Flow:
* **The Initial Regression**: V7 was originally built to reset the watchdog *only* on state transitions. This broke the bot because being in the `RUNNING` state for 13 minutes (a long manual quest) didn't trigger a transition, causing a false suicide.
* **The Final Fix**: V7 now strictly mirrors V6 Stable. The watchdog is explicitly reset inside `handle_finish` (on a successful reward tap), inside `handle_distraction`, and inside `transition_to` *only* when the destination state is `MENU`.

**Verdict**: V7 has regained 100% of V6 Stable's watchdog reliability.

---

## 4. Red Team Audit (Final Polish)
During the final Red Team Audit, several critical regressions and orphaned variables were identified and resolved to ensure V7 is fully stable before a live run:
* **The `_run_counted` Lock**: The boolean reset in `transition_to` was accidentally deleted, causing the bot to only count 1 run per session. This was surgically restored for states `["MENU", "READY", "CHECK_RUN_START", "ENTER_ROOM_LIST"]`.
* **Orphaned Variables Cleared**: `POLL_RUNNING` and `WAIT_LOBBY_READY` were safely removed as they belonged to the nested loop architecture of V6 and were no longer used in V7.
* **Stealth Math Verified**: Confirmed that `SAFETY_FLOOR_FACTOR` (0.05) and the `DELAY_COGNITIVE` timings (0.78s Base, 0.95s Distracted) are perfectly intact and actively pacing the bot.
* **Recovery Anchors Verified**: The `RECOVERY_MAP` array in V7 is a verified 1-to-1 match with V6 Stable.

V7 "The Surgeon" is now saved and ready for live run validation.