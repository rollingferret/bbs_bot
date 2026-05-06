import argparse
import os
import sys
import time
import subprocess
import random
import logging
import math
from typing import Optional, List, Tuple, Dict, Any, Union
from dataclasses import dataclass

import pyautogui
import pyscreeze
from Xlib import X, display, protocol, error
from PIL import Image

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("v6_behavior.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class BotConfiguration:
    """Centralized configuration for the BBS Bot V6.0 'Snapshot Engine'."""
    RAW_TITLE: str = "Bleach: Brave Souls"
    GAME_WINDOW_TITLE: str = "Bleach: Brave Souls"
    
    # --- Circadian Rhythm Profiles ---
    CIRCADIAN_PROFILES: Dict[str, Dict[str, Any]] = None
    
    # Current Active Profile (Defaults initialized in post_init)
    DELAY_COGNITIVE: Tuple[float, float] = (0.68, 0.05) 
    DELAY_SNIPE: float = 0.20         
    DELAY_TRANSITION: float = 0.5     
    DELAY_SOAK: float = 0.2           
    DELAY_POPUP: float = 1.5          
    DELAY_TAP: float = 1.5            
    DELAY_READY: float = 0.90         
    WAIT_ROOM_LOAD: float = 0.6       
    WAIT_SEARCH_AGAIN: float = 0.7    
    WAIT_LOBBY_READY: float = 0.3     
    WAIT_POST_RETRY: float = 1.0
    WAIT_REFOCUS: float = 0.02
    WAIT_REFRESH_COOLDOWN: float = 0.8
    WAIT_STABILIZE_ANIMATION: float = 0.8
    SAFETY_FLOOR_FACTOR: float = 0.05
    
    # --- Timeouts ---
    TIMEOUT_STUCK: float = 300  
    TIMEOUT_QUEST_MAX: float = 600
    TIMEOUT_GAME_START: float = 120
    TIMEOUT_READY: float = 30
    TIMEOUT_RUN_START: float = 300
    TIMEOUT_TAP_VERIFY: float = 15
    TIMEOUT_LOBBY_EXPAND: float = 20.0
    TIMEOUT_LOBBY_JOIN: float = 6.0
    TIMEOUT_ROOM_LIST_LOAD: float = 5.0
    TIMEOUT_SCAN_IDLE: float = 20.0
    TIMEOUT_VERIFY_UI: float = 0.5
    
    # --- Wait Constants ---
    WAIT_RETIRE_STEP: float = 1.0     
    WAIT_DISCONNECT_COOLING: float = 10.0
    WAIT_RESTART: float = 5.0
    WAIT_STARTUP_STEP: float = 2.0
    
    # --- Vision & Matching ---
    CONF_NORMAL: float = 0.80 
    CONF_HIGH: float = 0.95
    CONF_READY: float = 0.95 
    CONF_STARTUP: float = 0.85
    CONF_LOOSE: float = 0.70
    CONF_POPUP: float = 0.80 
    CONF_VERIFY_ACTION: float = 0.80  # Match CONF_NORMAL for consistency
    AUTO_MATCH_CONFIDENCE: float = 0.92 
    
    # --- Matching Algorithm ---
    ROOM_MATCH_WEIGHT: float = 0.1
    MAX_RULE_DISTANCE: int = 110
    AUTO_ICON_DEDUPE_DIST: int = 60
    CLICK_SIGMA_FACTOR: float = 10.0
    SNATCH_BOX_OFFSET: Tuple[int, int] = (20, 10)
    SNATCH_BOX_DIM: Tuple[int, int] = (40, 20)
    
    # --- Operational Safety ---
    WINDOW_NOT_FOUND_RETRIES: int = 5
    MAX_DISCONNECT_RETRIES: int = 3
    MAX_CONSECUTIVE_RECOVERIES: int = 3
    SESSION_MAX_HOURS: int = 16
    POLL_MAIN_LOOP: float = 0.05
    POLL_UI_VERIFY: float = 0.05
    POLL_POPUP: float = 0.5
    POLL_RECOVERY: float = 0.5
    POLL_RUNNING: float = 0.5
    POLL_PROPERTY_SYNC: float = 5.0
    
    # --- Behavioral Stealth ---
    FATIGUE_INCREASE_RATE: float = 0.001 
    MAX_FATIGUE_MODIFIER: float = 1.15
    FATIGUE_BASE: float = 1.0
    FATIGUE_AMPLITUDE: float = 0.15
    FATIGUE_PERIOD: int = 1800
    DISTRACTION_CHANCE: Tuple[int, int] = (25, 45)
    DISTRACTION_DURATION: Tuple[int, int] = (120, 480)
    
    # --- Technical Flags ---
    TAKE_DEBUG_SCREENSHOTS: bool = False
    MANAGE_INGAME_AUTO: bool = True
    USE_WMCTRL_ALWAYS_ON_TOP: bool = True

    TEMPLATES: Dict[str, str] = None

    def __post_init__(self):
        self.CIRCADIAN_PROFILES = {
            "SHIKAI_MAX": { # "PRO GAMER": Elite focus, perfect cadence
                "DELAY_COGNITIVE": (1.15, 0.15), "DELAY_SNIPE": 0.20, "DELAY_TRANSITION": 0.5,
                "DELAY_SOAK": 0.2, "DELAY_TAP": 1.5,
                "DELAY_POPUP": 1.5, "DELAY_READY": 0.90, "WAIT_ROOM_LOAD": 0.8,
                "WAIT_SEARCH_AGAIN": 0.9, "WAIT_LOBBY_READY": 0.3, "WAIT_POST_RETRY": 1.0,
                "WAIT_REFRESH_COOLDOWN": 0.9, "DELAY_POST_POPUP": 0.3, "WAIT_STABILIZE_ANIMATION": 0.8,
                "DURATION_MINS": (45, 90)
            },
            "SHIKAI_NORMAL": { # "CASUAL": Distracted, watching Netflix
                "DELAY_COGNITIVE": (1.50, 0.25), "DELAY_SNIPE": 0.40, "DELAY_TRANSITION": 1.2,
                "DELAY_SOAK": 0.4, "DELAY_TAP": 2.5,
                "DELAY_POPUP": 2.0, "DELAY_READY": 1.10, "WAIT_ROOM_LOAD": 1.0,
                "WAIT_SEARCH_AGAIN": 1.1, "WAIT_LOBBY_READY": 0.6, "WAIT_POST_RETRY": 2.0,
                "WAIT_REFRESH_COOLDOWN": 1.5, "DELAY_POST_POPUP": 0.6, "WAIT_STABILIZE_ANIMATION": 1.2,
                "DURATION_MINS": (60, 180)
            }
        }
        self.TEMPLATES = {
            "game_start": "images/game_start.png", "close_news": "images/close_news.png",
            "coop_1": "images/coop-1.png", "coop_2": "images/coop-2.png",
            "coop_quest": "images/coop_quest.png", "open_coop_quest": "images/open_coop_quest.png",
            "enter_room_button": "images/join_coop_quest.png", "search_again": "images/search_again.png",
            "auto": "images/auto_icon.png", "ingame_auto_off": "images/ingame_auto_off.png",
            "ingame_auto_on": "images/ingame_auto_on.png", "room_rules_valid": "images/room_rules_valid.png",
            "close": "images/close.png", "ready": "images/ready_button.png",
            "retire": "images/retire.png", "okay": "images/okay.png",
            "closed_room_coop_quest_menu": "images/closed_room_coop_quest_menu.png",
            "tap1": "images/tap1.png", "tap2": "images/tap2.png",
            "retry": "images/retry.png", "unavailable_close": "images/unavailable_close.png",
            "disconnect_retry": "images/disconnect_rerty.png",
        }
        
        # Apply initial profile
        self._apply_profile("SHIKAI_MAX")

    def _apply_profile(self, profile_name: str):
        s = self.CIRCADIAN_PROFILES[profile_name]
        self.DELAY_COGNITIVE = s["DELAY_COGNITIVE"]
        self.DELAY_SNIPE = s["DELAY_SNIPE"]
        self.DELAY_TRANSITION = s["DELAY_TRANSITION"]
        self.DELAY_SOAK = s["DELAY_SOAK"]
        self.DELAY_TAP = s["DELAY_TAP"]
        self.DELAY_POPUP = s["DELAY_POPUP"]
        self.DELAY_READY = s["DELAY_READY"]
        self.WAIT_ROOM_LOAD = s["WAIT_ROOM_LOAD"]
        self.WAIT_SEARCH_AGAIN = s["WAIT_SEARCH_AGAIN"]
        self.WAIT_LOBBY_READY = s["WAIT_LOBBY_READY"]
        self.WAIT_POST_RETRY = s["WAIT_POST_RETRY"]
        self.WAIT_REFRESH_COOLDOWN = s["WAIT_REFRESH_COOLDOWN"]
        self.WAIT_STABILIZE_ANIMATION = s["WAIT_STABILIZE_ANIMATION"]


def human_delay(profile: Union[float, Tuple[float, float]], fatigue: float = 1.0, safety_factor: float = 0.05) -> None:
    if isinstance(profile, (float, int)):
        mu, sigma = float(profile), float(profile) * 0.1
    else:
        mu, sigma = profile
    delay = random.gauss(mu * fatigue, sigma)
    time.sleep(max(delay, (mu * fatigue) * safety_factor))

class GameWindowNotFoundError(Exception): pass

class BBSBot:
    """
    Bleach: Brave Souls Autonomous Agent V6.0 'Snapshot Engine'.
    Universal "Check -> Soak -> Click -> Verify" Architecture. Zero xdotool lockups.
    """
    
    RECOVERY_MAP: List[Tuple[str, str]] = [
        ("READY", "ready"), ("RUNNING", "ingame_auto_on"), ("RUNNING", "ingame_auto_off"),
        ("CHECK_RUN_START", "retire"), ("FINISH", "tap1"),
        ("FINISH", "tap2"), ("FINISH", "retry"), 
        ("SCAN_ROOMS", "search_again"), ("ENTER_ROOM_LIST", "enter_room_button"),
        ("MENU", "open_coop_quest"), ("MENU", "coop_quest"), ("GAME_STARTUP", "game_start"),
        ("MENU", "closed_room_coop_quest_menu"), ("SCAN_ROOMS", "close"),
        ("SCAN_ROOMS", "unavailable_close"), ("MENU", "disconnect_retry")
    ]

    def __init__(self, config: BotConfiguration = BotConfiguration()) -> None:
        self.config = config
        
        self.active_profile: str = "SHIKAI_MAX"
        self.next_profile_swap: float = time.time() + random.randint(*self.config.CIRCADIAN_PROFILES["SHIKAI_MAX"]["DURATION_MINS"]) * 60
        
        self.state: str = "RECOVERY" 
        self.run_count: int = 0
        self.start_time: float = time.time()
        self.fatigue_start_time: float = time.time()
        self.last_state_change_time: float = time.time()
        self.quest_watchdog: float = time.time() 
        self.region: Optional[Tuple[int, int, int, int]] = None
        self.win_id: Optional[str] = None
        self.fatigue_modifier: float = 1.0
        self.disconnect_retry_count: int = 0
        self.window_not_found_count: int = 0
        self.consecutive_recovery_count: int = 0
        self.search_start_time: float = 0
        self._force_refresh: bool = False
        self.next_distraction_run: int = random.randint(*self.config.DISTRACTION_CHANCE)
        self.snapshot: Optional[Image.Image] = None
        
        self.handlers = {
            "MENU": self.handle_menu, "ENTER_ROOM_LIST": self.handle_enter_room_list,
            "SCAN_ROOMS": self.handle_scan_rooms, "READY": self.handle_ready,
            "CHECK_RUN_START": self.handle_check_run_start, "RUNNING": self.handle_running,
            "FINISH": self.handle_finish, "DISTRACTION": self.handle_distraction,
            "RECOVERY": self.handle_recovery, "GAME_STARTUP": self.handle_game_startup
        }

        self.cached_templates: Dict[str, Image.Image] = {}
        self._load_templates()
        pyautogui.FAILSAFE = False
        self.check_dependencies()
        
        try: self.disp = display.Display()
        except Exception:
            logger.error("FATAL: X11 Display error."); sys.exit(1)
            
        logger.info("BBS Bot V6.0 'Snapshot Engine' Initialized.")

    def _load_templates(self) -> None:
        for key, path in self.config.TEMPLATES.items():
            try: self.cached_templates[key] = Image.open(path).convert('RGB')
            except Exception as e: logger.error(f"Failed to cache {key}: {e}")

    def check_dependencies(self) -> None:
        for cmd in ["xdotool", "wmctrl", "pkill", "xprop"]:
            if subprocess.run(["which", cmd], capture_output=True).returncode != 0:
                logger.error(f"FATAL: Missing dependency: {cmd}"); sys.exit(1)

    # --- VISION ---
    def get_ui_region(self, element: str) -> Optional[Tuple[int, int, int, int]]:
        if not self.region: return None
        gx, gy, gw, gh = self.region
        if element == "auto": return (gx + gw // 2, gy + gh // 2, gw // 2, gh // 2)
        if element == "center_popup": return (gx + gw // 4, gy + gh // 4, gw // 2, gh // 2)
        return self.region

    def find_image(self, key: str, confidence: Optional[float] = None, region: Optional[Tuple] = None, haystack: Optional[Image.Image] = None) -> Optional[pyscreeze.Box]:
        template = self.cached_templates.get(key)
        conf = confidence or self.config.CONF_NORMAL
        reg = region or self.region
        if not template or not reg: return None
        
        t_start = time.time()
        try:
            if haystack:
                # Map screen region to haystack-relative coordinates
                h_reg = (reg[0] - self.region[0], reg[1] - self.region[1], reg[2], reg[3])
                res = pyautogui.locate(template, haystack, region=h_reg, confidence=conf)
                if res:
                    # Map result back to screen coordinates
                    res = pyscreeze.Box(res.left + self.region[0], res.top + self.region[1], res.width, res.height)
            else:
                res = pyautogui.locateOnScreen(template, region=reg, confidence=conf)
            
            if res:
                elapsed = time.time() - t_start
                if elapsed > 0.5:
                    logger.debug(f"VISION: Found '{key}' in {elapsed:.2f}s")
                return res
        except Exception: pass
        return None

    def find_stable_image(self, key: str, confidence: Optional[float] = None, region: Optional[Tuple] = None, frames: int = 2) -> Optional[pyscreeze.Box]:
        for _ in range(frames):
            res = self.find_image(key, confidence, region)
            if not res: return None
            time.sleep(self.config.POLL_UI_VERIFY)
        return res

    def find_all(self, key: str, confidence: float = 0.8, haystack: Optional[Image.Image] = None, region: Optional[Tuple] = None) -> List[pyscreeze.Box]:
        template = self.cached_templates.get(key)
        reg = region or self.region
        if not template or not reg: return []
        try:
            if haystack:
                h_reg = (reg[0] - self.region[0], reg[1] - self.region[1], reg[2], reg[3])
                res = list(pyautogui.locateAll(template, haystack, region=h_reg, confidence=confidence))
                return [pyscreeze.Box(r.left + self.region[0], r.top + self.region[1], r.width, r.height) for r in res]
            else:
                res = list(pyautogui.locateAllOnScreen(template, region=reg, confidence=confidence))
            if res: return res
            return []
        except Exception: return []

    # --- THE V4 STEALTH CORE ---
    def smart_click(self, target: Union[str, pyscreeze.Box], description: str, verify_key: Optional[str] = None, target_state: Optional[str] = None, wait_for_appearance: bool = False, custom_delay: Optional[Union[float, Tuple[float, float]]] = None, confidence: Optional[float] = None, region: Optional[Tuple[int, int, int, int]] = None, haystack: Optional[Image.Image] = None) -> bool:
        conf = confidence or self.config.CONF_NORMAL
        
        # 1. Locate Target
        box = target if isinstance(target, pyscreeze.Box) else self.find_image(target, confidence=conf, region=region, haystack=haystack)
        if not box:
            if verify_key == target and not wait_for_appearance:
                if target_state: self.transition_to(target_state)
                return True
            return False

        # 2. Human Cognitive Pacing
        human_delay(custom_delay or self.config.DELAY_COGNITIVE, self.fatigue_modifier, self.config.SAFETY_FLOOR_FACTOR)

        # 3. Gaussian Click Calculation
        mu_x, mu_y = box.left + box.width / 2, box.top + box.height / 2
        sigma_x, sigma_y = box.width / self.config.CLICK_SIGMA_FACTOR, box.height / self.config.CLICK_SIGMA_FACTOR
        click_x, click_y = int(random.gauss(mu_x, sigma_x)), int(random.gauss(mu_y, sigma_y))
        click_x = max(box.left, min(click_x, box.left + box.width - 1))
        click_y = max(box.top, min(click_y, box.top + box.height - 1))

        # 4. Focus Capture
        current_focus = None
        try:
            current_focus = subprocess.check_output(["xdotool", "getactivewindow"], text=True, stderr=subprocess.DEVNULL).strip()
        except Exception: pass

        # 5. Execute X11 Ghost Click
        success = self._send_x11_click(click_x, click_y)
        logger.info(f"CLICK [Run:{self.run_count}]: {description} at ({click_x}, {click_y})")

        # 6. Unconditional Refocus
        if success and current_focus:
            time.sleep(self.config.WAIT_REFOCUS)
            try:
                subprocess.run(["xdotool", "windowactivate", "--sync", current_focus, "windowraise", current_focus], check=False, stderr=subprocess.DEVNULL)
            except Exception: pass

        # 7. Rapid Verification Window
        if success and verify_key:
            v_start = time.time()
            while time.time() - v_start < self.config.TIMEOUT_VERIFY_UI:
                found_v = self.find_image(verify_key, confidence=self.config.CONF_VERIFY_ACTION)
                if (wait_for_appearance and found_v) or (not wait_for_appearance and not found_v):
                    if target_state: self.transition_to(target_state)
                    return True
                time.sleep(self.config.POLL_UI_VERIFY)
            return False

        # 8. Instant Transition
        if success and target_state: 
            self.transition_to(target_state)
        return True

    def _send_x11_click(self, x: int, y: int) -> bool:
        """Pure headless X11 click. No window manager interference."""
        try:
            window = self.disp.create_resource_object("window", int(self.win_id))
            geom = window.get_geometry()
            rel_x, rel_y = x - geom.x, y - geom.y
            details = {
                "root": self.disp.screen().root, "window": window, "same_screen": 1, "child": X.NONE,
                "root_x": x, "root_y": y, "event_x": rel_x, "event_y": rel_y, "state": 0, "detail": 1,
                "time": int(time.time() * 1000) & 0xFFFFFFFF,
            }
            window.send_event(protocol.event.ButtonPress(**details), propagate=True)
            window.send_event(protocol.event.ButtonRelease(**details), propagate=True)
            self.disp.flush(); self.disp.sync(); return True
        except Exception: return False

    # --- PROCEDURAL HANDLERS ---
    def handle_global_popups(self, haystack: Optional[Image.Image] = None) -> bool:
        now = time.time()
        if not hasattr(self, '_last_popup_check'): self._last_popup_check = 0
        if now - self._last_popup_check < self.config.POLL_POPUP: return False
        self._last_popup_check = now

        popups = ["close", "close_news", "okay", "unavailable_close", "closed_room_coop_quest_menu", "disconnect_retry"]
        for key in popups:
            conf = 0.99 if key == "disconnect_retry" else self.config.CONF_POPUP
            reg = self.region
            if key in ["okay", "closed_room_coop_quest_menu", "disconnect_retry", "close", "unavailable_close"]:
                reg = self.get_ui_region("center_popup")
            
            if self.find_image(key, confidence=conf, region=reg, haystack=haystack):
                logger.warning(f"GLOBAL: Popup '{key}' confirmed")
                if key == "disconnect_retry":
                    self.disconnect_retry_count += 1
                    if self.disconnect_retry_count > self.config.MAX_DISCONNECT_RETRIES:
                        self.recover_game(); return True
                
                self.smart_click(key, f"dismiss {key}", verify_key=key, custom_delay=self.config.DELAY_POPUP, confidence=conf, region=reg, haystack=haystack)
                if key == "disconnect_retry": time.sleep(self.config.WAIT_DISCONNECT_COOLING)
                else: human_delay(self.config.DELAY_POPUP, self.fatigue_modifier, self.config.SAFETY_FLOOR_FACTOR)

                if self.state != "GAME_STARTUP": self.transition_to("MENU")
                return True
        return False

    def handle_menu(self, haystack: Optional[Image.Image] = None) -> None:
        if self.find_image("open_coop_quest", haystack=haystack):
            self.smart_click("open_coop_quest", "specific quest", "enter_room_button", target_state="ENTER_ROOM_LIST", wait_for_appearance=True, haystack=haystack)
            return
            
        if self.find_image("coop_quest", haystack=haystack): 
            self.smart_click("coop_quest", "expand menu", "open_coop_quest", wait_for_appearance=True, haystack=haystack)
            return

        if self.find_image("enter_room_button", haystack=haystack): self.transition_to("ENTER_ROOM_LIST"); return
        
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_LOBBY_EXPAND:
            self.transition_to("RECOVERY")

    def handle_enter_room_list(self, haystack: Optional[Image.Image] = None) -> None:
        if self.find_image("enter_room_button", haystack=haystack):
            if self.smart_click("enter_room_button", "enter room list", haystack=haystack):
                start_load = time.time()
                while time.time() - start_load < self.config.TIMEOUT_ROOM_LIST_LOAD:
                    if self.find_image("auto") or self.find_image("search_again"):
                        time.sleep(self.config.WAIT_ROOM_LOAD)
                        self.transition_to("SCAN_ROOMS"); return
                    time.sleep(self.config.POLL_UI_VERIFY)
                logger.warning("Failed to verify room list load. Re-evaluating state.")
                return 
                
        self.transition_to("RECOVERY")

    def handle_scan_rooms(self, haystack: Optional[Image.Image] = None) -> None:
        if self.find_image("ready", confidence=self.config.CONF_READY, haystack=haystack): self.transition_to("READY"); return

        if getattr(self, '_force_refresh', False):
            if self.find_image("search_again", haystack=haystack):
                if self.smart_click("search_again", "recovery refresh", custom_delay=self.config.DELAY_POST_POPUP, haystack=haystack):
                    self.search_start_time = time.time()
                    self._force_refresh = False
                    time.sleep(self.config.WAIT_REFRESH_COOLDOWN)
            return

        if time.time() - self.search_start_time > self.config.TIMEOUT_SCAN_IDLE: 
            logger.warning(f"SCAN_ROOMS: No activity for {self.config.TIMEOUT_SCAN_IDLE}s. Yielding to RECOVERY.")
            self.transition_to("RECOVERY")
            return
        
        autos = self.find_all("auto", confidence=self.config.CONF_NORMAL, haystack=haystack)
        if autos:
            v_rules = self.find_all("room_rules_valid", confidence=self.config.CONF_LOOSE, haystack=haystack)
            valid = BBSBot.match_rooms(autos, v_rules, self.config)
            
            for auto, rule in valid:
                local_reg = (auto.left - 5, auto.top - 5, auto.width + 10, auto.height + 10)
                if not self.find_image("auto", region=local_reg, haystack=haystack):
                    logger.warning("Local anchor lost. Room list shifted. Refreshing.")
                    return

                px, py = (auto.left + rule.left + rule.width) // 2, auto.top + auto.height // 2
                ox, oy = self.config.SNATCH_BOX_OFFSET
                dw, dh = self.config.SNATCH_BOX_DIM
                target_box = pyscreeze.Box(px - ox, py - oy, dw, dh)
                
                if self.smart_click(target_box, "snatch room", custom_delay=self.config.DELAY_SNIPE):
                    start_v = time.time()
                    while time.time() - start_v < self.config.TIMEOUT_LOBBY_JOIN:
                        if self.find_stable_image("ready", confidence=self.config.CONF_READY, frames=3):
                            time.sleep(self.config.DELAY_READY)
                            if self.smart_click("ready", "snap ready", verify_key="ready", custom_delay=self.config.WAIT_LOBBY_READY, target_state="CHECK_RUN_START"):
                                return 
                            return 
                        
                        if self.find_image("closed_room_coop_quest_menu", confidence=self.config.CONF_NORMAL): 
                            if self.smart_click("closed_room_coop_quest_menu", "close room full", verify_key="closed_room_coop_quest_menu"):
                                logger.info("Room full. Kicked to menu. Detouring.")
                                self.transition_to("MENU")
                                return 
                        
                        if self.find_image("close", confidence=self.config.CONF_NORMAL) or \
                           self.find_image("unavailable_close", confidence=self.config.CONF_NORMAL):
                            key = "close" if self.find_image("close") else "unavailable_close"
                            if self.smart_click(key, "close unavailable", verify_key=key):
                                logger.info("Room unavailable. Refreshing list.")
                                self._force_refresh = True
                                return 
                                
                        time.sleep(self.config.POLL_UI_VERIFY)
        
        if time.time() - self.search_start_time > self.config.WAIT_SEARCH_AGAIN: 
            if self.find_image("search_again", haystack=haystack):
                if self.smart_click("search_again", "search again", haystack=haystack):
                    self.search_start_time = time.time()
                    time.sleep(self.config.WAIT_REFRESH_COOLDOWN)

    @staticmethod
    def match_rooms(autos: List[pyscreeze.Box], rules: List[pyscreeze.Box], config: BotConfiguration) -> List[Tuple[pyscreeze.Box, pyscreeze.Box]]:
        valid = []
        for a in BBSBot.dedupe_autos(autos, config):
            ax, ay = a.left + a.width//2, a.top + a.height//2
            best_r, min_d = None, float('inf')
            for r in rules:
                rx, ry = r.left + r.width//2, r.top + r.height//2
                if ry > ay:
                    d = abs(ry - ay) + abs(rx - ax) * config.ROOM_MATCH_WEIGHT
                    if d < min_d and d < config.MAX_RULE_DISTANCE:
                        min_d, best_r = d, r
            if best_r:
                valid.append((a, best_r))
        return valid

    @staticmethod
    def dedupe_autos(matches: List[pyscreeze.Box], config: BotConfiguration) -> List[pyscreeze.Box]:
        unique = []
        for m in matches:
            cx, cy = m.left + m.width//2, m.top + m.height//2
            if not any(((cx-(u.left+u.width//2))**2 + (cy-(u.top+u.height//2))**2)**0.5 < config.AUTO_ICON_DEDUPE_DIST for u in unique):
                unique.append(m)
        return unique

    def handle_ready(self, haystack: Optional[Image.Image] = None) -> None:
        if self.find_image("closed_room_coop_quest_menu", confidence=self.config.CONF_NORMAL, haystack=haystack):
            if self.smart_click("closed_room_coop_quest_menu", "room closed by host", haystack=haystack):
                self.transition_to("MENU"); return
        
        if self.find_image("close", confidence=self.config.CONF_NORMAL, haystack=haystack) or \
           self.find_image("unavailable_close", confidence=self.config.CONF_NORMAL, haystack=haystack):
            key = "close" if self.find_image("close", haystack=haystack) else "unavailable_close"
            if self.smart_click(key, "lobby disconnect", haystack=haystack):
                self.transition_to("MENU"); return

        if self.find_stable_image("ready", confidence=self.config.CONF_READY, frames=3):
            time.sleep(self.config.DELAY_READY)
            if self.smart_click("ready", "ready button", verify_key="ready", target_state="CHECK_RUN_START", haystack=haystack):
                return
        else:
            if self.find_image("ingame_auto_off", haystack=haystack) or self.find_image("ingame_auto_on", haystack=haystack) or self.find_image("retire", haystack=haystack):
                self.transition_to("CHECK_RUN_START"); return
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_READY: self.transition_to("RECOVERY")

    def handle_check_run_start(self, haystack: Optional[Image.Image] = None) -> None:
        if self.find_image("closed_room_coop_quest_menu", confidence=self.config.CONF_NORMAL, haystack=haystack):
            if self.smart_click("closed_room_coop_quest_menu", "room closed before start", haystack=haystack):
                self.transition_to("MENU"); return

        if self.find_image("ready", confidence=self.config.CONF_READY, haystack=haystack):
            self.transition_to("READY"); return

        if self.find_image("ingame_auto_on", confidence=self.config.CONF_HIGH, haystack=haystack):
            self.transition_to("RUNNING"); return
            
        if self.find_image("ingame_auto_off", confidence=self.config.AUTO_MATCH_CONFIDENCE, haystack=haystack):
            if self.config.MANAGE_INGAME_AUTO:
                if self.smart_click("ingame_auto_off", "enable auto", verify_key="ingame_auto_on", target_state="RUNNING", wait_for_appearance=True, confidence=self.config.AUTO_MATCH_CONFIDENCE, haystack=haystack):
                    return
            self.transition_to("RUNNING"); return
            
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_RUN_START: self.retire_from_quest()

    def handle_running(self, haystack: Optional[Image.Image] = None) -> None:
        if self.config.MANAGE_INGAME_AUTO:
            if self.find_image("ingame_auto_off", confidence=self.config.AUTO_MATCH_CONFIDENCE, haystack=haystack):
                self.smart_click("ingame_auto_off", "enable auto", verify_key="ingame_auto_on", wait_for_appearance=True, confidence=self.config.AUTO_MATCH_CONFIDENCE)
            
        if self.find_image("tap1", haystack=haystack): self.transition_to("FINISH"); return
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_QUEST_MAX: self.transition_to("RECOVERY")
        time.sleep(self.config.POLL_RUNNING)

    def handle_finish(self, haystack: Optional[Image.Image] = None) -> None:
        if self.find_image("tap1", haystack=haystack):
            if self.smart_click("tap1", "reward tap1"):
                time.sleep(self.config.WAIT_STABILIZE_ANIMATION)
                self.quest_watchdog = time.time()
            return
        if self.find_image("tap2", haystack=haystack):
            if self.smart_click("tap2", "reward tap2"):
                time.sleep(self.config.WAIT_STABILIZE_ANIMATION)
                self.quest_watchdog = time.time()
            return
        if self.find_image("retry", haystack=haystack):
            if self.smart_click("retry", "retry quest", verify_key="retry"):
                self.run_count += 1
                self.consecutive_recovery_count = 0 
                logger.info(f"Run #{self.run_count} complete. Next distraction at run {self.next_distraction_run}.")
                time.sleep(self.config.WAIT_POST_RETRY)
                if self.run_count >= self.next_distraction_run:
                    self.transition_to("DISTRACTION"); return
                self.transition_to("ENTER_ROOM_LIST"); return
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_TAP_VERIFY: self.transition_to("RECOVERY")

    def handle_game_startup(self, haystack: Optional[Image.Image] = None) -> None:
        for key in ["game_start", "close_news", "coop_1", "coop_2"]:
            conf = self.config.CONF_STARTUP if key in ["coop_1", "coop_2"] else self.config.CONF_NORMAL
            if self.find_image(key, confidence=conf, haystack=haystack):
                self.smart_click(key, f"startup {key}", verify_key=key, wait_for_appearance=False, confidence=conf, haystack=haystack)
                return 

        window_age = time.time() - getattr(self, '_startup_window_time', time.time())
        if window_age > 2.0 and (
            self.find_image("coop_quest", confidence=self.config.CONF_HIGH, haystack=haystack) or
            self.find_image("open_coop_quest", confidence=self.config.CONF_HIGH, haystack=haystack)):
            logger.info("GAME_STARTUP: Lobby detected. Startup sequence complete.")
            self.transition_to("MENU")

    def handle_recovery(self, haystack: Optional[Image.Image] = None) -> None:
        elapsed = time.time() - self.last_state_change_time
        if int(elapsed) > 0 and int(elapsed) % 10 == 0:
            if not hasattr(self, '_last_recovery_log') or int(elapsed) != self._last_recovery_log:
                logger.info(f"RECOVERY: Still searching for anchors... ({elapsed:.0f}s elapsed)")
                self._last_recovery_log = int(elapsed)
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_STUCK:
            self.recover_game()
        else:
            for state, template in self.RECOVERY_MAP:
                if self.find_image(template, haystack=haystack): self.transition_to(state); return
            time.sleep(self.config.POLL_RECOVERY)

    def handle_distraction(self, haystack: Optional[Image.Image] = None) -> None:
        duration = random.randint(*self.config.DISTRACTION_DURATION)
        logger.info(f"DISTRACTION: Resting for {duration}s...")
        time.sleep(duration)
        self.next_distraction_run = self.run_count + random.randint(*self.config.DISTRACTION_CHANCE)
        self.quest_watchdog = time.time() 
        self.fatigue_start_time = time.time()
        self.transition_to("RECOVERY")

    def retire_from_quest(self, haystack: Optional[Image.Image] = None) -> None:
        logger.warning("Retiring sequence...")
        if self.find_image("retire", haystack=haystack):
            self.smart_click("retire", "retire")
            if self.find_image("okay"): 
                self.smart_click("okay", "confirm")
                if self.find_image("closed_room_coop_quest_menu"): 
                    self.smart_click("closed_room_coop_quest_menu", "final confirm")
        self.transition_to("MENU")

    def recover_game(self) -> None:
        self.consecutive_recovery_count += 1
        if self.consecutive_recovery_count > self.config.MAX_CONSECUTIVE_RECOVERIES:
            logger.error(f"FATAL: Exceeded {self.config.MAX_CONSECUTIVE_RECOVERIES} consecutive recoveries. Game is permanently stuck or crashing.")
            sys.exit(1)
            
        logger.warning(f"HARD RECOVERY initiated (Attempt {self.consecutive_recovery_count}/{self.config.MAX_CONSECUTIVE_RECOVERIES})...")
        try: subprocess.run(["pkill", "-f", "BleachBraveSouls.exe"], stderr=subprocess.DEVNULL)
        except Exception: pass

        try:
            if hasattr(self, 'disp') and self.disp: self.disp.close()
            self.disp = display.Display()
        except Exception: pass

        self.region = None 
        self.win_id = None

        time.sleep(self.config.WAIT_RESTART)
        subprocess.Popen(["steam", "-applaunch", "1201240"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        start = time.time()
        window_found = False
        while time.time() - start < self.config.TIMEOUT_GAME_START:
            try:
                self.get_game_region()
                self.setup_window_properties()
                window_found = True
                break
            except GameWindowNotFoundError:
                time.sleep(self.config.WAIT_RESTART)
        
        if not window_found:
            logger.error("Failed to find game window after restart. Exiting to prevent loop.")
            sys.exit(1)
            
        self._startup_window_time = time.time()
        self.transition_to("GAME_STARTUP")

    def save_debug_screenshot(self, name: str) -> None:
        if not self.config.TAKE_DEBUG_SCREENSHOTS: return
        try:
            ts = time.strftime("%Y%m%d_%H%M%S")
            fname = f"screenshots/debug_{self.state}_{name}_{ts}.png"
            pyautogui.screenshot(fname, region=self.region); self._cleanup_screenshots()
        except Exception: pass

    def _cleanup_screenshots(self, max_files: int = 50) -> None:
        try:
            files = [os.path.join("screenshots", f) for f in os.listdir("screenshots") if f.startswith("debug_")]
            if len(files) > max_files:
                files.sort(key=os.path.getmtime)
                for f in files[:-max_files]: os.remove(f)
        except Exception: pass

    def transition_to(self, state: str):
        if self.state != state:
            logger.info(f"TRANSITION [Run:{self.run_count}]: {self.state} -> {state}")
            self.save_debug_screenshot(f"to_{state}")
            self.prev_state, self.state = self.state, state
            self.last_state_change_time = time.time()
            self.disconnect_retry_count = 0
            self._force_refresh = False  # Reset on any major state shift
            if state == "SCAN_ROOMS": self.search_start_time = time.time()
            if state == "MENU": 
                self.quest_watchdog = time.time()
                self.consecutive_recovery_count = 0 # Success: Reaching menu proves recovery worked

    def update_fatigue(self) -> None:
        elapsed = time.time() - self.fatigue_start_time
        self.fatigue_modifier = self.config.FATIGUE_BASE + self.config.FATIGUE_AMPLITUDE * abs(math.sin(elapsed * (2 * math.pi / self.config.FATIGUE_PERIOD)))

    def check_session_limit(self) -> None:
        if (time.time() - self.start_time) / 3600 >= self.config.SESSION_MAX_HOURS:
            logger.warning("SESSION LIMIT."); sys.exit(0)

    def check_quest_watchdog(self) -> None:
        if time.time() - self.quest_watchdog > self.config.TIMEOUT_QUEST_MAX:
            logger.error(f"WATCHDOG: Loop exceeded {self.config.TIMEOUT_QUEST_MAX}s. Hard Restarting."); self.recover_game()

    def ensure_window_ready(self) -> None:
        try:
            old_wid = self.win_id
            self.get_game_region()
            self.window_not_found_count = 0
            
            now = time.time()
            if not hasattr(self, '_last_property_sync'): self._last_property_sync = 0
            if self.win_id != old_wid or now - getattr(self, '_last_property_sync', 0) > self.config.POLL_PROPERTY_SYNC:
                self.setup_window_properties()
                self._last_property_sync = now
        except Exception:
            self.window_not_found_count += 1
            if self.window_not_found_count >= self.config.WINDOW_NOT_FOUND_RETRIES:
                self.recover_game(); self.window_not_found_count = 0

    def get_game_region(self) -> Tuple[int, int, int, int]:
        try:
            wids = subprocess.check_output(["xdotool", "search", "--onlyvisible", "--name", self.config.RAW_TITLE], text=True, stderr=subprocess.DEVNULL).strip().split()
            valid_wid = None
            for wid in wids:
                try:
                    pid = subprocess.check_output(["xdotool", "getwindowpid", wid], text=True, stderr=subprocess.DEVNULL).strip()
                    cmd = subprocess.check_output(["ps", "-p", pid, "-o", "cmd", "--no-headers"], text=True, stderr=subprocess.DEVNULL).strip()
                    if "BleachBraveSouls" in cmd:
                        xprop = subprocess.check_output(["xprop", "-id", wid, "WM_CLASS"], text=True, stderr=subprocess.DEVNULL)
                        if "steam_app_1201240" in xprop.lower() or "bleach" in xprop.lower():
                            valid_wid = wid; break
                except Exception: continue
            if not valid_wid: raise GameWindowNotFoundError()
            geo_lines = subprocess.check_output(["xdotool", "getwindowgeometry", "--shell", valid_wid], text=True, stderr=subprocess.DEVNULL).splitlines()
            geo = {k: int(v) for k, v in (line.split("=") for line in geo_lines if "=" in line)}
            self.win_id = valid_wid; sw, sh = pyautogui.size()
            self.region = (max(0, geo["X"]), max(0, geo["Y"]), min(geo["WIDTH"], sw-geo["X"]), min(geo["HEIGHT"], sh-geo["Y"]))
            return self.region
        except Exception as e: raise GameWindowNotFoundError(e)

    def setup_window_properties(self) -> None:
        if self.win_id and self.config.USE_WMCTRL_ALWAYS_ON_TOP:
            # Targeted by unique ID (-i) to prevent conflicts with Browser/YouTube content
            subprocess.run(["wmctrl", "-i", "-r", self.win_id, "-b", "add,sticky,above"], check=False, stderr=subprocess.DEVNULL)

    def log_session_summary(self) -> None:
        elapsed = time.time() - self.start_time
        logger.info(f"--- SESSION SUMMARY: {elapsed/3600:.2f}h | {self.run_count} runs ---")

    def check_circadian_rhythm(self) -> None:
        if time.time() > self.next_profile_swap:
            self.active_profile = "SHIKAI_NORMAL" if self.active_profile == "SHIKAI_MAX" else "SHIKAI_MAX"
            self.config._apply_profile(self.active_profile)
            
            duration_secs = random.randint(*self.config.CIRCADIAN_PROFILES[self.active_profile]["DURATION_MINS"]) * 60
            self.next_profile_swap = time.time() + duration_secs
            
            logger.info(f"CIRCADIAN SHIFT: Human focus changed. Entering '{self.active_profile}' for {duration_secs/60:.0f} minutes.")

    def run(self, test_restart: bool = False) -> None:
        try:
            if test_restart: self.recover_game()
            else: self.get_game_region(); self.setup_window_properties()
        except Exception: self.recover_game()
        while True:
            self.ensure_window_ready()
            
            # Snapshot Architecture: Single Capture per loop
            try: self.snapshot = pyautogui.screenshot(region=self.region)
            except Exception: self.snapshot = None
            
            self.update_fatigue()
            self.check_circadian_rhythm()
            self.check_session_limit()
            self.check_quest_watchdog()
            if self.handle_global_popups(self.snapshot): continue
            handler = self.handlers.get(self.state)
            if handler: handler(self.snapshot)
            else: self.transition_to("RECOVERY")
            time.sleep(self.config.POLL_MAIN_LOOP)

    def __del__(self):
        try: self.disp.close()
        except Exception: pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-restart", action="store_true")
    parser.add_argument("--debug-screenshots", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Monitor screen and log actions without clicking")
    args = parser.parse_args()
    bot = BBSBot()
    if args.debug_screenshots: bot.config.TAKE_DEBUG_SCREENSHOTS = True
    if args.dry_run:
        logger.info("DRY RUN MODE ENABLED: No clicks will be performed.")
        # Patch the click method to be a no-op
        bot._send_x11_click = lambda x, y: (logger.info(f"[DRY RUN] Would click at ({x}, {y})"), True)[1]
    
    try: bot.run(test_restart=args.test_restart)
    except KeyboardInterrupt: logger.info("Stopped."); bot.log_session_summary()
    except Exception as e: logger.exception(f"Fatal: {e}"); bot.log_session_summary(); sys.exit(1)