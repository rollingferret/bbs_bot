import os
import sys
import time
import subprocess
import random
import re
import logging
from datetime import datetime

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
    """Centralized configuration for the BBS Bot V3.1 'Diamond Polish'."""
    # Window settings
    RAW_TITLE = "Bleach: Brave Souls"
    GAME_WINDOW_TITLE = RAW_TITLE
    
    # 'Bankai' Speed Profile (V2 Parity)
    DELAY_COGNITIVE_LOAD = (0.1, 0.05)
    DELAY_SCREEN_TRANSITION = (0.5, 0.1)
    DELAY_POPUP_DISMISS = (1.5, 0.3)
    DELAY_TAP_PAUSE = (3.0, 0.4) # Mean 3s for tap transitions
    
    # State-specific timeouts
    TIMEOUT_STUCK = 300  
    TIMEOUT_QUEST_MAX = 300
    TIMEOUT_GAME_START = 120
    TIMEOUT_READY = 30
    TIMEOUT_RETRY = 45
    TIMEOUT_RUN_START = 300
    TIMEOUT_JOIN_VERIFY = 15
    TIMEOUT_LOBBY_EXPAND = 20
    TIMEOUT_TAP_VERIFY = 15
    
    # Wait Delays (Means)
    WAIT_ROOM_LOAD = 0.1
    WAIT_SEARCH_AGAIN = 0.5
    WAIT_RETIRE_STEP = 1.0
    WAIT_DISCONNECT_RECOVERY = 2.0
    WAIT_INGAME_AUTO_READY = 1.0
    
    # Behavioral Settings
    FATIGUE_INCREASE_RATE = 0.0  # Constant speed for event grinding
    MAX_FATIGUE_MODIFIER = 1.0
    
    # Distraction settings
    DISTRACTION_CHANCE = (15, 25) # Every 15-25 runs
    DISTRACTION_DURATION = (120, 480) # 2-8 minutes
    
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
    TEMPLATE_CONFIDENCE_NORMAL = 0.8
    TEMPLATE_CONFIDENCE_HIGH = 0.95
    TEMPLATE_CONFIDENCE_LOOSE = 0.7

def human_delay(mu, sigma_factor=0.3):
    """Gaussian-randomized sleep duration."""
    sigma = mu * sigma_factor
    delay = random.gauss(mu, sigma)
    delay = max(delay, mu * 0.1) # Absolute floor
    time.sleep(delay)

class GameWindowNotFoundError(Exception):
    pass

class BBSBot:
    def __init__(self, config=BotConfiguration()):
        self.config = config
        self.state = "RECOVERY" 
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
        
        logger.info("BBS Bot V3.1 'Wide-Jitter' Initialized.")

    # --- VISION WRAPPERS (Integrity Fix) ---

    def find_image(self, template_key, confidence=None, region=None):
        """Safe wrapper to catch ImageNotFoundException."""
        conf = confidence or self.config.TEMPLATE_CONFIDENCE_NORMAL
        reg = region or self.region
        try:
            return pyautogui.locateOnScreen(self.config.TEMPLATES[template_key], region=reg, confidence=conf)
        except (pyscreeze.ImageNotFoundException, pyautogui.ImageNotFoundException):
            return None
        except Exception as e:
            logger.error(f"Vision error ({template_key}): {e}")
            return None

    def find_all_images(self, template_key, confidence=None, region=None):
        """Safe wrapper for locateAllOnScreen."""
        conf = confidence or self.config.TEMPLATE_CONFIDENCE_NORMAL
        reg = region or self.region
        try:
            return list(pyautogui.locateAllOnScreen(self.config.TEMPLATES[template_key], region=reg, confidence=conf))
        except (pyscreeze.ImageNotFoundException, pyautogui.ImageNotFoundException):
            return []
        except Exception as e:
            logger.error(f"Vision error (all {template_key}): {e}")
            return []

    # --- BEHAVIORAL UTILITIES ---

    def fatigue_delay(self, mu, sigma_factor=0.3):
        human_delay(mu * self.fatigue_modifier, sigma_factor)

    def apply_cognitive_load(self):
        mu, sigma_factor = self.config.DELAY_COGNITIVE_LOAD
        self.fatigue_delay(mu, sigma_factor)

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
        """Match AUTO icons with Room Rules by proximity."""
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

    # --- X11 & WINDOW MANAGEMENT ---

    def ensure_window_ready(self):
        try:
            self.get_game_region()
            self.setup_window_properties()
        except GameWindowNotFoundError:
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
            except Exception: pass

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

    def smart_click(self, box, description="element", is_overlay=False):
        """Gaussian-weighted click with Sloppy/Precise logic."""
        self.apply_cognitive_load()
        
        mu_x = box.left + box.width / 2
        mu_y = box.top + box.height / 2
        
        if is_overlay:
            # Sloppy Overlay Jitter (200px spread)
            sigma_x = sigma_y = 100
        else:
            # Sloppy Button Jitter (sigma = width/4, ~70% coverage)
            sigma_x = box.width / 4
            sigma_y = box.height / 4
        
        click_x = int(random.gauss(mu_x, sigma_x))
        click_y = int(random.gauss(mu_y, sigma_y))
        
        # Clamp only for buttons; overlays can be anywhere on screen
        if not is_overlay:
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

    # --- RECOVERY ---

    def recover_game(self):
        logger.warning("RECOVERY: Restarting game process...")
        try:
            subprocess.run(["pkill", "-f", "BleachBraveSouls.exe"], check=False)
        except: pass
        time.sleep(5)
        subprocess.Popen(["steam", "-applaunch", "1201240"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        start_wait = time.time()
        while time.time() - start_wait < 120:
            if self.find_image("game_start"):
                logger.info("Game started successfully.")
                break
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

    def handle_menu(self):
        """Main menu navigation (MENU)."""
        # 1. Check if specific quest is already visible
        qbox = self.find_image("open_coop_quest")
        if qbox:
            self.smart_click(qbox, "specific quest")
            self.transition_to("ENTER_ROOM_LIST")
            return

        # 2. Otherwise click banner to expand
        box = self.find_image("coop_quest")
        if box:
            self.smart_click(box, "coop menu banner")
            self.fatigue_delay(0.5) # Fast polling for animation

        if time.time() - self.last_state_change_time > self.config.TIMEOUT_LOBBY_EXPAND:
            self.transition_to("RECOVERY")

    def handle_enter_room_list(self):
        """Enter room list (ENTER_ROOM_LIST)."""
        ebit = self.find_image("enter_room_button")
        if ebit:
            self.smart_click(ebit, "enter room list")
            self.fatigue_delay(0.5)
            self.transition_to("SCAN_ROOMS")
            return
        
        # If already at SCAN_ROOMS
        if self.find_image("search_again"):
            self.transition_to("SCAN_ROOMS")
            return

        if time.time() - self.last_state_change_time > 10:
            self.transition_to("RECOVERY")

    def handle_scan_rooms(self):
        """Scan and join rooms (SCAN_ROOMS)."""
        # V2 Performance: First Match, Immediate Click
        autos = self.find_all_images("auto")
        if autos:
            rules = self.find_all_images("room_rules_valid", confidence=0.7)
            valid_rooms = self.match_autos_with_rules(self.deduplicate_auto_icons(autos), rules)
            
            if valid_rooms:
                auto, rule = valid_rooms[0]
                logger.info("Joining room instantly.")
                px = int((auto.left + rule.left + rule.width) // 2)
                py = int(auto.top + auto.height // 2)
                self.smart_click(pyscreeze.Box(px-5, py-5, 10, 10), "join room")
                self.transition_to("READY")
                return

        sabox = self.find_image("search_again")
        if sabox:
            self.smart_click(sabox, "search again")
            self.fatigue_delay(0.5)
            return

        if time.time() - self.last_state_change_time > 15:
            self.transition_to("RECOVERY")

    def handle_ready(self):
        """Wait for ready and start (READY)."""
        full_box = self.find_image("closed_room_coop_quest_menu")
        if full_box:
            self.smart_click(full_box, "close full popup")
            self.transition_to("MENU")
            return

        rbox = self.find_image("ready")
        if rbox:
            if self.smart_click(rbox, "ready button"):
                self.transition_to("CHECK_RUN_START")
                return

        if time.time() - self.last_state_change_time > self.config.TIMEOUT_READY:
            self.transition_to("RECOVERY")

    def handle_check_run_start(self):
        """Poll for battle start (CHECK_RUN_START)."""
        # Success Indicators
        if self.find_image("ingame_auto_on", confidence=0.95) or self.find_image("ingame_auto_off", confidence=0.7):
            logger.info("Run started.")
            self.transition_to("RUNNING")
            return

        # Sad Paths
        full_box = self.find_image("closed_room_coop_quest_menu")
        if full_box:
            self.smart_click(full_box, "close closure popup")
            self.transition_to("MENU")
            return

        close_box = self.find_image("close")
        if close_box:
            self.smart_click(close_box, "close disconnect")
            self.transition_to("MENU")
            return

        if time.time() - self.last_state_change_time > self.config.TIMEOUT_RUN_START:
            logger.error("Run start timeout. Retiring.")
            retire_box = self.find_image("retire")
            if retire_box:
                self.smart_click(retire_box, "retire button")
                time.sleep(1)
                okay_box = self.find_image("okay")
                if okay_box: self.smart_click(okay_box, "confirm retire")
            self.transition_to("MENU")

    def handle_running(self):
        """Monitor battle progress (RUNNING)."""
        if self.config.MANAGE_INGAME_AUTO:
            offbox = self.find_image("ingame_auto_off", confidence=0.7)
            if offbox:
                self.smart_click(offbox, "enable auto")

        tbox = self.find_image("tap1")
        if tbox:
            logger.info("Quest completed.")
            self.transition_to("FINISH")
            return
        
        cbox = self.find_image("close")
        if cbox:
            self.smart_click(cbox, "close disconnect")

        if time.time() - self.last_state_change_time > self.config.TIMEOUT_QUEST_MAX:
            self.transition_to("RECOVERY")

    def handle_finish(self):
        """Tap through rewards to retry (FINISH)."""
        rt = self.find_image("retry")
        if rt:
            self.smart_click(rt, "retry quest")
            self.run_count += 1
            logger.info(f"Run {self.run_count} completed.")
            if self.run_count >= self.next_distraction_run:
                self.transition_to("DISTRACTION")
            else:
                self.transition_to("ENTER_ROOM_LIST")
            return

        t2 = self.find_image("tap2")
        if t2:
            self.smart_click(t2, "reward tap 2", is_overlay=True)
            return

        t1 = self.find_image("tap1")
        if t1:
            self.smart_click(t1, "reward tap 1", is_overlay=True)
            return

        if time.time() - self.last_state_change_time > self.config.TIMEOUT_TAP_VERIFY:
            self.transition_to("RECOVERY")

    def handle_game_startup(self):
        """Navigate from splash screens (GAME_STARTUP)."""
        for key in ["game_start", "close_news", "coop_1", "coop_2"]:
            box = self.find_image(key)
            if box:
                self.smart_click(box, f"startup {key}")
        
        if self.find_image("coop_quest"):
            self.transition_to("MENU")

    def handle_recovery(self):
        """Identify state or restart (RECOVERY)."""
        cbox = self.find_image("close")
        if cbox:
            self.smart_click(cbox, "error popup close")
            self.transition_to("MENU")
            return
        
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_STUCK:
            self.recover_game()
        else:
            recovery_templates = [
                ("RUNNING", "ingame_auto_on"),
                ("RUNNING", "ingame_auto_off"),
                ("CHECK_RUN_START", "retire"),
                ("FINISH", "tap1"),
                ("FINISH", "tap2"),
                ("FINISH", "retry"),
                ("READY", "ready"),
                ("SCAN_ROOMS", "search_again"),
                ("ENTER_ROOM_LIST", "enter_room_button"),
                ("MENU", "open_coop_quest"),
                ("MENU", "coop_quest"),
                ("GAME_STARTUP", "game_start")
            ]
            for state, template in recovery_templates:
                if self.find_image(template):
                    self.transition_to(state)
                    return
            time.sleep(2)

    def run(self):
        test_restart = "--test-restart" in sys.argv
        if "--debug-screenshots" in sys.argv:
            self.config.TAKE_DEBUG_SCREENSHOTS = True

        try:
            if test_restart: self.recover_game()
            else: self.get_game_region(); self.setup_window_properties()
        except GameWindowNotFoundError: self.recover_game()

        logger.info(f"Starting bot in state: {self.state}")
        while True:
            self.ensure_window_ready()
            self.check_session_limit()
            
            if self.state == "MENU": self.handle_menu()
            elif self.state == "ENTER_ROOM_LIST": self.handle_enter_room_list()
            elif self.state == "SCAN_ROOMS": self.handle_scan_rooms()
            elif self.state == "READY": self.handle_ready()
            elif self.state == "CHECK_RUN_START": self.handle_check_run_start()
            elif self.state == "RUNNING": self.handle_running()
            elif self.state == "FINISH": self.handle_finish()
            elif self.state == "DISTRACTION": self.handle_distraction()
            elif self.state == "RECOVERY": self.handle_recovery()
            elif self.state == "GAME_STARTUP": self.handle_game_startup()
            
            time.sleep(0.1)

if __name__ == "__main__":
    bot = BBSBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        sys.exit(1)
