import os
import sys
import time
import subprocess
import random
import re
import logging
from datetime import datetime, timedelta

import pyautogui
import pyscreeze
from Xlib import X, display, protocol

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("v3_behavior.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class BotConfiguration:
    """Centralized configuration for the BBS Bot V3."""
    # Window settings
    RAW_TITLE = "Bleach: Brave Souls"
    GAME_WINDOW_TITLE = RAW_TITLE
    
    # Gaussian delay defaults (mu, sigma_factor)
    DELAY_COGNITIVE_LOAD = (1.5, 0.3)
    DELAY_SCREEN_TRANSITION = (2.0, 0.3)
    DELAY_POPUP_DISMISS = (3.0, 0.4)
    DELAY_TAP_PAUSE = (5.0, 0.5)
    
    # State-specific timeouts
    TIMEOUT_STUCK = 300  
    TIMEOUT_QUEST_MAX = 300
    TIMEOUT_GAME_START = 120
    TIMEOUT_READY = 30
    TIMEOUT_RETRY = 45
    TIMEOUT_TAP_BUTTON = 20
    TIMEOUT_RETIRE_POLL = 15
    TIMEOUT_RUN_START = 300
    
    # Fatigue settings
    FATIGUE_INCREASE_RATE = 0.005  # 0.5% increase in mu per run
    MAX_FATIGUE_MODIFIER = 1.5      # Max 50% slower
    
    # Distraction settings
    DISTRACTION_CHANCE = (15, 25) # Every 15-25 runs
    DISTRACTION_DURATION = (120, 480) # 2-8 minutes in seconds
    
    # Session limits
    SESSION_MAX_HOURS = 12
    
    # Templates
    TEMPLATES = {
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
    
    # Technical toggles
    USE_WMCTRL_ALWAYS_ON_TOP = True
    USE_X11_DIRECT_CLICKS = True
    MANAGE_INGAME_AUTO = True
    TAKE_DEBUG_SCREENSHOTS = False
    TEMPLATE_CONFIDENCE_NORMAL = 0.8
    TEMPLATE_CONFIDENCE_HIGH = 0.95
    TEMPLATE_CONFIDENCE_LOOSE = 0.7

def human_delay(mu, sigma_factor=0.3):
    """Gaussian-randomized sleep duration."""
    sigma = mu * sigma_factor
    delay = random.gauss(mu, sigma)
    # Clamp delay to be at least a reasonable minimum
    delay = max(delay, mu * 0.5)
    time.sleep(delay)

class GameWindowNotFoundError(Exception):
    pass

class BBSBot:
    def __init__(self, config=BotConfiguration()):
        self.config = config
        self.state = "RECOVERY" # Start in RECOVERY to instantly identify current screen
        self.prev_state = None
        self.run_count = 0
        self.start_time = time.time()
        self.last_state_change_time = time.time()
        self.next_distraction_run = random.randint(*self.config.DISTRACTION_CHANCE)
        
        self.region = None
        self.win_id = None
        self.fatigue_modifier = 1.0
        
        os.makedirs("screenshots", exist_ok=True)
        pyautogui.FAILSAFE = False
        
        logger.info("BBS Bot V3 'Integrity' Initialized.")

    # --- BEHAVIORAL UTILITIES ---

    def fatigue_delay(self, mu, sigma_factor=0.3):
        """Gaussian delay with fatigue modifier applied to mu."""
        human_delay(mu * self.fatigue_modifier, sigma_factor)

    def apply_cognitive_load(self):
        """Simulate human reaction time before an action."""
        mu, sigma_factor = self.config.DELAY_COGNITIVE_LOAD
        self.fatigue_delay(mu, sigma_factor)

    def update_fatigue(self):
        """Increase fatigue modifier over time."""
        self.fatigue_modifier = min(
            self.config.MAX_FATIGUE_MODIFIER,
            1.0 + (self.run_count * self.config.FATIGUE_INCREASE_RATE)
        )

    def check_session_limit(self):
        """Terminate if active time exceeds limit."""
        elapsed_hours = (time.time() - self.start_time) / 3600
        if elapsed_hours >= self.config.SESSION_MAX_HOURS:
            logger.warning(f"Session limit reached ({self.config.SESSION_MAX_HOURS}h). Terminating.")
            subprocess.run(["pkill", "-f", "BleachBraveSouls.exe"], check=False)
            sys.exit(0)

    def take_debug_screenshot(self, tag):
        """Captures a screenshot for debugging purposes if enabled."""
        if not self.config.TAKE_DEBUG_SCREENSHOTS:
            return
        path = f"screenshots/{tag}_run{self.run_count}_{int(time.time())}.png"
        try:
            pyautogui.screenshot(region=self.region).save(path)
            logger.debug(f"Debug screenshot saved: {path}")
        except Exception as e:
            logger.error(f"Failed to save debug screenshot: {e}")

    def deduplicate_auto_icons(self, matches):
        """Remove overlapping AUTO icon detections."""
        if not matches: return []
        unique = []
        for match in matches:
            cx, cy = match.left + match.width // 2, match.top + match.height // 2
            if not any(((cx-(u.left+u.width//2))**2 + (cy-(u.top+u.height//2))**2)**0.5 < 60 for u in unique):
                unique.append(match)
        return unique

    def match_autos_with_rules(self, autos, rules):
        """Match AUTO icons with Room Rules by proximity (weighted)."""
        valid_rooms = []
        for auto in autos:
            ax, ay = auto.left + auto.width // 2, auto.top + auto.height // 2
            closest_rule = None
            min_dist = float("inf")
            for rule in rules:
                rx, ry = rule.left + rule.width // 2, rule.top + rule.height // 2
                if ry > ay: # Rule below AUTO
                    dist = abs(ry - ay) + abs(rx - ax) * 0.1
                    if dist < min_dist and dist < 100:
                        min_dist = dist
                        closest_rule = rule
            if closest_rule:
                valid_rooms.append((auto, closest_rule))
        return valid_rooms

    def transition_to(self, new_state):
        if self.state != new_state:
            logger.info(f"TRANSITION: {self.state} -> {new_state}")
            self.prev_state = self.state
            self.state = new_state
            self.last_state_change_time = time.time()

    # --- X11 & WINDOW MANAGEMENT (Preserved from V2) ---

    def ensure_window_ready(self):
        """Helper to re-discover window and set always-on-top property."""
        try:
            self.get_game_region()
            self.setup_window_properties()
        except GameWindowNotFoundError:
            logger.warning("Window lost, attempting recovery...")
            if time.time() - self.last_state_change_time > self.config.TIMEOUT_STUCK:
                self.recover_game()

    def get_game_region(self):
        try:
            wids = subprocess.check_output(
                ["xdotool", "search", "--onlyvisible", "--name", f"^{self.config.GAME_WINDOW_TITLE}$"],
                text=True
            ).strip().split()

            for wid in wids:
                if not wid: continue
                try:
                    pid = subprocess.check_output(["xdotool", "getwindowpid", wid], text=True).strip()
                    cmdline = subprocess.check_output(["ps", "-p", pid, "-o", "cmd", "--no-headers"], text=True).strip()

                    if "BleachBraveSouls.exe" in cmdline or "BLEACH Brave Souls" in cmdline:
                        geo_lines = subprocess.check_output(["xdotool", "getwindowgeometry", "--shell", wid], text=True).splitlines()
                        geo = {k: int(v) for k, v in (line.split("=") for line in geo_lines if "=" in line)}
                        self.win_id = wid
                        break
                except Exception: continue
            else:
                raise GameWindowNotFoundError("Game process not found.")

            sw, sh = pyautogui.size()
            x, y, w, h = geo["X"], geo["Y"], geo["WIDTH"], geo["HEIGHT"]
            self.region = (max(0, x), max(0, y), min(w, sw-x), min(h, sh-y))
            return self.region
        except Exception as e:
            raise GameWindowNotFoundError(e)

    def setup_window_properties(self):
        if self.config.USE_WMCTRL_ALWAYS_ON_TOP:
            try:
                subprocess.run(["wmctrl", "-r", self.config.GAME_WINDOW_TITLE, "-b", "add,sticky,above"], check=True)
            except Exception as e:
                logger.warning(f"WMCTRL failed: {e}")

    def send_x11_click(self, x, y):
        disp = None
        try:
            disp = display.Display()
            window = disp.create_resource_object("window", int(self.win_id))
            geom = window.get_geometry()
            rel_x, rel_y = x - geom.x, y - geom.y

            event_details = {
                "root": disp.screen().root, "window": window, "same_screen": 1,
                "child": X.NONE, "root_x": x, "root_y": y, "event_x": rel_x, "event_y": rel_y,
                "state": 0, "detail": 1, "time": int(time.time() * 1000) & 0xFFFFFFFF,
            }

            window.send_event(protocol.event.ButtonPress(**event_details), propagate=True)
            window.send_event(protocol.event.ButtonRelease(**event_details), propagate=True)
            disp.flush()
            disp.sync()
            return True
        except Exception as e:
            logger.error(f"X11 click failed: {e}")
            return False
        finally:
            if disp: disp.close()

    def smart_click(self, box, description="element"):
        """Gaussian-weighted click centered on the box midpoint."""
        self.apply_cognitive_load()
        
        # Center-weighted Gaussian coordinates
        mu_x = box.left + box.width / 2
        mu_y = box.top + box.height / 2
        # Sigma is 1/6th of width/height (approx 99.7% within bounds)
        sigma_x = box.width / 6
        sigma_y = box.height / 6
        
        click_x = int(random.gauss(mu_x, sigma_x))
        click_y = int(random.gauss(mu_y, sigma_y))
        
        # Clamp to box bounds
        click_x = max(box.left, min(click_x, box.left + box.width - 1))
        click_y = max(box.top, min(click_y, box.top + box.height - 1))

        current_window = None
        try:
            current_window = subprocess.check_output(["xdotool", "getactivewindow"], text=True).strip()
        except: pass

        success = self.send_x11_click(click_x, click_y)

        if success and current_window:
            time.sleep(0.01) # 10ms focus restore
            try:
                subprocess.run(["xdotool", "windowactivate", "--sync", current_window], check=False)
            except: pass

        logger.info(f"CLICK: {description} at ({click_x}, {click_y})")
        return success

    # --- RECOVERY (Preserved from V2) ---

    def recover_game(self):
        logger.warning("RECOVERY: Restarting game process...")
        subprocess.run(["pkill", "-f", "BleachBraveSouls.exe"], check=False)
        time.sleep(5)
        subprocess.Popen(["steam", "-applaunch", "1201240"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Wait for start screen
        start_wait = time.time()
        while time.time() - start_wait < 120:
            try:
                if pyautogui.locateOnScreen(self.config.TEMPLATES["game_start"], confidence=0.8):
                    logger.info("Game started successfully.")
                    break
            except: pass
            time.sleep(5)
        
        self.get_game_region()
        self.setup_window_properties()
        self.transition_to("GAME_STARTUP")

    # --- STATE HANDLERS ---

    def handle_distraction(self):
        duration = random.randint(*self.config.DISTRACTION_DURATION)
        logger.info(f"DISTRACTION: Taking a coffee break for {duration}s...")
        time.sleep(duration)
        self.next_distraction_run = self.run_count + random.randint(*self.config.DISTRACTION_CHANCE)
        self.transition_to("RECOVERY")

    def handle_lobby(self):
        """Main menu navigation (LOBBY)."""
        self.take_debug_screenshot("lobby")
        start_time = time.time()
        while time.time() - start_time < 20:
            # Check if specific quest is already visible
            try:
                if pyautogui.locateOnScreen(self.config.TEMPLATES["open_coop_quest"], region=self.region, confidence=0.8):
                    logger.info("Specific quest is visible.")
                    qbox = pyautogui.locateOnScreen(self.config.TEMPLATES["open_coop_quest"], region=self.region, confidence=0.8)
                    if qbox:
                        self.smart_click(qbox, "specific quest")
                        self.transition_to("ROOM_SELECTION")
                        return
            except: pass

            # Otherwise click the banner to expand
            try:
                box = pyautogui.locateOnScreen(self.config.TEMPLATES["coop_quest"], region=self.region, confidence=0.8)
                if box:
                    self.smart_click(box, "coop menu banner")
                    self.fatigue_delay(1.5)
            except: pass
            time.sleep(0.5)
        
        self.transition_to("RECOVERY")

    def handle_room_selection(self):
        """Scan and join rooms."""
        self.take_debug_screenshot("room_selection")
        try:
            # Enter room list if button visible
            ebit = pyautogui.locateOnScreen(self.config.TEMPLATES["enter_room_button"], region=self.region, confidence=0.8)
            if ebit:
                self.smart_click(ebit, "enter room list")
                self.fatigue_delay(2.0)
                return

            # Scan for AUTO and rules using robust V2 methods
            autos = self.deduplicate_auto_icons(list(pyautogui.locateAllOnScreen(self.config.TEMPLATES["auto"], region=self.region, confidence=0.8)))
            rules = list(pyautogui.locateAllOnScreen(self.config.TEMPLATES["room_rules_valid"], region=self.region, confidence=0.7))
            
            valid_rooms = self.match_autos_with_rules(autos, rules)
            
            if valid_rooms:
                auto, rule = valid_rooms[0]
                logger.info(f"Found {len(valid_rooms)} valid rooms. Joining first.")
                
                # Calculate target position between AUTO and Rule (V2 logic)
                px = int((auto.left + rule.left + rule.width) // 2)
                py = int(auto.top + auto.height // 2)
                click_box = pyscreeze.Box(px-5, py-5, 10, 10)
                
                if self.smart_click(click_box, "join room"):
                    # Robust verification (V2 logic)
                    start_time = time.time()
                    while time.time() - start_time < 15:
                        if pyautogui.locateOnScreen(self.config.TEMPLATES["ready"], region=self.region, confidence=0.8):
                            self.transition_to("COOP_LOBBY")
                            return
                        
                        # Check for popups
                        for popup_key, next_state in [("closed_room_coop_quest_menu", "LOBBY"), ("close", "ROOM_SELECTION")]:
                            pbox = pyautogui.locateOnScreen(self.config.TEMPLATES[popup_key], region=self.region, confidence=0.8)
                            if pbox:
                                logger.info(f"Join failed: {popup_key} detected.")
                                self.smart_click(pbox, "close popup")
                                self.fatigue_delay(1.5)
                                self.transition_to(next_state)
                                return
                        time.sleep(0.5)
            
            # If nothing found, search again
            sabox = pyautogui.locateOnScreen(self.config.TEMPLATES["search_again"], region=self.region, confidence=0.8)
            if sabox:
                self.smart_click(sabox, "search again")
                self.fatigue_delay(1.5)
        except Exception as e:
            logger.error(f"Error in room selection: {e}")

    def handle_coop_lobby(self):
        """Wait for ready and start."""
        try:
            # V2 Logic: Check for room full popup while in lobby
            pbox = pyautogui.locateOnScreen(self.config.TEMPLATES["closed_room_coop_quest_menu"], region=self.region, confidence=0.8)
            if pbox:
                logger.info("Room full popup in lobby.")
                self.smart_click(pbox, "close full popup")
                self.transition_to("LOBBY")
                return

            rbox = pyautogui.locateOnScreen(self.config.TEMPLATES["ready"], region=self.region, confidence=0.8)
            if rbox:
                if self.smart_click(rbox, "ready button"):
                    self.transition_to("WAIT_FOR_START")
                    return
        except: pass
        
        # Check if stuck in lobby
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_READY:
            self.transition_to("RECOVERY")

    def handle_wait_for_start(self):
        """Poll for battle start (V2 CHECK_RUN_START logic)."""
        start_time = self.last_state_change_time
        elapsed = time.time() - start_time
        
        if elapsed > self.config.TIMEOUT_RUN_START:
            logger.error("Run start timeout. Attempting to retire.")
            # Simplified retire logic for V3
            try:
                retire_box = pyautogui.locateOnScreen(self.config.TEMPLATES["retire"], region=self.region, confidence=0.8)
                if retire_box:
                    self.smart_click(retire_box, "retire button")
                    self.fatigue_delay(1.5)
                    # Poll for okay button
                    okay_box = pyautogui.locateOnScreen(self.config.TEMPLATES["okay"], region=self.region, confidence=0.8)
                    if okay_box: self.smart_click(okay_box, "confirm retire")
            except: pass
            self.transition_to("RECOVERY")
            return

        # Check for start indicators
        try:
            # Auto ON or OFF indicates we are in-game
            if pyautogui.locateOnScreen(self.config.TEMPLATES["ingame_auto_on"], region=self.region, confidence=0.9):
                logger.info("Run started (auto on).")
                self.transition_to("IN_BATTLE")
                return
            
            offbox = pyautogui.locateOnScreen(self.config.TEMPLATES["ingame_auto_off"], region=self.region, confidence=0.7)
            if offbox:
                logger.info("Run started (auto off). Enabling.")
                self.smart_click(offbox, "enable auto")
                self.transition_to("IN_BATTLE")
                return

            # Check for room closed or disconnect
            for key in ["closed_room_coop_quest_menu", "close"]:
                pbox = pyautogui.locateOnScreen(self.config.TEMPLATES[key], region=self.region, confidence=0.8)
                if pbox:
                    logger.warning(f"Run start failed: {key} detected.")
                    self.smart_click(pbox, "close popup")
                    self.transition_to("LOBBY")
                    return
        except: pass
        time.sleep(1)

    def handle_in_battle(self):
        """Monitor battle progress."""
        # Check for completion
        try:
            tbox = pyautogui.locateOnScreen(self.config.TEMPLATES["tap1"], region=self.region, confidence=0.8)
            if tbox:
                logger.info("Quest completed.")
                self.transition_to("REWARDS")
                return
            
            # Check for network disconnect during quest
            cbox = pyautogui.locateOnScreen(self.config.TEMPLATES["close"], region=self.region, confidence=0.8)
            if cbox:
                logger.warning("Disconnect during battle. Resuming.")
                self.smart_click(cbox, "close disconnect")
        except: pass

        if time.time() - self.last_state_change_time > self.config.TIMEOUT_QUEST_MAX:
            logger.error("Quest max time reached.")
            self.transition_to("RECOVERY")
        
        time.sleep(5)

    def handle_rewards(self):
        """Tap through rewards to retry (V2 FINISH logic)."""
        self.take_debug_screenshot("rewards")
        try:
            # Look for retry first (recovery scenario)
            rt = pyautogui.locateOnScreen(self.config.TEMPLATES["retry"], region=self.region, confidence=0.8)
            if rt:
                self.smart_click(rt, "retry quest")
                self.run_count += 1
                self.update_fatigue()
                logger.info(f"Run {self.run_count} completed. Fatigue: {self.fatigue_modifier:.2f}")
                
                if self.run_count >= self.next_distraction_run:
                    self.transition_to("DISTRACTION")
                else:
                    self.transition_to("COOP_LOBBY")
                return

            # Look for tap1
            t1 = pyautogui.locateOnScreen(self.config.TEMPLATES["tap1"], region=self.region, confidence=0.8)
            if t1:
                self.smart_click(t1, "reward tap 1")
                self.fatigue_delay(2.0)
                return
            
            # Look for tap2
            t2 = pyautogui.locateOnScreen(self.config.TEMPLATES["tap2"], region=self.region, confidence=0.8)
            if t2:
                self.smart_click(t2, "reward tap 2")
                self.fatigue_delay(2.0)
                return
        except: pass

        if time.time() - self.last_state_change_time > self.config.TIMEOUT_TAP_BUTTON:
            self.transition_to("RECOVERY")
        time.sleep(1)

    def handle_game_startup(self):
        """Navigate from splash screens."""
        try:
            for key in ["game_start", "close_news", "coop_1", "coop_2"]:
                box = pyautogui.locateOnScreen(self.config.TEMPLATES[key], region=self.region, confidence=0.8)
                if box:
                    self.smart_click(box, f"startup {key}")
                    self.fatigue_delay(2.0)
            
            # If we see the coop_quest banner, we're in LOBBY
            if pyautogui.locateOnScreen(self.config.TEMPLATES["coop_quest"], region=self.region, confidence=0.8):
                self.transition_to("LOBBY")
        except: pass

    def handle_recovery(self):
        """Identify state or restart."""
        # Check for common popups
        try:
            cbox = pyautogui.locateOnScreen(self.config.TEMPLATES["close"], region=self.region, confidence=0.8)
            if cbox:
                self.smart_click(cbox, "error popup close")
                self.transition_to("LOBBY")
                return
        except: pass
        
        # If stuck for too long, full restart
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_STUCK:
            self.recover_game()
        else:
            # Try to identify current screen
            recovery_templates = [
                ("LOBBY", "coop_quest"), 
                ("COOP_LOBBY", "ready"), 
                ("WAIT_FOR_START", "retire"), # Retire is visible in lobby/loading
                ("IN_BATTLE", "ingame_auto_on"),
                ("GAME_STARTUP", "game_start"),
                ("REWARDS", "tap1"),
                ("REWARDS", "tap2"),
                ("REWARDS", "retry"),
                ("ROOM_SELECTION", "enter_room_button"),
                ("ROOM_SELECTION", "search_again")
            ]
            for state, template in recovery_templates:
                try:
                    if pyautogui.locateOnScreen(self.config.TEMPLATES[template], region=self.region, confidence=0.8):
                        self.transition_to(state)
                        return
                except: pass
            time.sleep(5)

    def run(self):
        # Handle command line arguments
        test_restart = "--test-restart" in sys.argv
        if "--debug-screenshots" in sys.argv:
            self.config.TAKE_DEBUG_SCREENSHOTS = True
            logger.info("Debug screenshots enabled.")

        try:
            if test_restart:
                self.recover_game()
            else:
                self.get_game_region()
                self.setup_window_properties()
        except GameWindowNotFoundError:
            self.recover_game()

        logger.info(f"Starting bot in state: {self.state}")
        while True:
            self.ensure_window_ready()
            self.check_session_limit()
            
            if self.state == "LOBBY": self.handle_lobby()
            elif self.state == "ROOM_SELECTION": self.handle_room_selection()
            elif self.state == "COOP_LOBBY": self.handle_coop_lobby()
            elif self.state == "WAIT_FOR_START": self.handle_wait_for_start()
            elif self.state == "IN_BATTLE": self.handle_in_battle()
            elif self.state == "REWARDS": self.handle_rewards()
            elif self.state == "DISTRACTION": self.handle_distraction()
            elif self.state == "RECOVERY": self.handle_recovery()
            elif self.state == "GAME_STARTUP": self.handle_game_startup()
            
            time.sleep(0.5)

if __name__ == "__main__":
    bot = BBSBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        sys.exit(1)
