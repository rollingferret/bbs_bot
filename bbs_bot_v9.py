import argparse
import logging
import math
import os
import random
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import mss  # type: ignore
import pyautogui  # type: ignore
import pyscreeze  # type: ignore
from PIL import Image
from Xlib import display, X, protocol  # type: ignore

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("v9_behavior.log", mode="w"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


@dataclass
class BotConfiguration:
    """Centralized configuration for the BBS Bot V9.0 'Sentinel'."""

    RAW_TITLE: str = "Bleach: Brave Souls"
    CIRCADIAN_PROFILES: Optional[Dict[str, Dict[str, Any]]] = None

    # Timing Profiles
    DELAY_COGNITIVE: Tuple[float, float] = (0.78, 0.05)
    DELAY_SNIPE: float = 0.20
    DELAY_POPUP: float = 1.5
    DELAY_NEWS: float = 0.4
    DELAY_READY: float = 0.90
    WAIT_ROOM_LOAD: float = 1.0
    WAIT_SEARCH_AGAIN: float = 1.5
    WAIT_LOBBY_READY: float = 0.3
    WAIT_REFOCUS: float = 0.02
    WAIT_REFRESH_COOLDOWN: float = 2.5
    DELAY_POST_POPUP: float = 0.3
    WAIT_STABILIZE_ANIMATION: float = 1.2
    SAFETY_FLOOR_FACTOR: float = 0.05
    WAIT_RESTART: float = 5.0

    # Timeouts
    TIMEOUT_STUCK: float = 300
    TIMEOUT_QUEST_MAX: float = 600
    TIMEOUT_GAME_START: float = 120
    TIMEOUT_READY: float = 30
    TIMEOUT_RUN_START: float = 180
    TIMEOUT_TAP_VERIFY: float = 25.0
    TIMEOUT_LOBBY_EXPAND: float = 20.0
    TIMEOUT_LOBBY_JOIN: float = 10.0
    TIMEOUT_ROOM_LIST_LOAD: float = 5.0
    TIMEOUT_SCAN_IDLE: float = 20.0
    TIMEOUT_VERIFY_UI: float = 2.0

    # Vision
    CONF_NORMAL: float = 0.80
    CONF_HIGH: float = 0.90
    CONF_READY: float = 0.95
    CONF_STARTUP: float = 0.85
    CONF_LOOSE: float = 0.68
    CONF_POPUP: float = 0.85
    CONF_VERIFY_ACTION: float = 0.80

    # Logic
    AUTO_ICON_DEDUPE_DIST: int = 60
    ROOM_MATCH_WEIGHT: float = 0.1
    MAX_RULE_DISTANCE: int = 110
    SNATCH_BOX_OFFSET: Tuple[int, int] = (20, 10)
    SNATCH_BOX_DIM: Tuple[int, int] = (40, 20)

    # All-Auto Strategy
    ALLOW_ALL_AUTO_ROOMS: bool = False
    ALLOW_ALL_AUTO_OFFSET_X: int = -200

    # Operational Safety
    MAX_CONSECUTIVE_RECOVERIES: int = 3
    SESSION_MAX_HOURS: int = 16
    POLL_MAIN_LOOP: float = 0.1
    POLL_UI_VERIFY: float = 0.05
    POLL_POPUP: float = 0.5
    POLL_PROPERTY_SYNC: float = 5.0
    POLL_RUNNING: float = 0.5

    CASUAL_LINGER_RUNS: Tuple[int, int] = (8, 16)
    FATIGUE_BASE: float = 1.0
    FATIGUE_AMPLITUDE: float = 0.15
    FATIGUE_PERIOD: int = 1800
    DISTRACTION_DURATION: Tuple[int, int] = (120, 480)

    # Flags
    TAKE_DEBUG_SCREENSHOTS: bool = False
    ALIGNMENT_MODE: bool = False
    MANAGE_INGAME_AUTO: bool = True
    USE_WMCTRL_ALWAYS_ON_TOP: bool = True

    TEMPLATES: Optional[Dict[str, str]] = field(default=None)

    def __post_init__(self):
        self.CIRCADIAN_PROFILES = {
            "SHIKAI_MAX": {
                "DELAY_COGNITIVE": (0.78, 0.05), "DELAY_SNIPE": 0.20, "DELAY_POPUP": 1.5,
                "DELAY_READY": 0.90, "WAIT_ROOM_LOAD": 1.0, "WAIT_SEARCH_AGAIN": 1.5,
                "WAIT_LOBBY_READY": 0.3, "WAIT_POST_RETRY": 1.0, "WAIT_REFOCUS": 0.02,
                "WAIT_REFRESH_COOLDOWN": 2.0, "WAIT_STABILIZE_ANIMATION": 0.8,
                "TIMEOUT_VERIFY_UI": 0.8, "DURATION_MINS": (45, 90),
            },
            "SHIKAI_NORMAL": {
                "DELAY_COGNITIVE": (0.95, 0.10), "DELAY_SNIPE": 0.40, "DELAY_POPUP": 2.0,
                "DELAY_READY": 1.10, "WAIT_ROOM_LOAD": 1.2, "WAIT_SEARCH_AGAIN": 2.5,
                "WAIT_LOBBY_READY": 0.6, "WAIT_POST_RETRY": 2.0, "WAIT_REFOCUS": 0.05,
                "WAIT_REFRESH_COOLDOWN": 2.5, "WAIT_STABILIZE_ANIMATION": 1.2,
                "TIMEOUT_VERIFY_UI": 1.4, "DURATION_MINS": (60, 180),
            },
        }
        self.TEMPLATES = {
            "game_start": "images/game_start.png", "close_news": "images/close_news.png",
            "coop_1": "images/coop-1.png", "coop_2": "images/coop-2.png",
            "coop_quest": "images/coop_quest.png", "open_coop_quest": "images/open_coop_quest.png",
            "enter_room_button": "images/join_coop_quest.png", "search_again": "images/search_again.png",
            "auto": "images/auto_icon.png", "ingame_auto_off": "images/ingame_auto_off.png",
            "ingame_auto_on": "images/ingame_auto_on.png", "room_rules_valid": "images/room_rules_valid.png",
            "close": "images/close.png", "ready": "images/ready_button.png", "retire": "images/retire.png",
            "okay": "images/okay.png", "closed_room_coop_quest_menu": "images/closed_room_coop_quest_menu.png",
            "tap1": "images/tap1.png", "tap2": "images/tap2.png", "retry": "images/retry.png",
            "room_not_met": "images/room_not_met.png", "unavailable_close": "images/unavailable_close.png",
            "disconnect_retry": "images/disconnect_rerty.png",
        }
        self._apply_profile("SHIKAI_MAX")

    def _apply_profile(self, profile_name: str):
        if self.CIRCADIAN_PROFILES:
            s = self.CIRCADIAN_PROFILES[profile_name]
            self.DELAY_COGNITIVE = s["DELAY_COGNITIVE"]
            self.DELAY_SNIPE = s["DELAY_SNIPE"]
            self.DELAY_POPUP = s["DELAY_POPUP"]
            self.DELAY_READY = s["DELAY_READY"]
            self.WAIT_ROOM_LOAD = s["WAIT_ROOM_LOAD"]
            self.WAIT_SEARCH_AGAIN = s["WAIT_SEARCH_AGAIN"]
            self.WAIT_LOBBY_READY = s["WAIT_LOBBY_READY"]
            self.WAIT_POST_RETRY = 1.0
            self.WAIT_REFOCUS = s.get("WAIT_REFOCUS", 0.02)
            self.WAIT_REFRESH_COOLDOWN = s["WAIT_REFRESH_COOLDOWN"]
            self.WAIT_STABILIZE_ANIMATION = s["WAIT_STABILIZE_ANIMATION"]
            self.TIMEOUT_VERIFY_UI = s["TIMEOUT_VERIFY_UI"]


def human_delay(profile, fatigue=1.0, safety_factor=0.05):
    if isinstance(profile, (float, int)): mu, sigma = float(profile), float(profile) * 0.1
    else: mu, sigma = profile
    delay = random.gauss(mu * fatigue, sigma)
    time.sleep(max(delay, (mu * fatigue) * safety_factor))

class GameWindowNotFoundError(Exception): pass

class BBSBot:
    """BBS Sentinel V9.37 - V6 Speed + V2 Accuracy."""
    RECOVERY_MAP = [
        ("READY", "ready"), ("RUNNING", "ingame_auto_on"), ("RUNNING", "ingame_auto_off"),
        ("CHECK_RUN_START", "retire"), ("FINISH", "tap1"), ("FINISH", "tap2"), ("FINISH", "retry"),
        ("SCAN_ROOMS", "search_again"), ("JOIN_PENDING", "ready"), ("ENTER_ROOM_LIST", "enter_room_button"),
        ("MENU", "open_coop_quest"), ("MENU", "coop_quest"), ("MENU", "coop_1"), ("MENU", "coop_2"),
        ("GAME_STARTUP", "game_start"), ("MENU", "closed_room_coop_quest_menu"),
        ("SCAN_ROOMS", "close"), ("SCAN_ROOMS", "unavailable_close"), ("GAME_STARTUP", "close_news"),
    ]

    def __init__(self, config=BotConfiguration()):
        self.config = config
        pyautogui.FAILSAFE = False
        assert self.config.CIRCADIAN_PROFILES is not None
        self.active_profile = "SHIKAI_MAX"
        self.next_profile_swap = time.time() + random.randint(*self.config.CIRCADIAN_PROFILES[self.active_profile]["DURATION_MINS"]) * 60
        self.state, self.run_count, self.start_time = "RECOVERY", 0, time.time()
        self.next_distraction_run = 9999
        self.fatigue_start_time = self.last_state_change_time = self.quest_watchdog = time.time()
        self.win_id = self.region = self.snapshot = self.expected_okay_context = None
        self.consecutive_recovery_count = self.search_start_time = 0
        self._force_refresh = False
        self.fatigue_modifier, self._last_popup_check = 1.0, 0.0
        self._last_property_sync = self._last_id_search = 0.0
        self._run_counted = False
        self.disconnect_retry_count = 0
        self.handlers = {
            "MENU": self.handle_menu, "ENTER_ROOM_LIST": self.handle_enter_room_list,
            "SCAN_ROOMS": self.handle_scan_rooms, "JOIN_PENDING": self.handle_join_pending,
            "READY": self.handle_ready, "CHECK_RUN_START": self.handle_check_run_start,
            "RUNNING": self.handle_running, "FINISH": self.handle_finish,
            "DISTRACTION": self.handle_distraction, "GAME_STARTUP": self.handle_game_startup,
            "RECOVERY": self.handle_recovery,
        }
        self.cached_templates = {}
        self._load_templates()
        self.check_dependencies()
        try:
            self.disp = display.Display()
            self.sct = mss.mss()
        except Exception:
            logger.error("FATAL: X11/MSS Init Error"); sys.exit(1)
        if not os.path.exists("alignment_audit"): os.makedirs("alignment_audit")
        else:
            for f in os.listdir("alignment_audit"):
                try: os.remove(os.path.join("alignment_audit", f))
                except Exception: pass
        if not os.path.exists("error_snapshots"): os.makedirs("error_snapshots")
        logger.info("BBS Sentinel V9.37 Initialized.")

    def _load_templates(self):
        if not self.config.TEMPLATES: return
        for k, v in self.config.TEMPLATES.items():
            try: self.cached_templates[k] = Image.open(v).convert("RGB")
            except Exception: logger.error(f"Template error: {k}")

    def check_dependencies(self):
        for cmd in ["xdotool", "wmctrl", "pkill", "ps"]:
            if subprocess.run(["which", cmd], capture_output=True).returncode != 0:
                logger.error(f"FATAL: Missing {cmd}"); sys.exit(1)

    def save_debug_screenshot(self, name):
        if not self.snapshot: return
        try:
            ts = int(time.time())
            fname = f"alignment_audit/{name}_{ts}.png"
            self.snapshot.save(fname)
            files = sorted([os.path.join("alignment_audit", f) for f in os.listdir("alignment_audit")], key=os.path.getmtime)
            if len(files) > 100:
                for f in files[:-100]: os.remove(f)
        except Exception: pass

    def save_error_snapshot(self, reason):
        if not self.snapshot: return
        try:
            ts = int(time.time())
            fname = f"error_snapshots/error_{reason}_{ts}.png"
            self.snapshot.save(fname)
            logger.error(f"Error snapshot saved: {fname}")
        except Exception: pass

    def get_template_confidence(self, key):
        c = {
            "open_coop_quest": 0.90, "coop_quest": 0.90, "coop_1": 0.85, 
            "ready": 0.95, "disconnect_retry": 0.90, "unavailable_close": 0.95, 
            "close_news": 0.92, "close": 0.92,
            "ingame_auto_on": 0.95, "ingame_auto_off": 0.95,
            "tap1": 0.90, "tap2": 0.90, "retry": 0.90
        }
        return c.get(key, self.config.CONF_NORMAL)

    def find_image(self, key, confidence=None, region=None, haystack=None):
        t = self.cached_templates.get(key)
        conf = confidence or self.get_template_confidence(key)
        if not t or not self.region: return None
        try:
            if haystack:
                res = pyautogui.locate(t, haystack, confidence=conf)
                if res: return pyscreeze.Box(res.left + self.region[0], res.top + self.region[1], res.width, res.height)
                return None
            template_path = self.config.TEMPLATES.get(key, "")
            if not template_path: return None
            return pyautogui.locateOnScreen(template_path, region=self.region, confidence=conf)
        except Exception: return None

    def find_stable_image(self, key, confidence=None, frames=3):
        for _ in range(frames):
            res = self.find_image(key, confidence)
            if not res: return None
            time.sleep(self.config.POLL_UI_VERIFY)
        return res

    def find_all(self, key, confidence=0.8, haystack=None):
        t = self.cached_templates.get(key)
        if not t or not self.region: return []
        try:
            if haystack:
                res = list(pyautogui.locateAll(t, haystack, confidence=confidence))
                return [pyscreeze.Box(r.left + self.region[0], r.top + self.region[1], r.width, r.height) for r in res]
            template_path = self.config.TEMPLATES.get(key, "") if self.config.TEMPLATES else ""
            if template_path: return list(pyautogui.locateAllOnScreen(template_path, region=self.region, confidence=confidence))
            return []
        except Exception: return []

    def current_phase(self):
        p = {"GAME_STARTUP": "STARTUP", "MENU": "MENU", "ENTER_ROOM_LIST": "JOIN", "SCAN_ROOMS": "SEARCH",
             "JOIN_PENDING": "PENDING", "READY": "LOBBY", "CHECK_RUN_START": "PENDING", "RUNNING": "LIVE",
             "FINISH": "FINISH", "RECOVERY": "RECOVERY"}
        return p.get(self.state, "UNKNOWN")

    def can_click(self, key, expected_context=None):
        phase = self.current_phase()
        expected = expected_context or getattr(self, "expected_okay_context", None)
        if key == "okay": return expected == "RETIRE_CONFIRM" or self.state in {"SCAN_ROOMS", "RECOVERY", "READY", "CHECK_RUN_START"}
        allowed = {
            "STARTUP": {"close_news", "game_start", "coop_1", "coop_2", "close"},
            "MENU": {"coop_quest", "open_coop_quest", "close_news", "close", "coop_1", "coop_2"},
            "JOIN": {"enter_room_button", "close", "unavailable_close", "closed_room_coop_quest_menu"},
            "SEARCH": {"search_again", "auto", "closed_room_coop_quest_menu", "unavailable_close", "close", "okay", "disconnect_retry", "room_not_met"},
            "LOBBY": {"ready", "closed_room_coop_quest_menu", "unavailable_close", "close", "disconnect_retry", "room_not_met"},
            "PENDING": {"ready", "closed_room_coop_quest_menu", "unavailable_close", "close", "disconnect_retry", "retire", "room_not_met"},
            "LIVE": {"ingame_auto_off", "retire", "disconnect_retry", "closed_room_coop_quest_menu", "unavailable_close", "close", "room_not_met"},
            "FINISH": {"tap1", "tap2", "retry", "disconnect_retry", "close", "closed_room_coop_quest_menu", "unavailable_close", "room_not_met"},
            "RECOVERY": {"closed_room_coop_quest_menu", "unavailable_close", "close", "disconnect_retry", "close_news", "okay", "coop_quest", "open_coop_quest", "coop_1", "coop_2", "room_not_met"},
        }
        return key in allowed.get(phase, set())

    def smart_click(self, target, description, verify_key=None, target_state=None, wait_for_appearance=False, custom_delay=None, confidence=None, haystack=None, verify_timeout=None, expected_context=None):
        if isinstance(target, str) and not self.can_click(target, expected_context=expected_context):
            logger.error(f"SAFETY BLOCK: {target} in {self.current_phase()} phase"); time.sleep(0.5); return False
        human_delay(custom_delay or self.config.DELAY_COGNITIVE, self.fatigue_modifier, self.config.SAFETY_FLOOR_FACTOR)
        conf = confidence or self.get_template_confidence(target if isinstance(target, str) else "")
        box = self.find_image(target, confidence=conf, haystack=haystack) if isinstance(target, str) else target
        if not box: return verify_key == target and not wait_for_appearance
        mu_x, mu_y = box.left + box.width / 2, box.top + box.height / 2
        click_x, click_y = int(random.gauss(mu_x, box.width / 10)), int(random.gauss(mu_y, box.height / 10))
        if self.region:
            click_x = max(self.region[0], min(click_x, self.region[0] + self.region[2] - 1))
            click_y = max(self.region[1], min(click_y, self.region[1] + self.region[3] - 1))
        if self.config.ALIGNMENT_MODE: self.save_debug_screenshot(f"pre_click_{description.replace(' ', '_')}")
        cur_focus = None
        try: cur_focus = subprocess.check_output(["xdotool", "getactivewindow"], text=True, stderr=subprocess.DEVNULL).strip()
        except Exception: pass
        success = self._send_x11_click(click_x, click_y)
        logger.info(f"CLICK [Run:{self.run_count}]: {description} at ({click_x}, {click_y})")
        if success and cur_focus:
            time.sleep(self.config.WAIT_REFOCUS)
            try:
                subprocess.run(["xdotool", "windowfocus", cur_focus, "windowactivate", "--sync", cur_focus, "windowraise", cur_focus], check=False, stderr=subprocess.DEVNULL)
            except Exception: pass
        if success and verify_key:
            start, limit = time.time(), (verify_timeout or self.config.TIMEOUT_VERIFY_UI)
            while time.time() - start < limit:
                found = self.find_image(verify_key, confidence=self.config.CONF_VERIFY_ACTION)
                if (wait_for_appearance and found) or (not wait_for_appearance and not found):
                    if target_state: self.transition_to(target_state)
                    return True
                time.sleep(self.config.POLL_UI_VERIFY)
            return False
        if success and target_state: self.transition_to(target_state)
        return success

    def _send_x11_click(self, x, y):
        """Mechanically identical to V6: Silent Xlib injection."""
        try:
            if not self.win_id or not self.region: return False
            window = self.disp.create_resource_object("window", int(self.win_id))
            # V2 Accuracy: Use physical screen region offset to bypass OS titlebar scaling
            rel_x, rel_y = x - self.region[0], y - self.region[1]
            details = {
                "root": self.disp.screen().root,
                "window": window,
                "same_screen": 1,
                "child": X.NONE,
                "root_x": x,
                "root_y": y,
                "event_x": rel_x,
                "event_y": rel_y,
                "state": 0,
                "detail": 1,
                "time": int(time.time() * 1000) & 0xFFFFFFFF,
            }
            window.send_event(protocol.event.ButtonPress(**details), propagate=True)
            window.send_event(protocol.event.ButtonRelease(**details), propagate=True)
            self.disp.flush()
            self.disp.sync()
            return True
        except Exception: return False

    def is_safe_room_okay_context(self, haystack=None):
        if self.state not in {"SCAN_ROOMS", "RECOVERY", "MENU", "READY", "CHECK_RUN_START"}: return False
        for a in ["ingame_auto_on", "ingame_auto_off", "retire"]:
            if self.find_image(a, haystack=haystack): return False
        return True

    def handle_global_popups(self, haystack=None):
        now = time.time()
        if now - self._last_popup_check < self.config.POLL_POPUP: return False
        self._last_popup_check = now
        
        # V9.34 Surgical Block: Only block the generic modal 'close' button.
        # We MUST allow 'unavailable_close' and others even in ENTER_ROOM_LIST 
        # because those are real errors.
        blocked = ["close"] if self.state in ["ENTER_ROOM_LIST"] else []
        
        for key in ["disconnect_retry", "closed_room_coop_quest_menu", "room_not_met", "unavailable_close", "close_news", "okay", "close"]:
            if key in blocked: continue
            if key == "okay" and not self.is_safe_room_okay_context(haystack): continue
            
            conf = self.get_template_confidence(key)

            if self.find_image(key, confidence=conf, haystack=haystack):
                logger.warning(f"GLOBAL: Popup '{key}' confirmed")
                if key == "close_news": time.sleep(self.config.DELAY_NEWS)
                if key == "disconnect_retry": self.disconnect_retry_count += 1
                if not self.smart_click(key, f"dismiss {key}", verify_key=key, haystack=haystack):
                    return False
                
                # V9.48: Realignment with V6 State Truth
                if key in ["room_not_met", "unavailable_close", "close"]:
                    self.search_start_time = time.time()
                    if self.state in ["SCAN_ROOMS", "JOIN_PENDING", "READY", "CHECK_RUN_START", "FINISH"]: 
                        self.transition_to("SCAN_ROOMS"); self._force_refresh = True
                    return True
                
                if key in ["closed_room_coop_quest_menu", "okay"]:
                    self.transition_to("MENU")
                    return True
                
                if key == "disconnect_retry":
                    self.transition_to("RECOVERY")
                    return True

                if self.state not in ["GAME_STARTUP", "RUNNING", "FINISH", "CHECK_RUN_START", "RECOVERY"]:
                    self.transition_to("MENU")
                return True
        return False

    def handle_menu(self, haystack=None):
        if self.find_image("open_coop_quest", haystack=haystack):
            return self.smart_click("open_coop_quest", "specific quest", "enter_room_button", target_state="ENTER_ROOM_LIST", wait_for_appearance=True, haystack=haystack)
        if self.find_image("coop_quest", haystack=haystack):
            return self.smart_click("coop_quest", "expand menu", "open_coop_quest", wait_for_appearance=True, haystack=haystack)
        for key in ["coop_1", "coop_2"]:
            if self.find_image(key, haystack=haystack): return self.smart_click(key, f"navigate {key}", haystack=haystack)
        if self.find_image("enter_room_button", haystack=haystack): self.transition_to("ENTER_ROOM_LIST"); return True
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_LOBBY_EXPAND: self.transition_to("RECOVERY"); return True
        return False

    def handle_enter_room_list(self, haystack=None):
        # Case A: We are on the 'Select a Room Type' menu
        if self.find_image("enter_room_button", haystack=haystack):
            # V9.36: Stay in ENTER_ROOM_LIST after click so 'close' button is blocked
            # Fix: Wait for button disappearance to prevent double-clicks
            if self.smart_click("enter_room_button", "enter room list", verify_key="enter_room_button", wait_for_appearance=False, haystack=haystack): 
                return True
        
        # Case B: We skipped the menu and went straight to rooms (common after retry)
        if self.find_image("auto", haystack=haystack) or self.find_image("search_again", haystack=haystack):
            self.transition_to("SCAN_ROOMS")
            return True
            
        # Case C: We successfully re-joined via retry and are now in the lobby
        if self.find_image("ready", confidence=self.config.CONF_READY, haystack=haystack):
            self.transition_to("READY")
            return True

        if time.time() - self.last_state_change_time > 10.0: self.transition_to("RECOVERY"); return True
        return False

    def handle_scan_rooms(self, haystack=None):
        if self.find_image("ready", confidence=self.config.CONF_READY, haystack=haystack): self.transition_to("READY"); return True
        
        # V9.51: Increased idle timeout slightly to allow more scan cycles before recovery
        if time.time() - self.search_start_time > self.config.TIMEOUT_SCAN_IDLE: 
            logger.warning("SCAN_ROOMS: Idle timeout reached. Recovering...")
            self.transition_to("RECOVERY"); return True
        
        # Stability Pause: Wait for room list to settle
        time.sleep(0.4)
        
        autos = self.find_all("auto", haystack=haystack)
        if autos:
            v_rules = self.find_all("room_rules_valid", confidence=self.config.CONF_LOOSE, haystack=haystack)
            valid = BBSBot.match_rooms(autos, v_rules, self.config)
            candidates = []
            matched_ids = set()
            for auto, rule in valid: candidates.append((auto, rule, "strict")); matched_ids.add(id(auto))
            if self.config.ALLOW_ALL_AUTO_ROOMS:
                for a in BBSBot.dedupe_autos(autos, self.config):
                    if id(a) not in matched_ids: candidates.append((a, None, "fallback"))
            
            # Transparency: Log the scan results
            strict_count = sum(1 for _, _, m in candidates if m == "strict")
            fallback_count = sum(1 for _, _, m in candidates if m == "fallback")
            if candidates:
                logger.info(f"SCAN: Found {len(candidates)} rooms (Strict: {strict_count}, Fallback: {fallback_count})")

            # V9.51 Logic: If we found candidates, try to snatch them immediately.
            # If a snatch click fails to trigger a transition, we don't just sit here.
            if candidates and not self._force_refresh:
                self.search_start_time = time.time() # Reset idle timer on discovery
                for auto, rule, mode in candidates:
                    label = "Auto + Rules" if mode == "strict" else "Auto Only"
                    if mode == "strict" and rule: 
                        px, py = (auto.left + rule.left + rule.width) // 2, auto.top + auto.height // 2
                    else: 
                        px, py = auto.left + self.config.ALLOW_ALL_AUTO_OFFSET_X, auto.top + auto.height // 2
                    
                    target = pyscreeze.Box(px - self.config.SNATCH_BOX_OFFSET[0], py - self.config.SNATCH_BOX_OFFSET[1], self.config.SNATCH_BOX_DIM[0], self.config.SNATCH_BOX_DIM[1])
                    
                    # V9.51: Transition to JOIN_PENDING if click is successful.
                    # We use a verification check to ensure the room list actually changes or we enter a lobby.
                    if self.smart_click(target, f"snatch {mode} ({label})", haystack=haystack):
                        self.transition_to("JOIN_PENDING")
                        return True
                return True
        
        # V9.51: Improved Refresh Logic. If no autos or force refresh, click Search Again.
        if self._force_refresh or self.find_image("search_again", haystack=haystack):
            if time.time() - self.search_start_time > self.config.WAIT_SEARCH_AGAIN or self._force_refresh:
                if self.find_image("search_again", haystack=haystack):
                    # Only reset start time if we actually click refresh
                    if self.smart_click("search_again", "refresh list", haystack=haystack):
                        self.search_start_time = time.time()
                        self._force_refresh = False
                        time.sleep(self.config.WAIT_REFRESH_COOLDOWN)
                        return True
        return False

    @staticmethod
    def match_rooms(autos, rules, config):
        valid = []
        for a in BBSBot.dedupe_autos(autos, config):
            ax, ay = a.left + a.width // 2, a.top + a.height // 2
            # V9.51: Relaxed vertical alignment (45 -> 55) to catch OSIRIS-style badges.
            best_r, min_dy = None, float("inf")
            for r in rules:
                ry = r.top + r.height // 2
                dy = abs(ry - ay)
                if dy < 55 and dy < min_dy:
                    min_dy, best_r = dy, r
            if best_r: valid.append((a, best_r))
        return valid

    @staticmethod
    def dedupe_autos(matches, config):
        unique = []
        for m in matches:
            cx, cy = m.left + m.width // 2, m.top + m.height // 2
            if not any(((cx - (u.left + u.width // 2))**2 + (cy - (u.top + u.height // 2))**2)**0.5 < config.AUTO_ICON_DEDUPE_DIST for u in unique): unique.append(m)
        return unique

    def handle_join_pending(self, haystack=None):
        if self.find_stable_image("ready", confidence=self.config.CONF_READY, frames=3):
            time.sleep(self.config.DELAY_READY)
            return self.smart_click("ready", "snap ready", verify_key="ready", target_state="CHECK_RUN_START", haystack=haystack)
        if self.find_image("closed_room_coop_quest_menu", haystack=haystack) or self.find_image("room_not_met", haystack=haystack):
            key = "closed_room_coop_quest_menu" if self.find_image("closed_room_coop_quest_menu", haystack=haystack) else "room_not_met"
            if self.smart_click(key, "room fail", haystack=haystack): self.transition_to("SCAN_ROOMS"); return True
        if time.time() - self.last_state_change_time > 2.0:
            if self.find_image("auto", haystack=haystack) or self.find_image("search_again", haystack=haystack):
                logger.info("Room join failed silently. Forcing list refresh.")
                # Physical Refresh: Click Search Again to clear the stale list
                if self.find_image("search_again", haystack=haystack):
                    self.smart_click("search_again", "refresh list", haystack=haystack)
                    time.sleep(self.config.WAIT_REFRESH_COOLDOWN) # Wait for network load
                self.transition_to("SCAN_ROOMS"); return True
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_LOBBY_JOIN: self.transition_to("RECOVERY"); return True
        return False

    def handle_ready(self, haystack=None):
        if self.find_stable_image("ready", confidence=self.config.CONF_READY, frames=3):
            time.sleep(self.config.DELAY_READY)
            return self.smart_click("ready", "ready button", verify_key="ready", target_state="CHECK_RUN_START", haystack=haystack)
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_RUN_START: self.retire_from_quest(haystack=haystack); return True
        return False

    def handle_check_run_start(self, haystack=None):
        if self.find_stable_image("ingame_auto_on", frames=3) or self.find_stable_image("ingame_auto_off", frames=3): 
            self.transition_to("RUNNING"); return True
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_RUN_START: self.retire_from_quest(haystack=haystack); return True
        return False

    def handle_running(self, haystack=None):
        if self.find_stable_image("tap1", frames=3): self.transition_to("FINISH"); return True
        time.sleep(self.config.POLL_RUNNING); return False

    def handle_finish(self, haystack=None):
        if not self._run_counted: self.run_count += 1; self._run_counted = True
        for key in ["tap1", "tap2"]:
            if self.find_image(key, haystack=haystack):
                if self.smart_click(key, f"reward {key}", haystack=haystack):
                    time.sleep(self.config.WAIT_STABILIZE_ANIMATION)
                    return True
                return False
        if self.find_image("retry", haystack=haystack):
            if self.smart_click("retry", "retry quest", verify_key="retry", verify_timeout=self.config.TIMEOUT_ROOM_LIST_LOAD, haystack=haystack):
                time.sleep(self.config.WAIT_POST_RETRY)
                if self.run_count >= self.next_distraction_run:
                    self.next_distraction_run = 9999
                    self.transition_to("DISTRACTION")
                    return True
                self.transition_to("ENTER_ROOM_LIST")
                return True
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_TAP_VERIFY:
            self.transition_to("RECOVERY"); return True
        return False

    def handle_game_startup(self, haystack=None):
        for key in ["game_start", "coop_1", "coop_2"]:
            if self.find_image(key, haystack=haystack): return self.smart_click(key, f"startup {key}", verify_key=key, haystack=haystack)
        if self.find_image("coop_quest", haystack=haystack) or self.find_image("open_coop_quest", haystack=haystack): self.transition_to("MENU"); return True
        return False

    def handle_recovery(self, haystack=None):
        if self.config.ALIGNMENT_MODE: self.save_debug_screenshot("lost_in_recovery")
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_STUCK: self.recover_game(); return True
        for s, t in self.RECOVERY_MAP:
            if self.find_image(t, haystack=haystack): self.transition_to(s); return True
        return False

    def handle_distraction(self, haystack=None):
        logger.info("DISTRACTION: Sleeping..."); time.sleep(random.randint(*self.config.DISTRACTION_DURATION))
        self.quest_watchdog = time.time()
        self.fatigue_start_time = time.time()
        self.active_profile = "SHIKAI_MAX"
        self.config._apply_profile(self.active_profile)
        if self.config.CIRCADIAN_PROFILES:
            self.next_profile_swap = time.time() + random.randint(*self.config.CIRCADIAN_PROFILES[self.active_profile]["DURATION_MINS"]) * 60
        self.transition_to("RECOVERY")
        return True

    def transition_to(self, state):
        if self.state != state:
            logger.info(f"TRANSITION: {self.state} -> {state}"); old = self.state; self.state = state; self.last_state_change_time = time.time()
            if self.config.ALIGNMENT_MODE: self.save_debug_screenshot(f"to_{state}")
            if state == "RECOVERY": self.save_error_snapshot(f"recovery_from_{old}")
            if state in ["RUNNING", "READY"]: self.reset_quest_watchdog(state.lower())
            if state == "SCAN_ROOMS": self.search_start_time = time.time()
            if state in ["MENU", "READY", "CHECK_RUN_START", "ENTER_ROOM_LIST"]: self._run_counted = False
            if old == "FINISH" and state != "FINISH": self.reset_quest_watchdog("completed")

    def reset_quest_watchdog(self, reason="progress"):
        logger.info(f"WATCHDOG Reset ({reason})"); self.quest_watchdog = time.time(); self.consecutive_recovery_count = 0

    def retire_from_quest(self, haystack=None):
        logger.warning("Retiring..."); self.expected_okay_context = "RETIRE_CONFIRM"
        if self.find_image("retire", haystack=haystack):
            if self.smart_click("retire", "retire", verify_key="okay", wait_for_appearance=True, haystack=haystack):
                self.smart_click("okay", "confirm", verify_key="okay")
        self.expected_okay_context = None; self.transition_to("MENU"); return True

    def recover_game(self):
        self.save_error_snapshot("hard_recover_game")
        self.consecutive_recovery_count += 1
        if self.consecutive_recovery_count > self.config.MAX_CONSECUTIVE_RECOVERIES: sys.exit(1)
        self.quest_watchdog = time.time()
        subprocess.run(["pkill", "-f", "BleachBraveSouls.exe"], stderr=subprocess.DEVNULL)
        time.sleep(self.config.WAIT_RESTART)
        subprocess.Popen(["steam", "-applaunch", "1201240"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Patience: Wait for window to appear before returning
        start = time.time()
        while time.time() - start < self.config.TIMEOUT_GAME_START:
            try:
                if self.get_game_region(): break
            except GameWindowNotFoundError:
                time.sleep(2.0)
        
        self.transition_to("GAME_STARTUP")

    def check_quest_watchdog(self):
        if time.time() - self.quest_watchdog > self.config.TIMEOUT_QUEST_MAX: self.recover_game()

    def ensure_window_ready(self):
        try:
            self.get_game_region()
        except GameWindowNotFoundError:
            self.win_id = self.region = self.snapshot = None
            return False
        return True

    def get_game_region(self):
        try:
            now = time.time()
            if not self.win_id or (now - getattr(self, "_last_id_search", 0) > 5.0):
                cmd = ["xdotool", "search", "--name", self.config.RAW_TITLE]
                res = subprocess.run(cmd, capture_output=True, text=True)
                wids = res.stdout.strip().split()
                valid_wid = None
                for wid in wids:
                    try:
                        pid_res = subprocess.run(["xdotool", "getwindowpid", wid], capture_output=True, text=True)
                        pid = pid_res.stdout.strip()
                        if not pid: continue
                        proc_res = subprocess.run(["ps", "-p", pid, "-o", "cmd", "--no-headers"], capture_output=True, text=True)
                        proc_info = proc_res.stdout.strip()
                        if "BleachBraveSouls" in proc_info: valid_wid = wid; break
                    except Exception: continue
                if valid_wid: self.win_id = valid_wid
                self._last_id_search = now
            if not self.win_id: raise GameWindowNotFoundError("Window ID not found")
            geo_res = subprocess.run(["xdotool", "getwindowgeometry", "--shell", self.win_id], capture_output=True, text=True)
            if geo_res.returncode != 0: 
                self.win_id = None
                raise GameWindowNotFoundError("Window geometry retrieval failed")
            g = {line.split("=")[0]: int(line.split("=")[1]) for line in geo_res.stdout.splitlines() if "=" in line}
            if g.get("WIDTH", 0) > 100: self.win_id, self.region = self.win_id, (g["X"], g["Y"], g["WIDTH"], g["HEIGHT"]); return self.region
            raise GameWindowNotFoundError("Window geometry invalid")
        except GameWindowNotFoundError: raise
        except Exception as e:
            raise GameWindowNotFoundError(str(e)) from e

    def setup_window_properties(self):
        if self.win_id and self.config.USE_WMCTRL_ALWAYS_ON_TOP:
            subprocess.run(["wmctrl", "-i", "-r", self.win_id, "-b", "add,sticky,above"], check=False, stderr=subprocess.DEVNULL)
            try:
                state = subprocess.check_output(["xprop", "-id", self.win_id, "WM_STATE"], text=True, stderr=subprocess.DEVNULL).lower()
                if "iconic" in state: subprocess.run(["xdotool", "windowraise", self.win_id], check=False, stderr=subprocess.DEVNULL)
            except Exception: pass

    def check_circadian_rhythm(self):
        if time.time() > self.next_profile_swap:
            old = self.active_profile
            self.active_profile = "SHIKAI_NORMAL" if old == "SHIKAI_MAX" else "SHIKAI_MAX"
            self.config._apply_profile(self.active_profile)
            if self.config.CIRCADIAN_PROFILES:
                duration = random.randint(*self.config.CIRCADIAN_PROFILES[self.active_profile]["DURATION_MINS"]) * 60
                self.next_profile_swap = time.time() + duration
                logger.info(f"CIRCADIAN SHIFT: {self.active_profile} for {duration/60:.0f}m")
            if old == "SHIKAI_MAX" and self.active_profile == "SHIKAI_NORMAL":
                self.next_distraction_run = self.run_count + random.randint(*self.config.CASUAL_LINGER_RUNS)
                logger.info(f"FATIGUE: Break after run #{self.next_distraction_run}.")

    def check_session_limit(self):
        if (time.time() - self.start_time) / 3600 >= self.config.SESSION_MAX_HOURS: sys.exit(0)

    def update_fatigue(self):
        el = time.time() - self.fatigue_start_time
        self.fatigue_modifier = self.config.FATIGUE_BASE + self.config.FATIGUE_AMPLITUDE * abs(math.sin(el * (2 * math.pi / self.config.FATIGUE_PERIOD)))

    def run(self, test_restart=False):
        if test_restart: self.recover_game()
        self._load_templates(); self.check_dependencies(); self.reset_quest_watchdog("startup")
        last_prop_sync = 0.0
        while True:
            try:
                if not self.ensure_window_ready():
                    logger.warning("Game window not found; waiting...")
                    time.sleep(2.0)
                    continue

                if time.time() - last_prop_sync > self.config.POLL_PROPERTY_SYNC:
                    self.setup_window_properties(); last_prop_sync = time.time()
                
                monitor = {"top": self.region[1], "left": self.region[0], "width": self.region[2], "height": self.region[3]}
                sct_img = self.sct.grab(monitor); self.snapshot = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                
                self.check_quest_watchdog(); self.update_fatigue(); self.check_circadian_rhythm(); self.check_session_limit()
                handler = self.handlers.get(self.state)
                if handler and handler(self.snapshot): continue
                if self.handle_global_popups(self.snapshot): continue
                time.sleep(self.config.POLL_MAIN_LOOP)
            except Exception:
                logger.exception("Loop Error:")
                self.save_error_snapshot("fatal_loop_error")
                self.transition_to("RECOVERY")
                time.sleep(1)
        self.log_session_summary()

    def log_session_summary(self):
        elapsed = time.time() - self.start_time
        h, m, s = int(elapsed // 3600), int((elapsed % 3600) // 60), int(elapsed % 60)
        avg_run = (elapsed / 60.0) / max(1, self.run_count)
        
        summary = (
            "\n" + "="*35 + "\n"
            "   🏆 BBS SENTINEL SUMMARY 🏆\n"
            + "="*35 + "\n"
            f" ⏱️  Uptime       : {h:02d}h {m:02d}m {s:02d}s\n"
            f" ⚔️  Quests Cleared: {self.run_count}\n"
            f" ⚡  Avg Time/Run : {avg_run:.2f} mins\n"
            f" 🔌  Disconnects  : {self.disconnect_retry_count}\n"
            + "="*35
        )
        logger.info(summary)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-restart", action="store_true")
    parser.add_argument("--allow-all-auto-rooms", action="store_true")
    parser.add_argument("--alignment-mode", action="store_true")
    args = parser.parse_args()
    bot = BBSBot()
    if args.allow_all_auto_rooms: bot.config.ALLOW_ALL_AUTO_ROOMS = True
    if args.alignment_mode: bot.config.ALIGNMENT_MODE = True
    try: bot.run(test_restart=args.test_restart)
    except KeyboardInterrupt: bot.log_session_summary(); sys.exit(0)
    except Exception as e: logger.exception(f"Fatal: {e}"); bot.log_session_summary(); sys.exit(1)
