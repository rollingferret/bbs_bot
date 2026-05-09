import argparse
import logging
import math
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
from Xlib import X, display, protocol  # type: ignore

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("v9_behavior.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


@dataclass
class BotConfiguration:
    """Centralized configuration for the BBS Bot V9.0 'Hardened Sentinel'."""

    RAW_TITLE: str = "Bleach: Brave Souls"

    # --- Circadian Rhythm Profiles ---
    CIRCADIAN_PROFILES: Optional[Dict[str, Dict[str, Any]]] = None

    # Current Active Profile (Defaults)
    DELAY_COGNITIVE: Tuple[float, float] = (0.78, 0.05)
    DELAY_SNIPE: float = 0.20
    DELAY_POPUP: float = 1.5
    DELAY_READY: float = 0.90
    WAIT_ROOM_LOAD: float = 1.0
    WAIT_SEARCH_AGAIN: float = 1.5
    WAIT_LOBBY_READY: float = 0.3

    WAIT_POST_RETRY: float = 1.0
    WAIT_REFOCUS: float = 0.02
    WAIT_REFRESH_COOLDOWN: float = 2.0
    DELAY_POST_POPUP: float = 0.3
    WAIT_STABILIZE_ANIMATION: float = 0.8
    SAFETY_FLOOR_FACTOR: float = 0.05

    # --- Timeouts ---
    TIMEOUT_STUCK: float = 300
    TIMEOUT_QUEST_MAX: float = 300
    TIMEOUT_GAME_START: float = 120
    TIMEOUT_READY: float = 30
    TIMEOUT_RUN_START: float = 300
    TIMEOUT_TAP_VERIFY: float = 15
    TIMEOUT_LOBBY_EXPAND: float = 20.0
    TIMEOUT_LOBBY_JOIN: float = 10.0
    TIMEOUT_ROOM_LIST_LOAD: float = 5.0
    TIMEOUT_SCAN_IDLE: float = 20.0
    TIMEOUT_VERIFY_UI: float = 0.8

    # --- Wait Constants ---
    WAIT_DISCONNECT_COOLING: Tuple[int, int] = (8, 16)
    WAIT_RESTART: float = 5.0

    # --- Vision & Matching ---
    CONF_NORMAL: float = 0.80
    CONF_HIGH: float = 0.90
    CONF_READY: float = 0.95
    CONF_STARTUP: float = 0.85
    CONF_LOOSE: float = 0.70
    CONF_POPUP: float = 0.85
    CONF_VERIFY_ACTION: float = 0.80
    AUTO_MATCH_CONFIDENCE: float = 0.995
    AUTO_ON_CONFIDENCE: float = 0.85

    # --- Matching Algorithm ---
    ROOM_MATCH_WEIGHT: float = 0.1
    MAX_RULE_DISTANCE: int = 110
    AUTO_ICON_DEDUPE_DIST: int = 60
    CLICK_SIGMA_FACTOR: float = 10.0
    SNATCH_BOX_OFFSET: Tuple[int, int] = (20, 10)
    SNATCH_BOX_DIM: Tuple[int, int] = (40, 20)

    # --- All-Auto Policy ---
    ALLOW_ALL_AUTO_ROOMS: bool = False
    ALL_AUTO_SNATCH_BOX_DIM: Tuple[int, int] = (200, 40)

    # --- Operational Safety ---
    WINDOW_NOT_FOUND_RETRIES: int = 60
    MAX_DISCONNECT_RETRIES: Tuple[int, int] = (8, 16)
    MAX_CONSECUTIVE_RECOVERIES: int = 3
    SESSION_MAX_HOURS: int = 16
    POLL_MAIN_LOOP: float = 0.05
    POLL_UI_VERIFY: float = 0.05
    POLL_POPUP: float = 0.5
    POLL_RECOVERY: float = 0.5
    POLL_RUNNING: float = 0.5
    POLL_PROPERTY_SYNC: float = 5.0

    CASUAL_LINGER_RUNS: Tuple[int, int] = (8, 16)

    # --- Behavioral Stealth ---
    FATIGUE_BASE: float = 1.0
    FATIGUE_AMPLITUDE: float = 0.15
    FATIGUE_PERIOD: int = 1800
    DISTRACTION_DURATION: Tuple[int, int] = (120, 480)

    # --- Technical Flags ---
    TAKE_DEBUG_SCREENSHOTS: bool = False
    MANAGE_INGAME_AUTO: bool = True
    USE_WMCTRL_ALWAYS_ON_TOP: bool = True

    TEMPLATES: Optional[Dict[str, str]] = field(default=None)

    def __post_init__(self):
        self.CIRCADIAN_PROFILES = {
            "SHIKAI_MAX": {
                "DELAY_COGNITIVE": (0.78, 0.05),
                "DELAY_SNIPE": 0.20,
                "DELAY_POPUP": 1.5,
                "DELAY_READY": 0.90,
                "WAIT_ROOM_LOAD": 1.0,
                "WAIT_SEARCH_AGAIN": 1.5,
                "WAIT_LOBBY_READY": 0.3,
                "WAIT_POST_RETRY": 1.0,
                "WAIT_REFOCUS": 0.02,
                "WAIT_REFRESH_COOLDOWN": 2.0,
                "WAIT_STABILIZE_ANIMATION": 0.8,
                "TIMEOUT_VERIFY_UI": 0.8,
                "DURATION_MINS": (45, 90),
            },
            "SHIKAI_NORMAL": {
                "DELAY_COGNITIVE": (0.95, 0.10),
                "DELAY_SNIPE": 0.40,
                "DELAY_POPUP": 2.0,
                "DELAY_READY": 1.10,
                "WAIT_ROOM_LOAD": 1.2,
                "WAIT_SEARCH_AGAIN": 2.5,
                "WAIT_LOBBY_READY": 0.6,
                "WAIT_POST_RETRY": 2.0,
                "WAIT_REFOCUS": 0.05,
                "WAIT_REFRESH_COOLDOWN": 2.5,
                "WAIT_STABILIZE_ANIMATION": 1.2,
                "TIMEOUT_VERIFY_UI": 1.4,
                "DURATION_MINS": (60, 180),
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
            "room_not_met": "images/room_not_met.png",
            "unavailable_close": "images/unavailable_close.png",
            "disconnect_retry": "images/disconnect_rerty.png",
        }
        self._apply_profile("SHIKAI_MAX")

    def _apply_profile(self, profile_name: str):
        assert self.CIRCADIAN_PROFILES is not None
        s = self.CIRCADIAN_PROFILES[profile_name]
        self.DELAY_COGNITIVE = s["DELAY_COGNITIVE"]
        self.DELAY_SNIPE = s["DELAY_SNIPE"]
        self.DELAY_POPUP = s["DELAY_POPUP"]
        self.DELAY_READY = s["DELAY_READY"]
        self.WAIT_ROOM_LOAD = s["WAIT_ROOM_LOAD"]
        self.WAIT_SEARCH_AGAIN = s["WAIT_SEARCH_AGAIN"]
        self.WAIT_LOBBY_READY = s["WAIT_LOBBY_READY"]
        self.WAIT_POST_RETRY = s["WAIT_POST_RETRY"]
        self.WAIT_REFOCUS = s.get("WAIT_REFOCUS", 0.02)
        self.WAIT_REFRESH_COOLDOWN = s["WAIT_REFRESH_COOLDOWN"]
        self.WAIT_STABILIZE_ANIMATION = s["WAIT_STABILIZE_ANIMATION"]
        self.TIMEOUT_VERIFY_UI = s["TIMEOUT_VERIFY_UI"]


def human_delay(
    profile: Union[float, Tuple[float, float]],
    fatigue: float = 1.0,
    safety_factor: float = 0.05,
) -> None:
    if isinstance(profile, (float, int)):
        base, jitter = profile, profile * 0.1
    else:
        base, jitter = profile
    delay = random.uniform(base - jitter, base + jitter) * fatigue
    time.sleep(max(safety_factor, delay))


class GameWindowNotFoundError(Exception):
    pass


class BBSBot:
    """
    Bleach: Brave Souls Autonomous Agent V9.0 'Hardened Sentinel'.
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
        ("MENU", "coop_1"),
        ("MENU", "coop_2"),
        ("GAME_STARTUP", "game_start"),
        ("MENU", "closed_room_coop_quest_menu"),
        ("SCAN_ROOMS", "room_not_met"),
        ("SCAN_ROOMS", "close"),
        ("SCAN_ROOMS", "unavailable_close"),
        ("GAME_STARTUP", "close_news"),
        ("MENU", "disconnect_retry"),
    ]

    def __init__(self, config: BotConfiguration = BotConfiguration()) -> None:
        self.config = config
        pyautogui.FAILSAFE = False
        assert self.config.CIRCADIAN_PROFILES is not None
        self.active_profile: str = "SHIKAI_MAX"
        self.next_profile_swap = (
            time.time()
            + random.randint(
                *self.config.CIRCADIAN_PROFILES[self.active_profile]["DURATION_MINS"]
            )
            * 60
        )

        self.state: str = "RECOVERY"
        self.run_count: int = 0
        self.start_time: float = time.time()
        self.fatigue_start_time: float = time.time()
        self.last_state_change_time: float = time.time()
        self.win_id: Optional[str] = None
        self.region: Optional[Tuple[int, int, int, int]] = None
        self.cached_templates: Dict[str, Image.Image] = {}
        self.consecutive_recovery_count: int = 0
        self.search_start_time: float = 0
        self._force_refresh: bool = False
        self.next_distraction_run: int = 9999
        self.snapshot: Optional[Image.Image] = None
        self.expected_okay_context: Optional[str] = None
        self._last_popup_check: float = 0.0
        self._last_recovery_log: int = 0
        self._last_property_sync: float = 0.0
        self._last_id_search: float = 0.0
        self._run_counted: bool = False
        self._startup_window_time: float = time.time()
        self.quest_watchdog: float = time.time()
        self.fatigue_modifier: float = 1.0

        self.handlers = {
            "MENU": self.handle_menu,
            "ENTER_ROOM_LIST": self.handle_enter_room_list,
            "SCAN_ROOMS": self.handle_scan_rooms,
            "JOIN_PENDING": self.handle_join_pending,
            "READY": self.handle_ready,
            "CHECK_RUN_START": self.handle_check_run_start,
            "RUNNING": self.handle_running,
            "FINISH": self.handle_finish,
            "DISTRACTION": self.handle_distraction,
            "GAME_STARTUP": self.handle_game_startup,
            "RECOVERY": self.handle_recovery,
        }

        try:
            self.disp = display.Display()
            self.sct = mss.mss()
        except Exception:
            logger.error("FATAL: X11/MSS Display error.")
            sys.exit(1)

        self._load_templates()
        self.check_dependencies()
        logger.info("BBS Bot V9.0 'Hardened Sentinel' Initialized.")

    def _load_templates(self) -> None:
        if not self.config.TEMPLATES:
            return
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

    def get_template_confidence(self, key: str) -> float:
        """Centralized confidence mapping."""
        template_conf = {
            "open_coop_quest": self.config.CONF_HIGH,
            "coop_quest": self.config.CONF_HIGH,
            "coop_1": self.config.CONF_STARTUP,
            "coop_2": self.config.CONF_NORMAL,
            "search_again": self.config.CONF_NORMAL,
            "auto": self.config.CONF_NORMAL,
            "ready": self.config.CONF_READY,
            "tap1": self.config.CONF_NORMAL,
            "tap2": self.config.CONF_NORMAL,
            "retry": self.config.CONF_NORMAL,
            "closed_room_coop_quest_menu": self.config.CONF_POPUP,
            "unavailable_close": self.config.CONF_POPUP,
            "room_not_met": self.config.CONF_POPUP,
            "close": self.config.CONF_POPUP,
            "okay": self.config.CONF_POPUP,
            "close_news": self.config.CONF_STARTUP,
            "game_start": self.config.CONF_NORMAL,
            "disconnect_retry": 0.99,
        }
        return template_conf.get(key, self.config.CONF_NORMAL)

    def find_image(
        self,
        key: str,
        confidence: Optional[float] = None,
        region: Optional[Tuple[int, int, int, int]] = None,
        haystack: Optional[Image.Image] = None,
    ) -> Optional[pyscreeze.Box]:
        template = self.cached_templates.get(key)
        conf = confidence or self.get_template_confidence(key)
        reg = region or self.region
        if not template or not reg or not self.region:
            return None
        try:
            if haystack:
                # Prioritize high-speed snapshots in memory
                # Must adjust coordinates back to root-relative
                h_reg = (
                    reg[0] - self.region[0],
                    reg[1] - self.region[1],
                    reg[2],
                    reg[3],
                )
                res = pyautogui.locate(
                    template, haystack, region=h_reg, confidence=conf
                )
                if res:
                    return pyscreeze.Box(
                        res.left + self.region[0],
                        res.top + self.region[1],
                        res.width,
                        res.height,
                    )
                return None

            # High-speed fallback via MSS
            monitor = {"top": reg[1], "left": reg[0], "width": reg[2], "height": reg[3]}
            sct_img = self.sct.grab(monitor)
            pil_img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            res = pyautogui.locate(template, pil_img, confidence=conf)
            if res:
                return pyscreeze.Box(
                    res.left + reg[0], res.top + reg[1], res.width, res.height
                )
        except Exception:
            pass
        return None

    def find_stable_image(
        self,
        key: str,
        confidence: Optional[float] = None,
        region: Optional[Tuple[int, int, int, int]] = None,
        frames: int = 2,
    ) -> Optional[pyscreeze.Box]:
        for _ in range(frames):
            res = self.find_image(key, confidence, region)
            if not res:
                return None
            time.sleep(self.config.POLL_UI_VERIFY)
        return res

    def find_all(
        self,
        key: str,
        confidence: float = 0.8,
        haystack: Optional[Image.Image] = None,
        region: Optional[Tuple[int, int, int, int]] = None,
    ) -> List[pyscreeze.Box]:
        template = self.cached_templates.get(key)
        reg = region or self.region
        if not template or not reg or not self.region:
            return []
        try:
            if haystack:
                h_reg = (
                    reg[0] - self.region[0],
                    reg[1] - self.region[1],
                    reg[2],
                    reg[3],
                )
                res = list(
                    pyautogui.locateAll(
                        template, haystack, region=h_reg, confidence=confidence
                    )
                )
                return [
                    pyscreeze.Box(
                        r.left + self.region[0],
                        r.top + self.region[1],
                        r.width,
                        r.height,
                    )
                    for r in res
                ]

            monitor = {"top": reg[1], "left": reg[0], "width": reg[2], "height": reg[3]}
            sct_img = self.sct.grab(monitor)
            pil_img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            res = list(pyautogui.locateAll(template, pil_img, confidence=confidence))
            return [
                pyscreeze.Box(r.left + reg[0], r.top + reg[1], r.width, r.height)
                for r in res
            ]
        except Exception:
            return []

    def current_phase(self) -> str:
        return {
            "GAME_STARTUP": "STARTUP_SAFE",
            "MENU": "MENU_NAVIGATION",
            "ENTER_ROOM_LIST": "JOIN_CHOICE",
            "SCAN_ROOMS": "ROOM_SEARCH",
            "JOIN_PENDING": "JOIN_PENDING",
            "READY": "LOBBY_SAFE",
            "CHECK_RUN_START": "JOIN_PENDING",
            "RUNNING": "LIVE_RUN",
            "FINISH": "FINISH_REWARD",
            "RECOVERY": "RECOVERY_CLASSIFY",
            "DISTRACTION": "UNKNOWN_BLOCKED",
        }.get(self.state, "UNKNOWN_BLOCKED")

    def can_click(self, key: str, *, expected_context: Optional[str] = None) -> bool:
        phase = self.current_phase()
        expected = expected_context or getattr(self, "expected_okay_context", None)
        if key == "okay":
            # Allowed during explicit retirement or when re-anchoring
            return expected == "RETIRE_CONFIRM" or self.state in {
                "SCAN_ROOMS",
                "RECOVERY",
                "READY",
                "CHECK_RUN_START",
            }
        allowed_by_phase = {
            "STARTUP_SAFE": {"close_news", "game_start", "coop_1", "coop_2", "close"},
            "MENU_NAVIGATION": {
                "coop_quest",
                "open_coop_quest",
                "close_news",
                "close",
                "coop_1",
                "coop_2",
            },
            "JOIN_CHOICE": {
                "enter_room_button",
                "close",
                "unavailable_close",
                "closed_room_coop_quest_menu",
            },
            "ROOM_SEARCH": {
                "search_again",
                "auto",
                "closed_room_coop_quest_menu",
                "unavailable_close",
                "close",
                "okay",
                "disconnect_retry",
                "room_not_met",
            },
            "LOBBY_SAFE": {
                "ready",
                "closed_room_coop_quest_menu",
                "unavailable_close",
                "close",
                "disconnect_retry",
                "room_not_met",
            },
            "JOIN_PENDING": {
                "ready",
                "closed_room_coop_quest_menu",
                "unavailable_close",
                "close",
                "disconnect_retry",
                "retire",
                "room_not_met",
            },
            "LIVE_RUN": {
                "ingame_auto_off",
                "retire",
                "disconnect_retry",
                "closed_room_coop_quest_menu",
                "unavailable_close",
                "close",
                "room_not_met",
            },
            "FINISH_REWARD": {
                "tap1",
                "tap2",
                "retry",
                "disconnect_retry",
                "close",
                "closed_room_coop_quest_menu",
                "unavailable_close",
                "room_not_met",
            },
            "RECOVERY_CLASSIFY": {
                "closed_room_coop_quest_menu",
                "unavailable_close",
                "close",
                "disconnect_retry",
                "close_news",
                "okay",
                "coop_quest",
                "open_coop_quest",
                "coop_1",
                "coop_2",
                "room_not_met",
            },
        }
        return key in allowed_by_phase.get(phase, set())

    def smart_click(
        self,
        target: Union[str, pyscreeze.Box],
        description: str,
        verify_key: Optional[str] = None,
        target_state: Optional[str] = None,
        wait_for_appearance: bool = False,
        custom_delay: Optional[Union[float, Tuple[float, float]]] = None,
        confidence: Optional[float] = None,
        region: Optional[Tuple[int, int, int, int]] = None,
        haystack: Optional[Image.Image] = None,
        verify_timeout: Optional[float] = None,
        expected_context: Optional[str] = None,
    ) -> bool:
        if isinstance(target, str) and not self.can_click(
            target, expected_context=expected_context
        ):
            logger.error(
                f"SAFETY BLOCK: {target} blocked in {self.current_phase()} phase"
            )
            time.sleep(0.5)
            return False
        human_delay(
            custom_delay or self.config.DELAY_COGNITIVE,
            self.fatigue_modifier,
            self.config.SAFETY_FLOOR_FACTOR,
        )
        conf = confidence or self.get_template_confidence(
            target if isinstance(target, str) else ""
        )
        box = (
            self.find_image(target, confidence=conf, region=region, haystack=haystack)
            if isinstance(target, str)
            else target
        )
        if not box:
            return verify_key == target and not wait_for_appearance

        mu_x, mu_y = box.left + box.width / 2, box.top + box.height / 2
        click_x, click_y = (
            int(random.gauss(mu_x, box.width / 10)),
            int(random.gauss(mu_y, box.height / 10)),
        )
        click_x, click_y = (
            max(box.left, min(click_x, box.left + box.width - 1)),
            max(box.top, min(click_y, box.top + box.height - 1)),
        )

        # V9.21: Capture Focus (Mechanically identical to V6)
        current_focus = None
        try:
            current_focus = subprocess.check_output(
                ["xdotool", "getactivewindow"], text=True, stderr=subprocess.DEVNULL
            ).strip()
        except Exception:
            pass

        # Execute Silent X11 Click (Invisible Pilot)
        success = self._send_x11_click(click_x, click_y)
        logger.info(
            f"CLICK [Run:{self.run_count}]: {description} at ({click_x}, {click_y})"
        )

        # Refocus Reclaim (Mechanically identical to V6)
        if success and current_focus:
            time.sleep(self.config.WAIT_REFOCUS)
            try:
                subprocess.run(
                    [
                        "xdotool",
                        "windowfocus",
                        current_focus,
                        "windowactivate",
                        "--sync",
                        current_focus,
                        "windowraise",
                        current_focus,
                    ],
                    check=False,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

        if success:
            if verify_key:
                v_start, limit = (
                    time.time(),
                    (verify_timeout or self.config.TIMEOUT_VERIFY_UI),
                )
                while time.time() - v_start < limit:
                    found_v = self.find_image(
                        verify_key, confidence=self.config.CONF_VERIFY_ACTION
                    )
                    if (wait_for_appearance and found_v) or (
                        not wait_for_appearance and not found_v
                    ):
                        if target_state:
                            self.transition_to(target_state)
                        return True
                    time.sleep(self.config.POLL_UI_VERIFY)
                return False
            if target_state:
                self.transition_to(target_state)
        return success

    def _send_x11_click(self, x: int, y: int) -> bool:
        """Silent Xlib direct click (No focus stealing)."""
        try:
            if not self.win_id or not self.region:
                return False
            window = self.disp.create_resource_object("window", int(self.win_id))

            # Root-to-Window coordinate translation
            rel_x, rel_y = x - self.region[0], y - self.region[1]

            # V9.20: Direct event injection prevents mouse hijacking and window raising
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
        except Exception:
            return False

    def is_safe_room_okay_context(self, haystack: Optional[Image.Image] = None) -> bool:
        if self.state not in {
            "SCAN_ROOMS",
            "RECOVERY",
            "MENU",
            "READY",
            "CHECK_RUN_START",
        }:
            return False
        for anchor in ["ingame_auto_on", "ingame_auto_off", "retire"]:
            if self.find_image(anchor, haystack=haystack):
                return False
        return True

    def handle_global_popups(self, haystack: Optional[Image.Image] = None) -> bool:
        now = time.time()
        if now - self._last_popup_check < self.config.POLL_POPUP:
            return False
        self._last_popup_check = now
        popups = [
            "disconnect_retry",
            "closed_room_coop_quest_menu",
            "room_not_met",
            "unavailable_close",
            "close_news",
            "okay",
            "close",
        ]
        for key in popups:
            if key == "okay" and not self.is_safe_room_okay_context(haystack):
                continue
            if key == "close" and self.state == "ENTER_ROOM_LIST":
                continue
            if self.find_image(key, haystack=haystack):
                logger.warning(f"GLOBAL: Popup '{key}' confirmed")
                self.smart_click(
                    key, f"dismiss {key}", verify_key=key, haystack=haystack
                )
                if key in [
                    "closed_room_coop_quest_menu",
                    "room_not_met",
                    "unavailable_close",
                    "okay",
                    "close",
                ]:
                    self.search_start_time = time.time()
                    if self.state in ["SCAN_ROOMS", "JOIN_PENDING", "READY"]:
                        self.transition_to("SCAN_ROOMS")
                        return True
                if self.state != "GAME_STARTUP":
                    self.transition_to("MENU")
                return True
        return False

    def handle_menu(self, haystack: Optional[Image.Image] = None) -> bool:
        if self.find_image("open_coop_quest", haystack=haystack):
            return self.smart_click(
                "open_coop_quest",
                "specific quest",
                "enter_room_button",
                target_state="ENTER_ROOM_LIST",
                wait_for_appearance=True,
                haystack=haystack,
            )
        if self.find_image("coop_quest", haystack=haystack):
            return self.smart_click(
                "coop_quest",
                "expand menu",
                "open_coop_quest",
                wait_for_appearance=True,
                haystack=haystack,
            )
        for key in ["coop_1", "coop_2"]:
            if self.find_image(key, haystack=haystack):
                return self.smart_click(
                    key, f"navigate {key}", wait_for_appearance=False, haystack=haystack
                )
        if self.find_image("enter_room_button", haystack=haystack):
            self.transition_to("ENTER_ROOM_LIST")
            return True
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_LOBBY_EXPAND:
            self.transition_to("RECOVERY")
            return True
        return False

    def handle_enter_room_list(self, haystack: Optional[Image.Image] = None) -> bool:
        if self.find_image("enter_room_button", haystack=haystack):
            if self.smart_click(
                "enter_room_button", "enter room list", haystack=haystack
            ):
                start_load = time.time()
                while time.time() - start_load < self.config.TIMEOUT_ROOM_LIST_LOAD:
                    if self.find_image("auto", haystack=haystack) or self.find_image(
                        "search_again", haystack=haystack
                    ):
                        time.sleep(self.config.WAIT_ROOM_LOAD)
                        self.transition_to("SCAN_ROOMS")
                        return True
                    time.sleep(self.config.POLL_UI_VERIFY)
                return True

        # V9.18: Wait for screen to settle before panicking to RECOVERY
        if time.time() - self.last_state_change_time > 2.0:
            self.transition_to("RECOVERY")
        return True

    def handle_scan_rooms(self, haystack: Optional[Image.Image] = None) -> bool:
        if self.find_image(
            "ready", confidence=self.config.CONF_READY, haystack=haystack
        ):
            self.transition_to("READY")
            return True
        if time.time() - self.search_start_time > self.config.TIMEOUT_SCAN_IDLE:
            self.transition_to("RECOVERY")
            return True

        # Autonomous Search Refresh
        if self.find_image("search_again", haystack=haystack):
            if time.time() - self.search_start_time > self.config.WAIT_SEARCH_AGAIN:
                self.search_start_time = time.time()
                if self.smart_click("search_again", "refresh list", haystack=haystack):
                    time.sleep(self.config.WAIT_REFRESH_COOLDOWN)
                    return True

        autos = self.find_all("auto", haystack=haystack)
        if autos:
            v_rules = self.find_all(
                "room_rules_valid", confidence=self.config.CONF_LOOSE, haystack=haystack
            )
            valid = BBSBot.match_rooms(autos, v_rules, self.config)

            candidates = []
            matched_autos_ids = set()
            for auto, rule in valid:
                candidates.append((auto, rule, "strict"))
                matched_autos_ids.add(id(auto))

            if self.config.ALLOW_ALL_AUTO_ROOMS:
                for a in BBSBot.dedupe_autos(autos, self.config):
                    if id(a) not in matched_autos_ids:
                        candidates.append((a, None, "fallback"))

            if candidates:
                self.search_start_time = time.time()
                for auto, rule, mode in candidates:
                    if mode == "strict" and rule:
                        px, py = (
                            (auto.left + rule.left + rule.width) // 2,
                            auto.top + auto.height // 2,
                        )
                        label = "snatch room (strict)"
                    else:
                        # V9.21 Fixed banner coordinates: Click 200px to the LEFT of the icon
                        px, py = (
                            auto.left - 200,
                            auto.top + auto.height // 2,
                        )
                        label = "snatch room (all_auto)"

                    target_box = pyscreeze.Box(
                        px - self.config.SNATCH_BOX_OFFSET[0],
                        py - self.config.SNATCH_BOX_OFFSET[1],
                        self.config.SNATCH_BOX_DIM[0],
                        self.config.SNATCH_BOX_DIM[1],
                    )
                    if self.smart_click(target_box, label, haystack=haystack):
                        self.transition_to("JOIN_PENDING")
                        return True
                return True
        return False

    @staticmethod
    def match_rooms(autos, rules, config):
        valid = []
        for a in BBSBot.dedupe_autos(autos, config):
            ax, ay = a.left + a.width // 2, a.top + a.height // 2
            best_r, min_d = None, float("inf")
            for r in rules:
                rx, ry = r.left + r.width // 2, r.top + r.height // 2
                if ry > ay:
                    d = abs(ry - ay) + abs(rx - ax) * config.ROOM_MATCH_WEIGHT
                    if d < min_d and d < config.MAX_RULE_DISTANCE:
                        min_d, best_r = d, r
            if best_r:
                valid.append((a, best_r))
        return valid

    @staticmethod
    def dedupe_autos(matches, config):
        unique = []
        for m in matches:
            cx, cy = m.left + m.width // 2, m.top + m.height // 2
            if not any(
                (
                    (cx - (u.left + u.width // 2)) ** 2
                    + (cy - (u.top + u.height // 2)) ** 2
                )
                ** 0.5
                < config.AUTO_ICON_DEDUPE_DIST
                for u in unique
            ):
                unique.append(m)
        return unique

    def handle_join_pending(self, haystack: Optional[Image.Image] = None) -> bool:
        if self.find_stable_image("ready", confidence=self.config.CONF_READY, frames=3):
            # V9.18: Restore V6 patience buffer
            time.sleep(self.config.DELAY_READY)
            self.smart_click(
                "ready",
                "snap ready",
                verify_key="ready",
                target_state="CHECK_RUN_START",
                haystack=haystack,
            )
            return True
        if self.find_image(
            "closed_room_coop_quest_menu", haystack=haystack
        ) or self.find_image("room_not_met", haystack=haystack):
            key = (
                "closed_room_coop_quest_menu"
                if self.find_image("closed_room_coop_quest_menu", haystack=haystack)
                else "room_not_met"
            )
            if self.smart_click(key, "room fail", haystack=haystack):
                self.transition_to("SCAN_ROOMS")
                return True
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_LOBBY_JOIN:
            self.transition_to("RECOVERY")
            return True
        return False

    def handle_ready(self, haystack: Optional[Image.Image] = None) -> bool:
        if self.find_stable_image("ready", confidence=self.config.CONF_READY, frames=3):
            # V9.18: Restore V6 patience buffer
            time.sleep(self.config.DELAY_READY)
            self.smart_click(
                "ready",
                "ready button",
                verify_key="ready",
                target_state="CHECK_RUN_START",
                haystack=haystack,
            )
            return True
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_RUN_START:
            self.retire_from_quest(haystack=haystack)
            return True
        return False

    def handle_check_run_start(self, haystack: Optional[Image.Image] = None) -> bool:
        if self.find_image("ingame_auto_on", haystack=haystack) or self.find_image(
            "ingame_auto_off", haystack=haystack
        ):
            self.transition_to("RUNNING")
            return True
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_RUN_START:
            self.retire_from_quest(haystack=haystack)
            return True
        return False

    def handle_running(self, haystack: Optional[Image.Image] = None) -> bool:
        if self.find_image("tap1", haystack=haystack):
            self.transition_to("FINISH")
            return True
        time.sleep(self.config.POLL_RUNNING)
        return False

    def handle_finish(self, haystack: Optional[Image.Image] = None) -> bool:
        if not self._run_counted:
            self.run_count += 1
            self._run_counted = True
        for key in ["tap1", "tap2"]:
            if self.find_image(key, haystack=haystack):
                self.smart_click(key, f"reward {key}", haystack=haystack)
                return True
        if self.find_image("retry", haystack=haystack):
            if self.smart_click(
                "retry", "retry quest", verify_key="retry", haystack=haystack
            ):
                time.sleep(1.5)
                self.transition_to("ENTER_ROOM_LIST")
                return True
        return False

    def handle_game_startup(self, haystack: Optional[Image.Image] = None) -> bool:
        for key in ["game_start", "close_news", "coop_1", "coop_2"]:
            if self.find_image(key, haystack=haystack):
                self.smart_click(
                    key, f"startup {key}", verify_key=key, haystack=haystack
                )
                return True
        if self.find_image("coop_quest", haystack=haystack) or self.find_image(
            "open_coop_quest", haystack=haystack
        ):
            self.transition_to("MENU")
            return True
        return False

    def handle_recovery(self, haystack: Optional[Image.Image] = None) -> bool:
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_STUCK:
            self.recover_game()
            return True
        for state, template in self.RECOVERY_MAP:
            if self.find_image(template, haystack=haystack):
                self.transition_to(state)
                return True
        return False

    def handle_distraction(self, haystack: Optional[Image.Image] = None) -> bool:
        duration = random.randint(*self.config.DISTRACTION_DURATION)
        logger.info(f"DISTRACTION: Resting for {duration}s...")
        time.sleep(duration)
        self.reset_quest_watchdog("distraction_ended")
        self.transition_to("RECOVERY")
        return True

    def transition_to(self, state: str) -> None:
        if self.state != state:
            old_state = self.state
            logger.info(f"TRANSITION [Run:{self.run_count}]: {self.state} -> {state}")
            self.state = state
            self.last_state_change_time = time.time()
            if state == "RUNNING":
                self.reset_quest_watchdog("entered_running")
            if state == "SCAN_ROOMS":
                self.search_start_time = time.time()
            if state in ["MENU", "READY", "CHECK_RUN_START", "ENTER_ROOM_LIST"]:
                self._run_counted = False
            if old_state == "FINISH" and state != "FINISH":
                self.reset_quest_watchdog("run_completed")

    def reset_quest_watchdog(self, reason: str = "progress") -> None:
        logger.info(f"WATCHDOG: Resetting timer (Reason: {reason})")
        self.quest_watchdog = time.time()
        self.consecutive_recovery_count = 0

    def retire_from_quest(self, haystack: Optional[Image.Image] = None) -> bool:
        logger.warning("Retiring sequence...")
        self.expected_okay_context = "RETIRE_CONFIRM"
        if self.find_image("retire", haystack=haystack):
            self.smart_click("retire", "retire", haystack=haystack)
            if self.find_image("okay", haystack=haystack):
                self.smart_click("okay", "confirm", haystack=haystack)
                if self.find_image("closed_room_coop_quest_menu", haystack=haystack):
                    self.smart_click(
                        "closed_room_coop_quest_menu",
                        "final confirm",
                        haystack=haystack,
                    )
        self.expected_okay_context = None
        self.transition_to("MENU")
        return True

    def recover_game(self) -> None:
        self.consecutive_recovery_count += 1
        self.reset_quest_watchdog("hard_recovery_started")
        if self.consecutive_recovery_count > self.config.MAX_CONSECUTIVE_RECOVERIES:
            sys.exit(1)
        subprocess.run(
            ["pkill", "-f", "BleachBraveSouls.exe"], stderr=subprocess.DEVNULL
        )
        time.sleep(self.config.WAIT_RESTART)
        subprocess.Popen(
            ["steam", "-applaunch", "1201240"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.transition_to("GAME_STARTUP")

    def check_quest_watchdog(self) -> None:
        if time.time() - self.quest_watchdog > self.config.TIMEOUT_QUEST_MAX:
            self.recover_game()

    def get_game_region(self) -> Tuple[int, int, int, int]:
        """Robustly locate the actual game window ID and region with strict PID filtering."""
        try:
            # V9.22: Improved search for visible game window with strict process validation
            cmd = ["xdotool", "search", "--name", self.config.RAW_TITLE]
            wids = (
                subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
                .strip()
                .split()
            )

            for wid in wids:
                try:
                    # Verify PID belongs to the actual game process
                    pid = subprocess.check_output(
                        ["xdotool", "getwindowpid", wid],
                        text=True,
                        stderr=subprocess.DEVNULL,
                    ).strip()
                    proc_cmd = subprocess.check_output(
                        ["ps", "-p", pid, "-o", "cmd", "--no-headers"],
                        text=True,
                        stderr=subprocess.DEVNULL,
                    ).strip()

                    if "BleachBraveSouls" not in proc_cmd:
                        continue
                except Exception:
                    continue

                geo = subprocess.check_output(
                    ["xdotool", "getwindowgeometry", "--shell", wid], text=True
                )
                g = {
                    line.split("=")[0]: int(line.split("=")[1])
                    for line in geo.splitlines()
                    if "=" in line
                }

                # Actual game is 806x482, filter out splash/ghost windows
                if g.get("WIDTH", 0) > 100 and g.get("HEIGHT", 0) > 100:
                    self.win_id, self.region = wid, (
                        g["X"],
                        g["Y"],
                        g["WIDTH"],
                        g["HEIGHT"],
                    )
                    return self.region
            raise GameWindowNotFoundError()
        except Exception:
            raise GameWindowNotFoundError()

    def update_fatigue(self) -> None:
        elapsed = time.time() - self.fatigue_start_time
        self.fatigue_modifier = (
            self.config.FATIGUE_BASE
            + self.config.FATIGUE_AMPLITUDE
            * abs(math.sin(elapsed * (2 * math.pi / self.config.FATIGUE_PERIOD)))
        )

    def check_circadian_rhythm(self) -> None:
        if time.time() > self.next_profile_swap:
            old_profile = self.active_profile
            self.active_profile = (
                "SHIKAI_NORMAL" if old_profile == "SHIKAI_MAX" else "SHIKAI_MAX"
            )
            self.config._apply_profile(self.active_profile)
            if self.config.CIRCADIAN_PROFILES:
                duration_secs = (
                    random.randint(
                        *self.config.CIRCADIAN_PROFILES[self.active_profile][
                            "DURATION_MINS"
                        ]
                    )
                    * 60
                )
            else:
                duration_secs = 3600
            self.next_profile_swap = time.time() + duration_secs
            logger.info(
                f"CIRCADIAN SHIFT: {self.active_profile} for {duration_secs / 60:.0f} mins."
            )

    def check_session_limit(self) -> None:
        if (time.time() - self.start_time) / 3600 >= self.config.SESSION_MAX_HOURS:
            sys.exit(0)

    def log_session_summary(self) -> None:
        elapsed = time.time() - self.start_time
        hours, minutes, seconds = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
        logger.info(
            f"--- SESSION SUMMARY --- \nTotal Time: {int(hours)}h {int(minutes)}m {int(seconds)}s\nTotal Runs: {self.run_count}\nAvg Time/Run: {elapsed / 60 / max(1, self.run_count):.2f} mins\nDisconnects: 0\n-----------------------"
        )

    def run(self, test_restart: bool = False) -> None:
        if test_restart:
            self.recover_game()
        self._load_templates()
        self.check_dependencies()
        self.reset_quest_watchdog("startup")
        while True:
            try:
                self.get_game_region()
                if self.region:
                    monitor = {
                        "top": self.region[1],
                        "left": self.region[0],
                        "width": self.region[2],
                        "height": self.region[3],
                    }
                    sct_img = self.sct.grab(monitor)
                    self.snapshot = Image.frombytes(
                        "RGB", sct_img.size, sct_img.bgra, "raw", "BGRX"
                    )
                else:
                    self.snapshot = None

                self.check_quest_watchdog()
                self.update_fatigue()
                self.check_circadian_rhythm()
                self.check_session_limit()
                handler = self.handlers.get(self.state)
                if handler and handler(self.snapshot):
                    continue
                if self.handle_global_popups(self.snapshot):
                    continue
                time.sleep(self.config.POLL_MAIN_LOOP)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                self.transition_to("RECOVERY")
                time.sleep(1)
        self.log_session_summary()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-restart", action="store_true")
    parser.add_argument("--debug-screenshots", action="store_true")
    parser.add_argument("--allow-all-auto-rooms", action="store_true")
    args = parser.parse_args()
    bot = BBSBot()
    if args.debug_screenshots:
        bot.config.TAKE_DEBUG_SCREENSHOTS = True
    if args.allow_all_auto_rooms:
        bot.config.ALLOW_ALL_AUTO_ROOMS = True
    try:
        bot.run(test_restart=args.test_restart)
    except Exception as e:
        logger.exception(f"Fatal: {e}")
        sys.exit(1)
