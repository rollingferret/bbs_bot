import os
import sys
import time
import subprocess
import random

import pyautogui
import pyscreeze
from Xlib import X, display, protocol

class BBSBot:
    def __init__(self):
        # --- CONFIGURATION ---
        self._RAW_TITLE = "Bleach: Brave Souls"
        import re
        if not re.match(r'^[a-zA-Z0-9\s:.-]+$', self._RAW_TITLE):
            raise ValueError(f"Invalid game window title: {self._RAW_TITLE}")
        self.GAME_WINDOW_TITLE = self._RAW_TITLE

        # === TIMEOUTS AND DELAYS ===
        self.ROOM_LOAD_TIMEOUT = 5
        self.ROOM_LOAD_DELAY = 1
        self.LOBBY_LOAD_DELAY = 6
        self.ROOM_JOIN_CHECK_DELAY = 1.5
        self.CHECK_RUN_START_TIMEOUT = 300
        self.QUEST_MAX_TIME = 300
        self.GAME_START_BUTTON_TIMEOUT = 90
        self.POPUP_DISMISS_DELAY = 3.0
        self.SEARCH_AGAIN_DELAY = 2.0
        self.TAP_PAUSE_DELAY = 5.0
        self.SCREEN_TRANSITION_DELAY = 2.0
        self.RETRY_PAUSE_DELAY = 3
        self.ROOM_LIST_POLL_INTERVAL = 0.5
        self.READY_POLL_INTERVAL = 0.5
        self.READY_BUTTON_TIMEOUT = 15
        self.TAP1_BUTTON_TIMEOUT = 15
        self.TAP2_BUTTON_TIMEOUT = 20
        self.RETRY_BUTTON_TIMEOUT = 45.0
        self.DISCONNECT_RECOVERY_DELAY = 2.0
        self.RETIREMENT_STEP_DELAY = 1.0
        self.RUN_START_POLL_INTERVAL = 2.0
        self.QUEST_POLL_INTERVAL = 5.0
        self.FINAL_PAUSE_DELAY = 0.5

        # === PYAUTOGUI CONFIGURATION ===
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.1

        # === WINDOW MANAGEMENT ===
        self.USE_WMCTRL_ALWAYS_ON_TOP = True
        self.USE_X11_DIRECT_CLICKS = True

        # === TEMPLATE MATCHING ===
        self.CLICK_SOAK_DELAY = 0.5 # How long to wait after finding an image before clicking it.
        self.INGAME_AUTO_READY_DELAY = 1.5
        self.FOCUS_RESTORE_DELAY = 0.01
        self.TEMPLATE_CONFIDENCE_HIGH = 0.95
        self.TEMPLATE_CONFIDENCE_NORMAL = 0.8
        self.TEMPLATE_CONFIDENCE_LOOSE = 0.7
        self.CENTER_CLICK_OFFSET_FACTOR = 6
        self.AUTO_BUTTON_OFFSET_FACTOR = 10
        self.AUTO_ICON_MIN_DISTANCE = 60
        self.ROOM_MATCHING_WEIGHT_FACTOR = 0.1
        self.MAX_RULE_DISTANCE = 100

        self.TEMPLATES = {
            "game_start": "images/game_start.png",
            "close_news": "images/close_news.png",
            "coop_1": "images/coop-1.png",
            "coop_2": "images/coop-2.png",
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
        self.region = None
        self.win_id = None
        self.run_count = 0
        self.state = "MENU"
        self.restart_attempts = 0
        self.MAX_RESTARTS = 3
    
    def get_game_region(self):
        try:
            # Find all windows with the game title
            wids = subprocess.check_output(
                [
                    "xdotool",
                    "search",
                    "--onlyvisible",
                    "--name",
                    f"^{self.GAME_WINDOW_TITLE}$",
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
                        self.win_id = wid
                        break
                except (subprocess.CalledProcessError, IndexError, ValueError):
                    continue
            else:
                # No valid game window found
                raise Exception("No valid game process found with matching window title")
            
        except Exception as e:
            print(f"[ERROR] Window lookup failed: {e}")
            print(f"[ERROR] Make sure '{self.GAME_WINDOW_TITLE}' is running and visible")
            print("[ERROR] Ensure it's the actual game, not a browser tab")
            sys.exit(1)

        sw, sh = pyautogui.size()
        x = max(0, min(geo["X"], sw))
        y = max(0, min(geo["Y"], sh))
        w = max(1, min(geo["WIDTH"], sw - x))
        h = max(1, min(geo["HEIGHT"], sh - y))
        self.region = (x, y, w, h)
        return self.region, self.win_id

    def log_run(self, tag, message):
        """Consistent logging with run number prefix"""
        print(f"[RUN {self.run_count + 1}] [{tag}] {message}")

    def screenshot_and_exit(self, tag):
        suffix = f"_run{self.run_count}"
        path = f"screenshots/{tag}{suffix}_{int(time.time())}.png"
        pyautogui.screenshot(region=self.region).save(path)
        print(f"[FAIL] {tag}{suffix} → saved {path}")
        sys.exit(1)

    def restart_game_and_navigate(self):
        print("[RESTART] Game appears stuck - restarting and navigating back...")
        
        # Find and kill the specific game process (V1's robust kill logic)
        try:
            # Get all processes and find the game
            ps_output = subprocess.check_output(["ps", "aux"], text=True)
            for line in ps_output.split('\n'):
                if "BleachBraveSouls.exe" in line or ("proton" in line.lower() and "bleach" in line.lower()):
                    try:
                        # Extract and validate PID (second column)
                        pid = int(line.split()[1])
                        if pid > 0:  # Ensure positive PID
                            self.log_run("RESTART", f"Killing game process PID: {pid}")
                            subprocess.run(["kill", str(pid)], check=False)
                    except (ValueError, IndexError):
                        # Skip invalid lines
                        continue
        except Exception as e:
            self.log_run("RESTART", f"Process kill failed, trying pkill: {e}")
            # Fallback to pkill
            subprocess.run(["pkill", "-f", "BleachBraveSouls.exe"], check=False)
        
        time.sleep(5)  # V1's cleanup wait

        # Restart via Steam in a non-blocking way
        self.log_run("RESTART", "Starting game via Steam (non-blocking)...")
        subprocess.Popen(
            ["steam", "-applaunch", "1201240"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        
        # Actively poll for the game window to appear and get the button location
        self.log_run("RESTART", "Waiting for game to launch and 'game_start.png' to appear (timeout: 120s)...")
        start_time = time.time()
        game_start_box = None
        while time.time() - start_time < 120:
            try:
                # Use a temporary region for the whole screen to find the button
                full_screen_region = (0, 0, *pyautogui.size())
                found_box = pyautogui.locateOnScreen(self.TEMPLATES["game_start"], region=full_screen_region, confidence=self.TEMPLATE_CONFIDENCE_NORMAL)
                if found_box:
                    self.log_run("RESTART", f"'game_start.png' found after {time.time() - start_time:.1f}s. Game has launched.")
                    game_start_box = found_box
                    break
            except (pyscreeze.ImageNotFoundException, OSError, pyautogui.ImageNotFoundException):
                pass
            time.sleep(5) # Check every 5 seconds

        if not game_start_box:
            self.log_run("RESTART", "Game failed to start and show 'game_start.png' after 120s.")
            self.screenshot_and_exit("restart_launch_failed")

        # Re-discover the new window and return all necessary state
        self.log_run("RESTART", "Re-discovering game window...")
        self.region, self.win_id = self.get_game_region() # Update class attributes
        self.log_run("RESTART", f"New window ID: {self.win_id}, region: {self.region}")
        
        # Return the state AND the location of the button to avoid re-scanning
        return "GAME_STARTUP", game_start_box

    def try_state_recovery_or_exit(self, tag):
        """
        Attempt state recovery by scanning all templates.
        Returns recovered state if found, otherwise calls screenshot_and_exit.
        """
        print("[RECOVERY] Attempting to identify current screen state...")
        
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
                    self.TEMPLATES[template_key], 
                    region=self.region,
                    confidence=self.TEMPLATE_CONFIDENCE_NORMAL
                )
                if box:
                    detected_states.append((target_state, description, template_key))
                    print(f"[RECOVERY] Found: {description}")
            except Exception as e:
                print(f"[RECOVERY] Warning - error scanning {template_key}: {e}")
                # Continue to next template
        
        # Recovery decision logic
        if not detected_states:
            print("[RECOVERY] No known templates detected - NEW EDGE CASE")
            print("[RECOVERY] Attempting game restart as last resort...")
            # Take screenshot for debugging but don't exit
            suffix = f"_run{self.run_count}"
            path = f"screenshots/{tag}{suffix}_{int(time.time())}.png"
            pyautogui.screenshot(region=self.region).save(path)
            print(f"[RECOVERY] Screenshot saved: {path}")
            # Signal that a restart is needed
            return "RESTART_GAME"
            
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

    def simple_click(self, x, y, description="element"):
        """X11 click with immediate focus reclaim"""

        if self.USE_X11_DIRECT_CLICKS:
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
            success = self.send_x11_click_to_window(self.win_id, x, y)

            # Brief delay for X11 event processing, then reclaim focus
            if current_window and success:
                time.sleep(self.FOCUS_RESTORE_DELAY)  # Minimal delay for game event processing
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
            self.focus_game_window()
            pyautogui.click(x, y)
            print(f"[CLICK] ✅ {description} @ ({x},{y}) [pyautogui]")
            return True

    def send_x11_click_to_window(self, window_id, x, y):
        """Send click using X11 send_event (working method)"""
        disp = None
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
            return True

        except Exception as e:
            print(f"[X11] Click failed: {e}")
            return False
        finally:
            # Always close X11 connection to prevent resource leaks
            if disp:
                disp.close()

    def setup_wmctrl_always_on_top(self):
        """Set game window to be sticky and always on top using wmctrl"""
        try:
            subprocess.run(
                ["wmctrl", "-r", self.GAME_WINDOW_TITLE, "-b", "add,sticky,above"],
                check=True,
                stderr=subprocess.DEVNULL,
            )
            print("[WMCTRL] Game window set to sticky and always on top")
        except Exception as e:
            print(f"[WMCTRL] Failed to set window sticky/above: {e}")

    def focus_game_window(self):
        """Focus game window for reliable clicking (no logging during interference window)"""
        try:
            if self.USE_WMCTRL_ALWAYS_ON_TOP:
                # Just focus - no raise needed since wmctrl keeps window on top
                subprocess.run(
                    ["xdotool", "windowactivate", "--sync", self.win_id],
                    check=True,
                    stderr=subprocess.DEVNULL,
                )
            else:
                # Combined focus and raise in single xdotool call for better performance
                subprocess.run(
                    ["xdotool", "windowactivate", "--sync", self.win_id, "windowraise", self.win_id],
                    check=True,
                    stderr=subprocess.DEVNULL,
                )
        except Exception as e:
            print(f"[FOCUS] Failed to focus window: {e}")

    def poll_and_click(
        self,
        template_key,
        timeout=10,
        interval=0.5,
        description="element",
        center_click=False,
        only_poll=False, # New parameter
    ):
        """
        Poll for a template and click it when found.
        If only_poll is True, it will only poll and return True if found, without clicking.
        Returns True if found (and clicked, if not only_poll), False if timeout.
        """
        # Check if template file exists
        if not os.path.exists(self.TEMPLATES[template_key]):
            self.screenshot_and_exit(f"missing_{template_key}")

        # No noisy logging for quick, internal-only polls
        if not only_poll:
            print(f"[POLL] Looking for {description} (timeout: {timeout}s)")
        
        start_time = time.time()

        while time.time() - start_time < timeout:
            elapsed_time = time.time() - start_time

            try:
                template_box = pyautogui.locateOnScreen(
                    self.TEMPLATES[template_key],
                    region=self.region,
                    confidence=self.TEMPLATE_CONFIDENCE_NORMAL,
                )
                if template_box:
                    if only_poll:
                        # Don't log success for internal polls
                        return True
                    
                    print(f"[POLL] {description} found after {elapsed_time:.1f}s")
                    time.sleep(self.CLICK_SOAK_DELAY)

                    if center_click:
                        center_x = template_box.left + template_box.width // 2
                        center_y = template_box.top + template_box.height // 2
                        offset_x = random.randint(-template_box.width // self.CENTER_CLICK_OFFSET_FACTOR, template_box.width // self.CENTER_CLICK_OFFSET_FACTOR)
                        offset_y = random.randint(-template_box.height // self.CENTER_CLICK_OFFSET_FACTOR, template_box.height // self.CENTER_CLICK_OFFSET_FACTOR)
                        click_x, click_y = center_x + offset_x, center_y + offset_y
                    else:
                        click_x = random.randint(template_box.left, template_box.left + template_box.width - 1)
                        click_y = random.randint(template_box.top, template_box.top + template_box.height - 1)
                    
                    self.simple_click(click_x, click_y, description)
                    return True
            except (pyscreeze.ImageNotFoundException, OSError, pyautogui.ImageNotFoundException):
                pass
            
            # Use shorter sleep for internal, rapid-fire polling checks
            sleep_interval = 0.2 if only_poll else interval
            time.sleep(sleep_interval)

        if not only_poll:
            self.log_run("TIMEOUT", f"{description} not found after {timeout}s")
        
        return False

    def find_auto_icons(self):
        try:
            all_matches = list(
                pyautogui.locateAllOnScreen(
                    self.TEMPLATES["auto"], region=self.region, confidence=self.TEMPLATE_CONFIDENCE_NORMAL
                )
            )
            # Remove duplicate/overlapping detections
            return self.deduplicate_auto_icons(all_matches)
        except pyscreeze.ImageNotFoundException:
            return []

    def find_room_rules(self):
        """Find all room rules on screen"""
        try:
            return list(
                pyautogui.locateAllOnScreen(
                    self.TEMPLATES["room_rules_valid"],
                    region=self.region,
                    confidence=self.TEMPLATE_CONFIDENCE_LOOSE,
                )
            )
        except (
            pyscreeze.ImageNotFoundException,
            OSError,
            pyautogui.ImageNotFoundException,
        ):
            return []

    def match_autos_with_rules(self, autos, rules):
        """Match AUTO icons with Room Rules by proximity"""
        self.log_run("MATCH", "Grouping AUTO icons with Room Rules by proximity")
        valid_rooms = []

        for i, auto in enumerate(autos):
            auto_x, auto_y = auto.left + auto.width // 2, auto.top + auto.height // 2
            self.log_run("MATCH", f"AUTO {i + 1} at ({auto_x}, {auto_y})")

            closest_rule = None
            min_distance = float("inf")

            for j, rule in enumerate(rules):
                rule_x, rule_y = rule.left + rule.width // 2, rule.top + rule.height // 2

                if rule_y > auto_y:  # Rule must be below AUTO icon
                    distance = abs(rule_y - auto_y) + abs(rule_x - auto_x) * self.ROOM_MATCHING_WEIGHT_FACTOR
                    self.log_run(
                        "MATCH",
                        f"  Rule {j + 1} at ({rule_x}, {rule_y}), distance: {distance:.1f}",
                    )

                    if distance < min_distance and distance < self.MAX_RULE_DISTANCE:
                        min_distance = distance
                        closest_rule = rule
                        self.log_run(
                            "MATCH",
                            f"  → New closest rule (distance: {distance:.1f})"
                        )

            if closest_rule:
                rule_x, rule_y = (
                    closest_rule.left + closest_rule.width // 2,
                    closest_rule.top + closest_rule.height // 2,
                )
                self.log_run(
                    "MATCH",
                    f"✅ AUTO {i + 1} matched with Rule at ({rule_x}, {rule_y})",
                )
                valid_rooms.append((auto, closest_rule))
        return valid_rooms

    def deduplicate_auto_icons(self, matches):
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
                if distance < self.AUTO_ICON_MIN_DISTANCE:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_matches.append(match)
                print(f"[DEDUPE] Unique AUTO at ({center_x}, {center_y})")
            else:
                print(f"[DEDUPE] Filtered duplicate AUTO at ({center_x}, {center_y})")

        return unique_matches

    def find_and_click_ready_and_verify(self, timeout=30):
        self.log_run("ACTION", "Finding and clicking 'Ready' button...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                ready_box = pyautogui.locateOnScreen(
                    self.TEMPLATES["ready"],
                    region=self.region,
                    confidence=self.TEMPLATE_CONFIDENCE_NORMAL
                )
                
                if ready_box:
                    self.log_run("VERIFY", "Found 'Ready' button, waiting 1s to ensure it's interactive...")
                    time.sleep(1) # Wait for button to become interactive

                    # Click the button
                    self.simple_click(ready_box.left + ready_box.width // 2, ready_box.top + ready_box.height // 2, "ready button")

                    # Verify it disappeared
                    self.log_run("VERIFY", "Confirming 'Ready' button click...")
                    if self.poll_for_invisibility("ready", timeout=5, description="'Ready' button"):
                        self.log_run("VERIFY", "'Ready' button click successful.")
                        return True # Success
                    else:
                        self.log_run("ERROR", "'Ready' button still visible after click, assuming click failed. Retrying...")
                        # The loop will continue, trying the process again
            
            except (pyscreeze.ImageNotFoundException, OSError, pyautogui.ImageNotFoundException):
                elapsed = time.time() - start_time
                print(f"[POLL] Waiting for ready button... {elapsed:.1f}s")
                time.sleep(self.READY_POLL_INTERVAL)

        self.log_run("TIMEOUT", f"'Ready' button could not be successfully clicked after {timeout}s.")
        return False

    def poll_for_invisibility(self, template_key, timeout=10, interval=0.5, description="element to disappear"):
        print(f"[POLL] Waiting for {description} to disappear (timeout: {timeout}s)")
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # If template is still found, continue waiting
                if pyautogui.locateOnScreen(self.TEMPLATES[template_key], region=self.region, confidence=self.TEMPLATE_CONFIDENCE_NORMAL):
                    time.sleep(interval)
                else:
                    print(f"[POLL] {description} disappeared after {time.time() - start_time:.1f}s")
                    return True
            except (pyscreeze.ImageNotFoundException, OSError, pyautogui.ImageNotFoundException):
                # ImageNotFoundException means it's already gone, which is what we want
                print(f"[POLL] {description} disappeared after {time.time() - start_time:.1f}s (ImageNotFound)")
                return True
        
        print(f"[TIMEOUT] {description} did not disappear after {timeout}s")
        return False

    def run(self):
        game_start_box = None # Variable to hold pre-found button
        TEST_RESTART = len(sys.argv) > 1 and sys.argv[1] == "--test-restart"
        if TEST_RESTART:
            self.state, game_start_box = self.restart_game_and_navigate()
        else:
            self.get_game_region()
            self.state = "MENU"

        if self.USE_WMCTRL_ALWAYS_ON_TOP:
            self.setup_wmctrl_always_on_top()

        print(f"[SETUP] Bot ready. Game window region: {self.region}")
        print("[INFO] Press Ctrl+C to stop the bot")

        while True:
            self.log_run("STATE", f"Current state: {self.state}")

            if self.state == "RESTART_GAME":
                self.restart_attempts += 1
                if self.restart_attempts > self.MAX_RESTARTS:
                    self.log_run("FATAL", f"Maximum restart attempts ({self.MAX_RESTARTS}) reached. Exiting.")
                    self.screenshot_and_exit("max_restarts_reached")

                self.log_run("RESTART", f"Attempt #{self.restart_attempts} of {self.MAX_RESTARTS}...")
                self.state, game_start_box = self.restart_game_and_navigate()
                continue
            
            elif self.state == "GAME_STARTUP":
                self.log_run("STARTUP", "Navigating from game startup to co-op quest screen...")
                
                # Step 1: Click game start button
                self.log_run("STARTUP", "Step 1: Clicking game start button")
                if game_start_box:
                    self.log_run("STARTUP", "Pre-found game start button, clicking immediately.")
                    self.simple_click(
                        game_start_box.left + game_start_box.width // 2,
                        game_start_box.top + game_start_box.height // 2,
                        "game start button"
                    )
                    game_start_box = None # Reset after use
                else:
                    if not self.poll_and_click("game_start", timeout=self.GAME_START_BUTTON_TIMEOUT, description="game start button", center_click=True):
                        self.state = self.try_state_recovery_or_exit("timeout_game_start")
                        continue

                # Step 2: Close news popup
                self.log_run("STARTUP", "Step 2: Closing news popup")
                if not self.poll_and_click("close_news", timeout=30, description="close news popup"):
                    self.state = self.try_state_recovery_or_exit("timeout_close_news")
                    continue
                
                self.log_run("STARTUP", "Waiting 7s for screen to load...")
                time.sleep(7)
                
                # Step 3: Navigate to co-op (first button)
                self.log_run("STARTUP", "Step 3: Navigating to co-op (first button)")
                if not self.poll_and_click("coop_1", timeout=30, description="first coop navigation"):
                    self.state = self.try_state_recovery_or_exit("timeout_coop_1")
                    continue

                self.log_run("STARTUP", "Waiting 1s for coop screen to load...")
                time.sleep(1)
                
                # Step 4: Navigate to co-op (second button)
                self.log_run("STARTUP", "Step 4: Navigating to co-op (second button)")
                if not self.poll_and_click("coop_2", timeout=30, description="second coop navigation"):
                    self.state = self.try_state_recovery_or_exit("timeout_coop_2")
                    continue
                self.log_run("STARTUP", "Waiting 3s for screen to load...")
                time.sleep(3)
                
                self.log_run("STARTUP", "Navigation complete - transitioning to normal bot operation")
                self.state = "MENU"
                continue

            elif self.state == "MENU":
                self.log_run("STATE", f"MENU - Starting run #{self.run_count + 1}")

                # Step 1: Repeatedly click the main Co-op Quest banner until the specific quest is visible.
                self.log_run("STEP", "1 - Ensuring specific quest is visible")
                start_time = time.time()
                specific_quest_visible = False
                while time.time() - start_time < 20: # 20 second timeout for this sequence
                    # First, check if the target is already visible
                    if self.poll_and_click("open_coop_quest", timeout=0.2, only_poll=True):
                        self.log_run("INFO", "Specific quest is already visible.")
                        specific_quest_visible = True
                        break
                    
                    # If not, find and click the parent menu item
                    self.log_run("INFO", "Specific quest not visible, clicking main co-op menu...")
                    if not self.poll_and_click("coop_quest", timeout=1, description="coop quest menu"):
                        # If the main menu isn't even there, something is wrong.
                        self.log_run("ERROR", "Main co-op quest button not found.")
                        break # Break to fall through to recovery

                    time.sleep(1.0) # Wait a second for the UI to expand
                
                if not specific_quest_visible:
                    self.log_run("ERROR", "Specific quest did not appear after repeatedly clicking the main menu.")
                    self.state = self.try_state_recovery_or_exit("fail_open_coop_appear")
                    continue

                # Step 2: Click the specific quest and verify the transition.
                self.log_run("STEP", "2 - Clicking specific quest")
                if not self.poll_and_click("open_coop_quest", timeout=5, description="specific quest"):
                    self.state = self.try_state_recovery_or_exit("timeout_open_coop_quest")
                    continue

                # Step 3: Verify we have arrived at the room list screen by looking for the next button.
                self.log_run("VERIFY", "Confirming arrival at room list screen")
                if self.poll_and_click("enter_room_button", timeout=15, only_poll=True, description="enter room button"):
                    self.log_run("TRANSITION", "MENU → ENTER_ROOM_LIST")
                    self.state = "ENTER_ROOM_LIST"
                else:
                    self.log_run("ERROR", "Failed to find 'enter_room_button' after menu navigation.")
                    self.state = self.try_state_recovery_or_exit("fail_menu_navigation")
                
                continue

            elif self.state == "ENTER_ROOM_LIST":
                self.log_run("STATE", "ENTER_ROOM_LIST")
                # Step 3: Enter room list
                self.log_run("STEP", "3 - Entering room list")
                if not self.poll_and_click(
                    "enter_room_button",
                    timeout=10,
                    description="enter room list",
                    center_click=True,
                ):
                    self.state = self.try_state_recovery_or_exit("timeout_enter_room_button")
                    continue
                self.log_run("WAIT", "Waiting for room list to load...")
                # Poll for AUTO icons to appear (indicates room list loaded)
                start_time = time.time()
                while time.time() - start_time < self.ROOM_LOAD_TIMEOUT:
                    try:
                        test_autos = list(
                            pyautogui.locateAllOnScreen(
                                self.TEMPLATES["auto"],
                                region=self.region,
                                confidence=self.TEMPLATE_CONFIDENCE_NORMAL,
                            )
                        )
                        if len(test_autos) > 0:
                            elapsed = time.time() - start_time
                            self.log_run(
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
                    time.sleep(self.ROOM_LIST_POLL_INTERVAL)
                else:
                    self.log_run(
                        "TIMEOUT", "Room list didn't load - checking actual screen state"
                    )
                    # Use state recovery to determine where we actually are
                    self.state = self.try_state_recovery_or_exit("room_list_load_timeout")
                    continue

                # Additional delay to ensure room list is fully interactive
                self.log_run(
                    "WAIT",
                    f"Extra {self.ROOM_LOAD_DELAY}s delay for room list to become clickable...",
                )
                time.sleep(self.ROOM_LOAD_DELAY)
                self.log_run("TRANSITION", "ENTER_ROOM_LIST → SCAN_ROOMS")
                self.state = "SCAN_ROOMS"
                continue

            elif self.state == "SCAN_ROOMS":
                self.log_run("STATE", "SCAN_ROOMS")
                # Step 4: Find all AUTO icons and Room Rules, then match them
                self.log_run("STEP", "4 - Scanning for AUTO icons and Room Rules")
                autos = self.find_auto_icons()
                self.log_run("SCAN", f"Found {len(autos)} AUTO icons")

                rules = self.find_room_rules()
                self.log_run(
                    "SCAN",
                    f"Found {len(rules)} Room Rules" if rules else "No Room Rules found",
                )

                # Match AUTO icons with Room Rules
                valid_rooms = self.match_autos_with_rules(autos, rules)

                self.log_run(
                    "RESULT",
                    f"Found {len(autos)} AUTO icons, {len(rules)} Room Rules",
                )
                self.log_run(
                    "RESULT", f"Valid rooms = {len(valid_rooms)} (matched pairs)"
                )

                # Step 5a: if none valid → search again
                if not valid_rooms:
                    self.log_run("DECISION", "No valid rooms found - searching again")
                    if not self.poll_and_click(
                        "search_again",
                        timeout=10,
                        description="search again button",
                    ):
                        self.state = self.try_state_recovery_or_exit("timeout_search_again")
                        continue
                    
                    self.log_run(
                        "WAIT", f"{self.SEARCH_AGAIN_DELAY}s for new room list..."
                    )
                    time.sleep(self.SEARCH_AGAIN_DELAY)
                    self.log_run(
                        "TRANSITION", "SCAN_ROOMS → SCAN_ROOMS (search again)"
                    )
                    self.state = "SCAN_ROOMS"
                    continue

                # Step 5b: join first valid room
                self.log_run(
                    "DECISION",
                    f"Joining first valid room (1 of {len(valid_rooms)})",
                )
                auto, rule = valid_rooms[0]
                px = int((auto.left + rule.left + rule.width) // 2)
                py = int(auto.top + auto.height // 2)
                self.log_run(
                    "CALCULATE",
                    f"Target position: ({px}, {py}) - between AUTO and Rule",
                )

                self.simple_click(px, py, "room join")

                # Verify the result of the click instead of assuming success.
                self.log_run("VERIFY", "Polling for room join result...")
                outcome = "timeout"
                start_time = time.time()
                while time.time() - start_time < 15: # 15-second timeout
                    # Check for success state
                    if self.poll_and_click("ready", timeout=0.2, only_poll=True):
                        outcome = "success"
                        break
                    # Check for known failure states
                    if self.poll_and_click("closed_room_coop_quest_menu", timeout=0.2, only_poll=True):
                        outcome = "room_full"
                        break
                    if self.poll_and_click("close", timeout=0.2, only_poll=True):
                        outcome = "unavailable"
                        break
                    # If none of the above, keep polling
                    time.sleep(self.READY_POLL_INTERVAL)

                # Now, react based on the verified outcome
                if outcome == "success":
                    self.log_run("SUCCESS", "Room joined successfully.")
                    self.state = "READY"
                elif outcome == "room_full":
                    self.log_run("POPUP", "Room was full. Closing popup and restarting from menu.")
                    self.poll_and_click("closed_room_coop_quest_menu", timeout=5, description="room full popup")
                    time.sleep(self.POPUP_DISMISS_DELAY)
                    self.state = "MENU"
                elif outcome == "unavailable":
                    self.log_run("POPUP", "Room was unavailable. Closing popup and re-scanning.")
                    self.poll_and_click("close", timeout=5, description="popup close")
                    time.sleep(self.POPUP_DISMISS_DELAY)
                    self.state = "SCAN_ROOMS"
                else: # Timeout
                    self.log_run("TIMEOUT", "Join click had no effect or timed out. Re-scanning rooms.")
                    self.state = "SCAN_ROOMS" # Loop back to scan again
                
                continue

            elif self.state == "READY":
                self.log_run("STATE", "READY")
                # Step 6: Click ready button (lobby should be loaded now)
                self.log_run("STEP", "6 - Clicking ready button")

                # Custom polling for ready button that also checks for room full popup
                start_time = time.time()
                ready_clicked = False

                while time.time() - start_time < self.READY_BUTTON_TIMEOUT and not ready_clicked:
                    elapsed = time.time() - start_time

                    # Check for room full popup first
                    try:
                        room_full_box = pyautogui.locateOnScreen(
                            self.TEMPLATES["closed_room_coop_quest_menu"],
                            region=self.region,
                            confidence=self.TEMPLATE_CONFIDENCE_NORMAL,
                        )
                        if room_full_box:
                            print(
                                f"[RUN {self.run_count + 1}] [POPUP] Room full while waiting for ready - restarting from menu"
                            )
                            # Template delay OUTSIDE interference window
                            time.sleep(self.CLICK_SOAK_DELAY)
                            random_x = random.randint(
                                room_full_box.left,
                                room_full_box.left + room_full_box.width - 1,
                            )
                            random_y = random.randint(
                                room_full_box.top,
                                room_full_box.top + room_full_box.height - 1,
                            )
                            # Interference window: only focus restore delay (10ms)
                            self.simple_click(random_x, random_y, "room full popup")
                            time.sleep(self.POPUP_DISMISS_DELAY)
                            self.state = "MENU"
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
                            self.TEMPLATES["ready"],
                            region=self.region,
                            confidence=self.TEMPLATE_CONFIDENCE_NORMAL,
                        )
                        if ready_box:
                            self.log_run("ACTION", "Found 'Ready' button, waiting 2s before click...")
                            time.sleep(2.0) # Wait for button to be interactive

                            # Click the button
                            self.simple_click(
                                ready_box.left + ready_box.width // 2, 
                                ready_box.top + ready_box.height // 2, 
                                "ready button"
                            )

                            # Verify the click by polling for the button to disappear
                            if self.poll_for_invisibility("ready", timeout=5, description="'Ready' button to disappear"):
                                self.log_run("SUCCESS", "'Ready' button click verified.")
                                ready_clicked = True
                                break # Exit the while loop
                            else:
                                self.log_run("ERROR", "Ready button still visible after click. Retrying...")
                                # Let the loop continue to try clicking again
                    except (
                        pyscreeze.ImageNotFoundException,
                        OSError,
                        pyautogui.ImageNotFoundException,
                    ):
                        pass

                    print(f"[POLL] Waiting for ready button... {elapsed:.1f}s")
                    time.sleep(self.READY_POLL_INTERVAL)

                if self.state == "READY":  # Still in READY state, ready button was not clicked in the loop
                    if not ready_clicked:
                        # Timeout - attempt recovery
                        self.log_run("TIMEOUT", f"ready button not found after {self.READY_BUTTON_TIMEOUT}s - attempting recovery")
                        self.state = self.try_state_recovery_or_exit("timeout_ready")
                        continue

                    # Ready to start the quest, now check if it actually started
                    self.log_run("TRANSITION", "READY → CHECK_RUN_START")
                    self.state = "CHECK_RUN_START"
                continue
            
            elif self.state == "CHECK_RUN_START":
                self.log_run("STATE", "CHECK_RUN_START")
                self.log_run("STEP", "6.5 - Checking if run actually started...")

                # Poll for ingame auto button for 1.5 minutes
                start_time = time.time()
                run_started = False
                auto_found = False

                while time.time() - start_time < self.CHECK_RUN_START_TIMEOUT:
                    elapsed = time.time() - start_time

                    # Check for ingame auto off (should appear first) - loose threshold to catch it
                    try:
                        auto_off_box = pyautogui.locateOnScreen(
                            self.TEMPLATES["ingame_auto_off"],
                            region=self.region,
                            confidence=self.TEMPLATE_CONFIDENCE_LOOSE,
                        )
                        if auto_off_box:
                            print(
                                f"[RUN {self.run_count + 1}] [RUN] Found ingame auto OFF after {elapsed:.1f}s - waiting for game to be ready..."
                            )
                            # Wait for game to fully load OUTSIDE interference window
                            time.sleep(self.INGAME_AUTO_READY_DELAY)
                            # Template delay OUTSIDE interference window  
                            time.sleep(self.CLICK_SOAK_DELAY)
                            # Click near center of auto button (avoid edges for circular buttons)
                            center_x = auto_off_box.left + auto_off_box.width // 2
                            center_y = auto_off_box.top + auto_off_box.height // 2
                            # Small random offset from center (tighter for auto button reliability)
                            offset_x = random.randint(
                                -auto_off_box.width // self.AUTO_BUTTON_OFFSET_FACTOR,
                                auto_off_box.width // self.AUTO_BUTTON_OFFSET_FACTOR,
                            )
                            offset_y = random.randint(
                                -auto_off_box.height // self.AUTO_BUTTON_OFFSET_FACTOR,
                                auto_off_box.height // self.AUTO_BUTTON_OFFSET_FACTOR,
                            )
                            random_x = center_x + offset_x
                            random_y = center_y + offset_y
                            # Interference window: only focus restore delay (10ms)
                            self.simple_click(random_x, random_y, "ingame auto off")
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
                            self.TEMPLATES["ingame_auto_on"],
                            region=self.region,
                            confidence=self.TEMPLATE_CONFIDENCE_HIGH,
                        )
                        if auto_on_box:
                            print(
                                f"[RUN {self.run_count + 1}] [RUN] Found ingame auto ON after {elapsed:.1f}s - auto already enabled!"
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
                            self.TEMPLATES["closed_room_coop_quest_menu"],
                            region=self.region,
                            confidence=self.TEMPLATE_CONFIDENCE_NORMAL,
                        )
                        if room_closed_box:
                            print(
                                f"[RUN {self.run_count + 1}] [ERROR] Room closed by owner after {elapsed:.1f}s"
                            )
                            # Template delay OUTSIDE interference window
                            time.sleep(self.CLICK_SOAK_DELAY)
                            random_x = random.randint(
                                room_closed_box.left,
                                room_closed_box.left + room_closed_box.width - 1,
                            )
                            random_y = random.randint(
                                room_closed_box.top,
                                room_closed_box.top + room_closed_box.height - 1,
                            )
                            # Interference window: only focus restore delay (10ms)
                            self.simple_click(random_x, random_y, "room closed popup")
                            time.sleep(self.RETIREMENT_STEP_DELAY)
                            print(
                                f"[RUN {self.run_count + 1}] [RECOVERY] Room closed - restarting from menu"
                            )
                            self.state = "MENU"
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
                            self.TEMPLATES["close"],
                            region=self.region,
                            confidence=self.TEMPLATE_CONFIDENCE_NORMAL,
                        )
                        if close_btn_box:
                            print(
                                f"[RUN {self.run_count + 1}] [ERROR] Disconnect popup detected after {elapsed:.1f}s"
                            )
                            # Template delay OUTSIDE interference window
                            time.sleep(self.CLICK_SOAK_DELAY)
                            random_x = random.randint(
                                close_btn_box.left,
                                close_btn_box.left + close_btn_box.width - 1,
                            )
                            random_y = random.randint(
                                close_btn_box.top,
                                close_btn_box.top + close_btn_box.height - 1,
                            )
                            # Interference window: only focus restore delay (10ms)
                            self.simple_click(random_x, random_y, "disconnect popup close")
                            time.sleep(self.DISCONNECT_RECOVERY_DELAY)
                            print(
                                f"[RUN {self.run_count + 1}] [RECOVERY] Disconnect popup closed - restarting from menu"
                            )
                            self.state = "MENU"
                            break
                    except (
                        pyscreeze.ImageNotFoundException,
                        OSError,
                        pyautogui.ImageNotFoundException,
                    ):
                        pass

                    # Don't check for retire button here - it's always visible in lobby

                    print(
                        f"[RUN {self.run_count + 1}] [CHECK] Waiting for run to start... {elapsed:.1f}s"
                    )
                    time.sleep(self.RUN_START_POLL_INTERVAL)

                if run_started and auto_found:
                    print(
                        f"[RUN {self.run_count + 1}] [SUCCESS] Run confirmed started - proceeding to monitor quest"
                    )
                    print(f"[RUN {self.run_count + 1}] [TRANSITION] CHECK_RUN_START → RUNNING")
                    self.state = "RUNNING"
                elif self.state == "CHECK_RUN_START":  # Still in this state means timeout
                    self.log_run(
                        "TIMEOUT",
                        f"Run failed to start after {self.CHECK_RUN_START_TIMEOUT}s - trying to retire",
                    )
                    # Now try to find and click retire button
                    try:
                        retire_btn_box = pyautogui.locateOnScreen(
                            self.TEMPLATES["retire"],
                            region=self.region,
                            confidence=self.TEMPLATE_CONFIDENCE_NORMAL,
                        )
                        if retire_btn_box:
                            print(
                                f"[RUN {self.run_count + 1}] [RETIRE] Clicking retire button to leave room"
                            )
                            # Template delay OUTSIDE interference window
                            time.sleep(self.CLICK_SOAK_DELAY)
                            random_x = random.randint(
                                retire_btn_box.left,
                                retire_btn_box.left + retire_btn_box.width - 1,
                            )
                            random_y = random.randint(
                                retire_btn_box.top,
                                retire_btn_box.top + retire_btn_box.height - 1,
                            )
                            # Interference window: only focus restore delay (10ms)
                            self.simple_click(random_x, random_y, "retire button")
                            time.sleep(self.RETIREMENT_STEP_DELAY)

                            # Click okay to confirm retirement
                            self.log_run("RETIRE", "Looking for okay confirmation button...")
                            if not self.poll_and_click(
                                "okay",
                                timeout=10,
                                description="okay confirmation",
                            ):
                                self.state = self.try_state_recovery_or_exit("timeout_retire_okay")
                                break
                            
                            time.sleep(self.RETIREMENT_STEP_DELAY)

                            # Click final confirmation popup (closed_room_coop_quest_menu)
                            self.log_run("RETIRE", "Looking for final confirmation popup...")
                            if not self.poll_and_click(
                                "closed_room_coop_quest_menu",
                                timeout=10,
                                description="final retire confirmation",
                            ):
                                self.state = self.try_state_recovery_or_exit("timeout_final_retire_confirm")
                                break
                            
                            time.sleep(self.RETIREMENT_STEP_DELAY)

                            print(
                                f"[RUN {self.run_count + 1}] [RECOVERY] Retired from room - restarting from menu"
                            )
                            self.state = "MENU"
                        else:
                            print(
                                f"[RUN {self.run_count + 1}] [ERROR] No retire button found - game likely stuck on loading screen"
                            )
                            print(f"[RUN {self.run_count + 1}] [RESTART] Restarting game to recover from loading screen hang")
                            self.state = "RESTART_GAME"
                            
                    except (
                        pyscreeze.ImageNotFoundException,
                        OSError,
                        pyautogui.ImageNotFoundException,
                    ):
                        print(
                            f"[RUN {self.run_count + 1}] [ERROR] Retire button not found - attempting recovery"
                        )
                        self.state = self.try_state_recovery_or_exit("run_start_failed")
                        
                continue
            
            elif self.state == "RUNNING":
                self.log_run("STATE", "RUNNING")
                # Step 7: Poll for quest completion (tap1 button)
                self.log_run("STEP", "7 - Quest started - waiting for completion...")

                # Create a special polling function that doesn't click, just detects
                start = time.time()

                while time.time() - start < self.QUEST_MAX_TIME:
                    elapsed = time.time() - start

                    # Check if quest completed (tap1 button available)
                    try:
                        tap1_box = pyautogui.locateOnScreen(
                            self.TEMPLATES["tap1"],
                            region=self.region,
                            confidence=self.TEMPLATE_CONFIDENCE_NORMAL,
                        )
                        if tap1_box:
                            print(
                                f"[RUN {self.run_count + 1}] [QUEST] Quest completed after {elapsed:.1f}s"
                            )
                            print(f"[RUN {self.run_count + 1}] [TRANSITION] RUNNING → FINISH")
                            self.state = "FINISH"
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
                            self.TEMPLATES["close"],
                            region=self.region,
                            confidence=self.TEMPLATE_CONFIDENCE_NORMAL,
                        )
                        if close_btn_box:
                            print(
                                f"[RUN {self.run_count + 1}] [ERROR] Network disconnect during quest after {elapsed:.1f}s"
                            )
                            # Template delay OUTSIDE interference window
                            time.sleep(self.CLICK_SOAK_DELAY)
                            random_x = random.randint(
                                close_btn_box.left,
                                close_btn_box.left + close_btn_box.width - 1,
                            )
                            random_y = random.randint(
                                close_btn_box.top,
                                close_btn_box.top + close_btn_box.height - 1,
                            )
                            # Interference window: only focus restore delay (10ms)
                            self.simple_click(random_x, random_y, "network disconnect close")
                            print(
                                f"[RUN {self.run_count + 1}] [RECOVERY] Continuing quest (resume single player or restart)..."
                            )
                            # Continue in the same state - either continues as single player or we'll detect quest completion
                    except (
                        pyscreeze.ImageNotFoundException,
                        OSError,
                        pyautogui.ImageNotFoundException,
                    ):
                        pass

                    print(f"[RUN {self.run_count + 1}] [QUEST] Running... {elapsed:.0f}s")
                    time.sleep(self.QUEST_POLL_INTERVAL)
                else:
                    # Quest timeout - attempt recovery 
                    print(f"[RUN {self.run_count + 1}] [ERROR] Quest timeout after 5 minutes - attempting recovery")
                    self.state = self.try_state_recovery_or_exit("quest_timeout")
                    continue
                continue

            elif self.state == "FINISH":
                self.log_run("STATE", "FINISH")
                # Quest completion sequence: tap1 → tap2 → retry
                # Check which screen we're currently on to handle recovery scenarios
                
                # First, detect current screen state
                tap1_found = False
                tap2_found = False
                retry_found = False
                
                # Initialize variables to prevent scope issues
                tap1_box = None
                tap2_box = None
                retry_box = None
                
                try:
                    tap1_box = pyautogui.locateOnScreen(
                        self.TEMPLATES["tap1"],
                        region=self.region,
                        confidence=self.TEMPLATE_CONFIDENCE_NORMAL,
                    )
                    if tap1_box:
                        tap1_found = True
                except (pyscreeze.ImageNotFoundException, OSError, pyautogui.ImageNotFoundException):
                    pass
                
                try:
                    tap2_box = pyautogui.locateOnScreen(
                        self.TEMPLATES["tap2"],
                        region=self.region,
                        confidence=self.TEMPLATE_CONFIDENCE_NORMAL,
                    )
                    if tap2_box:
                        tap2_found = True
                except (pyscreeze.ImageNotFoundException, OSError, pyautogui.ImageNotFoundException):
                    pass
                    
                try:
                    retry_box = pyautogui.locateOnScreen(
                        self.TEMPLATES["retry"],
                        region=self.region,
                        confidence=self.TEMPLATE_CONFIDENCE_NORMAL,
                    )
                    if retry_box:
                        retry_found = True
                except (pyscreeze.ImageNotFoundException, OSError, pyautogui.ImageNotFoundException):
                    pass
                
                # Handle based on what we found
                if retry_found:
                    self.log_run("RECOVERY", "Found retry button - skipping directly to retry")
                    # Skip directly to step 10 (retry clicking)
                elif tap2_found:
                    self.log_run("RECOVERY", "Found tap2 - skipping to second tap")
                    # Skip to step 9 (tap2)
                elif tap1_found:
                    self.log_run("STEP", "8 - First tap to continue")
                    # Normal flow - start with tap1
                    start_time = time.time()
                    tap1_clicked = False
                    
                    while time.time() - start_time < self.TAP1_BUTTON_TIMEOUT and not tap1_clicked:
                        try:
                            tap1_box = pyautogui.locateOnScreen(
                                self.TEMPLATES["tap1"],
                                region=self.region,
                                confidence=self.TEMPLATE_CONFIDENCE_NORMAL,
                            )
                            if tap1_box:
                                # Template delay OUTSIDE interference window
                                time.sleep(self.CLICK_SOAK_DELAY)
                                # Click near center of tap1 button
                                center_x = tap1_box.left + tap1_box.width // 2
                                center_y = tap1_box.top + tap1_box.height // 2
                                offset_x = random.randint(
                                    -tap1_box.width // self.CENTER_CLICK_OFFSET_FACTOR,
                                    tap1_box.width // self.CENTER_CLICK_OFFSET_FACTOR,
                                )
                                offset_y = random.randint(
                                    -tap1_box.height // self.CENTER_CLICK_OFFSET_FACTOR,
                                    tap1_box.height // self.CENTER_CLICK_OFFSET_FACTOR,
                                )
                                random_x = center_x + offset_x
                                random_y = center_y + offset_y
                                # Interference window: only focus restore delay (10ms)
                                self.simple_click(random_x, random_y, "first tap button")
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
                        time.sleep(self.READY_POLL_INTERVAL)

                    if not tap1_clicked:
                        self.state = self.try_state_recovery_or_exit("timeout_tap1")
                        continue

                    self.log_run("WAIT", "Brief pause after first tap...")
                    time.sleep(self.TAP_PAUSE_DELAY)
                else:
                    # No tap buttons or retry found - go to recovery
                    self.state = self.try_state_recovery_or_exit("no_finish_buttons")
                    continue

                # Step 9: Handle tap2 (unless we're skipping to retry)
                if not retry_found:
                    self.log_run("STEP", "9 - Second tap to continue")
                    # Custom tap2 clicking with center focus
                    start_time = time.time()
                    tap2_clicked = False
                    while time.time() - start_time < self.TAP2_BUTTON_TIMEOUT and not tap2_clicked:
                        try:
                            tap2_box = pyautogui.locateOnScreen(
                                self.TEMPLATES["tap2"],
                                region=self.region,
                                confidence=self.TEMPLATE_CONFIDENCE_NORMAL,
                            )
                            if tap2_box:
                                # Template delay OUTSIDE interference window
                                time.sleep(self.CLICK_SOAK_DELAY)
                                # Click near center of tap2 button
                                center_x = tap2_box.left + tap2_box.width // 2
                                center_y = tap2_box.top + tap2_box.height // 2
                                offset_x = random.randint(
                                    -tap2_box.width // self.CENTER_CLICK_OFFSET_FACTOR,
                                    tap2_box.width // self.CENTER_CLICK_OFFSET_FACTOR,
                                )
                                offset_y = random.randint(
                                    -tap2_box.height // self.CENTER_CLICK_OFFSET_FACTOR,
                                    tap2_box.height // self.CENTER_CLICK_OFFSET_FACTOR,
                                )
                                random_x = center_x + offset_x
                                random_y = center_y + offset_y
                                # Interference window: only focus restore delay (10ms)
                                self.simple_click(random_x, random_y, "second tap button")
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
                        time.sleep(self.READY_POLL_INTERVAL)
                    
                    if not tap2_clicked:
                        self.state = self.try_state_recovery_or_exit("timeout_tap2")
                        continue
                    self.log_run(
                        "WAIT", "Waiting for screen transition after second tap..."
                    )
                    time.sleep(self.SCREEN_TRANSITION_DELAY)

                # Step 10: retry to loop back
                self.log_run("STEP", "10 - Clicking retry for next run")
                if not self.poll_and_click("retry", timeout=30, description="retry button"):
                    self.state = self.try_state_recovery_or_exit("timeout_retry")
                    continue
                
                self.log_run("WAIT", "Brief pause after retry...")
                time.sleep(self.RETRY_PAUSE_DELAY)

                print(f"✅ [RUN {self.run_count + 1}] Completed run #{self.run_count + 1}")
                self.run_count += 1
                self.restart_attempts = 0 # Reset restart counter on a successful run
                print(
                    f"[RUN {self.run_count}] [TRANSITION] FINISH → ENTER_ROOM_LIST"
                )
                time.sleep(self.FINAL_PAUSE_DELAY)
                self.state = "ENTER_ROOM_LIST"
                continue

            self.state = self.try_state_recovery_or_exit("unknown_state")

if __name__ == "__main__":
    bot = BBSBot()
    bot.run()