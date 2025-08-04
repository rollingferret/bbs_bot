import os
import sys
import time
import subprocess
import random

import pyautogui
import pyscreeze
from Xlib import X, display, protocol

# --- CONFIGURATION ---
GAME_WINDOW_TITLE = "Bleach: Brave Souls"

# === ROOM MANAGEMENT TIMEOUTS ===
ROOM_LOAD_TIMEOUT = 5  # Max time to wait for room list to load with AUTO icons
ROOM_LOAD_DELAY = 1  # Extra delay for room list to become clickable after loading
LOBBY_LOAD_DELAY = 6  # Time to wait for lobby to fully load after joining room
ROOM_JOIN_CHECK_DELAY = (
    1.5  # How long to wait before checking if room join succeeded/failed
)

# === QUEST EXECUTION TIMEOUTS ===
CHECK_RUN_START_TIMEOUT = (
    300  # Max time to wait for quest to start (looking for auto button) - increased for longer loading times
)
QUEST_MAX_TIME = 300  # Max time to wait for quest completion (5 minutes)

# === ROOM MATCHING CONFIG ===
MAX_RULE_DISTANCE = 100  # Max pixel distance to match AUTO icon with Room Rules

# === UI INTERACTION DELAYS ===
POPUP_DISMISS_DELAY = 2.0  # Wait after dismissing error/info popups
SEARCH_AGAIN_DELAY = 1.5  # Wait after clicking search again before re-scanning
TAP_PAUSE_DELAY = 5.0  # Pause between quest completion tap buttons
SCREEN_TRANSITION_DELAY = 2.0  # Wait for screen transitions (tap2 → retry screen)
RETRY_PAUSE_DELAY = 3  # Pause after clicking retry button for game to load

# === POLLING AND RECOVERY DELAYS ===
ROOM_LIST_POLL_INTERVAL = 0.5  # How often to check if room list loaded
READY_POLL_INTERVAL = 0.5  # How often to poll for ready button
READY_BUTTON_TIMEOUT = 15  # Max time to wait for ready button to appear
TAP1_BUTTON_TIMEOUT = 15      # Max time to wait for first tap button
TAP2_BUTTON_TIMEOUT = 20      # Max time to wait for second tap button
DISCONNECT_RECOVERY_DELAY = 2.0  # Wait after disconnect popup before restart
RETIREMENT_STEP_DELAY = 1.0  # Wait between retirement confirmation steps
RUN_START_POLL_INTERVAL = 2.0  # How often to check if quest started
QUEST_POLL_INTERVAL = 10.0  # How often to check quest completion
FINAL_PAUSE_DELAY = 0.5  # Brief final pause before next cycle

# === PYAUTOGUI CONFIGURATION ===
pyautogui.FAILSAFE = False  # Disable mouse-corner failsafe (use Ctrl+C instead)
pyautogui.PAUSE = 0.1  # Global delay after every pyautogui action (reduced for speed)


# === WINDOW MANAGEMENT ===
USE_WMCTRL_ALWAYS_ON_TOP = True  # Set to True to make game window sticky and always on top (works across workspaces)


# === CLICKING METHOD ===
USE_X11_DIRECT_CLICKS = True  # Set to True to use X11 direct window clicks (no focus stealing) vs pyautogui (needs focus)

# === TEMPLATE MATCHING ===
TEMPLATE_FOUND_DELAY = 0.05  # Small delay after finding template before clicking
INGAME_AUTO_READY_DELAY = 1.0  # Wait for game to fully load before clicking auto button

# === FOCUS MANAGEMENT ===
FOCUS_RESTORE_DELAY = 0.01  # Delay before focus restoration after X11 click

# === TEMPLATE MATCHING CONFIDENCE ===
TEMPLATE_CONFIDENCE_HIGH = 0.95  # For critical detection (ingame auto on)
TEMPLATE_CONFIDENCE_NORMAL = 0.8  # Standard confidence level
TEMPLATE_CONFIDENCE_LOOSE = 0.7  # For harder-to-match elements

# === CENTER CLICKING ===
CENTER_CLICK_OFFSET_FACTOR = 6  # Offset divisor for center-focused clicking
AUTO_BUTTON_OFFSET_FACTOR = 10  # Tighter offset for auto button (smaller clickable area)

# === AUTO ICON DETECTION ===
AUTO_ICON_MIN_DISTANCE = 60  # Min pixels between auto icons for dedup
ROOM_MATCHING_WEIGHT_FACTOR = 0.1  # Horizontal weight in room proximity algorithm

TEMPLATES = {
    # Game startup navigation
    "game_start": "images/game_start.png",
    "close_news": "images/close_news.png", 
    "coop_1": "images/coop-1.png",
    "coop_2": "images/coop-2.png",
    
    # Normal bot operation
    "coop_quest": "images/coop_quest.png",
    "open_coop_quest": "images/open_coop_quest.png",
    "enter_room_button": "images/join_coop_quest.png",
    "search_again": "images/search_again.png",
    "auto": "images/auto_icon.png",
    "ingame_auto_off": "images/ingame_auto_off.png",
    "ingame_auto_on": "images/ingame_auto_on.png",
    "room_rules_valid": "images/room_rules_valid.png",
    "close": "images/close.png",
    "ready": "images/ready_button.png",
    "retire": "images/retire.png",
    "okay": "images/okay.png",
    "closed_room_coop_quest_menu": "images/closed_room_coop_quest_menu.png",
    "tap1": "images/tap1.png",
    "tap2": "images/tap2.png",
    "retry": "images/retry.png",
}

os.makedirs("screenshots", exist_ok=True)

def get_game_region():
    try:
        # Find all windows with the game title
        wids = subprocess.check_output(
            [
                "xdotool",
                "search",
                "--onlyvisible",
                "--name",
                f"^{GAME_WINDOW_TITLE}$",
            ],
            text=True,
        ).strip().split()
        
        # Check each window to find the actual game process
        for wid in wids:
            if not wid:
                continue
            try:
                # Get the process ID for this window
                pid = subprocess.check_output(
                    ["xdotool", "getwindowpid", wid], text=True
                ).strip()
                
                # Check if this process is actually the game
                cmdline = subprocess.check_output(
                    ["ps", "-p", pid, "-o", "cmd", "--no-headers"], text=True
                ).strip()
                
                # Look for game executable in the command line
                if "BleachBraveSouls.exe" in cmdline or "BLEACH Brave Souls" in cmdline:
                    # This is the real game window
                    geo_lines = subprocess.check_output(
                        ["xdotool", "getwindowgeometry", "--shell", wid], text=True
                    ).splitlines()
                    geo = {
                        k: int(v) for k, v in (line.split("=") for line in geo_lines if "=" in line)
                    }
                    print(f"[GAME] Found game window ID: {wid} (PID: {pid})")
                    break
            except (subprocess.CalledProcessError, IndexError, ValueError):
                continue
        else:
            # No valid game window found
            raise Exception("No valid game process found with matching window title")
        
    except Exception as e:
        print(f"[ERROR] Window lookup failed: {e}")
        print(f"[ERROR] Make sure '{GAME_WINDOW_TITLE}' is running and visible")
        print("[ERROR] Ensure it's the actual game, not a browser tab")
        sys.exit(1)

    sw, sh = pyautogui.size()
    x = max(0, min(geo["X"], sw))
    y = max(0, min(geo["Y"], sh))
    w = max(1, min(geo["WIDTH"], sw - x))
    h = max(1, min(geo["HEIGHT"], sh - y))
    return (x, y, w, h), wid


def log_run(run_count, tag, message):
    """Consistent logging with run number prefix"""
    print(f"[RUN {run_count + 1}] [{tag}] {message}")


def restart_game_and_navigate():
    """Restart the game when completely stuck and navigate back to co-op"""
    print("[RESTART] Game appears stuck - restarting and navigating back...")
    
    # Find and kill the specific game process
    try:
        # Get all processes and find the game
        ps_output = subprocess.check_output(["ps", "aux"], text=True)
        for line in ps_output.split('\n'):
            if "BleachBraveSouls.exe" in line or ("proton" in line.lower() and "bleach" in line.lower()):
                try:
                    # Extract and validate PID (second column)
                    pid = int(line.split()[1])
                    if pid > 0:  # Ensure positive PID
                        print(f"[RESTART] Killing game process PID: {pid}")
                        subprocess.run(["kill", str(pid)], check=False)
                except (ValueError, IndexError):
                    # Skip invalid lines
                    continue
    except Exception as e:
        print(f"[RESTART] Process kill failed, trying pkill: {e}")
        # Fallback to pkill
        subprocess.run(["pkill", "-f", "BleachBraveSouls.exe"], check=False)
    
    time.sleep(5)  # Wait for cleanup
    
    # Restart via Steam
    print("[RESTART] Starting game via Steam...")
    subprocess.run(["steam", "steam://rungameid/1201240"], check=False)
    time.sleep(15)  # Give game time to fully load
    
    # Return to GAME_STARTUP state to navigate back to co-op
    return "GAME_STARTUP"


def screenshot_and_exit(region, tag, run_count=None):
    suffix = f"_run{run_count}" if run_count is not None else ""
    path = f"screenshots/{tag}{suffix}_{int(time.time())}.png"
    pyautogui.screenshot(region=region).save(path)
    print(f"[FAIL] {tag}{suffix} → saved {path}")
    sys.exit(1)


def try_state_recovery_or_exit(region, tag, run_count=None):
    """
    Attempt state recovery by scanning all templates.
    Returns recovered state if found, otherwise calls screenshot_and_exit.
    """
    print(f"[RECOVERY] Attempting to identify current screen state...")
    
    # Template → State mapping for recovery
    state_detection = [
        # Game startup screens
        ("game_start", "GAME_STARTUP", "Game startup - start button visible"),
        ("close_news", "GAME_STARTUP", "Game startup - news popup visible"),
        ("coop_1", "GAME_STARTUP", "Game startup - first coop navigation visible"),
        ("coop_2", "GAME_STARTUP", "Game startup - second coop navigation visible"),
        
        # Main menu screens 
        ("coop_quest", "MENU", "Main menu - coop quest button visible"),
        ("open_coop_quest", "MENU", "Quest selection - specific quest visible"),
        
        # Room list screens  
        ("enter_room_button", "ENTER_ROOM_LIST", "Join screen - need to enter room list"),
        ("auto", "SCAN_ROOMS", "Room list - AUTO icons visible"), 
        ("search_again", "SCAN_ROOMS", "Room list - search again visible"),
        
        # Lobby screens
        ("ready", "READY", "Room lobby - ready button visible"),
        
        # In-game screens
        ("ingame_auto_off", "CHECK_RUN_START", "Game starting - auto button OFF"),
        ("ingame_auto_on", "RUNNING", "Game running - auto already ON"),
        
        # Quest completion screens
        ("tap1", "FINISH", "Quest complete - first tap button"),
        ("tap2", "FINISH", "Quest complete - second tap button"), 
        ("retry", "FINISH", "Quest complete - retry button"),
        
        # Error/popup screens - restart from menu for safety
        ("close", "MENU", "Error popup detected - restarting from menu"),
        ("retire", "MENU", "Stuck in lobby - restarting from menu"),
        ("okay", "MENU", "Confirmation dialog - restarting from menu"),
    ]
    
    detected_states = []
    
    for template_key, target_state, description in state_detection:
        try:
            box = pyautogui.locateOnScreen(
                TEMPLATES[template_key], 
                region=region,
                confidence=TEMPLATE_CONFIDENCE_NORMAL
            )
            if box:
                detected_states.append((target_state, description, template_key))
                print(f"[RECOVERY] Found: {description}")
        except:
            pass
    
    # Recovery decision logic
    if not detected_states:
        print("[RECOVERY] No known templates detected - NEW EDGE CASE")
        screenshot_and_exit(region, tag, run_count)
        
    elif len(detected_states) == 1:
        state, desc, template = detected_states[0]
        print(f"[RECOVERY] ✅ Clear state identified: {desc}")
        return state
        
    else:
        # Multiple templates detected - use priority logic
        print(f"[RECOVERY] Multiple templates detected ({len(detected_states)}) - using priority logic")
        
        # Priority order: in-game states > lobby states > menu states
        priority_order = ["RUNNING", "CHECK_RUN_START", "FINISH", "READY", "SCAN_ROOMS", "ENTER_ROOM_LIST", "MENU"]
        
        for priority_state in priority_order:
            for state, desc, template in detected_states:
                if state == priority_state:
                    print(f"[RECOVERY] ✅ Priority state selected: {desc}")
                    return state
                    
        # Fallback (shouldn't reach here)
        state = detected_states[0][0]
        print(f"[RECOVERY] ⚠️ Fallback state: {state}")
        return state


def simple_click(x, y, description="element"):
    """X11 click with immediate focus reclaim"""

    if USE_X11_DIRECT_CLICKS:
        # Capture current window before click
        current_window = None
        window_name = "Unknown"
        try:
            current_window = subprocess.check_output(
                ["xdotool", "getactivewindow"], text=True
            ).strip()
            window_name = subprocess.check_output(
                ["xdotool", "getwindowname", current_window], text=True
            ).strip()
            print(f"[FOCUS] Before click - Window: {current_window} ({window_name})")
        except Exception as e:
            print(f"[FOCUS] Failed to get current window: {e}")

        # X11 direct clicking
        success = send_x11_click_to_window(win_id, x, y)

        # Brief delay for X11 event processing, then reclaim focus
        if current_window and success:
            time.sleep(FOCUS_RESTORE_DELAY)  # Minimal delay for game event processing
            try:
                subprocess.run(
                    [
                        "xdotool",
                        "windowactivate",
                        "--sync",
                        current_window,
                        "windowraise",
                        current_window,
                    ],
                    check=True,
                    stderr=subprocess.DEVNULL,
                )
                print(f"[FOCUS] Restored to: {current_window} ({window_name})")
            except Exception as e:
                print(f"[FOCUS] Failed to restore focus: {e}")

        if not success:
            print("[ERROR] X11 click failed! Check python-xlib installation")
            return False

        print(f"[CLICK] ✅ {description} @ ({x},{y}) [X11 + delayed refocus]")
        return True
    else:
        # Fallback pyautogui mode
        focus_game_window()
        pyautogui.click(x, y)
        print(f"[CLICK] ✅ {description} @ ({x},{y}) [pyautogui]")
        return True


def send_x11_click_to_window(window_id, x, y):
    """Send click using X11 send_event (working method)"""
    try:
        disp = display.Display()
        window = disp.create_resource_object("window", int(window_id))

        # Convert screen coordinates to window-relative coordinates
        geom = window.get_geometry()
        rel_x = x - geom.x
        rel_y = y - geom.y

        event_details = {
            "root": disp.screen().root,
            "window": window,
            "same_screen": 1,
            "child": X.NONE,
            "root_x": x,
            "root_y": y,
            "event_x": rel_x,
            "event_y": rel_y,
            "state": 0,
            "detail": 1,  # Left mouse button
            "time": int(time.time() * 1000) & 0xFFFFFFFF,
        }

        # Create and send button press event
        press_event = protocol.event.ButtonPress(**event_details)
        window.send_event(press_event, propagate=True)

        # Create and send button release event
        release_event = protocol.event.ButtonRelease(**event_details)
        window.send_event(release_event, propagate=True)

        # Flush events
        disp.flush()
        disp.sync()
        disp.close()
        return True

    except Exception as e:
        print(f"[X11] Click failed: {e}")
        return False


def setup_wmctrl_always_on_top():
    """Set game window to be sticky and always on top using wmctrl"""
    try:
        subprocess.run(
            ["wmctrl", "-r", GAME_WINDOW_TITLE, "-b", "add,sticky,above"],
            check=True,
            stderr=subprocess.DEVNULL,
        )
        print("[WMCTRL] Game window set to sticky and always on top")
    except Exception as e:
        print(f"[WMCTRL] Failed to set window sticky/above: {e}")


def focus_game_window():
    """Focus game window for reliable clicking (no logging during interference window)"""
    try:
        if USE_WMCTRL_ALWAYS_ON_TOP:
            # Just focus - no raise needed since wmctrl keeps window on top
            subprocess.run(
                ["xdotool", "windowactivate", "--sync", win_id],
                check=True,
                stderr=subprocess.DEVNULL,
            )
        else:
            # Combined focus and raise in single xdotool call for better performance
            subprocess.run(
                ["xdotool", "windowactivate", "--sync", win_id, "windowraise", win_id],
                check=True,
                stderr=subprocess.DEVNULL,
            )
    except Exception as e:
        print(f"[FOCUS] Failed to focus window: {e}")


def poll_and_click(
    template_key,
    region,
    timeout=10,
    interval=0.5,
    run_count=None,
    description="element",
    center_click=False,
):
    """
    Poll for a template and click it when found.
    Returns True if clicked successfully, False if timeout.
    """
    # Check if template file exists
    if not os.path.exists(TEMPLATES[template_key]):
        screenshot_and_exit(region, f"missing_{template_key}", run_count)

    print(f"[POLL] Looking for {description} (timeout: {timeout}s)")
    start_time = time.time()

    while time.time() - start_time < timeout:
        elapsed_time = time.time() - start_time

        try:
            # Get the full template box for safe random clicking
            template_box = pyautogui.locateOnScreen(
                TEMPLATES[template_key],
                region=region,
                confidence=TEMPLATE_CONFIDENCE_NORMAL,
            )
            if template_box:
                # Small delay after finding template OUTSIDE interference window
                time.sleep(TEMPLATE_FOUND_DELAY)

                if center_click:
                    # Center-focused clicking for better reliability
                    center_x = template_box.left + template_box.width // 2
                    center_y = template_box.top + template_box.height // 2
                    # Small random offset from center
                    offset_x = random.randint(
                        -template_box.width // CENTER_CLICK_OFFSET_FACTOR,
                        template_box.width // CENTER_CLICK_OFFSET_FACTOR,
                    )
                    offset_y = random.randint(
                        -template_box.height // CENTER_CLICK_OFFSET_FACTOR,
                        template_box.height // CENTER_CLICK_OFFSET_FACTOR,
                    )
                    click_x = center_x + offset_x
                    click_y = center_y + offset_y
                else:
                    # Random clicking within template bounds
                    click_x = random.randint(
                        template_box.left, template_box.left + template_box.width - 1
                    )
                    click_y = random.randint(
                        template_box.top, template_box.top + template_box.height - 1
                    )
                # Interference window: only focus restore delay (10ms)
                simple_click(click_x, click_y, description)
                print(
                    f"[POLL] {description} found and clicked after {elapsed_time:.1f}s"
                )
                return True
        except (
            pyscreeze.ImageNotFoundException,
            OSError,
            pyautogui.ImageNotFoundException,
        ):
            pass

        print(f"[POLL] Waiting for {description}... {elapsed_time:.1f}s")
        time.sleep(interval)

    # Timeout - take screenshot and exit (keep original behavior)
    print(f"[TIMEOUT] {description} not found after {timeout}s")
    if run_count is not None:
        screenshot_and_exit(region, f"timeout_{template_key}", run_count)
    return False


def find_auto_icons(region):
    try:
        all_matches = list(
            pyautogui.locateAllOnScreen(
                TEMPLATES["auto"], region=region, confidence=TEMPLATE_CONFIDENCE_NORMAL
            )
        )
        # Remove duplicate/overlapping detections
        return deduplicate_auto_icons(all_matches)
    except pyscreeze.ImageNotFoundException:
        return []


def find_room_rules(region):
    """Find all room rules on screen"""
    try:
        return list(
            pyautogui.locateAllOnScreen(
                TEMPLATES["room_rules_valid"],
                region=region,
                confidence=TEMPLATE_CONFIDENCE_LOOSE,
            )
        )
    except (
        pyscreeze.ImageNotFoundException,
        OSError,
        pyautogui.ImageNotFoundException,
    ):
        return []


def match_autos_with_rules(autos, rules, run_count):
    """Match AUTO icons with Room Rules by proximity"""
    log_run(run_count, "MATCH", "Grouping AUTO icons with Room Rules by proximity")
    valid_rooms = []

    for i, auto in enumerate(autos):
        auto_x, auto_y = auto.left + auto.width // 2, auto.top + auto.height // 2
        log_run(run_count, "MATCH", f"AUTO {i + 1} at ({auto_x}, {auto_y})")

        closest_rule = None
        min_distance = float("inf")

        for j, rule in enumerate(rules):
            rule_x, rule_y = rule.left + rule.width // 2, rule.top + rule.height // 2

            if rule_y > auto_y:  # Rule must be below AUTO icon
                distance = abs(rule_y - auto_y) + abs(rule_x - auto_x) * ROOM_MATCHING_WEIGHT_FACTOR
                log_run(
                    run_count,
                    "MATCH",
                    f"  Rule {j + 1} at ({rule_x}, {rule_y}), distance: {distance:.1f}",
                )

                if distance < min_distance and distance < MAX_RULE_DISTANCE:
                    min_distance = distance
                    closest_rule = rule
                    log_run(
                        run_count,
                        "MATCH",
                        f"  → New closest rule (distance: {distance:.1f})",
                    )

        if closest_rule:
            rule_x, rule_y = (
                closest_rule.left + closest_rule.width // 2,
                closest_rule.top + closest_rule.height // 2,
            )
            log_run(
                run_count,
                "MATCH",
                f"✅ AUTO {i + 1} matched with Rule at ({rule_x}, {rule_y}) - stopping search",
            )
            valid_rooms.append((auto, closest_rule))
            # Return immediately after finding first valid room for speed
            return valid_rooms
        else:
            log_run(
                run_count, "MATCH", f"❌ AUTO {i + 1} - no matching Room Rules found"
            )

    return valid_rooms


def deduplicate_auto_icons(matches, min_distance=AUTO_ICON_MIN_DISTANCE):
    """Remove overlapping AUTO icon detections that are too close together"""
    if not matches:
        return []

    unique_matches = []
    for match in matches:
        center_x = match.left + match.width // 2
        center_y = match.top + match.height // 2

        # Check if this match is too close to any existing unique match
        is_duplicate = False
        for unique in unique_matches:
            unique_x = unique.left + unique.width // 2
            unique_y = unique.top + unique.height // 2

            distance = ((center_x - unique_x) ** 2 + (center_y - unique_y) ** 2) ** 0.5
            if distance < min_distance:
                is_duplicate = True
                break

        if not is_duplicate:
            unique_matches.append(match)
            print(f"[DEDUPE] Unique AUTO at ({center_x}, {center_y})")
        else:
            print(f"[DEDUPE] Filtered duplicate AUTO at ({center_x}, {center_y})")

    return unique_matches


if __name__ == "__main__":
    # Test restart functionality - check before trying to find game window
    TEST_RESTART = len(sys.argv) > 1 and sys.argv[1] == "--test-restart"
    
    if TEST_RESTART:
        print("[TEST] Testing game restart functionality...")
        # Don't need to find existing game window - restart will start fresh game
        state = restart_game_and_navigate()
        # After restart, get the new game region
        region, win_id = get_game_region()
        print(f"Game window region after restart: {region}")
    else:
        # Normal startup - find existing game window and start farming
        region, win_id = get_game_region()
        print(f"Game window region: {region}")
        state = "MENU"  # Start normal farming operation

    # Set up wmctrl window management if enabled (after we have correct win_id)
    if USE_WMCTRL_ALWAYS_ON_TOP:
        setup_wmctrl_always_on_top()

    if USE_X11_DIRECT_CLICKS:
        print("[SETUP] Bot ready - using X11 direct clicks (no interference)")
    else:
        print("[SETUP] Bot ready - using pyautogui clicks (focus required)")
    print("[INFO] Press Ctrl+C to stop the bot")

    run_count = 0

    while True:
        if state == "GAME_STARTUP":
            print("[STARTUP] Navigating from game startup to co-op quest screen...")
            print("[STARTUP] Waiting 12s for game to fully initialize after restart...")
            time.sleep(12)
            
            # Step 1: Click game start button
            print("[STARTUP] Step 1: Clicking game start button")
            success = poll_and_click("game_start", region, timeout=30, description="game start button", center_click=True)
            if not success:
                print("[STARTUP] [ERROR] Failed to find/click game start button!")
                screenshot_and_exit(region, "startup_game_start_failed", run_count)
            
            print("[STARTUP] Waiting 8s for game to load...")
            time.sleep(8)
            
            # Step 2: Close news popup
            print("[STARTUP] Step 2: Closing news popup")
            poll_and_click("close_news", region, timeout=30, description="close news popup")
            print("[STARTUP] Waiting 7s for screen to load...")
            time.sleep(7)
            
            # Step 3: Navigate to co-op (first button)
            print("[STARTUP] Step 3: Navigating to co-op (first button)")
            poll_and_click("coop_1", region, timeout=30, description="first coop navigation")
            print("[STARTUP] Waiting 5s for coop screen to fully load and become clickable...")
            time.sleep(5)
            
            # Step 4: Navigate to co-op (second button)
            print("[STARTUP] Step 4: Navigating to co-op (second button)")
            poll_and_click("coop_2", region, timeout=30, description="second coop navigation")
            print("[STARTUP] Waiting 3s for screen to load...")
            time.sleep(3)
            
            print("[STARTUP] Navigation complete - transitioning to normal bot operation")
            state = "MENU"
            
        elif state == "MENU":
            log_run(run_count, "STATE", f"MENU - Starting run #{run_count + 1}")
            # Step 1: click main Co-op Quest banner
            log_run(run_count, "STEP", "1 - Clicking coop quest menu")
            poll_and_click(
                "coop_quest",
                region,
                timeout=10,
                run_count=run_count,
                description="coop quest menu",
            )

            # Step 2: select the specific quest
            log_run(run_count, "STEP", "2 - Selecting specific quest")
            poll_and_click(
                "open_coop_quest",
                region,
                timeout=10,
                run_count=run_count,
                description="specific quest",
            )

            log_run(run_count, "TRANSITION", "MENU → ENTER_ROOM_LIST")
            state = "ENTER_ROOM_LIST"

        elif state == "ENTER_ROOM_LIST":
            log_run(run_count, "STATE", "ENTER_ROOM_LIST")
            # Step 3: Enter room list
            log_run(run_count, "STEP", "3 - Entering room list")
            poll_and_click(
                "enter_room_button",
                region,
                timeout=10,
                run_count=run_count,
                description="enter room list",
                center_click=True,
            )
            log_run(run_count, "WAIT", "Waiting for room list to load...")
            # Poll for AUTO icons to appear (indicates room list loaded)
            start_time = time.time()
            while time.time() - start_time < ROOM_LOAD_TIMEOUT:
                try:
                    test_autos = list(
                        pyautogui.locateAllOnScreen(
                            TEMPLATES["auto"],
                            region=region,
                            confidence=TEMPLATE_CONFIDENCE_NORMAL,
                        )
                    )
                    if len(test_autos) > 0:
                        elapsed = time.time() - start_time
                        log_run(
                            run_count,
                            "LOADED",
                            f"Room list loaded with {len(test_autos)} AUTO icons after {elapsed:.1f}s",
                        )
                        break
                except (
                    pyscreeze.ImageNotFoundException,
                    OSError,
                    pyautogui.ImageNotFoundException,
                ):
                    pass
                time.sleep(ROOM_LIST_POLL_INTERVAL)
            else:
                log_run(
                    run_count, "TIMEOUT", "Room list didn't load - checking actual screen state"
                )
                # Use state recovery to determine where we actually are
                state = try_state_recovery_or_exit(region, "room_list_load_timeout", run_count)
                continue

            # Additional delay to ensure room list is fully interactive
            log_run(
                run_count,
                "WAIT",
                f"Extra {ROOM_LOAD_DELAY}s delay for room list to become clickable...",
            )
            time.sleep(ROOM_LOAD_DELAY)
            log_run(run_count, "TRANSITION", "ENTER_ROOM_LIST → SCAN_ROOMS")
            state = "SCAN_ROOMS"

        elif state == "SCAN_ROOMS":
            log_run(run_count, "STATE", "SCAN_ROOMS")
            # Step 4: Find all AUTO icons and Room Rules, then match them
            log_run(run_count, "STEP", "4 - Scanning for AUTO icons and Room Rules")
            autos = find_auto_icons(region)
            log_run(run_count, "SCAN", f"Found {len(autos)} AUTO icons")

            rules = find_room_rules(region)
            log_run(
                run_count,
                "SCAN",
                f"Found {len(rules)} Room Rules" if rules else "No Room Rules found",
            )

            # Match AUTO icons with Room Rules
            valid_rooms = match_autos_with_rules(autos, rules, run_count)

            log_run(
                run_count,
                "RESULT",
                f"Found {len(autos)} AUTO icons, {len(rules)} Room Rules",
            )
            log_run(
                run_count, "RESULT", f"Valid rooms = {len(valid_rooms)} (matched pairs)"
            )

            # Step 5a: if none valid → search again
            if not valid_rooms:
                log_run(run_count, "DECISION", "No valid rooms found - searching again")
                poll_and_click(
                    "search_again",
                    region,
                    timeout=10,
                    run_count=run_count,
                    description="search again button",
                )
                log_run(
                    run_count, "WAIT", f"{SEARCH_AGAIN_DELAY}s for new room list..."
                )
                time.sleep(SEARCH_AGAIN_DELAY)
                log_run(
                    run_count, "TRANSITION", "SCAN_ROOMS → SCAN_ROOMS (search again)"
                )
                state = "SCAN_ROOMS"
                continue

            # Step 5b: join first valid room
            log_run(
                run_count,
                "DECISION",
                f"Joining first valid room (1 of {len(valid_rooms)})",
            )
            auto, rule = valid_rooms[0]
            px = int((auto.left + rule.left + rule.width) // 2)
            py = int(auto.top + auto.height // 2)
            log_run(
                run_count,
                "CALCULATE",
                f"Target position: ({px}, {py}) - between AUTO and Rule",
            )

            simple_click(px, py, "room join")

            # Brief pause to check what happened
            log_run(
                run_count,
                "WAIT",
                f"{ROOM_JOIN_CHECK_DELAY}s to check if room join succeeded...",
            )
            time.sleep(ROOM_JOIN_CHECK_DELAY)

            # Check for room full popup (closed_room_coop_quest_menu.png)
            try:
                room_full_box = pyautogui.locateOnScreen(
                    TEMPLATES["closed_room_coop_quest_menu"],
                    region=region,
                    confidence=TEMPLATE_CONFIDENCE_NORMAL,
                )
                if room_full_box:
                    print(
                        f"[RUN {run_count + 1}] [POPUP] Room full - closing popup and restarting from menu"
                    )
                    # Template delay OUTSIDE interference window
                    time.sleep(TEMPLATE_FOUND_DELAY)
                    random_x = random.randint(
                        room_full_box.left, room_full_box.left + room_full_box.width - 1
                    )
                    random_y = random.randint(
                        room_full_box.top, room_full_box.top + room_full_box.height - 1
                    )
                    # Interference window: only focus restore delay (10ms)
                    simple_click(random_x, random_y, "room full popup")
                    print(
                        f"[RUN {run_count + 1}] [WAIT] {POPUP_DISMISS_DELAY}s for popup to close..."
                    )
                    time.sleep(POPUP_DISMISS_DELAY)
                    state = "MENU"  # Start from beginning
                    continue
            except (
                pyscreeze.ImageNotFoundException,
                OSError,
                pyautogui.ImageNotFoundException,
            ):
                pass

            # Check for unavailable popup or room owner disconnect
            try:
                popup_close_box = pyautogui.locateOnScreen(
                    TEMPLATES["close"],
                    region=region,
                    confidence=TEMPLATE_CONFIDENCE_NORMAL,
                )
                if popup_close_box:
                    print(
                        f"[RUN {run_count + 1}] [POPUP] Room unavailable/owner disconnect - closing popup and re-scanning"
                    )
                    # Template delay OUTSIDE interference window
                    time.sleep(TEMPLATE_FOUND_DELAY)
                    random_x = random.randint(
                        popup_close_box.left,
                        popup_close_box.left + popup_close_box.width - 1,
                    )
                    random_y = random.randint(
                        popup_close_box.top,
                        popup_close_box.top + popup_close_box.height - 1,
                    )
                    # Interference window: only focus restore delay (10ms)
                    simple_click(random_x, random_y, "popup close")
                    print(
                        f"[RUN {run_count + 1}] [WAIT] {POPUP_DISMISS_DELAY}s for popup to close and room list to refresh..."
                    )
                    time.sleep(POPUP_DISMISS_DELAY)
                    state = "SCAN_ROOMS"  # Re-scan for different rooms
                    continue
            except (
                pyscreeze.ImageNotFoundException,
                OSError,
                pyautogui.ImageNotFoundException,
            ):
                pass

            # If no popup, assume we joined successfully
            log_run(
                run_count,
                "SUCCESS",
                f"Room joined - waiting {LOBBY_LOAD_DELAY}s for lobby to load...",
            )
            time.sleep(LOBBY_LOAD_DELAY)  # Give lobby time to fully load after joining
            print(f"[RUN {run_count + 1}] [TRANSITION] SCAN_ROOMS → READY")
            state = "READY"

        elif state == "READY":
            log_run(run_count, "STATE", "READY")
            # Step 6: Click ready button (lobby should be loaded now)
            log_run(run_count, "STEP", "6 - Clicking ready button")

            # Custom polling for ready button that also checks for room full popup
            start_time = time.time()
            ready_clicked = False

            while time.time() - start_time < READY_BUTTON_TIMEOUT and not ready_clicked:
                elapsed = time.time() - start_time

                # Check for room full popup first
                try:
                    room_full_box = pyautogui.locateOnScreen(
                        TEMPLATES["closed_room_coop_quest_menu"],
                        region=region,
                        confidence=TEMPLATE_CONFIDENCE_NORMAL,
                    )
                    if room_full_box:
                        print(
                            f"[RUN {run_count + 1}] [POPUP] Room full while waiting for ready - restarting from menu"
                        )
                        # Template delay OUTSIDE interference window
                        time.sleep(TEMPLATE_FOUND_DELAY)
                        random_x = random.randint(
                            room_full_box.left,
                            room_full_box.left + room_full_box.width - 1,
                        )
                        random_y = random.randint(
                            room_full_box.top,
                            room_full_box.top + room_full_box.height - 1,
                        )
                        # Interference window: only focus restore delay (10ms)
                        simple_click(random_x, random_y, "room full popup")
                        time.sleep(POPUP_DISMISS_DELAY)
                        state = "MENU"
                        break
                except (
                    pyscreeze.ImageNotFoundException,
                    OSError,
                    pyautogui.ImageNotFoundException,
                ):
                    pass

                # Check for ready button
                try:
                    ready_box = pyautogui.locateOnScreen(
                        TEMPLATES["ready"],
                        region=region,
                        confidence=TEMPLATE_CONFIDENCE_NORMAL,
                    )
                    if ready_box:
                        # Template delay OUTSIDE interference window
                        time.sleep(TEMPLATE_FOUND_DELAY)

                        # Click randomly within the template bounds
                        random_x = random.randint(
                            ready_box.left, ready_box.left + ready_box.width - 1
                        )
                        random_y = random.randint(
                            ready_box.top, ready_box.top + ready_box.height - 1
                        )
                        # Interference window: only focus restore delay (10ms)
                        simple_click(random_x, random_y, "ready button")
                        print(
                            f"[POLL] ready button found and clicked after {elapsed:.1f}s"
                        )
                        ready_clicked = True
                        break
                except (
                    pyscreeze.ImageNotFoundException,
                    OSError,
                    pyautogui.ImageNotFoundException,
                ):
                    pass

                print(f"[POLL] Waiting for ready button... {elapsed:.1f}s")
                time.sleep(READY_POLL_INTERVAL)

            if state == "READY":  # Still in READY state, ready button was clicked
                if not ready_clicked:
                    # Timeout - attempt recovery
                    print(f"[TIMEOUT] ready button not found after {READY_BUTTON_TIMEOUT}s - attempting recovery")
                    state = try_state_recovery_or_exit(region, "timeout_ready", run_count)
                    continue

                # Ready to start the quest, now check if it actually started
                log_run(run_count, "TRANSITION", "READY → CHECK_RUN_START")
                state = "CHECK_RUN_START"

        elif state == "CHECK_RUN_START":
            log_run(run_count, "STATE", "CHECK_RUN_START")
            log_run(run_count, "STEP", "6.5 - Checking if run actually started...")

            # Poll for ingame auto button for 1.5 minutes
            start_time = time.time()
            run_started = False
            auto_found = False

            while time.time() - start_time < CHECK_RUN_START_TIMEOUT:
                elapsed = time.time() - start_time

                # Check for ingame auto off (should appear first) - loose threshold to catch it
                try:
                    auto_off_box = pyautogui.locateOnScreen(
                        TEMPLATES["ingame_auto_off"],
                        region=region,
                        confidence=TEMPLATE_CONFIDENCE_LOOSE,
                    )
                    if auto_off_box:
                        print(
                            f"[RUN {run_count + 1}] [RUN] Found ingame auto OFF after {elapsed:.1f}s - waiting for game to be ready..."
                        )
                        # Wait for game to fully load OUTSIDE interference window
                        time.sleep(INGAME_AUTO_READY_DELAY)
                        # Template delay OUTSIDE interference window  
                        time.sleep(TEMPLATE_FOUND_DELAY)
                        # Click near center of auto button (avoid edges for circular buttons)
                        center_x = auto_off_box.left + auto_off_box.width // 2
                        center_y = auto_off_box.top + auto_off_box.height // 2
                        # Small random offset from center (tighter for auto button reliability)
                        offset_x = random.randint(
                            -auto_off_box.width // AUTO_BUTTON_OFFSET_FACTOR,
                            auto_off_box.width // AUTO_BUTTON_OFFSET_FACTOR,
                        )
                        offset_y = random.randint(
                            -auto_off_box.height // AUTO_BUTTON_OFFSET_FACTOR,
                            auto_off_box.height // AUTO_BUTTON_OFFSET_FACTOR,
                        )
                        random_x = center_x + offset_x
                        random_y = center_y + offset_y
                        # Interference window: only focus restore delay (10ms)
                        simple_click(random_x, random_y, "ingame auto off")
                        run_started = True
                        auto_found = True
                        break
                except (
                    pyscreeze.ImageNotFoundException,
                    OSError,
                    pyautogui.ImageNotFoundException,
                ):
                    pass

                # Also check for auto on (in case it was already enabled) - strict threshold
                try:
                    auto_on_box = pyautogui.locateOnScreen(
                        TEMPLATES["ingame_auto_on"],
                        region=region,
                        confidence=TEMPLATE_CONFIDENCE_HIGH,
                    )
                    if auto_on_box:
                        print(
                            f"[RUN {run_count + 1}] [RUN] Found ingame auto ON after {elapsed:.1f}s - auto already enabled!"
                        )
                        run_started = True
                        auto_found = True
                        break
                except (
                    pyscreeze.ImageNotFoundException,
                    OSError,
                    pyautogui.ImageNotFoundException,
                ):
                    pass

                # Check for room closure popup (owner closed room)
                try:
                    room_closed_box = pyautogui.locateOnScreen(
                        TEMPLATES["closed_room_coop_quest_menu"],
                        region=region,
                        confidence=TEMPLATE_CONFIDENCE_NORMAL,
                    )
                    if room_closed_box:
                        print(
                            f"[RUN {run_count + 1}] [ERROR] Room closed by owner after {elapsed:.1f}s"
                        )
                        # Template delay OUTSIDE interference window
                        time.sleep(TEMPLATE_FOUND_DELAY)
                        random_x = random.randint(
                            room_closed_box.left,
                            room_closed_box.left + room_closed_box.width - 1,
                        )
                        random_y = random.randint(
                            room_closed_box.top,
                            room_closed_box.top + room_closed_box.height - 1,
                        )
                        # Interference window: only focus restore delay (10ms)
                        simple_click(random_x, random_y, "room closed popup")
                        time.sleep(RETIREMENT_STEP_DELAY)
                        print(
                            f"[RUN {run_count + 1}] [RECOVERY] Room closed - restarting from menu"
                        )
                        state = "MENU"
                        break
                except (
                    pyscreeze.ImageNotFoundException,
                    OSError,
                    pyautogui.ImageNotFoundException,
                ):
                    pass

                # Check for any disconnect popup (network/room owner) - both use close button
                try:
                    close_btn_box = pyautogui.locateOnScreen(
                        TEMPLATES["close"],
                        region=region,
                        confidence=TEMPLATE_CONFIDENCE_NORMAL,
                    )
                    if close_btn_box:
                        print(
                            f"[RUN {run_count + 1}] [ERROR] Disconnect popup detected after {elapsed:.1f}s"
                        )
                        # Template delay OUTSIDE interference window
                        time.sleep(TEMPLATE_FOUND_DELAY)
                        random_x = random.randint(
                            close_btn_box.left,
                            close_btn_box.left + close_btn_box.width - 1,
                        )
                        random_y = random.randint(
                            close_btn_box.top,
                            close_btn_box.top + close_btn_box.height - 1,
                        )
                        # Interference window: only focus restore delay (10ms)
                        simple_click(random_x, random_y, "disconnect popup close")
                        time.sleep(DISCONNECT_RECOVERY_DELAY)
                        print(
                            f"[RUN {run_count + 1}] [RECOVERY] Disconnect popup closed - restarting from menu"
                        )
                        state = "MENU"
                        break
                except (
                    pyscreeze.ImageNotFoundException,
                    OSError,
                    pyautogui.ImageNotFoundException,
                ):
                    pass

                # Don't check for retire button here - it's always visible in lobby

                print(
                    f"[RUN {run_count + 1}] [CHECK] Waiting for run to start... {elapsed:.1f}s"
                )
                time.sleep(RUN_START_POLL_INTERVAL)

            if run_started and auto_found:
                print(
                    f"[RUN {run_count + 1}] [SUCCESS] Run confirmed started - proceeding to monitor quest"
                )
                print(f"[RUN {run_count + 1}] [TRANSITION] CHECK_RUN_START → RUNNING")
                state = "RUNNING"
            elif state == "CHECK_RUN_START":  # Still in this state means timeout
                log_run(
                    run_count,
                    "TIMEOUT",
                    f"Run failed to start after {CHECK_RUN_START_TIMEOUT}s - trying to retire",
                )
                # Now try to find and click retire button
                try:
                    retire_btn_box = pyautogui.locateOnScreen(
                        TEMPLATES["retire"],
                        region=region,
                        confidence=TEMPLATE_CONFIDENCE_NORMAL,
                    )
                    if retire_btn_box:
                        print(
                            f"[RUN {run_count + 1}] [RETIRE] Clicking retire button to leave room"
                        )
                        # Template delay OUTSIDE interference window
                        time.sleep(TEMPLATE_FOUND_DELAY)
                        random_x = random.randint(
                            retire_btn_box.left,
                            retire_btn_box.left + retire_btn_box.width - 1,
                        )
                        random_y = random.randint(
                            retire_btn_box.top,
                            retire_btn_box.top + retire_btn_box.height - 1,
                        )
                        # Interference window: only focus restore delay (10ms)
                        simple_click(random_x, random_y, "retire button")
                        time.sleep(RETIREMENT_STEP_DELAY)

                        # Click okay to confirm retirement
                        print(
                            f"[RUN {run_count + 1}] [RETIRE] Looking for okay confirmation button..."
                        )
                        poll_and_click(
                            "okay",
                            region,
                            timeout=10,
                            run_count=run_count,
                            description="okay confirmation",
                        )
                        time.sleep(RETIREMENT_STEP_DELAY)

                        # Click final confirmation popup (closed_room_coop_quest_menu)
                        print(
                            f"[RUN {run_count + 1}] [RETIRE] Looking for final confirmation popup..."
                        )
                        poll_and_click(
                            "closed_room_coop_quest_menu",
                            region,
                            timeout=10,
                            run_count=run_count,
                            description="final retire confirmation",
                        )
                        time.sleep(RETIREMENT_STEP_DELAY)

                        print(
                            f"[RUN {run_count + 1}] [RECOVERY] Retired from room - restarting from menu"
                        )
                        state = "MENU"
                    else:
                        print(
                            f"[RUN {run_count + 1}] [ERROR] No retire button found - game likely stuck on loading screen"
                        )
                        print(f"[RUN {run_count + 1}] [RESTART] Restarting game to recover from loading screen hang")
                        state = restart_game_and_navigate()
                        # Update game region after restart
                        region, win_id = get_game_region()
                        print(f"[RUN {run_count + 1}] [RESTART] Updated game window region: {region}")
                        # Re-setup wmctrl with new window ID
                        if USE_WMCTRL_ALWAYS_ON_TOP:
                            setup_wmctrl_always_on_top()
                        break
                except (
                    pyscreeze.ImageNotFoundException,
                    OSError,
                    pyautogui.ImageNotFoundException,
                ):
                    print(
                        f"[RUN {run_count + 1}] [ERROR] Retire button not found - attempting recovery"
                    )
                    state = try_state_recovery_or_exit(region, "run_start_failed", run_count)
                    break

        elif state == "RUNNING":
            log_run(run_count, "STATE", "RUNNING")
            # Step 7: Poll for quest completion (tap1 button)
            log_run(run_count, "STEP", "7 - Quest started - waiting for completion...")

            # Create a special polling function that doesn't click, just detects
            start = time.time()

            while time.time() - start < QUEST_MAX_TIME:
                elapsed = time.time() - start

                # Check if quest completed (tap1 button available)
                try:
                    tap1_box = pyautogui.locateOnScreen(
                        TEMPLATES["tap1"],
                        region=region,
                        confidence=TEMPLATE_CONFIDENCE_NORMAL,
                    )
                    if tap1_box:
                        print(
                            f"[RUN {run_count + 1}] [QUEST] Quest completed after {elapsed:.1f}s"
                        )
                        print(f"[RUN {run_count + 1}] [TRANSITION] RUNNING → FINISH")
                        state = "FINISH"
                        break
                except (
                    pyscreeze.ImageNotFoundException,
                    OSError,
                    pyautogui.ImageNotFoundException,
                ):
                    pass

                # Check for network disconnect popup during quest (resume single player or close)
                try:
                    close_btn_box = pyautogui.locateOnScreen(
                        TEMPLATES["close"],
                        region=region,
                        confidence=TEMPLATE_CONFIDENCE_NORMAL,
                    )
                    if close_btn_box:
                        print(
                            f"[RUN {run_count + 1}] [ERROR] Network disconnect during quest after {elapsed:.1f}s"
                        )
                        # Template delay OUTSIDE interference window
                        time.sleep(TEMPLATE_FOUND_DELAY)
                        random_x = random.randint(
                            close_btn_box.left,
                            close_btn_box.left + close_btn_box.width - 1,
                        )
                        random_y = random.randint(
                            close_btn_box.top,
                            close_btn_box.top + close_btn_box.height - 1,
                        )
                        # Interference window: only focus restore delay (10ms)
                        simple_click(random_x, random_y, "network disconnect close")
                        print(
                            f"[RUN {run_count + 1}] [RECOVERY] Continuing quest (resume single player or restart)..."
                        )
                        # Continue in the same state - either continues as single player or we'll detect quest completion
                except (
                    pyscreeze.ImageNotFoundException,
                    OSError,
                    pyautogui.ImageNotFoundException,
                ):
                    pass

                print(f"[RUN {run_count + 1}] [QUEST] Running... {elapsed:.0f}s")
                time.sleep(QUEST_POLL_INTERVAL)
            else:
                # Quest timeout - attempt recovery 
                print(f"[RUN {run_count + 1}] [ERROR] Quest timeout after 5 minutes - attempting recovery")
                state = try_state_recovery_or_exit(region, "quest_timeout", run_count)
                continue

        elif state == "FINISH":
            log_run(run_count, "STATE", "FINISH")
            # Steps 8–9: tap to continue twice (center-focused clicking)
            log_run(run_count, "STEP", "8 - First tap to continue")

            # Custom tap1 clicking with center focus
            start_time = time.time()
            tap1_clicked = False
            while time.time() - start_time < TAP1_BUTTON_TIMEOUT and not tap1_clicked:
                try:
                    tap1_box = pyautogui.locateOnScreen(
                        TEMPLATES["tap1"],
                        region=region,
                        confidence=TEMPLATE_CONFIDENCE_NORMAL,
                    )
                    if tap1_box:
                        # Template delay OUTSIDE interference window
                        time.sleep(TEMPLATE_FOUND_DELAY)
                        # Click near center of tap1 button
                        center_x = tap1_box.left + tap1_box.width // 2
                        center_y = tap1_box.top + tap1_box.height // 2
                        offset_x = random.randint(
                            -tap1_box.width // CENTER_CLICK_OFFSET_FACTOR,
                            tap1_box.width // CENTER_CLICK_OFFSET_FACTOR,
                        )
                        offset_y = random.randint(
                            -tap1_box.height // CENTER_CLICK_OFFSET_FACTOR,
                            tap1_box.height // CENTER_CLICK_OFFSET_FACTOR,
                        )
                        random_x = center_x + offset_x
                        random_y = center_y + offset_y
                        # Interference window: only focus restore delay (10ms)
                        simple_click(random_x, random_y, "first tap button")
                        print(
                            f"[POLL] first tap button found and clicked after {time.time() - start_time:.1f}s"
                        )
                        tap1_clicked = True
                        break
                except (
                    pyscreeze.ImageNotFoundException,
                    OSError,
                    pyautogui.ImageNotFoundException,
                ):
                    pass
                time.sleep(READY_POLL_INTERVAL)

            if not tap1_clicked:
                state = try_state_recovery_or_exit(region, "timeout_tap1", run_count)
                continue

            log_run(run_count, "WAIT", "Brief pause after first tap...")
            time.sleep(TAP_PAUSE_DELAY)

            log_run(run_count, "STEP", "9 - Second tap to continue")

            # Custom tap2 clicking with center focus
            start_time = time.time()
            tap2_clicked = False
            while time.time() - start_time < TAP2_BUTTON_TIMEOUT and not tap2_clicked:
                try:
                    tap2_box = pyautogui.locateOnScreen(
                        TEMPLATES["tap2"],
                        region=region,
                        confidence=TEMPLATE_CONFIDENCE_NORMAL,
                    )
                    if tap2_box:
                        # Template delay OUTSIDE interference window
                        time.sleep(TEMPLATE_FOUND_DELAY)
                        # Click near center of tap2 button
                        center_x = tap2_box.left + tap2_box.width // 2
                        center_y = tap2_box.top + tap2_box.height // 2
                        offset_x = random.randint(
                            -tap2_box.width // CENTER_CLICK_OFFSET_FACTOR,
                            tap2_box.width // CENTER_CLICK_OFFSET_FACTOR,
                        )
                        offset_y = random.randint(
                            -tap2_box.height // CENTER_CLICK_OFFSET_FACTOR,
                            tap2_box.height // CENTER_CLICK_OFFSET_FACTOR,
                        )
                        random_x = center_x + offset_x
                        random_y = center_y + offset_y
                        # Interference window: only focus restore delay (10ms)
                        simple_click(random_x, random_y, "second tap button")
                        print(
                            f"[POLL] second tap button found and clicked after {time.time() - start_time:.1f}s"
                        )
                        tap2_clicked = True
                        break
                except (
                    pyscreeze.ImageNotFoundException,
                    OSError,
                    pyautogui.ImageNotFoundException,
                ):
                    pass
                time.sleep(READY_POLL_INTERVAL)

            if not tap2_clicked:
                state = try_state_recovery_or_exit(region, "timeout_tap2", run_count)
                continue
            log_run(
                run_count, "WAIT", "Waiting for screen transition after second tap..."
            )
            time.sleep(SCREEN_TRANSITION_DELAY)

            # Step 10: retry to loop back
            log_run(run_count, "STEP", "10 - Clicking retry for next run")
            poll_and_click(
                "retry",
                region,
                timeout=10,
                run_count=run_count,
                description="retry button",
            )
            log_run(run_count, "WAIT", "Brief pause after retry...")
            time.sleep(RETRY_PAUSE_DELAY)

            run_count += 1
            print(f"✅ [RUN {run_count}] Completed run #{run_count}")
            print(
                f"[RUN {run_count}] [TRANSITION] FINISH → ENTER_ROOM_LIST"
            )
            time.sleep(FINAL_PAUSE_DELAY)
            state = "ENTER_ROOM_LIST"
