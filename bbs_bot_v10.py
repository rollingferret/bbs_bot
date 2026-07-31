import argparse
import fnmatch
import logging
import math
import os
import random
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Optional, Tuple, Union

import mss  # type: ignore
import pyautogui  # type: ignore
import pyscreeze  # type: ignore
from PIL import Image
from Xlib import Xatom, display, X, protocol  # type: ignore

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        RotatingFileHandler("v10_behavior.log", maxBytes=5 * 1024 * 1024, backupCount=5),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def add_alignment_log_handler():
    os.makedirs("alignment_audit", exist_ok=True)
    log_path = os.path.abspath("alignment_audit/alignment_behavior.log")
    for handler in logger.handlers:
        if getattr(handler, "baseFilename", None) == log_path:
            return
    handler = RotatingFileHandler(log_path, maxBytes=2 * 1024 * 1024, backupCount=3)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    logger.info(f"ALIGNMENT: Mirroring behavior log to {log_path}")


@dataclass
class BotConfiguration:
    """Centralized configuration for the BBS Bot V10 Sentinel."""

    RAW_TITLE: str = "Bleach: Brave Souls"
    CIRCADIAN_PROFILES: Optional[Dict[str, Dict[str, Any]]] = None

    # Timing Profiles
    DELAY_COGNITIVE: Tuple[float, float] = (0.78, 0.05)
    DELAY_NEWS: float = 0.4
    DELAY_READY: float = 0.90
    WAIT_SEARCH_AGAIN: float = 1.7
    WAIT_REFOCUS: float = 0.02
    WAIT_REFOCUS_FALLBACK_MAX_AGE: float = 10.0
    WAIT_REFRESH_COOLDOWN: float = 2.0
    ROOM_FAIL_REFRESH_DELAY: float = 1.5
    WAIT_DOWNLOAD_AFTER_CONFIRM: float = 45.0
    WAIT_STABILIZE_ANIMATION: float = 1.2
    SAFETY_FLOOR_FACTOR: float = 0.05
    WAIT_RESTART: float = 5.0

    # Timeouts
    TIMEOUT_STUCK: float = 90
    TIMEOUT_QUEST_MAX: float = 480
    TIMEOUT_GAME_START: float = 120
    TIMEOUT_RUN_START: float = 180
    TIMEOUT_TAP_VERIFY: float = 25.0
    TIMEOUT_LOBBY_EXPAND: float = 20.0
    TIMEOUT_LOBBY_JOIN: float = 10.0
    TIMEOUT_ROOM_LIST_LOAD: float = 5.0
    TIMEOUT_SCAN_IDLE: float = 20.0
    TIMEOUT_VERIFY_UI: float = 2.0

    # Wait Constants
    WAIT_DISCONNECT_COOLING: Tuple[int, int] = (2, 4)

    # Vision
    CONF_NORMAL: float = 0.80
    CONF_READY: float = 0.95
    CONF_LOOSE: float = 0.68
    CONF_POPUP: float = 0.85
    CONF_VERIFY_ACTION: float = 0.80

    # Logic
    AUTO_ICON_DEDUPE_DIST: int = 60
    ROOM_MATCH_WEIGHT: float = 0.1
    MAX_RULE_DISTANCE: int = 110
    SNATCH_BOX_OFFSET: Tuple[int, int] = (20, 10)
    SNATCH_BOX_DIM: Tuple[int, int] = (40, 20)
    ROOM_ROW_BUCKET: int = 42
    ROOM_PRE_CLICK_RECHECK_GAP: float = 0.20
    JOIN_FAIL_LIST_GRACE: float = 3.2
    MENU_TEMPLATE_MIN_Y_RATIO: float = 0.05
    PREFER_BOTTOM_ROOMS: bool = True

    # All-Auto Strategy
    ALLOW_ALL_AUTO_ROOMS: bool = False
    ALLOW_ALL_AUTO_OFFSET_X: int = -200

    # Operational Safety
    MAX_CONSECUTIVE_RECOVERIES: int = 3
    SESSION_MAX_HOURS: int = 16
    POLL_MAIN_LOOP: float = 0.1
    POLL_UI_VERIFY: float = 0.1
    POLL_POPUP: float = 0.75
    POLL_RUNNING: float = 1.0
    POLL_MENU: float = 0.20
    POLL_RECOVERY: float = 0.25
    POLL_GAME_STARTUP: float = 0.30

    CASUAL_LINGER_RUNS: Tuple[int, int] = (8, 16)
    ENABLE_COFFEE_BREAKS: bool = True
    FATIGUE_BASE: float = 1.0
    FATIGUE_AMPLITUDE: float = 0.15
    FATIGUE_PERIOD: int = 1800
    DISTRACTION_DURATION: Tuple[int, int] = (120, 480)
    SHORT_DISTRACTION_DURATION: Tuple[int, int] = (25, 75)
    MAX_INCIDENT_SNAPSHOTS: int = 1000
    MAX_ROUTINE_SNAPSHOTS: int = 80
    MAX_ALIGNMENT_SNAPSHOTS: int = 100

    # Flags
    ALIGNMENT_MODE: bool = False
    RESTORE_FOCUS_AFTER_CLICK: bool = True
    START_PROFILE: str = "SHIKAI_MAX"

    TEMPLATES: Optional[Dict[str, str]] = field(default=None)

    def __post_init__(self):
        self.CIRCADIAN_PROFILES = {
            "SHIKAI_MAX": {
                "DELAY_COGNITIVE": (0.78, 0.05), "DELAY_READY": 0.90, "WAIT_SEARCH_AGAIN": 1.7,
                "WAIT_POST_RETRY": 1.0, "WAIT_REFOCUS": 0.02,
                "WAIT_REFRESH_COOLDOWN": 1.2, "WAIT_STABILIZE_ANIMATION": 0.8,
                "TIMEOUT_VERIFY_UI": 0.8, "DURATION_MINS": (45, 90),
            },
            "SHIKAI_NORMAL": {
                "DELAY_COGNITIVE": (0.95, 0.10), "DELAY_READY": 1.10, "WAIT_SEARCH_AGAIN": 3.0,
                "WAIT_POST_RETRY": 2.0, "WAIT_REFOCUS": 0.05,
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
            "network_retry_button": "images/network_retry_button.png",
            "network_title_error": "images/network_title_error.png",
            "download_data_title": "images/download_data_title.png", "download_data_yes": "images/download_data_yes.png",
            "update_return_title": "images/update_return_title.png",
            "update_return_message": "images/update_return_message.png",
            "update_return_ok": "images/update_return_ok.png",
            "login_failed_title": "images/login_failed_title.png", "login_failed_ok": "images/login_failed_ok.png",
            "brave_bonus_title": "images/brave_bonus_title.png", "brave_bonus_cancel": "images/brave_bonus_cancel.png",
            "player_rank_reward_title": "images/player_rank_reward_title.png",
            "player_rank_reward_close": "images/player_rank_reward_close.png",
        }
        self._apply_profile(self.START_PROFILE)

    def _apply_profile(self, profile_name: str):
        if self.CIRCADIAN_PROFILES:
            s = self.CIRCADIAN_PROFILES[profile_name]
            self.DELAY_COGNITIVE = s["DELAY_COGNITIVE"]
            self.DELAY_READY = s["DELAY_READY"]
            self.WAIT_SEARCH_AGAIN = s["WAIT_SEARCH_AGAIN"]
            self.WAIT_POST_RETRY = s["WAIT_POST_RETRY"]
            self.WAIT_REFOCUS = s.get("WAIT_REFOCUS", 0.02)
            self.WAIT_REFRESH_COOLDOWN = s["WAIT_REFRESH_COOLDOWN"]
            self.WAIT_STABILIZE_ANIMATION = s["WAIT_STABILIZE_ANIMATION"]
            self.TIMEOUT_VERIFY_UI = s["TIMEOUT_VERIFY_UI"]


def human_delay(profile, fatigue=1.0, safety_factor=0.05):
    if isinstance(profile, (float, int)): mu, sigma = float(profile), float(profile) * 0.1
    else: mu, sigma = profile
    delay = random.gauss(mu * fatigue, sigma)
    time.sleep(max(delay, (mu * fatigue) * safety_factor))


def ready_trace_enabled(description):
    return description in {"snap ready", "ready button"}


def parse_cpu_list(value):
    cpus = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            cpus.update(range(int(start), int(end) + 1))
        else:
            cpus.add(int(part))
    return cpus


def parse_cpu_affinity(value):
    value = value.strip()
    if value.lower() == "auto":
        return choose_auto_cpu_affinity()
    cpus = parse_cpu_list(value)
    if not cpus:
        raise ValueError("CPU affinity cannot be empty")
    return cpus


def read_cpu_times():
    times = {}
    with open("/proc/stat", "r", encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if not parts or not parts[0].startswith("cpu") or parts[0] == "cpu":
                continue
            cpu = int(parts[0][3:])
            values = [int(v) for v in parts[1:]]
            idle = values[3] + (values[4] if len(values) > 4 else 0)
            total = sum(values)
            times[cpu] = (idle, total)
    return times


def read_cpu_siblings(cpu):
    path = f"/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return frozenset(parse_cpu_list(f.read().strip()))
    except Exception:
        return frozenset({cpu})


def choose_auto_cpu_affinity(count=4, sample_seconds=1.5):
    allowed = set(os.sched_getaffinity(0))
    before = read_cpu_times()
    time.sleep(sample_seconds)
    after = read_cpu_times()
    usage = {}
    for cpu in allowed:
        if cpu not in before or cpu not in after:
            continue
        idle_before, total_before = before[cpu]
        idle_after, total_after = after[cpu]
        total_delta = max(1, total_after - total_before)
        idle_delta = idle_after - idle_before
        usage[cpu] = 1.0 - (idle_delta / total_delta)

    groups = {}
    for cpu in sorted(allowed):
        group = read_cpu_siblings(cpu) & allowed
        groups.setdefault(group or frozenset({cpu}), []).append(cpu)

    preferred = []
    for group_cpus in groups.values():
        best = min(group_cpus, key=lambda cpu: usage.get(cpu, 1.0))
        preferred.append(best)

    ranked = sorted(preferred, key=lambda cpu: usage.get(cpu, 1.0))
    cpus = set(ranked[: min(count, len(ranked))])
    if not cpus:
        raise ValueError("CPU affinity auto-selection found no available CPUs")
    return cpus


def format_cpu_affinity(cpus):
    return ",".join(str(c) for c in sorted(cpus))


def describe_cpu_affinity_source(value):
    return "auto-selected" if value.strip().lower() == "auto" else "pinned"


def apply_cpu_affinity(value):
    try:
        cpus = parse_cpu_affinity(value)
        os.sched_setaffinity(0, cpus)
        logger.info(f"CPU affinity {describe_cpu_affinity_source(value)} to: {format_cpu_affinity(cpus)}")
    except AttributeError:
        logger.warning("CPU affinity is not supported on this platform.")
    except Exception as e:
        logger.warning(f"CPU affinity '{value}' could not be applied: {e}")


class GameWindowNotFoundError(Exception): pass

class BBSBot:
    """BBS Sentinel V10 runtime state machine."""
    RECOVERY_MAP = [
        ("READY", "ready"), ("RUNNING", "ingame_auto_on"), ("RUNNING", "ingame_auto_off"),
        ("CHECK_RUN_START", "retire"), ("FINISH", "tap1"), ("FINISH", "tap2"), ("FINISH", "retry"),
        ("SCAN_ROOMS", "search_again"), ("JOIN_PENDING", "ready"), ("ENTER_ROOM_LIST", "enter_room_button"),
        ("MENU", "open_coop_quest"), ("MENU", "coop_quest"), ("MENU", "coop_1"), ("MENU", "coop_2"),
        ("GAME_STARTUP", "game_start"),
    ]

    def __init__(self, config=None):
        self.config = config or BotConfiguration()
        pyautogui.FAILSAFE = False
        assert self.config.CIRCADIAN_PROFILES is not None
        self.active_profile = self.config.START_PROFILE
        self.next_profile_swap = time.time() + random.randint(*self.config.CIRCADIAN_PROFILES[self.active_profile]["DURATION_MINS"]) * 60
        self.state, self.run_count, self.start_time = "RECOVERY", 0, time.time()
        self.next_distraction_run = 9999
        self.fatigue_start_time = self.last_state_change_time = self.quest_watchdog = time.time()
        self.win_id = self.region = self.snapshot = self.expected_okay_context = None
        self.consecutive_recovery_count = self.search_start_time = 0
        self._force_refresh = False
        self._next_refresh_time = 0.0
        self._last_room_signature = None
        self._last_join_row = None
        self.fatigue_modifier, self._last_popup_check = 1.0, 0.0
        self._last_id_search = 0.0
        self._last_non_game_focus = None
        self._last_non_game_focus_at = 0.0
        self._loop_restore_focus = None
        self._loop_restore_focus_at = 0.0
        self._game_visibility_dirty = True
        self._x_time_display = None
        self._x_time_offset = None
        self._x_time_offset_at = None
        self._user_time_cleared_for = None
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
        self.template_variants = {}
        self._load_templates()
        self.check_dependencies()
        try:
            self.disp = display.Display()
            self.sct = mss.mss()
        except Exception:
            logger.error("FATAL: X11/MSS Init Error"); sys.exit(1)
        try:
            self._x_time_display = display.Display()
        except Exception as exc:
            self._x_time_display = None
            if self.config.ALIGNMENT_MODE:
                logger.info(f"FOCUS: timestamp display init failed: {exc}")
        if not os.path.exists("alignment_audit"): os.makedirs("alignment_audit")
        elif self.config.ALIGNMENT_MODE:
            for f in os.listdir("alignment_audit"):
                if f.startswith("alignment_behavior.log"):
                    continue
                try: os.remove(os.path.join("alignment_audit", f))
                except Exception: pass
        if self.config.ALIGNMENT_MODE:
            add_alignment_log_handler()
        self.ensure_snapshot_dirs()
        self.prune_old_files("error_snapshots/routine", "error_*.png", self.config.MAX_ROUTINE_SNAPSHOTS)
        self.prune_old_files("error_snapshots/incidents", "error_*.png", self.config.MAX_INCIDENT_SNAPSHOTS)
        logger.info(f"BBS Sentinel V10 Initialized. profile={self.active_profile}")

    def _load_templates(self):
        if not self.config.TEMPLATES: return
        for k, v in self.config.TEMPLATES.items():
            try:
                self.cached_templates[k] = Image.open(v).convert("RGB")
                variants = [(v, self.cached_templates[k])]
                root, ext = os.path.splitext(v)
                for alt in sorted(fnmatch.filter(os.listdir(os.path.dirname(v) or "."), os.path.basename(root) + "_bk*" + ext)):
                    alt_path = os.path.join(os.path.dirname(v), alt)
                    variants.append((alt_path, Image.open(alt_path).convert("RGB")))
                self.template_variants[k] = variants
            except Exception: logger.error(f"Template error: {k}")

    def check_dependencies(self):
        for cmd in ["xdotool", "wmctrl", "pkill", "ps"]:
            if subprocess.run(["which", cmd], capture_output=True).returncode != 0:
                logger.error(f"FATAL: Missing {cmd}"); sys.exit(1)
        if subprocess.run(["which", "xwininfo"], capture_output=True).returncode != 0:
            logger.warning("WARN: Missing xwininfo; falling back to less reliable xdotool geometry")

    @staticmethod
    def prune_old_files(directory, pattern, keep):
        try:
            files = sorted([os.path.join(directory, f) for f in os.listdir(directory)], key=os.path.getmtime)
        except Exception:
            return
        matching = [f for f in files if fnmatch.fnmatch(os.path.basename(f), pattern)]
        if len(matching) <= keep:
            return
        for f in matching[:-keep]:
            try: os.remove(f)
            except Exception: pass

    @staticmethod
    def error_snapshot_bucket(reason):
        if reason.startswith("recovery_from_"):
            return "routine"
        return "incidents"

    def ensure_snapshot_dirs(self):
        os.makedirs("error_snapshots/routine", exist_ok=True)
        os.makedirs("error_snapshots/incidents", exist_ok=True)
        os.makedirs("error_snapshots/hard_restarts", exist_ok=True)

    def save_debug_screenshot(self, name):
        if not self.snapshot: return
        try:
            ts = int(time.time() * 1000)
            fname = f"alignment_audit/{name}_{ts}.png"
            self.snapshot.save(fname)
            logger.info(f"ALIGNMENT: Screenshot saved: {fname} state={self.state} run={self.run_count}")
            self.prune_old_files("alignment_audit", "*.png", self.config.MAX_ALIGNMENT_SNAPSHOTS)
        except Exception: pass

    def save_error_snapshot(self, reason):
        if not self.snapshot: return
        try:
            self.ensure_snapshot_dirs()
            ts = int(time.time() * 1000)
            bucket = self.error_snapshot_bucket(reason)
            fname = f"error_snapshots/{bucket}/error_{reason}_{ts}.png"
            self.snapshot.save(fname)
            logger.error(f"Error snapshot saved: {fname}")
            keep = self.config.MAX_ROUTINE_SNAPSHOTS if bucket == "routine" else self.config.MAX_INCIDENT_SNAPSHOTS
            self.prune_old_files(f"error_snapshots/{bucket}", "error_*.png", keep)
        except Exception: pass

    def save_hard_restart_snapshot(self, reason):
        try:
            self.ensure_snapshot_dirs()
            ts = int(time.time() * 1000)
            safe_reason = "".join(c if c.isalnum() or c in "-_" else "_" for c in reason)
            state = self.state
            base = f"error_snapshots/hard_restarts/restart_{safe_reason}_{state}_{ts}"
            screenshot_status = "missing"
            if not self.snapshot:
                try:
                    region = self.get_game_region()
                    monitor = {"top": region[1], "left": region[0], "width": region[2], "height": region[3]}
                    sct_img = self.sct.grab(monitor)
                    self.snapshot = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                except Exception as e:
                    screenshot_status = f"missing:{type(e).__name__}"
            if self.snapshot:
                self.snapshot.save(f"{base}.png")
                screenshot_status = "saved"
            with open(f"{base}.txt", "w", encoding="utf-8") as f:
                f.write(f"reason={reason}\nstate={state}\nrun_count={self.run_count}\nscreenshot={screenshot_status}\n")
            logger.error(f"Hard restart evidence saved: {base} screenshot={screenshot_status}")
            self.prune_old_files("error_snapshots/hard_restarts", "restart_*.png", self.config.MAX_INCIDENT_SNAPSHOTS)
            self.prune_old_files("error_snapshots/hard_restarts", "restart_*.txt", self.config.MAX_INCIDENT_SNAPSHOTS)
        except Exception:
            pass

    def get_template_confidence(self, key):
        c = {
            "open_coop_quest": 0.90, "coop_quest": 0.90, "coop_1": 0.85, 
            "ready": 0.95, "disconnect_retry": 0.90, "unavailable_close": 0.95, 
            "close_news": 0.92, "close": 0.92,
            "ingame_auto_on": 0.95, "ingame_auto_off": 0.95,
            "tap1": 0.90, "tap2": 0.90, "retry": 0.90,
            "network_retry_button": 0.92, "network_title_error": 0.92,
            "download_data_title": 0.92, "download_data_yes": 0.92,
            "update_return_title": 0.92, "update_return_message": 0.92, "update_return_ok": 0.92,
            "login_failed_title": 0.92, "login_failed_ok": 0.92,
            "brave_bonus_title": 0.92, "brave_bonus_cancel": 0.92,
            "player_rank_reward_title": 0.92, "player_rank_reward_close": 0.92,
        }
        return c.get(key, self.config.CONF_NORMAL)

    def find_image(self, key, confidence=None, region=None, haystack=None):
        conf = confidence or self.get_template_confidence(key)
        if not self.region: return None
        try:
            if haystack:
                for _, t in self.template_variants.get(key, []):
                    try:
                        res = pyautogui.locate(t, haystack, confidence=conf)
                    except Exception:
                        res = None
                    if res:
                        return pyscreeze.Box(res.left + self.region[0], res.top + self.region[1], res.width, res.height)
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
        if not self.region: return []
        try:
            if haystack:
                matches = []
                for _, t in self.template_variants.get(key, []):
                    try:
                        found = pyautogui.locateAll(t, haystack, confidence=confidence)
                        for r in found:
                            matches.append(pyscreeze.Box(r.left + self.region[0], r.top + self.region[1], r.width, r.height))
                    except Exception:
                        continue
                return matches
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
        modal_actions = {
            "unavailable_close",
            "closed_room_coop_quest_menu",
            "disconnect_retry", "network_retry_button", "download_data_yes", "brave_bonus_cancel",
            "update_return_ok", "login_failed_ok", "player_rank_reward_close",
        }
        if key in modal_actions:
            return True
        if key == "okay":
            return expected == "RETIRE_CONFIRM" or self.state in {"GAME_STARTUP", "MENU", "ENTER_ROOM_LIST", "SCAN_ROOMS", "JOIN_PENDING", "RECOVERY", "READY", "CHECK_RUN_START"}
        allowed = {
            "STARTUP": {"close_news", "game_start", "coop_1", "coop_2", "close"},
            "MENU": {"coop_quest", "open_coop_quest", "close_news", "close", "coop_1", "coop_2"},
            "JOIN": {"enter_room_button", "close"},
            "SEARCH": {"search_again", "auto", "unavailable_close", "close", "okay", "disconnect_retry"},
            "LOBBY": {"ready", "unavailable_close", "close", "disconnect_retry"},
            "PENDING": {"ready", "unavailable_close", "close", "disconnect_retry", "retire"},
            "LIVE": {"ingame_auto_off", "retire", "disconnect_retry", "unavailable_close", "close"},
            "FINISH": {"tap1", "tap2", "retry", "disconnect_retry", "close", "unavailable_close", "player_rank_reward_close"},
            "RECOVERY": {"unavailable_close", "close", "disconnect_retry", "close_news", "okay", "coop_quest", "open_coop_quest", "coop_1", "coop_2", "player_rank_reward_close"},
        }
        return key in allowed.get(phase, set())

    def smart_click(self, target, description, verify_key=None, target_state=None, wait_for_appearance=False, custom_delay=None, confidence=None, haystack=None, verify_timeout=None, expected_context=None):
        if isinstance(target, str) and not self.can_click(target, expected_context=expected_context):
            logger.error(f"SAFETY BLOCK: {target} in {self.current_phase()} phase"); time.sleep(0.5); return False
        trace_ready = ready_trace_enabled(description)
        trace_start = time.perf_counter()
        click_profile = custom_delay or self.config.DELAY_COGNITIVE
        human_delay(click_profile, self.fatigue_modifier, self.config.SAFETY_FLOOR_FACTOR)
        if trace_ready:
            logger.info(
                f"READY TRACE: smart_click delay={time.perf_counter() - trace_start:.3f}s "
                f"profile={click_profile} fatigue={self.fatigue_modifier:.3f}"
            )
        locate_start = time.perf_counter()
        conf = confidence or self.get_template_confidence(target if isinstance(target, str) else "")
        box = self.find_image(target, confidence=conf, haystack=haystack) if isinstance(target, str) else target
        if trace_ready:
            logger.info(f"READY TRACE: smart_click locate={time.perf_counter() - locate_start:.3f}s found={bool(box)}")
        if not box: return verify_key == target and not wait_for_appearance
        mu_x, mu_y = box.left + box.width / 2, box.top + box.height / 2
        click_x, click_y = int(random.gauss(mu_x, box.width / 10)), int(random.gauss(mu_y, box.height / 10))
        if self.region:
            click_x = max(self.region[0], min(click_x, self.region[0] + self.region[2] - 1))
            click_y = max(self.region[1], min(click_y, self.region[1] + self.region[3] - 1))
        if self.config.ALIGNMENT_MODE:
            screenshot_start = time.perf_counter()
            self.save_debug_screenshot(f"pre_click_{description.replace(' ', '_')}")
            if trace_ready:
                logger.info(f"READY TRACE: pre_click_screenshot={time.perf_counter() - screenshot_start:.3f}s")
        focus_start = time.perf_counter()
        cur_focus, restore_focus, restore_source, focus_detail = self.restore_focus_for_click()
        if trace_ready:
            logger.info(f"READY TRACE: focus_lookup={time.perf_counter() - focus_start:.3f}s")
        if self.config.ALIGNMENT_MODE:
            logger.info(
                f"FOCUS: before click '{description}' active={self.window_label(cur_focus)} "
                f"game={self.window_label(self.win_id)} restore={self.window_label(restore_focus)} "
                f"source={restore_source}"
            )
            logger.info(
                f"FOCUS TRACE: '{description}' "
                f"preclick={self.window_label(focus_detail['preclick'])} valid={focus_detail['preclick_valid']} "
                f"loop={self.window_label(focus_detail['loop'])} valid={focus_detail['loop_valid']} age={focus_detail['loop_age']:.2f}s "
                f"fallback={self.window_label(focus_detail['fallback'])} valid={focus_detail['fallback_valid']} age={focus_detail['fallback_age']:.2f}s "
                f"preclick_eq_loop={focus_detail['preclick_eq_loop']} "
                f"preclick_eq_fallback={focus_detail['preclick_eq_fallback']} "
                f"selected={self.window_label(restore_focus)} source={restore_source}"
            )
        click_start = time.perf_counter()
        success = self._send_x11_click(click_x, click_y)
        if trace_ready:
            logger.info(f"READY TRACE: x11_click={time.perf_counter() - click_start:.3f}s success={success}")
        logger.info(f"CLICK [Run:{self.run_count}]: {description} at ({click_x}, {click_y})")
        if success and restore_focus:
            restore_start = time.perf_counter()
            self.restore_previous_focus(restore_focus)
            if trace_ready:
                logger.info(f"READY TRACE: focus_restore={time.perf_counter() - restore_start:.3f}s")
        if success and verify_key:
            verify_start = time.perf_counter()
            start, limit = time.time(), (verify_timeout or self.config.TIMEOUT_VERIFY_UI)
            while time.time() - start < limit:
                found = self.find_image(verify_key, confidence=self.config.CONF_VERIFY_ACTION)
                if (wait_for_appearance and found) or (not wait_for_appearance and not found):
                    if trace_ready:
                        logger.info(f"READY TRACE: verify={time.perf_counter() - verify_start:.3f}s found={bool(found)}")
                    if target_state: self.transition_to(target_state)
                    return True
                time.sleep(self.config.POLL_UI_VERIFY)
            if trace_ready:
                logger.info(f"READY TRACE: verify_timeout={time.perf_counter() - verify_start:.3f}s")
            return False
        if success and target_state: self.transition_to(target_state)
        return success

    def restore_previous_focus(self, cur_focus):
        if not self.config.RESTORE_FOCUS_AFTER_CLICK or not self.is_valid_restore_window(cur_focus):
            return
        time.sleep(self.config.WAIT_REFOCUS)
        try:
            active = self.current_active_window()
            restored = active == cur_focus
            if not restored:
                restored = self.activate_window_with_timestamp(cur_focus)
            if not restored:
                subprocess.run(
                    ["xdotool", "windowfocus", cur_focus, "windowactivate", "--sync", cur_focus, "windowraise", cur_focus],
                    check=False,
                    stderr=subprocess.DEVNULL,
                )
            if self.config.ALIGNMENT_MODE:
                try:
                    active = subprocess.check_output(["xdotool", "getactivewindow"], text=True, stderr=subprocess.DEVNULL).strip()
                except Exception:
                    active = None
                logger.info(f"FOCUS: restored active={self.window_label(active)} target={self.window_label(cur_focus)}")
            self._game_visibility_dirty = True
        except Exception:
            return

    def activate_window_with_timestamp(self, window_id):
        try:
            timestamp = self.x_server_time()
            if timestamp is None:
                return False
            wid = int(str(window_id), 0)
            root = self.disp.screen().root
            window = self.disp.create_resource_object("window", wid)
            active_atom = self.disp.intern_atom("_NET_ACTIVE_WINDOW")
            event = protocol.event.ClientMessage(
                window=window,
                client_type=active_atom,
                data=(32, [2, timestamp, 0, 0, 0]),
            )
            root.send_event(event, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
            window.configure(stack_mode=X.Above)
            self.disp.flush()
            self.disp.sync()
            return True
        except Exception as exc:
            if self.config.ALIGNMENT_MODE:
                logger.info(f"FOCUS: timestamped activation failed for {self.window_label(window_id)}: {exc}")
            return False

    def x_server_time(self):
        now = time.monotonic()
        if self._x_time_offset is not None and self._x_time_offset_at is not None and now - self._x_time_offset_at <= 300.0:
            return (int(time.monotonic() * 1000) + self._x_time_offset) & 0xFFFFFFFF
        if self._x_time_offset is None and self._x_time_offset_at is not None and now - self._x_time_offset_at <= 300.0:
            return None
        server_time = self.probe_x_server_time()
        self._x_time_offset_at = now
        if server_time is None:
            return None
        monotonic_ms = int(time.monotonic() * 1000)
        self._x_time_offset = int(server_time) - monotonic_ms
        return (int(time.monotonic() * 1000) + self._x_time_offset) & 0xFFFFFFFF

    def probe_x_server_time(self):
        if self._x_time_display is None:
            return None
        try:
            ts_disp = self._x_time_display
            root = ts_disp.screen().root
            timestamp_atom = ts_disp.intern_atom("_BBS_BOT_TIMESTAMP")
            root.change_attributes(event_mask=X.PropertyChangeMask)
            ts_disp.sync()
            while ts_disp.pending_events():
                ts_disp.next_event()
            root.change_property(
                timestamp_atom,
                Xatom.CARDINAL,
                32,
                [random.randint(1, 0x7FFFFFFF)],
                X.PropModeReplace,
            )
            ts_disp.flush()
            deadline = time.monotonic() + 0.25
            while time.monotonic() < deadline:
                ts_disp.sync()
                while ts_disp.pending_events():
                    event = ts_disp.next_event()
                    if event.type == X.PropertyNotify and event.atom == timestamp_atom and event.time:
                        return event.time
                time.sleep(0.005)
        except Exception as exc:
            if self.config.ALIGNMENT_MODE:
                logger.info(f"FOCUS: timestamp lookup failed: {exc}")
        return None

    def clear_stale_user_time(self):
        if not self.win_id or self._user_time_cleared_for == self.win_id:
            return
        try:
            ts = self.x_server_time()
            if ts is None:
                if self.config.ALIGNMENT_MODE:
                    logger.info(f"FOCUS: stale _NET_WM_USER_TIME clear deferred for {self.window_label(self.win_id)}: no X timestamp")
                return
            win = self.disp.create_resource_object("window", int(self.win_id))
            user_time_atom = self.disp.intern_atom("_NET_WM_USER_TIME")
            user_time_window_atom = self.disp.intern_atom("_NET_WM_USER_TIME_WINDOW")
            delegate_prop = win.get_full_property(user_time_window_atom, Xatom.WINDOW)
            target = win
            if delegate_prop and len(delegate_prop.value):
                target = self.disp.create_resource_object("window", int(delegate_prop.value[0]))
            cur = target.get_full_property(user_time_atom, Xatom.CARDINAL)
            if cur and len(cur.value):
                old = int(cur.value[0]) & 0xFFFFFFFF
            else:
                old = None
            if old is not None and old != ts and (self.x_timestamp_after(old, ts) or old > ts):
                target.change_property(user_time_atom, Xatom.CARDINAL, 32, [ts], X.PropModeReplace)
                self.disp.flush()
                logger.warning(f"FOCUS: cleared stale _NET_WM_USER_TIME {old} -> {ts}")
            self._user_time_cleared_for = self.win_id
        except Exception as exc:
            if self.config.ALIGNMENT_MODE:
                logger.info(f"FOCUS: stale _NET_WM_USER_TIME check failed: {exc}")

    @staticmethod
    def x_timestamp_after(candidate, reference):
        return ((int(candidate) - int(reference)) & 0xFFFFFFFF) < 0x80000000 and int(candidate) != int(reference)

    @staticmethod
    def monotonic_x_timestamp_fallback():
        return int(time.monotonic() * 1000) & 0xFFFFFFFF

    def capture_loop_focus(self):
        self._loop_restore_focus = None
        self._loop_restore_focus_at = 0.0
        focus = self.current_active_window()
        if self.is_valid_restore_window(focus):
            self.remember_user_focus(focus)
            self._loop_restore_focus = focus
            self._loop_restore_focus_at = time.time()
        elif self.config.ALIGNMENT_MODE:
            logger.info(f"FOCUS: loop sample ignored active={self.window_label(focus)} game={self.window_label(self.win_id)}")

    def restore_focus_for_click(self):
        cur_focus = self.current_active_window()
        now = time.time()
        cur_valid = self.is_valid_restore_window(cur_focus)
        loop_valid = self.is_valid_restore_window(self._loop_restore_focus)
        fallback_valid = self.recent_user_focus_is_valid()
        detail = {
            "preclick": cur_focus,
            "preclick_valid": cur_valid,
            "loop": self._loop_restore_focus,
            "loop_valid": loop_valid,
            "loop_age": now - self._loop_restore_focus_at if self._loop_restore_focus_at else float("inf"),
            "fallback": self._last_non_game_focus,
            "fallback_valid": fallback_valid,
            "fallback_age": now - self._last_non_game_focus_at if self._last_non_game_focus_at else float("inf"),
            "preclick_eq_loop": cur_focus == self._loop_restore_focus,
            "preclick_eq_fallback": cur_focus == self._last_non_game_focus,
        }
        if cur_valid:
            self.remember_user_focus(cur_focus)
            return cur_focus, cur_focus, "current_preclick", detail
        if loop_valid:
            return cur_focus, self._loop_restore_focus, "loop_sample", detail
        if fallback_valid:
            return cur_focus, self._last_non_game_focus, "recent_fallback", detail
        return cur_focus, None, "none", detail

    def remember_user_focus(self, window_id):
        self._last_non_game_focus = window_id
        self._last_non_game_focus_at = time.time()

    def recent_user_focus_is_valid(self):
        if time.time() - self._last_non_game_focus_at > self.config.WAIT_REFOCUS_FALLBACK_MAX_AGE:
            return False
        return self.is_valid_restore_window(self._last_non_game_focus)

    def is_valid_restore_window(self, window_id):
        if not window_id or window_id == self.win_id:
            return False
        try:
            return subprocess.run(
                ["xdotool", "getwindowname", str(window_id)],
                capture_output=True,
                text=True,
                timeout=0.25,
            ).returncode == 0
        except Exception:
            return False

    @staticmethod
    def current_active_window():
        try:
            return subprocess.check_output(["xdotool", "getactivewindow"], text=True, stderr=subprocess.DEVNULL).strip()
        except Exception:
            return None

    def window_label(self, window_id):
        if not window_id:
            return "none"
        try:
            name = subprocess.check_output(
                ["xdotool", "getwindowname", str(window_id)],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=0.25,
            ).strip()
        except Exception:
            name = "unknown"
        return f"{window_id}:{name}"

    def _send_x11_click(self, x, y):
        """Mechanically identical to V6: Silent Xlib injection."""
        try:
            if not self.win_id or not self.region: return False
            window = self.disp.create_resource_object("window", int(self.win_id))
            # V2 Accuracy: Use physical screen region offset to bypass OS titlebar scaling
            rel_x, rel_y = x - self.region[0], y - self.region[1]
            event_time = self.x_server_time()
            if event_time is None:
                event_time = self.monotonic_x_timestamp_fallback()
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
                "time": event_time,
            }
            window.send_event(protocol.event.ButtonPress(**details), propagate=True)
            window.send_event(protocol.event.ButtonRelease(**details), propagate=True)
            self.disp.flush()
            self.disp.sync()
            return True
        except Exception: return False

    def is_safe_room_okay_context(self, haystack=None):
        if self.state not in {"GAME_STARTUP", "SCAN_ROOMS", "JOIN_PENDING", "RECOVERY", "MENU", "READY", "CHECK_RUN_START"}: return False
        for a in ["ingame_auto_on", "ingame_auto_off", "retire"]:
            if self.find_image(a, haystack=haystack): return False
        return True

    def has_room_list_context(self, haystack=None):
        return bool(self.find_image("auto", haystack=haystack) or self.find_image("search_again", haystack=haystack))

    def has_room_fail_context(self, haystack=None):
        return bool(
            self.has_room_list_context(haystack)
            or self.find_image("room_not_met", haystack=haystack)
            or self.state == "JOIN_PENDING"
        )

    def has_network_error_context(self, haystack=None):
        return bool(self.find_image("network_title_error", haystack=haystack))

    def close_room_fail_modal(self, haystack=None, reason="closed_room_coop_quest_menu"):
        if not (self.find_image("closed_room_coop_quest_menu", haystack=haystack) and self.find_image("unavailable_close", haystack=haystack)):
            return False
        logger.warning("GLOBAL: No Available Rooms modal confirmed")
        if self.smart_click("unavailable_close", "dismiss no available rooms", verify_key="closed_room_coop_quest_menu", haystack=haystack):
            self.route_room_fail(reason)
            return True
        return False

    def close_coop_menu_modal(self, haystack=None, reason="coop menu modal"):
        if not self.find_image("closed_room_coop_quest_menu", haystack=haystack):
            return False
        logger.warning(f"GLOBAL: Co-Op Quest Menu modal confirmed ({reason})")
        if self.smart_click(
            "closed_room_coop_quest_menu",
            "return co-op quest menu",
            verify_key="closed_room_coop_quest_menu",
            haystack=haystack,
        ):
            self.transition_to("MENU")
            return True
        return False

    def capture_snapshot(self):
        if not self.region:
            return None
        monitor = {"top": self.region[1], "left": self.region[0], "width": self.region[2], "height": self.region[3]}
        sct_img = self.sct.grab(monitor)
        self.snapshot = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        return self.snapshot

    def box_y_ratio(self, box):
        if not self.region:
            return 0.0
        return (box.top - self.region[1]) / max(1, self.region[3])

    def valid_menu_box(self, box):
        return self.box_y_ratio(box) >= self.config.MENU_TEMPLATE_MIN_Y_RATIO

    def find_menu_image(self, key, haystack=None):
        matches = self.find_all(key, confidence=self.get_template_confidence(key), haystack=haystack)
        valid = [m for m in matches if self.valid_menu_box(m)]
        if not valid:
            return None
        return sorted(valid, key=lambda b: b.top)[0]

    def current_room_signature(self, autos):
        rows = []
        for a in BBSBot.dedupe_autos(autos, self.config):
            cy = a.top + a.height // 2
            rows.append(round(cy / self.config.ROOM_ROW_BUCKET) * self.config.ROOM_ROW_BUCKET)
        return tuple(sorted(rows))

    def note_room_list_signature(self, signature):
        if signature != self._last_room_signature:
            if self._last_room_signature is not None:
                logger.info("SCAN: Room list changed.")
            self._last_room_signature = signature

    def room_row_bucket(self, y):
        return round(y / self.config.ROOM_ROW_BUCKET) * self.config.ROOM_ROW_BUCKET

    def log_last_room_failed(self, reason):
        if self._last_join_row is None:
            return
        row = self.room_row_bucket(self._last_join_row)
        logger.info(f"ROOM FAIL: {reason}; forcing Search Again after row {row}")

    def refresh_delay(self):
        return self.config.WAIT_SEARCH_AGAIN + random.uniform(0.15, 0.75)

    def click_search_again(self, haystack=None, reason="refresh list"):
        now = time.time()
        if now < self._next_refresh_time:
            return False
        if not self.find_image("search_again", haystack=haystack):
            return False
        if self.smart_click("search_again", reason, haystack=haystack):
            self.search_start_time = time.time()
            self._force_refresh = False
            self.clear_room_scan_tracking("search again")
            self._next_refresh_time = time.time() + self.refresh_delay()
            time.sleep(self.config.WAIT_REFRESH_COOLDOWN)
            return True
        return False

    def route_room_fail(self, key):
        self.log_last_room_failed(key)
        self.search_start_time = time.time()
        self._force_refresh = True
        self._next_refresh_time = time.time() + self.config.ROOM_FAIL_REFRESH_DELAY
        if self.state in {"GAME_STARTUP", "RECOVERY"}:
            self.transition_to("RECOVERY")
        else:
            self.transition_to("SCAN_ROOMS")

    def build_room_candidates(self, haystack=None):
        autos = self.find_all("auto", haystack=haystack)
        if not autos:
            return [], (), []
        signature = self.current_room_signature(autos)
        v_rules = self.find_all("room_rules_valid", confidence=self.config.CONF_LOOSE, haystack=haystack)
        invalid_rules = self.find_all("room_not_met", confidence=self.config.CONF_POPUP, haystack=haystack)
        valid = BBSBot.match_rooms(autos, v_rules, self.config)
        candidates = []
        matched_ids = set()
        invalid_count = 0
        for auto, rule in valid:
            if BBSBot.has_invalid_room_rule(auto, invalid_rules, self.config):
                invalid_count += 1
                continue
            candidates.append((auto, rule, "strict"))
            matched_ids.add(id(auto))
        if self.config.ALLOW_ALL_AUTO_ROOMS:
            for a in BBSBot.dedupe_autos(autos, self.config):
                if id(a) not in matched_ids and not BBSBot.has_invalid_room_rule(a, invalid_rules, self.config):
                    candidates.append((a, None, "fallback"))
        if invalid_count:
            logger.info(f"SCAN: Rejected {invalid_count} room row(s) with Room Rules Not Met.")
        return autos, signature, candidates

    def candidate_still_valid_before_click(self, row_y, mode):
        time.sleep(self.config.ROOM_PRE_CLICK_RECHECK_GAP)
        snap = self.capture_snapshot()
        _, _, candidates = self.build_room_candidates(snap)
        row = self.room_row_bucket(row_y)
        for auto, _, candidate_mode in candidates:
            candidate_row = self.room_row_bucket(auto.top + auto.height // 2)
            if candidate_row == row and candidate_mode == mode:
                return True
        logger.info(f"SCAN: Candidate row {row} failed pre-click rule recheck; skipping.")
        return False

    def sort_room_candidates(self, candidates):
        room_order = -1 if self.config.PREFER_BOTTOM_ROOMS else 1
        return sorted(candidates, key=lambda c: (0 if c[2] == "strict" else 1, room_order * c[0].top))

    def click_room_candidate(self, auto, rule, mode, haystack=None):
        row_y = auto.top + auto.height // 2
        label = "Auto + Rules" if mode == "strict" else "Auto Only"
        if mode == "strict" and rule:
            px, py = (auto.left + rule.left + rule.width) // 2, row_y
        else:
            px, py = auto.left + self.config.ALLOW_ALL_AUTO_OFFSET_X, row_y

        target = pyscreeze.Box(
            px - self.config.SNATCH_BOX_OFFSET[0],
            py - self.config.SNATCH_BOX_OFFSET[1],
            self.config.SNATCH_BOX_DIM[0],
            self.config.SNATCH_BOX_DIM[1],
        )

        if self.smart_click(target, f"snatch {mode} ({label})", haystack=haystack):
            self._last_join_row = row_y
            self.transition_to("JOIN_PENDING")
            return True
        return False

    def clicked_row_has_room_not_met(self, haystack=None):
        if self._last_join_row is None:
            return False
        clicked_row = self.room_row_bucket(self._last_join_row)
        for marker in self.find_all("room_not_met", confidence=self.config.CONF_POPUP, haystack=haystack):
            marker_row = self.room_row_bucket(marker.top + marker.height // 2)
            if marker_row == clicked_row:
                return True
        return False

    def clear_room_scan_tracking(self, reason):
        if self._last_room_signature is not None or self._last_join_row is not None:
            logger.info(f"SCAN: Clearing room scan tracking ({reason}).")
        self._last_room_signature = None
        self._last_join_row = None
        self._next_refresh_time = 0.0

    def handle_global_popups(self, haystack=None):
        now = time.time()
        if now - self._last_popup_check < self.config.POLL_POPUP: return False
        self._last_popup_check = now
        
        # Only block the generic modal 'close' button.
        # We MUST allow 'unavailable_close' and others even in ENTER_ROOM_LIST 
        # because those are real errors.
        blocked = ["close"] if self.state in ["ENTER_ROOM_LIST"] else []
        
        if self.find_image("download_data_title", haystack=haystack) and self.find_image("download_data_yes", haystack=haystack):
            logger.warning("GLOBAL: Download data prompt confirmed")
            if self.smart_click("download_data_yes", "confirm download data", verify_key="download_data_yes", haystack=haystack):
                self.reset_quest_watchdog("download-data")
                time.sleep(self.config.WAIT_DOWNLOAD_AFTER_CONFIRM)
                self.transition_to("RECOVERY")
                return True

        if (
            self.find_image("update_return_title", haystack=haystack)
            and self.find_image("update_return_message", haystack=haystack)
            and self.find_image("update_return_ok", haystack=haystack)
        ):
            logger.warning("GLOBAL: Update return-to-title prompt confirmed")
            if self.smart_click("update_return_ok", "dismiss update return prompt", verify_key="update_return_message", haystack=haystack):
                self.reset_quest_watchdog("update-return")
                self.transition_to("RECOVERY")
                return True

        if self.find_image("login_failed_title", haystack=haystack) and self.find_image("login_failed_ok", haystack=haystack):
            logger.warning("GLOBAL: Login failed prompt confirmed")
            if self.smart_click("login_failed_ok", "dismiss login failed", verify_key="login_failed_title", haystack=haystack):
                self.transition_to("RECOVERY")
                return True

        if self.find_image("brave_bonus_title", haystack=haystack) and self.find_image("brave_bonus_cancel", haystack=haystack):
            logger.warning("GLOBAL: Brave Bonus prompt confirmed; canceling for later claim")
            if self.smart_click("brave_bonus_cancel", "cancel brave bonus", verify_key="brave_bonus_cancel", haystack=haystack):
                self.transition_to("RECOVERY")
                return True

        if self.find_image("player_rank_reward_title", haystack=haystack) and self.find_image("player_rank_reward_close", haystack=haystack):
            logger.warning("GLOBAL: Player Rank Reward prompt confirmed")
            if self.smart_click(
                "player_rank_reward_close",
                "dismiss player rank reward",
                verify_key="player_rank_reward_title",
                haystack=haystack,
            ):
                if self.state == "RECOVERY":
                    self.transition_to("FINISH")
                return True

        if self.has_network_error_context(haystack):
            retry_key = "network_retry_button" if self.find_image("network_retry_button", haystack=haystack) else "disconnect_retry"
            if self.find_image(retry_key, haystack=haystack):
                logger.warning("GLOBAL: Network retry prompt confirmed")
                if self.smart_click(retry_key, "network retry", verify_key=retry_key, haystack=haystack):
                    self.disconnect_retry_count += 1
                    cool_time = random.randint(*self.config.WAIT_DISCONNECT_COOLING)
                    logger.warning(f"DISCONNECT: Cooling down for {cool_time}s...")
                    time.sleep(cool_time)
                    self.transition_to("RECOVERY")
                    return True

        if self.close_room_fail_modal(haystack=haystack):
            return True

        if self.close_coop_menu_modal(haystack=haystack):
            return True

        for key in ["close_news", "okay", "close"]:
            if key in blocked: continue
            if key == "okay" and not self.is_safe_room_okay_context(haystack): continue
            
            conf = self.get_template_confidence(key)

            if self.find_image(key, confidence=conf, haystack=haystack):
                logger.warning(f"GLOBAL: Popup '{key}' confirmed")
                if key == "close_news": time.sleep(self.config.DELAY_NEWS)

                if not self.smart_click(key, f"dismiss {key}", verify_key=key, haystack=haystack):
                    return False

                # Realign with visible state instead of trusting stale state.
                if key == "close":
                    if self.state == "RUNNING":
                        self.transition_to("RECOVERY")
                    elif self.has_room_fail_context(haystack):
                        self.route_room_fail(key)
                    else:
                        self.transition_to("RECOVERY")
                    return True

                if key == "okay":
                    if self.has_room_fail_context(haystack):
                        self.route_room_fail(key)
                    else:
                        self.transition_to("MENU")
                    return True

                if self.state not in ["GAME_STARTUP", "RUNNING", "FINISH", "CHECK_RUN_START", "RECOVERY"]:
                    self.transition_to("MENU")
                return True
        return False

    def handle_menu(self, haystack=None):
        open_coop_quest = self.find_menu_image("open_coop_quest", haystack=haystack)
        if open_coop_quest:
            return self.smart_click(open_coop_quest, "specific quest", "enter_room_button", target_state="ENTER_ROOM_LIST", wait_for_appearance=True, haystack=haystack)
        coop_quest = self.find_menu_image("coop_quest", haystack=haystack)
        if coop_quest:
            return self.smart_click(coop_quest, "expand menu", "open_coop_quest", wait_for_appearance=True, haystack=haystack)
        for key in ["coop_1", "coop_2"]:
            if self.find_image(key, haystack=haystack): return self.smart_click(key, f"navigate {key}", haystack=haystack)
        if self.find_image("enter_room_button", haystack=haystack): self.transition_to("ENTER_ROOM_LIST"); return True
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_LOBBY_EXPAND: self.transition_to("RECOVERY"); return True
        return False

    def handle_enter_room_list(self, haystack=None):
        # Case A: We are on the 'Select a Room Type' menu
        if self.find_image("enter_room_button", haystack=haystack):
            # Stay in ENTER_ROOM_LIST after click so the generic 'close' button remains blocked.
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
        
        # Allow several scan cycles before escalating to recovery.
        if time.time() - self.search_start_time > self.config.TIMEOUT_SCAN_IDLE: 
            logger.warning("SCAN_ROOMS: Idle timeout reached. Recovering...")
            self.transition_to("RECOVERY"); return True

        if self._force_refresh:
            if self.click_search_again(haystack=haystack):
                return True
            return False
        
        # Stability Pause: Wait for room list to settle
        time.sleep(0.4)
        scan_haystack = self.capture_snapshot() or haystack
        
        autos, signature, candidates = self.build_room_candidates(scan_haystack)
        if autos:
            self.note_room_list_signature(signature)
            
            # Transparency: Log the scan results
            strict_count = sum(1 for _, _, m in candidates if m == "strict")
            fallback_count = sum(1 for _, _, m in candidates if m == "fallback")
            if candidates:
                logger.info(f"SCAN: Found {len(candidates)} rooms (Strict: {strict_count}, Fallback: {fallback_count})")

            # If we found candidates, try to snatch them immediately.
            # If a snatch click fails to trigger a transition, force a list refresh.
            if candidates and not self._force_refresh:
                candidates = self.sort_room_candidates(candidates)
                self.search_start_time = time.time() # Reset idle timer on discovery
                skipped = 0
                for auto, rule, mode in candidates:
                    row_y = auto.top + auto.height // 2
                    if not self.candidate_still_valid_before_click(row_y, mode):
                        skipped += 1
                        continue
                    if self.click_room_candidate(auto, rule, mode, haystack=scan_haystack):
                        return True
                if skipped:
                    logger.info(f"SCAN: Skipped {skipped} invalid room row(s); refreshing list.")
                    self._force_refresh = True
                return True
        
        # If no valid rooms are available, refresh the list.
        if self._force_refresh or self.find_image("search_again", haystack=scan_haystack):
            if time.time() - self.search_start_time > self.config.WAIT_SEARCH_AGAIN or self._force_refresh:
                if self.click_search_again(haystack=scan_haystack):
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
                # Restore V6 Directional Logic: Rule text is physically below Auto OK
                if ry > ay:
                    d = abs(ry - ay) + abs(rx - ax) * config.ROOM_MATCH_WEIGHT
                    if d < min_d and d < config.MAX_RULE_DISTANCE:
                        min_d, best_r = d, r
            if best_r: valid.append((a, best_r))
        return valid

    @staticmethod
    def has_invalid_room_rule(auto, invalid_rules, config):
        ax, ay = auto.left + auto.width // 2, auto.top + auto.height // 2
        for r in invalid_rules:
            rx, ry = r.left + r.width // 2, r.top + r.height // 2
            if ry > ay:
                d = abs(ry - ay) + abs(rx - ax) * config.ROOM_MATCH_WEIGHT
                if d < config.MAX_RULE_DISTANCE:
                    return True
        return False

    @staticmethod
    def dedupe_autos(matches, config):
        unique = []
        for m in matches:
            cx, cy = m.left + m.width // 2, m.top + m.height // 2
            if not any(((cx - (u.left + u.width // 2))**2 + (cy - (u.top + u.height // 2))**2)**0.5 < config.AUTO_ICON_DEDUPE_DIST for u in unique): unique.append(m)
        return unique

    def handle_join_pending(self, haystack=None):
        ready_box = self.find_stable_image("ready", confidence=self.config.CONF_READY, frames=3)
        if ready_box:
            self.clear_room_scan_tracking("ready found")
            ready_sleep_start = time.perf_counter()
            time.sleep(self.config.DELAY_READY)
            logger.info(f"READY TRACE: delay_ready={time.perf_counter() - ready_sleep_start:.3f}s configured={self.config.DELAY_READY:.2f}")
            return self.smart_click(ready_box, "snap ready", verify_key="ready", target_state="CHECK_RUN_START", haystack=haystack)
        if self.run_started():
            self.clear_room_scan_tracking("run started before ready")
            self.transition_to("RUNNING")
            return True
        if self.close_room_fail_modal(haystack=haystack, reason="closed_room_coop_quest_menu"):
            return True
        if self.clicked_row_has_room_not_met(haystack=haystack) and self.has_room_list_context(haystack):
            logger.info("JOIN_PENDING: Clicked room row shows rules not met; treating join as failed.")
            self.log_last_room_failed("room_not_met")
            self._force_refresh = True
            self.transition_to("SCAN_ROOMS")
            return True
        if time.time() - self.last_state_change_time > self.config.JOIN_FAIL_LIST_GRACE:
            if self.find_image("auto", haystack=haystack) or self.find_image("search_again", haystack=haystack):
                logger.info("Room join failed silently. Forcing list refresh.")
                self.log_last_room_failed("silent join fail")
                self._force_refresh = True
                self.transition_to("SCAN_ROOMS"); return True
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_LOBBY_JOIN: self.transition_to("RECOVERY"); return True
        return False

    def handle_ready(self, haystack=None):
        ready_box = self.find_stable_image("ready", confidence=self.config.CONF_READY, frames=3)
        if ready_box:
            self.clear_room_scan_tracking("ready state")
            ready_sleep_start = time.perf_counter()
            time.sleep(self.config.DELAY_READY)
            logger.info(f"READY TRACE: delay_ready={time.perf_counter() - ready_sleep_start:.3f}s configured={self.config.DELAY_READY:.2f}")
            return self.smart_click(ready_box, "ready button", verify_key="ready", target_state="CHECK_RUN_START", haystack=haystack)
        if self.run_started():
            self.clear_room_scan_tracking("run started before ready")
            self.transition_to("RUNNING")
            return True
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_RUN_START: self.retire_from_quest(haystack=haystack); return True
        return False

    def run_started(self):
        return self.find_stable_image("ingame_auto_on", frames=3) or self.find_stable_image("ingame_auto_off", frames=3)

    def handle_check_run_start(self, haystack=None):
        if self.run_started():
            self.clear_room_scan_tracking("run started")
            self.transition_to("RUNNING"); return True
        if time.time() - self.last_state_change_time > self.config.TIMEOUT_RUN_START: self.retire_from_quest(haystack=haystack); return True
        return False

    def handle_running(self, haystack=None):
        if self.find_image("game_start", haystack=haystack):
            logger.warning("RUNNING: Title screen visible; reanchoring.")
            self.transition_to("RECOVERY")
            return True
        if self.find_stable_image("tap1", frames=3): self.transition_to("FINISH"); return True
        return False

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
        if self.find_menu_image("coop_quest", haystack=haystack) or self.find_menu_image("open_coop_quest", haystack=haystack): self.transition_to("MENU"); return True
        return False

    def handle_recovery(self, haystack=None):
        if self.config.ALIGNMENT_MODE: self.save_debug_screenshot("lost_in_recovery")
        if self.close_coop_menu_modal(haystack=haystack, reason="recovery"):
            return True
        if self.recovery_timed_out(): return True
        for s, t in self.RECOVERY_MAP:
            if self.find_image(t, haystack=haystack): self.transition_to(s); return True
        return False

    def handle_distraction(self, haystack=None):
        if not self.config.ENABLE_COFFEE_BREAKS:
            logger.info("DISTRACTION: Coffee breaks disabled; continuing.")
            self.transition_to("RECOVERY")
            return True
        duration = random.randint(*self.config.DISTRACTION_DURATION)
        logger.info(f"DISTRACTION: Taking a coffee break ({duration}s)...")
        time.sleep(duration)
        
        # Reset the quest watchdog when an intentional break ends.
        # We must zero out all timers because the 2-8 min sleep would otherwise
        # leave us with very little 'budget' before a hard restart (10m).
        self.reset_quest_watchdog("post-break") 
        self.search_start_time = time.time()
        self.last_state_change_time = time.time()
        
        self.fatigue_start_time = time.time()
        self.active_profile = "SHIKAI_MAX"
        self.config._apply_profile(self.active_profile)
        if self.config.CIRCADIAN_PROFILES:
            self.next_profile_swap = time.time() + random.randint(*self.config.CIRCADIAN_PROFILES[self.active_profile]["DURATION_MINS"]) * 60
        
        # Let recovery find the current visible UI after the restart.
        self.transition_to("RECOVERY")
        return True

    def transition_to(self, state):
        if self.state != state:
            logger.info(f"TRANSITION: {self.state} -> {state}"); old = self.state; self.state = state; self.last_state_change_time = time.time()
            self._game_visibility_dirty = True
            if self.config.ALIGNMENT_MODE: self.save_debug_screenshot(f"to_{state}")
            if state == "RECOVERY": self.save_error_snapshot(f"recovery_from_{old}")
            if state in ["RUNNING", "READY"]: self.reset_quest_watchdog(state.lower())
            if state == "SCAN_ROOMS": self.search_start_time = time.time()
            if state in ["MENU", "READY", "CHECK_RUN_START", "ENTER_ROOM_LIST"]: self._run_counted = False
            if old == "FINISH" and state != "FINISH": self.reset_quest_watchdog("completed")

    def reset_quest_watchdog(self, reason="progress"):
        logger.info(f"WATCHDOG Reset ({reason})"); self.quest_watchdog = time.time(); self.consecutive_recovery_count = 0

    def recovery_timed_out(self):
        if self.state == "RECOVERY" and time.time() - self.last_state_change_time > self.config.TIMEOUT_STUCK:
            self.recover_game("recovery_timeout")
            return True
        return False

    def retire_from_quest(self, haystack=None):
        logger.warning("Retiring..."); self.expected_okay_context = "RETIRE_CONFIRM"
        if self.find_image("retire", haystack=haystack):
            if self.smart_click("retire", "retire", verify_key="okay", wait_for_appearance=True, haystack=haystack):
                self.smart_click("okay", "confirm", verify_key="okay")
        self.expected_okay_context = None; self.transition_to("MENU"); return True

    def recover_game(self, reason="hard_recover_game", capture_evidence=True):
        if capture_evidence:
            self.save_hard_restart_snapshot(reason)
            self.save_error_snapshot("hard_recover_game")
        else:
            logger.info(f"Startup restart requested: {reason}")
        self.consecutive_recovery_count += 1
        if self.consecutive_recovery_count > self.config.MAX_CONSECUTIVE_RECOVERIES:
            logger.error("CIRCUIT BREAKER: Max consecutive recoveries reached. Exiting.")
            self.log_session_summary()
            sys.exit(1)
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
        if time.time() - self.quest_watchdog > self.config.TIMEOUT_QUEST_MAX: self.recover_game("quest_watchdog")

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
            self.clear_stale_user_time()

            try:
                xwin_res = subprocess.run(["xwininfo", "-id", self.win_id], capture_output=True, text=True)
            except FileNotFoundError:
                xwin_res = None
                if self.config.ALIGNMENT_MODE:
                    logger.info("WINDOW: xwininfo missing; using xdotool geometry fallback")
            if xwin_res and xwin_res.returncode == 0:
                values = {}
                for name, pattern in {
                    "X": r"Absolute upper-left X:\s*(-?\d+)",
                    "Y": r"Absolute upper-left Y:\s*(-?\d+)",
                    "WIDTH": r"Width:\s*(\d+)",
                    "HEIGHT": r"Height:\s*(\d+)",
                }.items():
                    match = re.search(pattern, xwin_res.stdout)
                    if match:
                        values[name] = int(match.group(1))
                if values.get("WIDTH", 0) > 100 and values.get("HEIGHT", 0) > 100:
                    self.region = (values["X"], values["Y"], values["WIDTH"], values["HEIGHT"])
                    return self.region

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
        if not self.win_id:
            return
        subprocess.run(["wmctrl", "-i", "-r", self.win_id, "-b", "add,sticky,above"], check=False, stderr=subprocess.DEVNULL)
        try:
            state = subprocess.check_output(["xprop", "-id", self.win_id, "WM_STATE"], text=True, stderr=subprocess.DEVNULL).lower()
            if "iconic" in state: subprocess.run(["xdotool", "windowraise", self.win_id], check=False, stderr=subprocess.DEVNULL)
        except Exception: pass

    def ensure_game_visible_for_vision(self):
        if not self.win_id or not self._game_visibility_dirty:
            return
        active_before = self.current_active_window() if self.config.ALIGNMENT_MODE else None
        self.setup_window_properties()
        subprocess.run(["xdotool", "windowraise", self.win_id], check=False, stderr=subprocess.DEVNULL)
        if self.config.ALIGNMENT_MODE:
            active_after = self.current_active_window()
            logger.info(
                f"FOCUS TRACE: vision visibility active_before={self.window_label(active_before)} "
                f"active_after={self.window_label(active_after)} game={self.window_label(self.win_id)}"
            )
        self._game_visibility_dirty = False

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

    def run(self, restart_game_on_start=False):
        if restart_game_on_start: self.recover_game("startup_restart", capture_evidence=False)
        self.reset_quest_watchdog("startup")
        while True:
            try:
                if not self.ensure_window_ready():
                    logger.warning("Game window not found; waiting...")
                    time.sleep(2.0)
                    continue

                self.capture_loop_focus()

                self.ensure_game_visible_for_vision()
                
                monitor = {"top": self.region[1], "left": self.region[0], "width": self.region[2], "height": self.region[3]}
                sct_img = self.sct.grab(monitor); self.snapshot = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                
                self.check_quest_watchdog(); self.update_fatigue(); self.check_circadian_rhythm(); self.check_session_limit()
                if self.recovery_timed_out(): continue
                if self.handle_global_popups(self.snapshot): continue
                handler = self.handlers.get(self.state)
                if handler and handler(self.snapshot): continue
                time.sleep(self.state_idle_delay())
            except Exception:
                logger.exception("Loop Error:")
                self.save_error_snapshot("fatal_loop_error")
                self.transition_to("RECOVERY")
                time.sleep(1)
        self.log_session_summary()

    def state_idle_delay(self):
        return {
            "MENU": self.config.POLL_MENU,
            "RECOVERY": self.config.POLL_RECOVERY,
            "GAME_STARTUP": self.config.POLL_GAME_STARTUP,
            "RUNNING": self.config.POLL_RUNNING,
        }.get(self.state, self.config.POLL_MAIN_LOOP)

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
    parser.add_argument("--no-coffee-breaks", action="store_true")
    parser.add_argument("--short-coffee-breaks", action="store_true")
    parser.add_argument("--top-rooms-first", action="store_true")
    parser.add_argument("--no-refocus", action="store_true")
    parser.add_argument("--profile", choices=["max", "normal"], default="max")
    parser.add_argument("--cpu-affinity", help="Pin bot process to CPU cores, e.g. auto, 8-11, or 8,9,10,11")
    args = parser.parse_args()
    if args.cpu_affinity: apply_cpu_affinity(args.cpu_affinity)
    config = BotConfiguration()
    profile_map = {"max": "SHIKAI_MAX", "normal": "SHIKAI_NORMAL"}
    config.START_PROFILE = profile_map[args.profile]
    config._apply_profile(config.START_PROFILE)
    if args.allow_all_auto_rooms: config.ALLOW_ALL_AUTO_ROOMS = True
    if args.alignment_mode: config.ALIGNMENT_MODE = True
    if args.no_coffee_breaks: config.ENABLE_COFFEE_BREAKS = False
    if args.short_coffee_breaks: config.DISTRACTION_DURATION = config.SHORT_DISTRACTION_DURATION
    if args.top_rooms_first: config.PREFER_BOTTOM_ROOMS = False
    if args.no_refocus: config.RESTORE_FOCUS_AFTER_CLICK = False
    bot = BBSBot(config)
    try: bot.run(restart_game_on_start=args.test_restart)
    except KeyboardInterrupt: bot.log_session_summary(); sys.exit(0)
    except Exception as e: logger.exception(f"Fatal: {e}"); bot.log_session_summary(); sys.exit(1)
