import os
import sys
import time
import subprocess
import random

import pyautogui
import pyscreeze

# --- CONFIGURATION ---
GAME_WINDOW_TITLE = "Bleach: Brave Souls"

# Timeouts and delays
ROOM_LOAD_TIMEOUT = 5
ROOM_LOAD_DELAY = 1
LOBBY_LOAD_DELAY = 5.5
CHECK_RUN_START_TIMEOUT = 90
QUEST_MAX_TIME = 300
MAX_RULE_DISTANCE = 100

# Standard pyautogui configuration
pyautogui.FAILSAFE = False  # Disable failsafe - we'll use Ctrl+C instead
pyautogui.PAUSE = 0.3  # 0.3s delay after every pyautogui action for stability

TEMPLATES = {
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
    "tap1": "images/tap1.png",
    "tap2": "images/tap2.png",
    "retry": "images/retry.png",
}

os.makedirs("screenshots", exist_ok=True)


def get_game_region():
    try:
        wid = (
            subprocess.check_output(
                [
                    "xdotool",
                    "search",
                    "--onlyvisible",
                    "--name",
                    f"^{GAME_WINDOW_TITLE}$",
                ],
                text=True,
            )
            .strip()
            .split()[0]
        )
        geo_lines = subprocess.check_output(
            ["xdotool", "getwindowgeometry", "--shell", wid], text=True
        ).splitlines()
        geo = {k: int(v) for k, v in (l.split("=") for l in geo_lines if "=" in l)}
    except Exception as e:
        print("Window lookup failed:", e)
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

def screenshot_and_exit(region, tag, run_count=None):
    suffix = f"_run{run_count}" if run_count is not None else ""
    path = f"screenshots/{tag}{suffix}_{int(time.time())}.png"
    pyautogui.screenshot(region=region).save(path)
    print(f"[FAIL] {tag}{suffix} → saved {path}")
    sys.exit(1)


def simple_click(x, y, description="element"):
    """Simple pyautogui click with randomization for human-like behavior"""
    # Focus and raise game window before clicking (ensures click registers)
    focus_game_window()
    
    # Add small random delay before clicking (0.1-0.4s)
    random_delay = random.uniform(0.1, 0.4)
    time.sleep(random_delay)
    
    # Click at the provided coordinates (already randomized by poll_and_click)
    print(f"[CLICK] {description} @ ({x},{y}) [random within template]")
    pyautogui.click(x, y)
    print(f"[CLICK] ✅ Clicked {description}")
    
    # Add small random delay after clicking (0.05-0.2s)
    post_delay = random.uniform(0.05, 0.2)
    time.sleep(post_delay)

def focus_game_window():
    """Focus and raise game window for reliable clicking"""
    try:
        # Both focus AND raise for reliable clicking
        subprocess.run(["xdotool", "windowactivate", "--sync", win_id], 
                       check=True, stderr=subprocess.DEVNULL)
        subprocess.run(["xdotool", "windowraise", win_id], 
                       check=True, stderr=subprocess.DEVNULL)
        time.sleep(0.2)  # Give window time to come to front and get focus
        print("[FOCUS] Game window focused and raised for click")
    except Exception as e:
        print(f"[FOCUS] Failed to focus/raise window: {e}")


def poll_and_click(template_key, region, timeout=10, interval=0.5, run_count=None, description="element"):
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
                TEMPLATES[template_key], region=region, confidence=0.8)
            if template_box:
                # Click randomly within the template bounds (guaranteed safe)
                random_x = random.randint(template_box.left, template_box.left + template_box.width - 1)
                random_y = random.randint(template_box.top, template_box.top + template_box.height - 1)
                simple_click(random_x, random_y, description)
                print(f"[POLL] {description} found and clicked after {elapsed_time:.1f}s")
                return True
        except (pyscreeze.ImageNotFoundException, OSError,
                pyautogui.ImageNotFoundException):
            pass

        print(f"[POLL] Waiting for {description}... {elapsed_time:.1f}s")
        time.sleep(interval)
    
    # Timeout - take screenshot and return False
    print(f"[TIMEOUT] {description} not found after {timeout}s")
    if run_count is not None:
        screenshot_and_exit(region, f"timeout_{template_key}", run_count)
    return False
def find_auto_icons(region):
    try:
        all_matches = list(
            pyautogui.locateAllOnScreen(
                TEMPLATES["auto"], region=region, confidence=0.8
            )
        )
        # Remove duplicate/overlapping detections
        return deduplicate_auto_icons(all_matches)
    except pyscreeze.ImageNotFoundException:
        return []

def find_room_rules(region):
    """Find all room rules on screen"""
    try:
        return list(pyautogui.locateAllOnScreen(
            TEMPLATES["room_rules_valid"], region=region, confidence=0.7))
    except (pyscreeze.ImageNotFoundException, OSError, pyautogui.ImageNotFoundException):
        return []

def match_autos_with_rules(autos, rules, run_count):
    """Match AUTO icons with Room Rules by proximity"""
    log_run(run_count, "MATCH", "Grouping AUTO icons with Room Rules by proximity")
    valid_rooms = []
    
    for i, auto in enumerate(autos):
        auto_x, auto_y = auto.left + auto.width // 2, auto.top + auto.height // 2
        log_run(run_count, "MATCH", f"AUTO {i+1} at ({auto_x}, {auto_y})")
        
        closest_rule = None
        min_distance = float("inf")
        
        for j, rule in enumerate(rules):
            rule_x, rule_y = rule.left + rule.width // 2, rule.top + rule.height // 2
            
            if rule_y > auto_y:  # Rule must be below AUTO icon
                distance = abs(rule_y - auto_y) + abs(rule_x - auto_x) * 0.1
                log_run(run_count, "MATCH", f"  Rule {j+1} at ({rule_x}, {rule_y}), distance: {distance:.1f}")
                
                if distance < min_distance and distance < MAX_RULE_DISTANCE:
                    min_distance = distance
                    closest_rule = rule
                    log_run(run_count, "MATCH", f"  → New closest rule (distance: {distance:.1f})")
        
        if closest_rule:
            rule_x, rule_y = closest_rule.left + closest_rule.width // 2, closest_rule.top + closest_rule.height // 2
            log_run(run_count, "MATCH", f"✅ AUTO {i+1} matched with Rule at ({rule_x}, {rule_y})")
            valid_rooms.append((auto, closest_rule))
        else:
            log_run(run_count, "MATCH", f"❌ AUTO {i+1} - no matching Room Rules found")
    
    return valid_rooms

def deduplicate_auto_icons(matches, min_distance=40):
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
    region, win_id = get_game_region()
    print(f"DEBUG region = {region}")
    print("[SETUP] Bot ready - using simple pyautogui clicks")
    print("[INFO] Press Ctrl+C to stop the bot")

    run_count = 0
    state = "MENU"

    while True:
        if state == "MENU":
            log_run(run_count, "STATE", f"MENU - Starting run #{run_count + 1}")
            # Step 1: click main Co-op Quest banner
            log_run(run_count, "STEP", "1 - Clicking coop quest menu")
            poll_and_click("coop_quest", region, timeout=10, run_count=run_count, description="coop quest menu")

            # Step 2: select the specific quest
            log_run(run_count, "STEP", "2 - Selecting specific quest")
            poll_and_click("open_coop_quest", region, timeout=10, run_count=run_count, description="specific quest")

            log_run(run_count, "TRANSITION", "MENU → ENTER_ROOM_LIST")
            state = "ENTER_ROOM_LIST"

        elif state == "ENTER_ROOM_LIST":
            log_run(run_count, "STATE", "ENTER_ROOM_LIST")
            # Step 3: Enter room list
            log_run(run_count, "STEP", "3 - Entering room list")
            poll_and_click("enter_room_button", region, timeout=10, run_count=run_count, description="enter room list")
            log_run(run_count, "WAIT", "Waiting for room list to load...")
            # Poll for AUTO icons to appear (indicates room list loaded)
            start_time = time.time()
            while time.time() - start_time < ROOM_LOAD_TIMEOUT:
                try:
                    test_autos = list(pyautogui.locateAllOnScreen(
                        TEMPLATES["auto"], region=region, confidence=0.8))
                    if len(test_autos) > 0:
                        elapsed = time.time() - start_time
                        log_run(run_count, "LOADED", f"Room list loaded with {len(test_autos)} AUTO icons after {elapsed:.1f}s")
                        break
                except (pyscreeze.ImageNotFoundException, OSError, 
                        pyautogui.ImageNotFoundException):
                    pass
                time.sleep(0.5)
            else:
                log_run(run_count, "TIMEOUT", "Room list didn't load - continuing anyway")
            
            # Additional delay to ensure room list is fully interactive
            log_run(run_count, "WAIT", f"Extra {ROOM_LOAD_DELAY}s delay for room list to become clickable...")
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
            log_run(run_count, "SCAN", f"Found {len(rules)} Room Rules" if rules else "No Room Rules found")
            
            # Match AUTO icons with Room Rules
            valid_rooms = match_autos_with_rules(autos, rules, run_count)
            
            log_run(run_count, "RESULT", f"Found {len(autos)} AUTO icons, {len(rules)} Room Rules")
            log_run(run_count, "RESULT", f"Valid rooms = {len(valid_rooms)} (matched pairs)")

            # Step 5a: if none valid → search again
            if not valid_rooms:
                log_run(run_count, "DECISION", "No valid rooms found - searching again")
                poll_and_click("search_again", region, timeout=10, run_count=run_count, description="search again button")
                refresh_delay = 0.5
                log_run(run_count, "WAIT", f"{refresh_delay}s for new room list...")
                time.sleep(refresh_delay)
                log_run(run_count, "TRANSITION", "SCAN_ROOMS → SCAN_ROOMS (search again)")
                state = "SCAN_ROOMS"
                continue

            # Step 5b: join first valid room (simplified - focus timing should make this reliable)
            log_run(run_count, "DECISION", f"Joining first valid room (1 of {len(valid_rooms)})")
            auto, rule = valid_rooms[0]
            px = int((auto.left + rule.left + rule.width) // 2)
            py_ = int(auto.top + auto.height // 2)
            log_run(run_count, "CALCULATE", f"Target position: ({px}, {py_}) - between AUTO and Rule")
            
            simple_click(px, py_, "room join")
            
            # Brief pause to check what happened
            check_delay = 1.5
            log_run(run_count, "WAIT", f"{check_delay}s to check if room join succeeded...")
            time.sleep(check_delay)
            
            # Check for unavailable popup or room owner disconnect
            try:
                popup_close = pyautogui.locateCenterOnScreen(
                    TEMPLATES["close"], region=region, confidence=0.8)
                if popup_close:
                    popup_delay = 1.5
                    print(f"[RUN {run_count + 1}] [POPUP] Room unavailable/owner disconnect - closing popup and re-scanning")
                    simple_click(popup_close[0], popup_close[1], "popup close")
                    print(f"[RUN {run_count + 1}] [WAIT] {popup_delay}s for popup to close and room list to refresh...")
                    time.sleep(popup_delay)
                    state = "SCAN_ROOMS"  # Re-scan for different rooms
                    continue
            except (pyscreeze.ImageNotFoundException, OSError, 
                    pyautogui.ImageNotFoundException):
                pass
                
            # If no popup, assume we joined successfully  
            log_run(run_count, "SUCCESS", f"Room joined - waiting {LOBBY_LOAD_DELAY}s for lobby to load...")
            time.sleep(LOBBY_LOAD_DELAY)  # Give lobby time to fully load after joining
            print(f"[RUN {run_count + 1}] [TRANSITION] SCAN_ROOMS → READY")
            state = "READY"

        elif state == "READY":
            log_run(run_count, "STATE", "READY")
            # Step 6: Click ready button (lobby should be loaded now)
            log_run(run_count, "STEP", "6 - Clicking ready button")
            poll_and_click(
                'ready', region,
                timeout=15,
                interval=0.5,
                run_count=run_count,
                description="ready button"
            )
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
                
                # Check for ingame auto off (should appear first)
                try:
                    auto_off = pyautogui.locateCenterOnScreen(
                        TEMPLATES['ingame_auto_off'], region=region, confidence=0.8)
                    if auto_off:
                        print(f"[RUN {run_count + 1}] [RUN] Found ingame auto OFF after {elapsed:.1f}s - clicking to turn ON!")
                        simple_click(auto_off[0], auto_off[1], "ingame auto off")
                        run_started = True
                        auto_found = True
                        break
                except (pyscreeze.ImageNotFoundException, OSError, pyautogui.ImageNotFoundException):
                    pass
                
                # Also check for auto on (in case it was already enabled)
                try:
                    auto_on = pyautogui.locateCenterOnScreen(
                        TEMPLATES['ingame_auto_on'], region=region, confidence=0.8)
                    if auto_on:
                        print(f"[RUN {run_count + 1}] [RUN] Found ingame auto ON after {elapsed:.1f}s - auto already enabled!")
                        run_started = True
                        auto_found = True
                        break
                except (pyscreeze.ImageNotFoundException, OSError, pyautogui.ImageNotFoundException):
                    pass
                
                # Check for any disconnect popup (network/room owner) - both use close button
                try:
                    close_btn = pyautogui.locateCenterOnScreen(
                        TEMPLATES['close'], region=region, confidence=0.8)
                    if close_btn:
                        print(f"[RUN {run_count + 1}] [ERROR] Disconnect popup detected after {elapsed:.1f}s")
                        simple_click(close_btn[0], close_btn[1], "disconnect popup close")
                        time.sleep(2)
                        print(f"[RUN {run_count + 1}] [RECOVERY] Disconnect popup closed - restarting from menu")
                        state = "MENU"
                        break
                except (pyscreeze.ImageNotFoundException, OSError, pyautogui.ImageNotFoundException):
                    pass
                
                # Don't check for retire button here - it's always visible in lobby
                
                print(f"[RUN {run_count + 1}] [CHECK] Waiting for run to start... {elapsed:.1f}s")
                time.sleep(2)  # Check every 2 seconds
            
            if run_started and auto_found:
                print(f"[RUN {run_count + 1}] [SUCCESS] Run confirmed started - proceeding to monitor quest")
                print(f"[RUN {run_count + 1}] [TRANSITION] CHECK_RUN_START → RUNNING")
                state = "RUNNING"
            elif state == "CHECK_RUN_START":  # Still in this state means timeout
                log_run(run_count, "TIMEOUT", f"Run failed to start after {CHECK_RUN_START_TIMEOUT}s - trying to retire")
                # Now try to find and click retire button
                try:
                    retire_btn = pyautogui.locateCenterOnScreen(
                        TEMPLATES['retire'], region=region, confidence=0.8)
                    if retire_btn:
                        print(f"[RUN {run_count + 1}] [RETIRE] Clicking retire button to leave room")
                        simple_click(retire_btn[0], retire_btn[1], "retire button")
                        time.sleep(1)
                        
                        # Click okay to confirm retirement
                        print(f"[RUN {run_count + 1}] [RETIRE] Looking for okay confirmation button...")
                        poll_and_click("okay", region, timeout=10, run_count=run_count, description="okay confirmation")
                        time.sleep(1)
                        
                        print(f"[RUN {run_count + 1}] [RECOVERY] Retired from room - restarting from menu")
                        state = "MENU"
                    else:
                        print(f"[RUN {run_count + 1}] [ERROR] No retire button found - taking screenshot")
                        screenshot_and_exit(region, "no_retire_button", run_count)
                except (pyscreeze.ImageNotFoundException, OSError, pyautogui.ImageNotFoundException):
                    print(f"[RUN {run_count + 1}] [ERROR] Retire button not found - taking screenshot")
                    screenshot_and_exit(region, "run_start_failed", run_count)

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
                    pt = pyautogui.locateCenterOnScreen(
                        TEMPLATES['tap1'], region=region, confidence=0.8)
                    if pt:
                        print(f"[RUN {run_count + 1}] [QUEST] Quest completed after {elapsed:.1f}s")
                        print(f"[RUN {run_count + 1}] [TRANSITION] RUNNING → FINISH")
                        state = "FINISH"
                        break
                except (pyscreeze.ImageNotFoundException, OSError, pyautogui.ImageNotFoundException):
                    pass
                
                # Check for network disconnect popup during quest (resume single player or close)
                try:
                    close_btn = pyautogui.locateCenterOnScreen(
                        TEMPLATES['close'], region=region, confidence=0.8)
                    if close_btn:
                        print(f"[RUN {run_count + 1}] [ERROR] Network disconnect during quest after {elapsed:.1f}s")
                        simple_click(close_btn[0], close_btn[1], "network disconnect close")
                        print(f"[RUN {run_count + 1}] [RECOVERY] Continuing quest (resume single player or restart)...")
                        # Continue in the same state - either continues as single player or we'll detect quest completion
                except (pyscreeze.ImageNotFoundException, OSError, pyautogui.ImageNotFoundException):
                    pass
                
                print(f"[RUN {run_count + 1}] [QUEST] Running... {elapsed:.0f}s")
                time.sleep(10)  # Check every 10 seconds
            else:
                # Quest timeout - screenshot and exit
                print(f"[RUN {run_count + 1}] [ERROR] Quest timeout after 5 minutes")
                screenshot_and_exit(region, "quest_timeout", run_count)

        elif state == "FINISH":
            log_run(run_count, "STATE", "FINISH")
            # Steps 8–9: tap to continue twice
            log_run(run_count, "STEP", "8 - First tap to continue")
            poll_and_click("tap1", region, timeout=15, run_count=run_count, description="first tap button")
            log_run(run_count, "WAIT", "Brief pause after first tap...")
            time.sleep(1)  # Very brief pause

            log_run(run_count, "STEP", "9 - Second tap to continue")
            poll_and_click("tap2", region, timeout=10, run_count=run_count, description="second tap button")
            log_run(run_count, "WAIT", "Brief pause after second tap...")
            time.sleep(1)  # Very brief pause

            # Step 10: retry to loop back
            log_run(run_count, "STEP", "10 - Clicking retry for next run")
            poll_and_click("retry", region, timeout=10, run_count=run_count, description="retry button")
            log_run(run_count, "WAIT", "Brief pause after retry...")
            time.sleep(0.5)  # Very brief pause

            run_count += 1
            print(f"✅ [RUN {run_count}] Completed run #{run_count}")
            print(
                f"[RUN {run_count}] [TRANSITION] FINISH → ENTER_ROOM_LIST (retry should go to room list)"
            )
            time.sleep(0.5)
            state = "ENTER_ROOM_LIST"
