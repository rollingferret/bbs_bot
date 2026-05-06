# Engineering Log - BBS Bot (V7.2 Build)

## System Evolution (Trace)
*   **V2:** Hardcoded sleeps. Poor efficiency, high stability.
*   **V3:** High-cadence async. Fast but prone to state-drift and animation race conditions.
*   **V5:** Unit-tested state machine. Robust but high CPU overhead due to redundant scans.
*   **V7:** Refactored Vision Engine + Sub-process caching. Final production build.

## Technical Problem/Solution Log

### 1. Resource Exhaustion (Vision)
*   **Problem:** Multiple `locateOnScreen` calls per loop caused 100% CPU spikes and interface stutter.
*   **Solution:** Implemented **Single-Capture Loop**. Captures exactly one `pyautogui.screenshot(region=self.region)` per 100ms cycle.
*   **Implementation:** All sub-checks (Auto-quadrant, Reward anchors) use coordinate math to slice the existing memory buffer.

### 2. Focus Jumps & Workspace Drift
*   **Problem:** Using `windowactivate` forced the Window Manager to jump the user to the game's original workspace.
*   **Solution:** Passive restoration via `wmctrl` flags (`sticky,above`) and `windowraise`.
*   **Implementation:** Monitors window properties via `xprop`. If state != sticky, re-apply flags. Window "follows" the user silently without stealing workspace focus.

### 3. Loop Latency (Shell Spawns)
*   **Problem:** Spawning `xdotool` search processes every 100ms introduced ~40ms of kernel-level latency.
*   **Solution:** **Window ID Caching**.
*   **Implementation:** Caches `win_id` in memory. Uses lightweight `xprop -id` to verify window existence. Full system search only triggers every 5s (`POLL_PROPERTY_SYNC`) or if the ID becomes invalid.

### 4. Reward Counting Drift
*   **Problem:** Server lag often caused the bot to skip the `tap1` image, resulting in unrecorded runs.
*   **Solution:** Authoritative **Cycle-Lock**.
*   **Implementation:** Credits the run the moment **any** finish anchor (`tap1`, `tap2`, `retry`) is detected. Flips `_run_counted` flag to prevent duplicate credits. Lock is only reset when the bot successfully transitions back to `READY`.

### 5. False Auto-Toggle (Flash Bug)
*   **Problem:** Explosions in boss rooms matched the Grey (OFF) template at standard confidence, causing the bot to turn Auto OFF.
*   **Solution:** **Dual-Confidence Filter**.
*   **Implementation:** Checks for Green (ON) first at 0.85 (Forgiving). If found, exits. Only checks for Grey (OFF) at 0.995 (Strict).

## Validation Standards
*   **Type Integrity:** 100% `mypy` verified to prevent `NoneType` crashes during long-duration sessions.
*   **Linting:** 100% `ruff` (PEP 8) compliant.
*   **Unit Tests:** `test_v5_logic.py` validates matching math independently of the X11 environment.
