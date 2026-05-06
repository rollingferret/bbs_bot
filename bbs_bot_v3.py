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
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("v3_behavior.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


@dataclass
class BotConfiguration:
    """Centralized configuration for the BBS Bot V3.30 'Nuclear Grade'."""

    RAW_TITLE: str = "Bleach: Brave Souls"
    GAME_WINDOW_TITLE: str = "Bleach: Brave Souls"

    # --- Circadian Rhythm Profiles ---
    CIRCADIAN_PROFILES: Dict[str, Dict[str, Any]] = None

    # Current Active Profile (Defaults initialized in post_init)
    DELAY_COGNITIVE: Tuple[float, float] = (0.28, 0.08)
    DELAY_SNIPE: float = 0.20
    DELAY_TRANSITION: float = 0.7
    DELAY_POPUP: float = 1.0
    DELAY_TAP: float = 4.0
    DELAY_READY: float = 0.20
    WAIT_ROOM_LOAD: float = 0.4
    WAIT_SEARCH_AGAIN: float = 1.0
    WAIT_LOBBY_READY: float = 0.5
    WAIT_POST_RETRY: float = 1.5

    # --- Timeouts ---
    TIMEOUT_STUCK: float = 300
    TIMEOUT_QUEST_MAX: float = 600  # Hard watchdog for entire loop (10 mins)
    TIMEOUT_GAME_START: float = 120
    TIMEOUT_READY: float = 30
    TIMEOUT_RETRY: float = 45
    TIMEOUT_RUN_START: float = 300
    TIMEOUT_TAP_VERIFY: float = 15
    TIMEOUT_SEARCH_MAX: float = 60
    TIMEOUT_LOBBY_EXPAND: float = 20.0

    # --- Wait Constants ---
    WAIT_ROOM_LOAD: float = 0.4  # Quick list stabilization
    WAIT_SEARCH_AGAIN: float = 1.0  # Hardcore refresh cadence
    WAIT_LOBBY_READY: float = 0.5  # Snappy lobby soak
    WAIT_RETIRE_STEP: float = 1.0
    WAIT_DISCONNECT_COOLING: float = 10.0
    WAIT_INGAME_AUTO_READY: float = 1.5
    WAIT_POST_RETRY: float = 1.5  # Halved the 3s breather for instant re-queue
    WAIT_REFOCUS: float = 0.02  # Quiet Hybrid Delay
    WAIT_RESTART: float = 5.0  # Game relaunch buffer
    WAIT_STARTUP_STEP: float = 0.5  # Splash screen pause

    # --- Vision & Matching ---
    CONF_NORMAL: float = 0.80
    CONF_HIGH: float = 0.95
    CONF_READY: float = 0.95
    CONF_LOOSE: float = 0.70
    CONF_POPUP: float = 0.98
    AUTO_MATCH_CONFIDENCE: float = 0.92

    # --- Matching Algorithm ---
    ROOM_MATCH_WEIGHT: float = 0.1
    MAX_RULE_DISTANCE: int = 110
    AUTO_ICON_DEDUPE_DIST: int = 60

    # --- Operational Safety ---
    WINDOW_NOT_FOUND_RETRIES: int = 5
    MAX_DISCONNECT_RETRIES: int = 3
    SESSION_MAX_HOURS: int = 16
    POLL_MAIN_LOOP: float = 0.1
    POLL_UI_VERIFY: float = 0.1  # Relaxed to 10fps to prevent CPU/X11 lag
    POLL_RECOVERY: float = 0.5  # Baseline anchor scan
    POLL_RUNNING: float = 2.0  # End-of-quest check
    HEARTBEAT_INTERVAL: float = 60

    # --- Behavioral Stealth ---
    FATIGUE_INCREASE_RATE: float = 0.001
    MAX_FATIGUE_MODIFIER: float = 1.15
    DISTRACTION_CHANCE: Tuple[int, int] = (25, 45)
    DISTRACTION_DURATION: Tuple[int, int] = (120, 480)

    # --- Technical Flags ---
    TAKE_DEBUG_SCREENSHOTS: bool = False
    MANAGE_INGAME_AUTO: bool = True
    USE_WMCTRL_ALWAYS_ON_TOP: bool = True

    TEMPLATES: Dict[str, str] = None

    def __post_init__(self):
        self.CIRCADIAN_PROFILES = {
            "SHIKAI_MAX": {
                "DELAY_COGNITIVE": (0.28, 0.08),
                "DELAY_SNIPE": 0.20,
                "DELAY_TRANSITION": 0.7,
                "DELAY_POPUP": 1.0,
                "DELAY_READY": 0.20,
                "WAIT_ROOM_LOAD": 0.4,
                "WAIT_SEARCH_AGAIN": 1.0,
                "WAIT_LOBBY_READY": 0.5,
                "WAIT_POST_RETRY": 2.0,
                "DURATION_MINS": (45, 90),  # Sweaty grinding
            },
            "SHIKAI_NORMAL": {
                "DELAY_COGNITIVE": (0.35, 0.12),
                "DELAY_SNIPE": 0.35,
                "DELAY_TRANSITION": 1.2,
                "DELAY_POPUP": 1.5,
                "DELAY_READY": 0.40,
                "WAIT_ROOM_LOAD": 0.8,
                "WAIT_SEARCH_AGAIN": 1.8,
                "WAIT_LOBBY_READY": 1.0,
                "WAIT_POST_RETRY": 3.5,
                "DURATION_MINS": (60, 180),  # Watching Netflix
            },
        }
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
            "unavailable_close": "images/unavailable_close.png",
            "disconnect_retry": "images/disconnect_rerty.png",
        }


def human_delay(
    profile: Union[float, Tuple[float, float]], fatigue: float = 1.0
) -> None:
    if isinstance(profile, (float, int)):
        mu, sigma = float(profile), float(profile) * 0.1
    else:
        mu, sigma = profile
    delay = random.gauss(mu * fatigue, sigma)
    time.sleep(max(delay, (mu * fatigue) * 0.05))


class GameWindowNotFoundError(Exception):
    pass


class BBSBot:
    """
    Bleach: Brave Souls Autonomous Agent V3.28 'Nuclear Grade'.
    Final Polished Architecture: All Timings in Config + Quest Watchdog.
    """

    RECOVERY_MAP: List[Tuple[str, str]] = [
        ("READY", "ready"),
        ("RUNNING", "ingame_auto_on"),
        ("RUNNING", "ingame_auto_off"),
        ("CHECK_RUN_START", "retire"),
        ("FINISH", "tap1"),
        ("FINISH", "tap2"),
        ("FINISH", "retry"),
        ("SCAN_ROOMS", "search_again"),
        ("ENTER_ROOM_LIST", "enter_room_button"),
        ("MENU", "open_coop_quest"),
        ("MENU", "coop_quest"),
        ("GAME_STARTUP", "game_start"),
        ("GAME_STARTUP", "close_news"),
        ("GAME_STARTUP", "coop_1"),
        ("GAME_STARTUP", "coop_2"),
        ("MENU", "closed_room_coop_quest_menu"),
        ("SCAN_ROOMS", "close"),
        ("SCAN_ROOMS", "unavailable_close"),
        ("MENU", "disconnect_retry"),
    ]

    def __init__(self, config: BotConfiguration = BotConfiguration()) -> None:
        self.config = config

        # Initialize Circadian Rhythm to start strong
        self.active_profile: str = "SHIKAI_MAX"
        self.next_profile_swap: float = (
            time.time()
            + random.randint(
                *self.config.CIRCADIAN_PROFILES["SHIKAI_MAX"]["DURATION_MINS"]
            )
            * 60
        )

        self.state: str = "RECOVERY"
        self.prev_state: Optional[str] = None
        self.run_count: int = 0
        self.start_time: float = time.time()
        self.last_state_change_time: float = time.time()
        self.quest_watchdog: float = time.time()  # Persistent timer across states
        self.last_heartbeat: float = 0
        self.region: Optional[Tuple[int, int, int, int]] = None
        self.win_id: Optional[str] = None
        self.fatigue_modifier: float = 1.0
        self.disconnect_retry_count: int = 0
        self.window_not_found_count: int = 0
        self.search_start_time: float = 0
        self.next_distraction_run: int = random.randint(*self.config.DISTRACTION_CHANCE)
        self.state_history: List[str] = []

        self.handlers = {
            "MENU": self.handle_menu,
            "ENTER_ROOM_LIST": self.handle_enter_room_list,
            "SCAN_ROOMS": self.handle_scan_rooms,
            "READY": self.handle_ready,
            "CHECK_RUN_START": self.handle_check_run_start,
            "RUNNING": self.handle_running,
            "FINISH": self.handle_finish,
            "DISTRACTION": self.handle_distraction,
            "RECOVERY": self.handle_recovery,
            "GAME_STARTUP": self.handle_game_startup,
        }

        self.cached_templates: Dict[str, Image.Image] = {}
        self._load_templates()
        pyautogui.FAILSAFE = False
        self.check_dependencies()

        try:
            self.disp = display.Display()
        except:
            logger.error("FATAL: X11 Display error.")
            sys.exit(1)

        logger.info("BBS Bot V3.32 'Startup Hardening' Initialized.")

    def _load_templates(self) -> None:
        for key, path in self.config.TEMPLATES.items():
            try:
                self.cached_templates[key] = Image.open(path).convert("RGB")
            except Exception as e:
                logger.error(f"Failed to cache {key}: {e}")

    def check_dependencies(self) -> None:
        for cmd in ["xdotool", "wmctrl", "pkill", "xprop"]:
            if subprocess.run(["which", cmd], capture_output=True).returncode != 0:
                logger.error(f"FATAL: Missing dependency: {cmd}")
                sys.exit(1)

    # --- VISION ---
    def get_ui_region(self, element: str) -> Optional[Tuple[int, int, int, int]]:
        if not self.region:
            return None
        gx, gy, gw, gh = self.region
        if element == "auto":
            return (gx + gw // 2, gy + gh // 2, gw // 2, gh // 2)
        if element == "center_popup":
            return (gx + gw // 4, gy + gh // 4, gw // 2, gh // 2)
        return self.region

    def find_image(
        self,
        key: str,
        confidence: Optional[float] = None,
        region: Optional[Tuple] = None,
    ) -> Optional[pyscreeze.Box]:
        template = self.cached_templates.get(key)
        conf = confidence or self.config.CONF_NORMAL
        reg = region or self.region
        if not template or not reg:
            return None
        try:
            res = pyautogui.locateOnScreen(template, region=reg, confidence=conf)
            if res:
                return res
            return pyautogui.locateOnScreen(
                template, region=reg, confidence=conf - 0.05
            )
        except:
            return None

    def find_stable_image(
        self,
        key: str,
        confidence: Optional[float] = None,
        region: Optional[Tuple] = None,
        frames: int = 2,
    ) -> Optional[pyscreeze.Box]:
        for _ in range(frames):
            res = self.find_image(key, confidence, region)
            if not res:
                return None
            time.sleep(self.config.POLL_UI_VERIFY)
        return res

    def find_all(self, key: str, confidence: float = 0.8) -> List[pyscreeze.Box]:
        template = self.cached_templates.get(key)
        if not template or not self.region:
            return []
        try:
            res = list(
                pyautogui.locateAllOnScreen(
                    template, region=self.region, confidence=confidence
                )
            )
            if res:
                return res
            return list(
                pyautogui.locateAllOnScreen(
                    template, region=self.region, confidence=confidence - 0.05
                )
            )
        except:
            return []

    # --- ACTIONS ---
    def smart_click(
        self,
        box: pyscreeze.Box,
        description: str = "element",
        custom_delay: Optional[Union[float, Tuple[float, float]]] = None,
    ) -> bool:
        human_delay(custom_delay or self.config.DELAY_COGNITIVE, self.fatigue_modifier)
        mu_x, mu_y = box.left + box.width / 2, box.top + box.height / 2
        sigma_x, sigma_y = box.width / 5, box.height / 5
        click_x, click_y = (
            int(random.gauss(mu_x, sigma_x)),
            int(random.gauss(mu_y, sigma_y)),
        )

        click_x = max(box.left, min(click_x, box.left + box.width - 1))
        click_y = max(box.top, min(click_y, box.top + box.height - 1))

        current_focus = None
        try:
            wid_raw = subprocess.check_output(
                ["xdotool", "getactivewindow"], text=True, stderr=subprocess.DEVNULL
            ).strip()
            if wid_raw:
                current_focus = wid_raw
        except:
            pass

        success = self._send_x11_click(click_x, click_y)

        if success and current_focus and current_focus != self.win_id:
            time.sleep(self.config.WAIT_REFOCUS)  # Configured refocus gap
            try:
                subprocess.run(
                    ["xdotool", "windowactivate", "--sync", current_focus],
                    check=False,
                    stderr=subprocess.DEVNULL,
                )
            except:
                pass

        logger.info(f"CLICK: {description} at ({click_x}, {click_y})")
        return success

    def _send_x11_click(self, x: int, y: int) -> bool:
        try:
            window = self.disp.create_resource_object("window", int(self.win_id))
            geom = window.get_geometry()
            rel_x, rel_y = x - geom.x, y - geom.y
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
        except:
            return False

    def smart_click_and_verify(
        self,
        box: pyscreeze.Box,
        description: str,
        verify_key: str,
        timeout: float = 5.0,
        target_state: Optional[str] = None,
    ) -> bool:
        if self.smart_click(box, description):
            start = time.time()
            while time.time() - start < timeout:
                if not self.find_image(verify_key, confidence=0.85):
                    if target_state:
                        self.transition_to(target_state)
                    return True
                time.sleep(self.config.POLL_UI_VERIFY)
        return False

    # --- VIGILANCE ---
    def handle_global_popups(self) -> bool:
        popups = [
            "close",
            "close_news",
            "okay",
            "unavailable_close",
            "closed_room_coop_quest_menu",
            "disconnect_retry",
        ]
        for key in popups:
            conf = 0.99 if key == "disconnect_retry" else self.config.CONF_POPUP
            reg = self.region
            if key in [
                "okay",
                "closed_room_coop_quest_menu",
                "disconnect_retry",
                "close",
                "unavailable_close",
            ]:
                reg = self.get_ui_region("center_popup")

            box = self.find_image(key, confidence=conf, region=reg)
            if box:
                logger.warning(f"GLOBAL: Popup '{key}' confirmed")
                if key == "disconnect_retry":
                    self.disconnect_retry_count += 1
                    if self.disconnect_retry_count > self.config.MAX_DISCONNECT_RETRIES:
                        self.recover_game()
                        return True

                self.smart_click_and_verify(box, f"dismiss {key}", key, timeout=3.0)
                if key == "disconnect_retry":
                    time.sleep(self.config.WAIT_DISCONNECT_COOLING)
                else:
                    human_delay(self.config.DELAY_POPUP, self.fatigue_modifier)

                self.transition_to("MENU")
                return True
        return False

    # --- PROCEDURAL HANDLERS ---
    def handle_menu(self) -> None:
        if self.find_image("enter_room_button"):
            self.transition_to("ENTER_ROOM_LIST")
            return
        if self.find_image("ready"):
            self.transition_to("READY")
            return

        start_time = time.time()
        while time.time() - start_time < 20:
            # 1. Check if we are already on the specific quest menu
            qbox = self.find_image("open_coop_quest")
            if qbox:
                self.smart_click(qbox, "specific quest")
                v_start = time.time()
                while time.time() - v_start < 5.0:
                    if self.find_image("enter_room_button"):
                        self.transition_to("ENTER_ROOM_LIST")
                        return
                    time.sleep(self.config.POLL_UI_VERIFY)
                return

            # 2. Check if we are on the main game lobby (need to expand the menu)
            box = self.find_image("coop_quest")
            if box:
                self.smart_click(box, "expand menu")
                time.sleep(self.config.DELAY_TRANSITION)
                continue  # Loop back to find the specific quest banner

            # If neither is found, wait briefly and try again
            time.sleep(self.config.POLL_UI_VERIFY)

        self.transition_to("RECOVERY")

    def handle_enter_room_list(self) -> None:
        if self.find_image("ready"):
            self.transition_to("READY")
            return

        # STABILITY GUARD: Don't click join button while it's still animating in
        ebit = self.find_stable_image("enter_room_button")
        if ebit:
            # HUMAN PACING: Screen Recognition Pause.
            # A human takes longer to react to a newly loaded screen than to a menu they are already navigating.
            recognition_delay = (
                self.config.DELAY_TRANSITION * 1.2
            )  # Snappier 0.8s recognition
            self.smart_click(ebit, "enter room list", custom_delay=recognition_delay)

            start_load = time.time()
            while time.time() - start_load < 5.0:
                # If there are rooms, we see 'auto'. If it's empty, we see 'search_again'.
                if self.find_image("auto") or self.find_image("search_again"):
                    time.sleep(self.config.WAIT_ROOM_LOAD)
                    self.transition_to("SCAN_ROOMS")
                    return
                time.sleep(self.config.POLL_UI_VERIFY)
            logger.warning("Failed to verify room list load. Re-evaluating state.")
            return  # Let next tick decide if we go to RECOVERY or retry
        self.transition_to("RECOVERY")

    def handle_scan_rooms(self) -> None:
        if self.find_image("ready"):
            self.transition_to("READY")
            return

        if time.time() - self.search_start_time > self.config.TIMEOUT_SEARCH_MAX:
            self.transition_to("MENU")
            return
        autos = self.find_all("auto")
        if autos:
            rules = self.find_all("room_rules_valid", confidence=self.config.CONF_LOOSE)
            valid = self.match_rooms(autos, rules)

            for auto, rule in valid:
                px, py = (
                    (auto.left + rule.left + rule.width) // 2,
                    auto.top + auto.height // 2,
                )
                self.smart_click(
                    pyscreeze.Box(px - 20, py - 10, 40, 20),
                    "snatch room",
                    custom_delay=self.config.DELAY_SNIPE,
                )

                start_v = time.time()
                while time.time() - start_v < 6.0:
                    rbox = self.find_stable_image(
                        "ready", confidence=self.config.CONF_READY
                    )
                    if rbox:
                        time.sleep(self.config.WAIT_LOBBY_READY)
                        if self.smart_click(
                            rbox, "snap ready", custom_delay=self.config.DELAY_READY
                        ):
                            vv_start = time.time()
                            while time.time() - vv_start < 5.0:
                                if self.find_image("retire"):
                                    self.transition_to("CHECK_RUN_START")
                                    return
                                time.sleep(self.config.POLL_UI_VERIFY)
                        return
                    if self.find_image("closed_room_coop_quest_menu", confidence=0.9):
                        box = self.find_image("closed_room_coop_quest_menu")
                        if box:
                            self.smart_click(box, "close room full")
                            break  # Next room
                    if self.find_image("close", confidence=0.9):
                        box = self.find_image("close")
                        if box:
                            self.smart_click(box, "close unavailable")
                            break  # Next room
                    time.sleep(self.config.POLL_UI_VERIFY)

        sabox = self.find_image("search_again")
        if sabox:
            self.smart_click(sabox, "search again")
            self.search_start_time = time.time()  # Reset timeout if actively searching
            time.sleep(self.config.WAIT_SEARCH_AGAIN)

    def match_rooms(self, autos, rules):
        valid = []
        for a in self.dedupe_autos(autos):
            ax, ay = a.left + a.width // 2, a.top + a.height // 2
            best_r, min_d = None, float("inf")
            for r in rules:
                rx, ry = r.left + r.width // 2, r.top + r.height // 2
                if ry > ay:
                    d = abs(ry - ay) + abs(rx - ax) * self.config.ROOM_MATCH_WEIGHT
                    if d < min_d and d < self.config.MAX_RULE_DISTANCE:
                        min_d, best_r = d, r
            if best_r:
                valid.append((a, best_r))
        return valid

    def dedupe_autos(self, matches):
        unique = []
        for m in matches:
            cx, cy = m.left + m.width // 2, m.top + m.height // 2
            if not any(
                (
                    (cx - (u.left + u.width // 2)) ** 2
                    + (cy - (u.top + u.height // 2)) ** 2
                )
                ** 0.5
                < self.config.AUTO_ICON_DEDUPE_DIST
                for u in unique
            ):
                unique.append(m)
        return unique

    def handle_ready(self) -> None:
        rbox = self.find_stable_image("ready")
        if rbox:
            if self.smart_click(
                rbox, "ready button", custom_delay=self.config.DELAY_READY
            ):
                v_start = time.time()
                while time.time() - v_start < 5.0:
                    if self.find_image("retire"):
                        self.transition_to("CHECK_RUN_START")
                        return
                    time.sleep(self.config.POLL_UI_VERIFY)
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_READY:
            self.transition_to("RECOVERY")

    def handle_check_run_start(self) -> None:
        reg = self.get_ui_region("auto")
        if self.find_image(
            "ingame_auto_on", confidence=self.config.CONF_HIGH, region=reg
        ):
            self.transition_to("RUNNING")
            return
        offbox = self.find_image(
            "ingame_auto_off", confidence=self.config.AUTO_MATCH_CONFIDENCE, region=reg
        )
        if offbox:
            if self.config.MANAGE_INGAME_AUTO:
                self.smart_click(offbox, "enable auto", custom_delay=1.5)
            self.transition_to("RUNNING")
            return
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_RUN_START:
            self.retire_from_quest()

    def handle_running(self) -> None:
        if self.find_image("tap1"):
            self.transition_to("FINISH")
            return
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_QUEST_MAX:
            self.transition_to("RECOVERY")
        time.sleep(self.config.POLL_RUNNING)

    def handle_finish(self) -> None:
        tap1_box = self.find_image("tap1")
        if tap1_box:
            if self.smart_click(tap1_box, "reward tap1"):
                time.sleep(self.config.DELAY_TAP)
                self.quest_watchdog = time.time()
            return
        tap2_box = self.find_image("tap2")
        if tap2_box:
            if self.smart_click(tap2_box, "reward tap2"):
                time.sleep(self.config.DELAY_TRANSITION)
                self.quest_watchdog = time.time()
            return
        rt = self.find_image("retry")
        if rt:
            if self.smart_click_and_verify(rt, "retry quest", "retry"):
                self.run_count += 1
                if self.run_count >= self.next_distraction_run:
                    self.transition_to("DISTRACTION")
                else:
                    time.sleep(self.config.WAIT_POST_RETRY)
                    self.transition_to("ENTER_ROOM_LIST")
                return
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_TAP_VERIFY:
            self.transition_to("RECOVERY")

    def handle_game_startup(self) -> None:
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_GAME_START:
            logger.error("Startup hung. Restarting.")
            self.recover_game()
            return

        for key in ["game_start", "close_news", "coop_1", "coop_2"]:
            box = self.find_image(key)
            if box:
                self.smart_click(box, f"startup {key}")
                time.sleep(self.config.WAIT_STARTUP_STEP)
                return  # Yield to main loop
        if self.find_image("coop_quest") or self.find_image("open_coop_quest"):
            self.transition_to("MENU")

    def handle_recovery(self) -> None:
        elapsed = time.time() - self.last_state_change_time
        if int(elapsed) > 0 and int(elapsed) % 10 == 0:
            if (
                not hasattr(self, "_last_recovery_log")
                or int(elapsed) != self._last_recovery_log
            ):
                logger.info(
                    f"RECOVERY: Still searching for anchors... ({elapsed:.0f}s elapsed)"
                )
                self._last_recovery_log = int(elapsed)
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_STUCK:
            self.recover_game()
        else:
            for state, template in self.RECOVERY_MAP:
                if self.find_image(template):
                    self.transition_to(state)
                    return
            time.sleep(self.config.POLL_RECOVERY)

    def handle_distraction(self) -> None:
        duration = random.randint(*self.config.DISTRACTION_DURATION)
        logger.info(f"DISTRACTION: Resting for {duration}s...")
        time.sleep(duration)
        self.next_distraction_run = self.run_count + random.randint(
            *self.config.DISTRACTION_CHANCE
        )
        self.quest_watchdog = time.time()  # Reset watchdog after coffee break
        self.transition_to("RECOVERY")

    def retire_from_quest(self) -> None:
        logger.warning("Retiring sequence...")
        rbox = self.find_image("retire")
        if rbox:
            self.smart_click(rbox, "retire")
            time.sleep(self.config.WAIT_RETIRE_STEP)
            ok = self.find_image("okay")
            if ok:
                self.smart_click(ok, "confirm")
                time.sleep(self.config.WAIT_RETIRE_STEP)
                final = self.find_image("closed_room_coop_quest_menu")
                if final:
                    self.smart_click(final, "final confirm")
        self.transition_to("MENU")

    def recover_game(self) -> None:
        logger.warning("HARD RECOVERY initiated...")
        try:
            subprocess.run(
                ["pkill", "-f", "BleachBraveSouls.exe"], stderr=subprocess.DEVNULL
            )
        except:
            pass

        # Regenerate X11 Socket to prevent permanent paralysis on display server crash
        try:
            if hasattr(self, "disp") and self.disp:
                self.disp.close()
            self.disp = display.Display()
        except:
            pass

        time.sleep(self.config.WAIT_RESTART)
        subprocess.Popen(
            ["steam", "-applaunch", "1201240"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        start = time.time()
        while time.time() - start < self.config.TIMEOUT_GAME_START:
            if self.find_image("game_start"):
                break
            time.sleep(self.config.WAIT_RESTART)
        self.get_game_region()
        self.setup_window_properties()
        self.transition_to("GAME_STARTUP")
        self.quest_watchdog = time.time()  # Reset watchdog after hard recovery

    def save_debug_screenshot(self, name: str) -> None:
        if not self.config.TAKE_DEBUG_SCREENSHOTS:
            return
        try:
            ts = time.strftime("%Y%m%d_%H%M%S")
            fname = f"screenshots/debug_{self.state}_{name}_{ts}.png"
            pyautogui.screenshot(fname, region=self.region)
            self._cleanup_screenshots()
        except:
            pass

    def _cleanup_screenshots(self, max_files: int = 50) -> None:
        try:
            files = [
                os.path.join("screenshots", f)
                for f in os.listdir("screenshots")
                if f.startswith("debug_")
            ]
            if len(files) > max_files:
                files.sort(key=os.path.getmtime)
                for f in files[:-max_files]:
                    os.remove(f)
        except:
            pass

    def transition_to(self, state: str):
        if self.state != state:
            logger.info(f"TRANSITION: {self.state} -> {state}")
            self.save_debug_screenshot(f"to_{state}")
            self.prev_state, self.state = self.state, state
            self.last_state_change_time = time.time()
            self.disconnect_retry_count = 0
            if state == "SCAN_ROOMS":
                self.search_start_time = time.time()

    def update_fatigue(self) -> None:
        elapsed = time.time() - self.start_time
        self.fatigue_modifier = 1.0 + 0.15 * abs(
            math.sin(elapsed * (2 * math.pi / 1800))
        )

    def check_session_limit(self) -> None:
        if (time.time() - self.start_time) / 3600 >= self.config.SESSION_MAX_HOURS:
            logger.warning("SESSION LIMIT.")
            sys.exit(0)

    def check_quest_watchdog(self) -> None:
        """Nuclear Guard: Detect infinite loops in stuck quests."""
        if time.time() - self.quest_watchdog > self.config.TIMEOUT_QUEST_MAX:
            logger.error(
                f"WATCHDOG: Loop exceeded {self.config.TIMEOUT_QUEST_MAX}s. Hard Restarting."
            )
            self.recover_game()

    def ensure_window_ready(self) -> None:
        # CPU OPTIMIZATION: Only poll OS for window geometry every 5 seconds
        if (
            hasattr(self, "last_window_check")
            and time.time() - self.last_window_check < 5.0
        ):
            return
        self.last_window_check = time.time()

        try:
            self.get_game_region()
            self.window_not_found_count = 0
        except:
            self.window_not_found_count += 1
            if self.window_not_found_count >= self.config.WINDOW_NOT_FOUND_RETRIES:
                self.recover_game()
                self.window_not_found_count = 0

    def get_game_region(self) -> Tuple[int, int, int, int]:
        try:
            wids = (
                subprocess.check_output(
                    [
                        "xdotool",
                        "search",
                        "--onlyvisible",
                        "--name",
                        self.config.RAW_TITLE,
                    ],
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
                .strip()
                .split()
            )
            valid_wid = None
            for wid in wids:
                try:
                    pid = subprocess.check_output(
                        ["xdotool", "getwindowpid", wid],
                        text=True,
                        stderr=subprocess.DEVNULL,
                    ).strip()
                    cmd = subprocess.check_output(
                        ["ps", "-p", pid, "-o", "cmd", "--no-headers"],
                        text=True,
                        stderr=subprocess.DEVNULL,
                    ).strip()
                    if "BleachBraveSouls" in cmd:
                        xprop = subprocess.check_output(
                            ["xprop", "-id", wid, "WM_CLASS"],
                            text=True,
                            stderr=subprocess.DEVNULL,
                        )
                        if (
                            "steam_app_1201240" in xprop.lower()
                            or "bleach" in xprop.lower()
                        ):
                            valid_wid = wid
                            break
                except:
                    continue
            if not valid_wid:
                raise GameWindowNotFoundError()
            geo_lines = subprocess.check_output(
                ["xdotool", "getwindowgeometry", "--shell", valid_wid],
                text=True,
                stderr=subprocess.DEVNULL,
            ).splitlines()
            geo = {
                k: int(v)
                for k, v in (line.split("=") for line in geo_lines if "=" in line)
            }
            self.win_id = valid_wid
            sw, sh = pyautogui.size()
            self.region = (
                max(0, geo["X"]),
                max(0, geo["Y"]),
                min(geo["WIDTH"], sw - geo["X"]),
                min(geo["HEIGHT"], sh - geo["Y"]),
            )
            return self.region
        except Exception as e:
            raise GameWindowNotFoundError(e)

    def setup_window_properties(self) -> None:
        if self.win_id and self.config.USE_WMCTRL_ALWAYS_ON_TOP:
            subprocess.run(
                [
                    "wmctrl",
                    "-i",
                    "-r",
                    self.win_id,
                    "-b",
                    "add,sticky,above,skip_taskbar,skip_pager",
                ],
                check=False,
                stderr=subprocess.DEVNULL,
            )

    def log_session_summary(self) -> None:
        elapsed = time.time() - self.start_time
        logger.info(
            f"--- SESSION SUMMARY: {elapsed / 3600:.2f}h | {self.run_count} runs ---"
        )

    def check_circadian_rhythm(self) -> None:
        """Dynamically swap profiles to simulate a human's focus/fatigue cycle."""
        if time.time() > self.next_profile_swap:
            self.active_profile = (
                "SHIKAI_NORMAL" if self.active_profile == "SHIKAI_MAX" else "SHIKAI_MAX"
            )
            prof = self.config.CIRCADIAN_PROFILES[self.active_profile]

            # Apply new psychological profile
            self.config.DELAY_COGNITIVE = prof["DELAY_COGNITIVE"]
            self.config.DELAY_SNIPE = prof["DELAY_SNIPE"]
            self.config.DELAY_TRANSITION = prof["DELAY_TRANSITION"]
            self.config.DELAY_POPUP = prof["DELAY_POPUP"]
            self.config.DELAY_READY = prof["DELAY_READY"]
            self.config.WAIT_ROOM_LOAD = prof["WAIT_ROOM_LOAD"]
            self.config.WAIT_SEARCH_AGAIN = prof["WAIT_SEARCH_AGAIN"]
            self.config.WAIT_LOBBY_READY = prof["WAIT_LOBBY_READY"]
            self.config.WAIT_POST_RETRY = prof["WAIT_POST_RETRY"]

            duration_secs = random.randint(*prof["DURATION_MINS"]) * 60
            self.next_profile_swap = time.time() + duration_secs

            logger.info(
                f"CIRCADIAN SHIFT: Human focus changed. Entering '{self.active_profile}' for {duration_secs / 60:.0f} minutes."
            )

    def run(self, test_restart: bool = False) -> None:
        try:
            if test_restart:
                self.recover_game()
            else:
                self.get_game_region()
                self.setup_window_properties()
        except:
            self.recover_game()
        while True:
            self.ensure_window_ready()
            self.update_fatigue()
            self.check_circadian_rhythm()
            self.check_session_limit()
            self.check_quest_watchdog()
            if self.handle_global_popups():
                continue
            handler = self.handlers.get(self.state)
            if handler:
                handler()
            else:
                self.transition_to("RECOVERY")
            time.sleep(self.config.POLL_MAIN_LOOP)

    def __del__(self):
        try:
            self.disp.close()
        except:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-restart", action="store_true")
    parser.add_argument("--debug-screenshots", action="store_true")
    args = parser.parse_args()
    bot = BBSBot()
    if args.debug_screenshots:
        bot.config.TAKE_DEBUG_SCREENSHOTS = True
    try:
        bot.run(test_restart=args.test_restart)
    except KeyboardInterrupt:
        logger.info("Stopped.")
        bot.log_session_summary()
    except Exception as e:
        logger.exception(f"Fatal: {e}")
        bot.log_session_summary()
        sys.exit(1)
