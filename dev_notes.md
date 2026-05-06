# Development Notes - BBS Bot (V6 'Snapshot Engine')

## Architectural Evolution
The bot has evolved through several major paradigms:
*   **V2 (The Slug):** Procedural architecture with hardcoded `time.sleep()` calls.
*   **V3 (The Ghost):** "Fire and forget" interaction logic running at 10fps.
*   **V4 (The Stealth Engine):** Introduced Dictionary-Mapped State Machine and Circadian rhythms.
*   **V5.8 (The Hardened Engine):** Definitive synthesis of state-awareness and snappy reaction speed.
*   **V6.0+ (The Snapshot Engine):** Current standard. Refactored the core vision loop for extreme resource efficiency and absolute focus stability.

## Core V6/V7 Technologies

### 1. Snapshot Architecture (Vision Efficiency)
Previous versions performed full-screen image matching for every UI element. V6.0 introduces the "Single Capture" loop:
*   **Mechanism:** At the top of every 100ms cycle, exactly one `pyautogui.screenshot(region=self.region)` is captured.
*   **Memory Offsets:** All subsequent checks (like `get_ui_region("auto")`) do not take new screenshots. They perform mathematical coordinate offsets against the existing image in memory.
*   **Performance:** Drastically reduces CPU load and eliminates "stuttering" during intensive co-op rooms.

### 2. Passive Persistence (The "Sword & Shield")
V6.5+ implements a "Polite" window management strategy to solve workspace jumping and focus loss:
*   **The Shield (Passive):** The bot enforces `Sticky` (on all desktops) and `Above` (Always on Top) flags via `wmctrl`. This ensures the game window is visually present wherever the user goes.
*   **The Sword (Active):** `get_game_region` performs a low-overhead `xprop` audit of `WM_STATE` and `_NET_WM_DESKTOP`. If the window is minimized or loses its sticky bit, the bot passively re-applies the flags and uses `windowraise` to lift it.
*   **Mental Model Alignment:** Unlike `windowactivate`, which causes annoying workspace "dragging," V6.8+ uses passive lifts. The game "follows" the user silently.

### 3. Dual-Confidence Auto Management
To prevent the "Flash Bug" (where flashy boss-death animations fooled the bot into disabling Auto), V6.5 introduces:
*   **Forgiving Green (0.85):** The bot prioritizes looking for the Green (ON) button first. It uses a lower confidence to ensure that even through special effects, it recognizes the button is already ON and does nothing.
*   **Strict Grey (0.995):** The bot only clicks the screen if it is mathematically certain it sees the exact Grey (OFF) template. This creates a "One-Way Gate" that keeps Auto firmly enabled.

### 4. Precision Run Counting (Cycle Lock)
V7.0 introduces an authoritative run counting lock to ensure 100% accurate session stats:
*   **The Problem:** Lag often causes the bot to see multiple finish images (`tap1`, `tap2`) or skip them entirely.
*   **The Fix:** A single authoritative `is_done` check at the start of the `handle_finish` cycle credits the run to the `run_count` and immediately flips a `_run_counted` lock. 
*   **Reset:** The lock is only reset when the bot successfully joins a new lobby (`READY` state), ensuring exactly one credit per quest.

### 5. Surgical Sub-Processing (ID Caching)
To reduce the overhead of constant `xdotool` and `ps` spawns:
*   **WID Caching:** The bot caches the Window ID after the first search.
*   **Cold Cache Refresh:** It only performs a full system-wide search (`xdotool search --name`) if the cached ID fails an `xprop` check or every 5 seconds (`POLL_PROPERTY_SYNC`).
*   **Latency:** Reduces loop latency by ~40ms on modern Linux kernels.

## Validation & Quality Standards
V6/V7 enforces strict software engineering standards to prevent "Overnight Crashes":
*   **Type Safety:** 100% `mypy` verified. Eliminates `NoneType` index crashes in vision logic.
*   **Linting:** 100% `ruff` (PEP 8) compliant.
*   **Sanity Testing:** `test_v6_sanity.py` simulates X11 boot loops without interacting with real windows, ensuring the engine structure remains sound after refactors.
