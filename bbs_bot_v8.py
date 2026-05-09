"""BBS Bot V8 AI-Ingestible Strict Phase Candidate.

AI QUICK MAP
============
Runtime model:
    state + phase + expected_context + can_click() + verified smart_click()

State flow:
    GAME_STARTUP -> MENU -> COOP_JOIN_CHOICE -> ROOM_LIST -> JOIN_PENDING
    -> READY -> CHECK_RUN_START -> RUNNING -> FINISH -> ROOM_LIST/COOP_JOIN_CHOICE/MENU

Critical safety laws:
    1. Generic okay.png is never globally safe.
       It is allowed only in ROOM_LIST, JOIN_PENDING, or expected RETIRE_CONFIRM.
    2. join_coop_quest.png is keyed as enter_room_button and is clickable only in COOP_JOIN_CHOICE.
    3. JOIN_PENDING ignores stale room-list anchors until WAIT_JOIN_LIST_GRACE and stable-frame proof.
    4. Known popups route through deterministic recovery, not generic click-and-hope.
    5. Telemetry is append-only JSONL in AGENT_TELEMETRY_DIR for local agents to inspect.

AI navigation anchors in this file:
    - AI_MANIFEST: machine-readable behavior contract
    - BotConfiguration: public tuning knobs
    - BBSBot.RECOVERY_MAP / STATE_PRIORITY / POPUP_PRIORITY: screen classifier inputs
    - BBSBot.current_phase(): state -> safety phase mapping
    - BBSBot.can_click(): allowed-action gate
    - BBSBot.smart_click(): transactional click wrapper
    - BBSBot.handle_global_popups(): known popup router
    - BBSBot.handle_*(): state handlers
    - BBSBot.run(): main priority loop

For agents:
    Do not broad-refactor. Read AI_MANIFEST first, then patch the smallest failing
    phase/region/confidence/routing rule shown by telemetry.
"""

# Lightweight manifest path: allows agents to inspect the behavior contract on
# machines without an X display. This block intentionally runs before pyautogui/Xlib imports.
import sys as _ai_sys
if "--print-ai-manifest" in _ai_sys.argv or "--write-ai-manifest" in _ai_sys.argv:
    import json as _ai_json
    AI_MANIFEST_BOOTSTRAP = {
        "version": "v8_strict_phase_ai_ingest",
        "states": ["GAME_STARTUP", "MENU", "COOP_JOIN_CHOICE", "ROOM_LIST", "JOIN_PENDING", "READY", "CHECK_RUN_START", "RUNNING", "FINISH", "RECOVERY", "DISTRACTION"],
        "phase_by_state": {"GAME_STARTUP": "STARTUP_SAFE", "MENU": "MENU_NAVIGATION", "COOP_JOIN_CHOICE": "JOIN_CHOICE", "ROOM_LIST": "ROOM_SEARCH", "JOIN_PENDING": "JOIN_PENDING", "READY": "LOBBY_SAFE", "CHECK_RUN_START": "JOIN_PENDING", "RUNNING": "LIVE_RUN", "FINISH": "FINISH_REWARD", "RECOVERY": "RECOVERY_CLASSIFY", "DISTRACTION": "UNKNOWN_BLOCKED"},
        "critical_rules": [
            "okay allowed only in ROOM_LIST, JOIN_PENDING, or expected RETIRE_CONFIRM",
            "enter_room_button/images/join_coop_quest.png allowed only in COOP_JOIN_CHOICE",
            "JOIN_PENDING ignores stale room-list anchors before grace/stable-frame proof",
            "known failure popups use deterministic routing",
            "telemetry writes JSONL/current_state/screenshots for agents",
        ],
        "room_modes": {"strict_rules": "default", "all_auto": "experimental opt-in"},
        "telemetry_files": ["agent_telemetry/current_state.json", "agent_telemetry/events.jsonl", "agent_telemetry/alerts.jsonl", "agent_telemetry/screenshots/"],
    }
    _payload = _ai_json.dumps(AI_MANIFEST_BOOTSTRAP, indent=2, sort_keys=True)
    if "--write-ai-manifest" in _ai_sys.argv:
        _idx = _ai_sys.argv.index("--write-ai-manifest")
        if _idx + 1 >= len(_ai_sys.argv):
            raise SystemExit("--write-ai-manifest requires a path")
        with open(_ai_sys.argv[_idx + 1], "w", encoding="utf-8") as _f:
            _f.write(_payload + "\n")
    if "--print-ai-manifest" in _ai_sys.argv:
        print(_payload)
    raise SystemExit(0)


import argparse
import os
import sys
import time
import subprocess
import random
import logging
import math
import json
import shutil
from typing import Optional, List, Tuple, Dict, Any, Union
from dataclasses import dataclass

import pyautogui
import pyscreeze
from Xlib import X, display, protocol
from PIL import Image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("v8_strict_phase.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


AI_MANIFEST: Dict[str, Any] = {
    "version": "v8_strict_phase_ai_ingest",
    "purpose": "Bleach Brave Souls co-op automation with strict phase-gated click safety and agent-readable telemetry.",
    "do_not_broad_refactor": True,
    "runtime_model": {
        "formula": "state + phase + expected_context + can_click + verified_action + telemetry",
        "truth_order": ["blocking_safe_context", "observed_anchor", "verified_click_outcome", "state_variable", "previous_intent"],
    },
    "states": [
        "GAME_STARTUP", "MENU", "COOP_JOIN_CHOICE", "ROOM_LIST", "JOIN_PENDING",
        "READY", "CHECK_RUN_START", "RUNNING", "FINISH", "RECOVERY", "DISTRACTION",
    ],
    "state_flow_happy_path": [
        "GAME_STARTUP", "MENU", "COOP_JOIN_CHOICE", "ROOM_LIST", "JOIN_PENDING",
        "READY", "CHECK_RUN_START", "RUNNING", "FINISH", "ROOM_LIST",
    ],
    "phase_by_state": {
        "GAME_STARTUP": "STARTUP_SAFE",
        "MENU": "MENU_NAVIGATION",
        "COOP_JOIN_CHOICE": "JOIN_CHOICE",
        "ROOM_LIST": "ROOM_SEARCH",
        "JOIN_PENDING": "JOIN_PENDING",
        "READY": "LOBBY_SAFE",
        "CHECK_RUN_START": "JOIN_PENDING",
        "RUNNING": "LIVE_RUN",
        "FINISH": "FINISH_REWARD",
        "RECOVERY": "RECOVERY_CLASSIFY",
        "DISTRACTION": "UNKNOWN_BLOCKED",
    },
    "critical_templates": {
        "enter_room_button": {
            "image": "images/join_coop_quest.png",
            "meaning": "Join Room button on Create/Join choice screen, not a room-list join action.",
            "allowed_only_in_states": ["COOP_JOIN_CHOICE"],
        },
        "okay": {
            "image": "images/okay.png",
            "meaning": "Shared OK button; safe only in room-error contexts or explicit retire confirmation.",
            "allowed_only_in_states": ["ROOM_LIST", "JOIN_PENDING"],
            "allowed_contexts": ["RETIRE_CONFIRM"],
            "forbidden_live_states": ["RUNNING", "CHECK_RUN_START", "READY", "FINISH", "RECOVERY", "MENU", "GAME_STARTUP"],
        },
        "closed_room_coop_quest_menu": {
            "meaning": "Room full/not-met style error. Dismiss, short reanchor, fallback safely.",
            "route": "reanchor_after_room_error(prefer_refresh=False)",
        },
        "unavailable_close": {
            "meaning": "Unavailable room error. Dismiss, short reanchor, prefer room-list refresh.",
            "route": "reanchor_after_room_error(prefer_refresh=True)",
        },
    },
    "room_modes": {
        "strict_rules": "Default; snatch AUTO rows only when room_rules_valid is nearby.",
        "all_auto": "Experimental; dedupe all AUTO rows and rely on room-error cleanup for invalid rooms.",
    },
    "known_failure_routes": {
        "close_news": "startup-safe blocker; close before startup navigation continues",
        "closed_room_coop_quest_menu": "ROOM_LIST/JOIN_PENDING popup -> dismiss -> reanchor -> fallback MENU/ROOM_LIST",
        "unavailable_close": "ROOM_LIST/JOIN_PENDING popup -> dismiss -> reanchor -> _force_refresh ROOM_LIST",
        "disconnect_retry": "count streak -> dismiss -> cooldown -> recover_game if over limit",
        "dangerous_unknown_okay": "save screenshot + telemetry + raise RuntimeError before click",
    },
    "telemetry_files": {
        "current_state": "agent_telemetry/current_state.json",
        "events": "agent_telemetry/events.jsonl",
        "alerts": "agent_telemetry/alerts.jsonl",
        "screenshots": "agent_telemetry/screenshots/",
        "latest_screenshot": "agent_telemetry/latest_screenshot.txt",
        "latest_alert_screenshot": "agent_telemetry/latest_alert_screenshot.txt",
    },
    "agent_rules": [
        "Never add generic global okay clicking.",
        "Never click enter_room_button outside COOP_JOIN_CHOICE.",
        "Do not add masking unless a screenshot-backed test proves rectangular regions cannot work.",
        "Do not globally raise confidence; tune template-specific confidence or region first.",
        "Patch one failed decision at a time using telemetry and screenshots.",
    ],
}


def get_ai_manifest() -> Dict[str, Any]:
    """Return the machine-readable behavior contract for agents/tests."""
    return AI_MANIFEST


# === AI_SECTION: CONFIG_PUBLIC_KNOBS ===
@dataclass
class BotConfiguration:
    """Minimal public tuning surface for V8.

    The bot still exposes old attribute names internally because handlers use
    them, but users/agents should tune only the small group below. Everything
    else is derived in ``_derive_runtime_aliases`` or the Shikai profile map.

    Primary knobs:
      - ROOM_SEARCH_MODE / --allow-all-auto-rooms
      - CONF_NORMAL, CONF_JOIN_CHOICE, CONF_POPUP if telemetry proves matching issues
      - BOT_SPEED_PROFILE, MAIN_POLL, STARTUP_WAIT_TIMEOUT if the whole bot feels slow
      - FOCUS_MODE only if screenshots show focus/visibility problems
    """

    RAW_TITLE: str = "Bleach: Brave Souls"

    # Speed / timing: keep this tiny. Derived aliases below feed the old names.
    BOT_SPEED_PROFILE: str = "fast"  # fast | normal
    MAIN_POLL: float = 0.05
    STARTUP_CLICK_COOLDOWN: float = 1.25
    STARTUP_WAIT_TIMEOUT: float = 1.5
    WAIT_JOIN_LIST_GRACE: float = 2.0
    JOIN_LIST_STABLE_FRAMES: int = 3

    # Long guardrails. These are broad safety limits, not micro-tuning knobs.
    STARTUP_TIMEOUT: float = 120.0
    READY_TIMEOUT: float = 30.0
    RUN_START_TIMEOUT: float = 300.0
    QUEST_TIMEOUT: float = 600.0
    RECOVERY_TIMEOUT: float = 300.0
    ROOM_SCAN_IDLE_TIMEOUT: float = 20.0
    LOBBY_JOIN_TIMEOUT: float = 6.0

    # Confidence. V8 also has per-template overrides in get_template_confidence().
    CONF_NORMAL: float = 0.85
    CONF_JOIN_CHOICE: float = 0.85
    CONF_POPUP: float = 0.85
    CONF_READY: float = 0.90
    CONF_LOOSE: float = 0.70

    # Room search policy.
    ROOM_SEARCH_MODE: str = "strict_rules"  # strict_rules | all_auto
    MAX_RULE_DISTANCE: int = 110
    AUTO_ICON_DEDUPE_DIST: int = 60
    ALL_AUTO_CLICK_OFFSET_X: int = 0

    # Safety / session policy.
    FOCUS_MODE: str = "GAME_VISIBLE_GHOST"  # GAME_VISIBLE_GHOST | GAME_FOCUSED | NO_RESTORE | LEGACY_GHOST
    MANAGE_INGAME_AUTO: bool = True
    ENABLE_DANGEROUS_OKAY_HARD_RECOVERY: bool = False
    MAX_CONSECUTIVE_RECOVERIES: int = 3
    SESSION_MAX_HOURS: int = 16

    # Shikai/circadian behavior.
    CASUAL_LINGER_RUNS: Tuple[int, int] = (8, 16)
    DISTRACTION_DURATION: Tuple[int, int] = (120, 480)

    # Telemetry / agent-readable traces.
    TAKE_DEBUG_SCREENSHOTS: bool = False
    ENABLE_TELEMETRY: bool = True
    AGENT_TELEMETRY_DIR: str = "agent_telemetry"

    CIRCADIAN_PROFILES: Optional[Dict[str, Dict[str, Any]]] = None
    TEMPLATES: Optional[Dict[str, str]] = None

    def __post_init__(self):
        # Internal profile map. Treat these as implementation defaults; do not
        # tune unless telemetry proves a whole profile is too fast/slow.
        self.CIRCADIAN_PROFILES = {
            "SHIKAI_MAX": {
                "DELAY_COGNITIVE": (0.68, 0.05),
                "DELAY_SNIPE": 0.20,
                "DELAY_POPUP": 1.5,
                "DELAY_READY": 0.90,
                "WAIT_ROOM_LOAD": 0.60,
                "WAIT_SEARCH_AGAIN": 0.80,
                "WAIT_POST_RETRY": 1.0,
                "WAIT_REFOCUS": 0.02,
                "WAIT_REFRESH_COOLDOWN": 0.80,
                "WAIT_STABILIZE_ANIMATION": 0.80,
                "TIMEOUT_VERIFY_UI": 0.70,
                "DURATION_MINS": (45, 90),
            },
            "SHIKAI_NORMAL": {
                "DELAY_COGNITIVE": (0.85, 0.10),
                "DELAY_SNIPE": 0.40,
                "DELAY_POPUP": 2.0,
                "DELAY_READY": 1.10,
                "WAIT_ROOM_LOAD": 0.80,
                "WAIT_SEARCH_AGAIN": 1.50,
                "WAIT_POST_RETRY": 2.0,
                "WAIT_REFOCUS": 0.02,
                "WAIT_REFRESH_COOLDOWN": 1.40,
                "WAIT_STABILIZE_ANIMATION": 1.20,
                "TIMEOUT_VERIFY_UI": 1.40,
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
            "unavailable_close": "images/unavailable_close.png",
            "disconnect_retry": "images/disconnect_rerty.png",
        }
        self._derive_runtime_aliases()
        self._apply_profile("SHIKAI_MAX")

    def _derive_runtime_aliases(self):
        """Compatibility aliases for the existing one-file handlers.

        These are not first-line tuning knobs. They preserve the old handler API
        while the visible config remains small.
        """
        # Confidence aliases expected by existing methods.
        self.CONF_HIGH = 0.85
        self.CONF_STARTUP = 0.85
        self.CONF_VERIFY_ACTION = 0.80
        self.CONF_DISCONNECT = 0.99
        self.AUTO_MATCH_CONFIDENCE = 0.92
        self.AUTO_ON_CONFIDENCE = 0.85

        # Room geometry / click math aliases.
        self.ROOM_MATCH_WEIGHT = 0.1
        self.CLICK_SIGMA_FACTOR = 10.0
        self.SNATCH_BOX_OFFSET = (20, 10)
        self.SNATCH_BOX_DIM = (40, 20)
        self.ALL_AUTO_SNATCH_BOX_DIM = (44, 24)

        # Low-level timing aliases.
        self.UI_POLL = 0.05
        self.CLICK_HOLD = 0.04
        self.SHORT_POST_CLICK = 0.20
        self.NORMAL_POST_CLICK = 0.80
        self.WAIT_CLICK_HOLD = self.CLICK_HOLD
        self.POLL_MAIN_LOOP = self.MAIN_POLL
        self.POLL_UI_VERIFY = self.UI_POLL
        self.POLL_POPUP = 0.5
        self.POLL_RECOVERY = 0.5
        self.POLL_PROPERTY_SYNC = 5.0
        self.SAFETY_FLOOR_FACTOR = 0.05
        self.DELAY_POST_POPUP = 0.3
        self.WAIT_DISCONNECT_COOLING = (8, 16)
        self.WAIT_RESTART = 5.0

        # Timeout aliases used by handlers.
        self.TIMEOUT_STUCK = self.RECOVERY_TIMEOUT
        self.TIMEOUT_QUEST_MAX = self.QUEST_TIMEOUT
        self.TIMEOUT_GAME_START = self.STARTUP_TIMEOUT
        self.TIMEOUT_READY = self.READY_TIMEOUT
        self.TIMEOUT_RUN_START = self.RUN_START_TIMEOUT
        self.TIMEOUT_TAP_VERIFY = 15.0
        self.TIMEOUT_LOBBY_EXPAND = 20.0
        self.TIMEOUT_LOBBY_JOIN = self.LOBBY_JOIN_TIMEOUT
        self.TIMEOUT_ROOM_LIST_LOAD = 5.0
        self.TIMEOUT_SCAN_IDLE = self.ROOM_SCAN_IDLE_TIMEOUT
        self.WINDOW_NOT_FOUND_RETRIES = 60
        self.MAX_DISCONNECT_RETRIES = (8, 16)
        self.USE_WMCTRL_ALWAYS_ON_TOP = True

        # Fatigue aliases.
        self.FATIGUE_BASE = 1.0
        self.FATIGUE_AMPLITUDE = 0.15
        self.FATIGUE_PERIOD = 1800

        # Telemetry aliases.
        self.TRACE_DIR = "traces"
        self.TRACE_MAX_VALUE_LEN = 500
        self.AGENT_EVENTS_FILE = "events.jsonl"
        self.AGENT_ALERTS_FILE = "alerts.jsonl"
        self.AGENT_CURRENT_STATE_FILE = "current_state.json"
        self.AGENT_LATEST_SCREENSHOT_FILE = "latest_screenshot.txt"
        self.AGENT_LATEST_ALERT_SCREENSHOT_FILE = "latest_alert_screenshot.txt"
        self.AGENT_HEARTBEAT_INTERVAL = 1.0

    def _apply_profile(self, profile_name: str):
        if self.CIRCADIAN_PROFILES is None:
            return
        s = self.CIRCADIAN_PROFILES[profile_name]
        self.DELAY_COGNITIVE = s["DELAY_COGNITIVE"]
        self.DELAY_SNIPE = s["DELAY_SNIPE"]
        self.DELAY_POPUP = s["DELAY_POPUP"]
        self.DELAY_READY = s["DELAY_READY"]
        self.WAIT_ROOM_LOAD = s["WAIT_ROOM_LOAD"]
        self.WAIT_SEARCH_AGAIN = s["WAIT_SEARCH_AGAIN"]
        self.WAIT_POST_RETRY = s["WAIT_POST_RETRY"]
        self.WAIT_REFOCUS = s.get("WAIT_REFOCUS", 0.02)
        self.WAIT_REFRESH_COOLDOWN = s["WAIT_REFRESH_COOLDOWN"]
        self.WAIT_STABILIZE_ANIMATION = s["WAIT_STABILIZE_ANIMATION"]
        self.TIMEOUT_VERIFY_UI = s["TIMEOUT_VERIFY_UI"]


# === AI_SECTION: DATA_TYPES ===
@dataclass
class AnchorHit:
    key: str
    state_hint: str
    confidence: float
    box: pyscreeze.Box  # Absolute screen coordinates
    priority: int
    is_popup: bool
    timestamp: float = 0.0


@dataclass
class ScreenClassification:
    hits: List[AnchorHit]
    popup_hits: List[AnchorHit]
    state_hits: List[AnchorHit]
    selected_state: str
    selected_anchor: Optional[AnchorHit]
    ambiguous: bool
    reason: str
    recommended_action: str


def human_delay(
    profile: Union[float, Tuple[float, float]],
    fatigue: float = 1.0,
    safety_factor: float = 0.05,
) -> None:
    if isinstance(profile, (float, int)):
        mu, sigma = float(profile), float(profile) * 0.1
    else:
        mu, sigma = profile
    delay = random.gauss(mu * fatigue, sigma)
    time.sleep(max(delay, (mu * fatigue) * safety_factor))


class GameWindowNotFoundError(Exception):
    pass


# === AI_SECTION: BOT_CORE_STATE_MACHINE ===
class BBSBot:
    RECOVERY_MAP: List[Tuple[str, str, bool]] = [
        ("RUNNING", "ingame_auto_on", False),
        ("RUNNING", "ingame_auto_off", False),
        ("READY", "ready", False),
        ("MENU", "open_coop_quest", False),
        ("MENU", "coop_quest", False),
        ("FINISH", "tap1", False),
        ("FINISH", "tap2", False),
        ("FINISH", "retry", False),
        ("ROOM_LIST", "search_again", False),
        ("COOP_JOIN_CHOICE", "enter_room_button", False),
        ("CHECK_RUN_START", "retire", False),
        ("GAME_STARTUP", "game_start", False),
        ("MENU", "closed_room_coop_quest_menu", True),
        ("ROOM_LIST", "unavailable_close", True),
        ("MENU", "disconnect_retry", True),
        ("GAME_STARTUP", "close_news", True),
        # Generic okay/close are state hints, not auto-dismiss global popups.
        # This prevents clicking static UI 'Close' buttons in the room list.
        ("ROOM_LIST", "okay", False),
        ("ROOM_LIST", "close", False),
    ]

    STATE_PRIORITY: List[str] = [
        "RUNNING",
        "CHECK_RUN_START",
        "FINISH",
        "READY",
        "MENU",
        "JOIN_PENDING",
        "ROOM_LIST",
        "COOP_JOIN_CHOICE",
        "GAME_STARTUP",
    ]

    POPUP_PRIORITY: List[str] = [
        "disconnect_retry",
        "close_news",
        "closed_room_coop_quest_menu",
        "unavailable_close",
    ]

    def __init__(self, config: BotConfiguration = BotConfiguration()) -> None:
        self.config = config
        import pyautogui

        pyautogui.FAILSAFE = False
        assert self.config.CIRCADIAN_PROFILES is not None
        self.active_profile: str = "SHIKAI_MAX"
        self.next_profile_swap: float = (
            time.time()
            + random.randint(
                *self.config.CIRCADIAN_PROFILES["SHIKAI_MAX"]["DURATION_MINS"]
            )
            * 60
        )

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
        self.disconnect_retry_limit: int = random.randint(*self.config.MAX_DISCONNECT_RETRIES)
        self.window_not_found_count: int = 0
        self.consecutive_recovery_count: int = 0
        self.search_start_time: float = 0
        self.next_distraction_run: int = 9999
        self.snapshot: Optional[Image.Image] = None
        self._last_popup_check: float = 0.0
        self._last_recovery_log: int = 0
        self._last_property_sync: float = 0.0
        self._last_id_search: float = 0.0
        self._startup_window_time: float = time.time()
        self._force_refresh: bool = False
        self._run_counted: bool = False
        # Only explicit flows may set this. Generic okay is resource-dangerous.
        self.expected_okay_context: Optional[str] = None
        self._menu_action_fail_count: int = 0
        self._last_startup_click: Dict[str, float] = {}
        self.trace_events: List[Dict[str, Any]] = []
        self.trace_path: Optional[str] = None
        self.agent_telemetry_dir: Optional[str] = None
        self.agent_events_path: Optional[str] = None
        self.agent_alerts_path: Optional[str] = None
        self.agent_current_state_path: Optional[str] = None
        self.agent_latest_screenshot_path: Optional[str] = None
        self.agent_latest_alert_screenshot_path: Optional[str] = None
        self._last_agent_heartbeat: float = 0.0
        if self.config.ENABLE_TELEMETRY:
            os.makedirs(self.config.TRACE_DIR, exist_ok=True)
            self.trace_path = os.path.join(
                self.config.TRACE_DIR, f"v8_trace_{int(self.start_time)}.jsonl"
            )

            self.agent_telemetry_dir = self.config.AGENT_TELEMETRY_DIR
            os.makedirs(self.agent_telemetry_dir, exist_ok=True)
            os.makedirs(os.path.join(self.agent_telemetry_dir, "screenshots"), exist_ok=True)
            self.agent_events_path = os.path.join(self.agent_telemetry_dir, self.config.AGENT_EVENTS_FILE)
            self.agent_alerts_path = os.path.join(self.agent_telemetry_dir, self.config.AGENT_ALERTS_FILE)
            self.agent_current_state_path = os.path.join(self.agent_telemetry_dir, self.config.AGENT_CURRENT_STATE_FILE)
            self.agent_latest_screenshot_path = os.path.join(self.agent_telemetry_dir, self.config.AGENT_LATEST_SCREENSHOT_FILE)
            self.agent_latest_alert_screenshot_path = os.path.join(self.agent_telemetry_dir, self.config.AGENT_LATEST_ALERT_SCREENSHOT_FILE)

        self.handlers = {
            "MENU": self.handle_menu,
            "COOP_JOIN_CHOICE": self.handle_coop_join_choice,
            "ROOM_LIST": self.handle_room_list,
            "JOIN_PENDING": self.handle_join_pending,
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
        self.check_dependencies()

        try:
            self.disp = display.Display()
        except Exception:
            logger.error("FATAL: X11 Display error.")
            sys.exit(1)

        logger.info("BBS Bot V8 Strict Phase Candidate Initialized.")

    def _trace_value(self, value: Any) -> Any:
        """Convert runtime objects into JSON-safe telemetry values."""
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, (list, tuple)):
            return [self._trace_value(v) for v in value]
        if isinstance(value, dict):
            return {str(k): self._trace_value(v) for k, v in value.items()}
        # pyscreeze.Box is tuple-like and exposes left/top/width/height.
        if all(hasattr(value, attr) for attr in ("left", "top", "width", "height")):
            return {
                "left": int(value.left),
                "top": int(value.top),
                "width": int(value.width),
                "height": int(value.height),
            }
        text = repr(value)
        max_len = getattr(self.config, "TRACE_MAX_VALUE_LEN", 500)
        return text[:max_len]

    def _atomic_write_json(self, path: Optional[str], data: Dict[str, Any]) -> None:
        if not path:
            return
        try:
            tmp = f"{path}.tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._trace_value(data), fh, sort_keys=True, indent=2)
                fh.write("\n")
            os.replace(tmp, path)
        except Exception:
            pass

    def _append_jsonl(self, path: Optional[str], record: Dict[str, Any]) -> None:
        if not path:
            return
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(self._trace_value(record), sort_keys=True) + "\n")
        except Exception:
            pass

    def _agent_alert_event(self, event: str) -> bool:
        return event in {
            "dangerous_confirmation_blocked",
            "safety_block",
            "verify_failed",
            "popup_dismiss_failed",
            "hard_recovery",
            "fatal",
            "recovery_timeout",
            "state_timeout",
        }

    def _update_agent_latest_screenshot(self, screenshot: Optional[str], alert: bool = False) -> None:
        if not screenshot:
            return
        try:
            # Text pointers are safer than symlinks across agent sandboxes/editors.
            if self.agent_latest_screenshot_path:
                with open(self.agent_latest_screenshot_path, "w", encoding="utf-8") as fh:
                    fh.write(str(screenshot) + "\n")
            if alert and self.agent_latest_alert_screenshot_path:
                with open(self.agent_latest_alert_screenshot_path, "w", encoding="utf-8") as fh:
                    fh.write(str(screenshot) + "\n")
            # Best-effort copy into the agent telemetry folder for easy discovery.
            if self.agent_telemetry_dir and os.path.exists(screenshot):
                base = os.path.basename(screenshot)
                target = os.path.join(self.agent_telemetry_dir, "screenshots", base)
                if os.path.abspath(target) != os.path.abspath(screenshot):
                    shutil.copy2(screenshot, target)
        except Exception:
            pass

    def write_agent_state(self, last_event: Optional[Dict[str, Any]] = None) -> None:
        """Write a small current-state file agents can poll without running the game."""
        if not getattr(self.config, "ENABLE_TELEMETRY", False):
            return
        try:
            phase = self.current_phase()
        except Exception:
            phase = "UNKNOWN"
        payload: Dict[str, Any] = {
            "ts": round(time.time(), 6),
            "state": getattr(self, "state", None),
            "phase": phase,
            "run_count": getattr(self, "run_count", None),
            "active_profile": getattr(self, "active_profile", None),
            "expected_okay_context": getattr(self, "expected_okay_context", None),
            "region": getattr(self, "region", None),
            "win_id": getattr(self, "win_id", None),
            "trace_path": getattr(self, "trace_path", None),
            "events_path": getattr(self, "agent_events_path", None),
            "alerts_path": getattr(self, "agent_alerts_path", None),
            "latest_screenshot_pointer": getattr(self, "agent_latest_screenshot_path", None),
            "latest_alert_screenshot_pointer": getattr(self, "agent_latest_alert_screenshot_path", None),
        }
        if last_event is not None:
            payload["last_event"] = last_event
        self._atomic_write_json(getattr(self, "agent_current_state_path", None), payload)

    def emit_trace(self, event: str, **payload: Any) -> Dict[str, Any]:
        """Write a structured JSONL decision trace for agents/humans to inspect."""
        try:
            phase = self.current_phase()
        except Exception:
            phase = "UNKNOWN"
        record: Dict[str, Any] = {
            "ts": round(time.time(), 6),
            "event": event,
            "state": getattr(self, "state", None),
            "phase": phase,
            "run_count": getattr(self, "run_count", None),
        }
        for key, value in payload.items():
            record[key] = self._trace_value(value)
        self.trace_events.append(record)
        if getattr(self.config, "ENABLE_TELEMETRY", False) and getattr(self, "trace_path", None):
            try:
                with open(self.trace_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, sort_keys=True) + "\n")
            except Exception:
                pass
            self._append_jsonl(getattr(self, "agent_events_path", None), record)
            is_alert = self._agent_alert_event(event)
            if is_alert:
                self._append_jsonl(getattr(self, "agent_alerts_path", None), record)
            screenshot = record.get("screenshot") or record.get("debug_screenshot")
            if isinstance(screenshot, str):
                self._update_agent_latest_screenshot(screenshot, alert=is_alert)
            self.write_agent_state(last_event=record)
        return record

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

    def get_ui_region(self, name: str):
        return self.region

    def get_template_confidence(self, key: str) -> float:
        template_conf = {
            "open_coop_quest": self.config.CONF_HIGH,
            "coop_quest": self.config.CONF_HIGH,
            "enter_room_button": 0.85,
            "search_again": 0.85,
            "auto": self.config.CONF_NORMAL,
            "room_rules_valid": self.config.CONF_LOOSE,
            "ready": self.config.CONF_READY,
            "ingame_auto_on": self.config.AUTO_ON_CONFIDENCE,
            "ingame_auto_off": 0.92,
            "tap1": self.config.CONF_NORMAL,
            "tap2": self.config.CONF_NORMAL,
            "retry": 0.85,
            "disconnect_retry": 0.95,
            "closed_room_coop_quest_menu": self.config.CONF_POPUP,
            "unavailable_close": self.config.CONF_POPUP,
            "close": self.config.CONF_POPUP,
            "okay": self.config.CONF_POPUP,
            "close_news": self.config.CONF_STARTUP,
            "game_start": self.config.CONF_STARTUP,
            "coop_1": self.config.CONF_STARTUP,
            "coop_2": self.config.CONF_STARTUP,
            "retire": self.config.CONF_NORMAL,
        }
        return template_conf.get(key, self.config.CONF_NORMAL)

    def get_template_region(self, key: str):
        return self.region

    def wait_for_any(
        self,
        keys: List[str],
        timeout: float = 3.0,
        haystack: Optional[Image.Image] = None,
        confidence: Optional[float] = None,
    ) -> Optional[str]:
        start = time.time()
        import pyautogui

        while time.time() - start < timeout:
            if haystack is None or time.time() - start > 0.1:
                if self.region:
                    try:
                        haystack = pyautogui.screenshot(region=self.region)
                    except Exception:
                        pass
            for key in keys:
                if self.find_image(key, confidence=confidence, haystack=haystack):
                    return key
            import time as time_mod

            time_mod.sleep(self.config.POLL_MAIN_LOOP)
        return None

    def classify_screen(
        self, haystack: Optional[Image.Image] = None
    ) -> ScreenClassification:
        """
        Evidence-driven screen classification.
        Scans all known anchors and popups against the current snapshot.
        Known popup hits are prioritized, but deterministic routing happens in
        handle_global_popups/route_known_popup_after_dismiss.
        """
        shot = haystack or self.snapshot
        if shot is None:
            try:
                self.snapshot = pyautogui.screenshot(region=self.region)
                shot = self.snapshot
            except Exception:
                return ScreenClassification(
                    [], [], [], "RECOVERY", None, False, "No snapshot", "RECOVERY"
                )

        hits: List[AnchorHit] = []
        for hint, key, is_popup in self.RECOVERY_MAP:
            conf = self.get_template_confidence(key)
            reg = self.get_template_region(key)
            box = self.find_image(key, confidence=conf, region=reg, haystack=shot)
            if box:
                prio = 99
                if is_popup and key in self.POPUP_PRIORITY:
                    prio = self.POPUP_PRIORITY.index(key)
                elif not is_popup and hint in self.STATE_PRIORITY:
                    prio = self.STATE_PRIORITY.index(hint)

                hits.append(
                    AnchorHit(
                        key=key,
                        state_hint=hint,
                        confidence=conf,
                        box=box,
                        priority=prio,
                        is_popup=is_popup,
                        timestamp=time.time(),
                    )
                )

        popup_hits = [h for h in hits if h.is_popup]
        state_hits = [h for h in hits if not h.is_popup]

        selected_anchor = None
        selected_state = self.state
        reason = "No anchors detected"
        recommended_action = "CONTINUE"

        if popup_hits:
            popup_hits.sort(key=lambda x: x.priority)
            selected_anchor = popup_hits[0]
            selected_state = selected_anchor.state_hint
            reason = f"Popup detected: {selected_anchor.key}"
            recommended_action = f"DISMISS {selected_anchor.key}"
        elif state_hits:
            state_hits.sort(key=lambda x: x.priority)
            selected_anchor = state_hits[0]
            selected_state = selected_anchor.state_hint
            reason = f"State anchor detected: {selected_anchor.key}"
            recommended_action = f"TRANSITION TO {selected_state}"

        ambiguous = len(hits) > 1
        if ambiguous:
            reason += f" (Ambiguity resolved from {len(hits)} hits)"

        return ScreenClassification(
            hits=hits,
            popup_hits=popup_hits,
            state_hits=state_hits,
            selected_state=selected_state,
            selected_anchor=selected_anchor,
            ambiguous=ambiguous,
            reason=reason,
            recommended_action=recommended_action,
        )

    def is_screen_stable(self, frames: int = 3, interval: float = 0.05) -> bool:
        """Verify the screen is not animating or transitioning."""
        if not self.region:
            return False
        try:
            last_shot = pyautogui.screenshot(region=self.region)
            for _ in range(frames - 1):
                time.sleep(interval)
                current_shot = pyautogui.screenshot(region=self.region)
                # Quick pixel-by-pixel comparison (resized for speed)
                if last_shot.resize((64, 64)).tobytes() != current_shot.resize((64, 64)).tobytes():
                    return False
                last_shot = current_shot
            return True
        except Exception:
            return False

    def find_image(
        self,
        key: str,
        confidence: Optional[float] = None,
        region: Optional[Tuple] = None,
        haystack: Optional[Image.Image] = None,
    ) -> Optional[pyscreeze.Box]:
        template = self.cached_templates.get(key)
        conf = confidence if confidence is not None else self.get_template_confidence(key)
        reg = region or self.region
        if not template or not reg:
            return None

        try:
            # V8.1: Prefer direct screen scan to avoid snapshot-vs-screen discrepancies
            res = pyautogui.locateOnScreen(self.config.TEMPLATES[key], region=reg, confidence=conf)
            if res:
                return res
            
            # Fallback to provided haystack if screen scan fails
            if haystack:
                # Relative region calculation
                h_reg = (0, 0, haystack.width, haystack.height)
                res = pyautogui.locate(template, haystack, region=h_reg, confidence=conf)
                if res:
                    return pyscreeze.Box(
                        res.left + self.region[0],
                        res.top + self.region[1],
                        res.width,
                        res.height,
                    )
        except Exception:
            pass
        return None

    def find_all(
        self,
        key: str,
        confidence: Optional[float] = None,
        region: Optional[Tuple] = None,
        haystack: Optional[Image.Image] = None,
    ) -> List[pyscreeze.Box]:
        """
        Find all occurrences of a template within a region or haystack.
        """
        template = self.cached_templates.get(key)
        conf = confidence if confidence is not None else self.get_template_confidence(key)
        reg = region or self.get_template_region(key) or self.region
        if not template or not reg:
            return []

        try:
            if haystack:
                region_val = self.region
                if not region_val:
                    return []
                h_reg = (reg[0] - region_val[0], reg[1] - region_val[1], reg[2], reg[3])
                res = list(
                    pyautogui.locateAll(
                        template, haystack, region=h_reg, confidence=conf
                    )
                )
                return [
                    pyscreeze.Box(
                        r.left + region_val[0],
                        r.top + region_val[1],
                        r.width,
                        r.height,
                    )
                    for r in res
                ]
            else:
                return list(
                    pyautogui.locateAllOnScreen(template, region=reg, confidence=conf)
                )
        except Exception:
            pass
        return []

    def _restore_focus(self, window_id: Optional[str]) -> None:
        """Backward-compatible wrapper for old callers."""
        self._restore_focus_after_click(window_id)

    def _run_focus_cmd(self, cmd: List[str], timeout: float = 0.25) -> None:
        try:
            subprocess.run(
                cmd,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
            )
        except Exception:
            pass

    def _restore_focus_after_click(self, previous_window_id: Optional[str]) -> None:
        """
        Focus policy for visible-pixel automation.
        Default GAME_VISIBLE_GHOST keeps the game above/visible and avoids
        raising the previous window over the game, because screenshots depend
        on visible pixels inside self.region.
        """
        time.sleep(self.config.WAIT_REFOCUS)
        mode = getattr(self.config, "FOCUS_MODE", "GAME_VISIBLE_GHOST")

        if mode == "NO_RESTORE":
            return

        if mode == "GAME_FOCUSED":
            if self.win_id:
                self._run_focus_cmd(["xdotool", "windowfocus", self.win_id])
                self._run_focus_cmd(["xdotool", "windowactivate", "--sync", self.win_id])
                self._run_focus_cmd(["xdotool", "windowraise", self.win_id])
                self._run_focus_cmd(["wmctrl", "-i", "-r", self.win_id, "-b", "add,sticky,above"])
            return

        if mode == "LEGACY_GHOST":
            if previous_window_id:
                self._run_focus_cmd(["xdotool", "windowfocus", previous_window_id])
                self._run_focus_cmd(["xdotool", "windowactivate", "--sync", previous_window_id])
                self._run_focus_cmd(["xdotool", "windowraise", previous_window_id])
            return

        # GAME_VISIBLE_GHOST: do not raise the previous window. Keep game visible.
        # Direct X11 click normally does not steal focus, so this mode is stable
        # for unattended visual automation.
        if self.win_id:
            self._run_focus_cmd(["wmctrl", "-i", "-r", self.win_id, "-b", "add,sticky,above"])

    # === AI_SECTION: SAFETY_PHASE_MAPPING ===
    def current_phase(self) -> str:
        """Safety phase is intentionally stricter than screen state."""
        return {
            "GAME_STARTUP": "STARTUP_SAFE",
            "MENU": "MENU_NAVIGATION",
            "COOP_JOIN_CHOICE": "JOIN_CHOICE",
            "ROOM_LIST": "ROOM_SEARCH",
            "JOIN_PENDING": "JOIN_PENDING",
            "READY": "LOBBY_SAFE",
            "CHECK_RUN_START": "JOIN_PENDING",
            "RUNNING": "LIVE_RUN",
            "FINISH": "FINISH_REWARD",
            "RECOVERY": "RECOVERY_CLASSIFY",
            "DISTRACTION": "UNKNOWN_BLOCKED",
        }.get(self.state, "UNKNOWN_BLOCKED")

    # === AI_SECTION: ALLOWED_ACTION_GATE ===
    def can_click(self, key: str, *, expected_context: Optional[str] = None) -> bool:
        """
        Phase-gated safety policy. This is the core v8 guardrail:
        visible image != permission to click.
        """
        phase = self.current_phase()
        expected = expected_context or self.expected_okay_context

        if key == "okay":
            # okay.png is shared by room-search error dialogs and paid-resource revive prompts.
            # It is allowed in explicitly safe contexts:
            #   1) retire confirmation created by this bot, or
            #   2) ROOM_SEARCH / JOIN_PENDING / RECOVERY / MENU room-error cleanup.
            # It is forbidden in LIVE_RUN / READY / FINISH.
            return expected == "RETIRE_CONFIRM" or self.state in {"ROOM_LIST", "JOIN_PENDING", "RECOVERY", "MENU"}

        allowed_by_phase = {
            "STARTUP_SAFE": {"close_news", "game_start", "coop_1", "coop_2", "close"},
            "MENU_NAVIGATION": {"coop_quest", "open_coop_quest", "close_news", "close"},
            "JOIN_CHOICE": {"enter_room_button", "close", "unavailable_close", "closed_room_coop_quest_menu"},
            "ROOM_SEARCH": {"search_again", "auto", "closed_room_coop_quest_menu", "unavailable_close", "close", "disconnect_retry"},
            "JOIN_PENDING": {"closed_room_coop_quest_menu", "unavailable_close", "close", "disconnect_retry", "retire"},
            "LOBBY_SAFE": {"ready", "closed_room_coop_quest_menu", "unavailable_close", "close", "disconnect_retry"},
            "LIVE_RUN": {"ingame_auto_off", "retire", "disconnect_retry"},
            "FINISH_REWARD": {"tap1", "tap2", "retry", "disconnect_retry", "close"},
            "RECOVERY_CLASSIFY": {"closed_room_coop_quest_menu", "unavailable_close", "close", "disconnect_retry", "close_news"},
        }
        return key in allowed_by_phase.get(phase, set())

    def is_safe_room_okay_context(self, haystack: Optional[Image.Image] = None) -> bool:
        """
        okay.png is allowed for room-search/recovery error dialogs, but never
        for live-run death/revive prompts.
        """
        if self.state not in {"ROOM_LIST", "JOIN_PENDING", "RECOVERY", "MENU"}:
            return False

        # If any live-run/finish/lobby anchors are visible, do not trust generic okay.
        dangerous_anchors = [
            "ingame_auto_on",
            "ingame_auto_off",
            "retire",
            "ready",
            "tap1",
            "tap2",
            "retry",
        ]
        for anchor in dangerous_anchors:
            if self.find_image(anchor, haystack=haystack):
                self.emit_trace(
                    "room_okay_context_rejected",
                    key="okay",
                    reason=f"live_or_terminal_anchor_visible:{anchor}",
                )
                return False
        return True

    def handle_forbidden_confirmations(self, haystack: Optional[Image.Image] = None) -> bool:
        """Never click unknown okay/revive/orb prompts. Stop safe by default."""
        if not self.find_image("okay", haystack=haystack):
            return False
        if self.expected_okay_context == "RETIRE_CONFIRM":
            return False
        if self.state in {"ROOM_LIST", "JOIN_PENDING", "RECOVERY", "MENU"} and self.is_safe_room_okay_context(haystack):
            # Room-full/not-met sometimes exposes only a generic okay button. Let
            # handle_global_popups dismiss and route it through the room-error path.
            return False

        logger.error(
            f"DANGEROUS UNKNOWN OKAY detected in state={self.state} phase={self.current_phase()}. "
            "Refusing to click to protect resources."
        )
        shot = self.save_debug_screenshot("dangerous_unknown_okay")
        self.emit_trace("dangerous_confirmation_blocked", key="okay", screenshot=shot)
        # Safer than clicking: stop the bot for manual review. If you prefer relaunch,
        # change this to self.recover_game(); return True.
        raise RuntimeError("Dangerous unknown OKAY prompt detected; bot stopped before clicking.")

    # === AI_SECTION: TRANSACTIONAL_ACTIONS ===
    def smart_click(
        self,
        target: Union[str, pyscreeze.Box],
        description: str,
        verify_key: Optional[str] = None,
        target_state: Optional[str] = None,
        wait_for_appearance: bool = False,
        pre_click_delay: Optional[Union[float, Tuple[float, float]]] = None,
        post_click_sleep: Optional[float] = None,
        verify_timeout: Optional[float] = None,
        confidence: Optional[float] = None,
        region: Optional[Tuple[int, int, int, int]] = None,
        haystack: Optional[Image.Image] = None,
        non_transactional: bool = False,
        custom_delay: Optional[Union[float, Tuple[float, float]]] = None,
    ) -> bool:
        """
        Evidence-Driven Interaction Model.
        """
        if isinstance(target, str) and not self.can_click(target):
            logger.error(
                f"SAFETY BLOCK: refusing click target={target} description={description} "
                f"state={self.state} phase={self.current_phase()} expected={self.expected_okay_context}"
            )
            shot = self.save_debug_screenshot(f"blocked_{target}")
            self.emit_trace(
                "safety_block",
                target=target,
                description=description,
                expected_context=self.expected_okay_context,
                screenshot=shot,
            )
            return False

        conf = (
            confidence
            if confidence is not None
            else self.get_template_confidence(target)
            if isinstance(target, str)
            else self.config.CONF_NORMAL
        )

        # 1. Locate Target
        box = (
            target
            if isinstance(target, pyscreeze.Box)
            else self.find_image(
                target, confidence=conf, region=region, haystack=haystack
            )
        )

        if not box:
            # Disappearance verification: if we wanted it gone and it's already gone, success.
            if verify_key == target and not wait_for_appearance:
                if target_state:
                    self.transition_to(target_state)
                return True
            return False

        # 2. Surgical Pacing
        human_delay(
            custom_delay or pre_click_delay or self.config.DELAY_COGNITIVE,
            self.fatigue_modifier,
            self.config.SAFETY_FLOOR_FACTOR,
        )

        # 3. Gaussian Click Calculation
        mu_x, mu_y = box.left + box.width / 2, box.top + box.height / 2
        sigma_x, sigma_y = (
            box.width / self.config.CLICK_SIGMA_FACTOR,
            box.height / self.config.CLICK_SIGMA_FACTOR,
        )
        click_x, click_y = (
            int(random.gauss(mu_x, sigma_x)),
            int(random.gauss(mu_y, sigma_y)),
        )
        click_x = max(box.left, min(click_x, box.left + box.width - 1))
        click_y = max(box.top, min(click_y, box.top + box.height - 1))

        # 4. Focus Management
        current_focus = None
        try:
            current_focus = subprocess.check_output(
                ["xdotool", "getactivewindow"], text=True, stderr=subprocess.DEVNULL
            ).strip()
        except Exception:
            pass

        # 5. Execute X11 Ghost Click
        success = self._send_x11_click(click_x, click_y)
        logger.info(
            f"CLICK [Run:{self.run_count}]: {description} at ({click_x}, {click_y})"
        )
        self.emit_trace(
            "click",
            target=target if isinstance(target, str) else "box",
            description=description,
            click=(click_x, click_y),
            box=box,
            confidence=conf,
            verify_key=verify_key,
            wait_for_appearance=wait_for_appearance,
            target_state=target_state,
        )

        # 6. Refocus
        if success and current_focus:
            self._restore_focus_after_click(current_focus)

        # 7. Verification Window
        if success and verify_key and not non_transactional:
            timeout = verify_timeout or self.config.TIMEOUT_VERIFY_UI
            v_start = time.time()
            while time.time() - v_start < timeout:
                # We scan fresh frames for verification to see the change
                found_v = self.find_image(
                    verify_key, confidence=self.config.CONF_VERIFY_ACTION
                )
                if (wait_for_appearance and found_v) or (
                    not wait_for_appearance and not found_v
                ):
                    self.emit_trace(
                        "verify_success",
                        description=description,
                        verify_key=verify_key,
                        wait_for_appearance=wait_for_appearance,
                        target_state=target_state,
                    )
                    if target_state:
                        self.transition_to(target_state)
                    # Stabilization delay
                    time.sleep(post_click_sleep or self.config.WAIT_STABILIZE_ANIMATION)
                    return True
                time.sleep(self.config.POLL_UI_VERIFY)

            logger.warning(
                f"VERIFY FAILED: {description} (key: {verify_key}, wait: {wait_for_appearance})"
            )
            shot = self.save_debug_screenshot(f"verify_failed_{verify_key or 'unknown'}")
            self.emit_trace(
                "verify_failed",
                description=description,
                verify_key=verify_key,
                wait_for_appearance=wait_for_appearance,
                timeout=timeout,
                screenshot=shot,
            )
            return False

        # 8. Transition (only if safe or explicitly non-transactional)
        if success:
            if target_state:
                if verify_key and not non_transactional:
                    # Should have returned in verification loop
                    pass
                else:
                    if verify_key and non_transactional:
                        logger.warning(
                            f"Risky transition: {target_state} without verification for {description}"
                        )
                    self.transition_to(target_state)

            time.sleep(post_click_sleep or self.config.WAIT_STABILIZE_ANIMATION)
            return True

        return False

    def _send_x11_click(self, x: int, y: int) -> bool:
        try:
            if not self.win_id:
                return False
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
            self.disp.flush()
            time.sleep(self.config.WAIT_CLICK_HOLD)
            window.send_event(protocol.event.ButtonRelease(**details), propagate=True)
            self.disp.flush()
            self.disp.sync()
            return True
        except Exception:
            return False

    def reanchor_after_popup(
        self,
        source_key: str,
        *,
        prefer_refresh: bool = False,
        timeout: float = 1.0,
        fallback_state: str = "RECOVERY",
    ) -> bool:
        """
        Short sad-path reanchor after a known popup is dismissed.

        This intentionally does NOT run on the happy path. It performs one
        bounded post-popup observation window, then falls back to the old
        deterministic route instead of waiting or guessing forever.
        """
        self.emit_trace(
            "reanchor_start",
            source_key=source_key,
            prefer_refresh=prefer_refresh,
            timeout=timeout,
            fallback_state=fallback_state,
        )
        next_anchor = self.wait_for_any(
            [
                "auto",
                "search_again",
                "enter_room_button",
                "open_coop_quest",
                "coop_quest",
            ],
            timeout=timeout,
        )

        if next_anchor in ["auto", "search_again"]:
            logger.info(
                f"POPUP REANCHOR: {source_key} -> room list via {next_anchor}"
            )
            self.emit_trace("reanchor_result", source_key=source_key, next_anchor=next_anchor, to_state="ROOM_LIST")
            self._force_refresh = bool(prefer_refresh)
            self.search_start_time = time.time()
            self.transition_to("ROOM_LIST")
            return True

        if next_anchor == "enter_room_button":
            logger.info(f"POPUP REANCHOR: {source_key} -> enter room screen")
            self.emit_trace("reanchor_result", source_key=source_key, next_anchor=next_anchor, to_state="COOP_JOIN_CHOICE")
            self._force_refresh = False
            self.transition_to("COOP_JOIN_CHOICE")
            return True

        if next_anchor in ["open_coop_quest", "coop_quest"]:
            logger.info(f"POPUP REANCHOR: {source_key} -> menu via {next_anchor}")
            self.emit_trace("reanchor_result", source_key=source_key, next_anchor=next_anchor, to_state="MENU")
            self._force_refresh = False
            self.transition_to("MENU")
            return True

        logger.warning(
            f"POPUP REANCHOR: {source_key} found no anchor in {timeout:.1f}s; "
            f"falling back to {fallback_state}"
        )
        self.emit_trace("reanchor_fallback", source_key=source_key, fallback_state=fallback_state)
        if fallback_state == "ROOM_LIST":
            self._force_refresh = bool(prefer_refresh)
            self.search_start_time = time.time()
            self.transition_to("ROOM_LIST")
        elif fallback_state == "MENU":
            self._force_refresh = False
            self.transition_to("MENU")
        else:
            self._force_refresh = False
            self.transition_to("RECOVERY")
        return True

    def route_known_popup_after_dismiss(self, key: str) -> bool:
        """Deterministic old-school routes for known failure popups."""
        if key == "closed_room_coop_quest_menu":
            logger.info("POPUP ROUTE: closed/room-not-met -> short reanchor, MENU fallback")
            self._force_refresh = False
            return self.reanchor_after_popup(
                key, prefer_refresh=False, timeout=1.0, fallback_state="MENU"
            )

        if key == "unavailable_close":
            logger.info("POPUP ROUTE: unavailable -> short reanchor, ROOM_LIST refresh fallback")
            self._force_refresh = True
            self.search_start_time = time.time()
            return self.reanchor_after_popup(
                key, prefer_refresh=True, timeout=1.0, fallback_state="ROOM_LIST"
            )

        if key == "okay":
            # Generic okay is allowed only in ROOM_SEARCH/JOIN_PENDING room-error contexts
            # or explicit retire confirmation. Retire confirmation is handled inside
            # retire_from_quest(), so a global okay here means room-full/not-met cleanup.
            if not self.is_safe_room_okay_context():
                logger.error("POPUP ROUTE: unsafe okay reached global router; refusing to route.")
                shot = self.save_debug_screenshot("unsafe_global_okay")
                self.emit_trace("dangerous_confirmation_blocked", key="okay", screenshot=shot)
                raise RuntimeError("Unsafe OKAY reached global popup router")
            logger.info("POPUP ROUTE: room-search okay -> short reanchor, ROOM_LIST refresh fallback")
            self._force_refresh = True
            self.search_start_time = time.time()
            return self.reanchor_after_popup(
                key, prefer_refresh=True, timeout=1.0, fallback_state="ROOM_LIST"
            )

        if key == "disconnect_retry":
            logger.info("POPUP ROUTE: disconnect retry handled; cooldown then MENU")
            time.sleep(random.randint(*self.config.WAIT_DISCONNECT_COOLING))
            if self.state != "GAME_STARTUP":
                self.transition_to("MENU")
            return True

        if key == "close":
            logger.info("POPUP ROUTE: generic close -> context reset")
            if self.state in ["ROOM_LIST", "JOIN_PENDING", "COOP_JOIN_CHOICE", "READY"]:
                self._force_refresh = True
                self.search_start_time = time.time()
                self.transition_to("ROOM_LIST")
            elif self.state != "GAME_STARTUP":
                self.transition_to("MENU")
            return True

        if key == "close_news":
            logger.info("POPUP ROUTE: close_news -> GAME_STARTUP")
            if self.state != "GAME_STARTUP":
                self.transition_to("GAME_STARTUP")
            return True

        return True

    # === AI_SECTION: DETERMINISTIC_POPUP_ROUTER ===
    def handle_global_popups(self, haystack: Optional[Image.Image] = None, force: bool = False) -> bool:
        """
        Transactional popup dismissal with deterministic routing.
        Known failure popups must not be smoothed into generic reclassification.
        """
        now = time.time()
        if not force and now - self._last_popup_check < self.config.POLL_POPUP:
            return False
        self._last_popup_check = now

        classification = self.classify_screen(haystack=haystack)
        if not classification.popup_hits:
            return False

        target = classification.popup_hits[0]
        key = target.key
        logger.warning(f"GLOBAL: Popup '{key}' confirmed via classification")
        self.emit_trace("popup_detected", key=key, classification=classification.reason, hits=[h.key for h in classification.hits])

        if key == "okay" and not self.is_safe_room_okay_context(haystack):
            logger.error("GLOBAL: okay detected outside safe room-error context; refusing to click.")
            shot = self.save_debug_screenshot("dangerous_global_okay")
            self.emit_trace("dangerous_confirmation_blocked", key="okay", screenshot=shot)
            raise RuntimeError("Dangerous OKAY detected by global popup handler")

        if key == "disconnect_retry":
            self.disconnect_retry_count += 1
            if self.disconnect_retry_count > self.disconnect_retry_limit:
                logger.error(
                    f"Disconnect limit reached ({self.disconnect_retry_count}/{self.disconnect_retry_limit}). Relaunching."
                )
                self.disconnect_retry_count = 0
                self.disconnect_retry_limit = random.randint(*self.config.MAX_DISCONNECT_RETRIES)
                self.recover_game()
                return True

        dismiss_success = self.smart_click(
            key,
            f"dismiss {key}",
            verify_key=key,
            wait_for_appearance=False,
            pre_click_delay=self.config.DELAY_POPUP if key == "disconnect_retry" else 0.2,
            post_click_sleep=0.5,
            confidence=target.confidence,
            region=self.get_template_region(key),
            haystack=haystack,
        )

        if not dismiss_success:
            logger.warning(
                f"Failed to verify dismissal of {key}; consuming this tick and retrying popup-first next loop."
            )
            shot = self.save_debug_screenshot(f"popup_dismiss_failed_{key}")
            self.emit_trace("popup_dismiss_failed", key=key, screenshot=shot)
            self._last_popup_check = 0.0
            return True

        return self.route_known_popup_after_dismiss(key)

    # === AI_SECTION: STATE_HANDLERS_BEGIN ===
    def handle_menu(self, haystack: Optional[Image.Image] = None) -> bool:
        """Main menu handler with false-positive guard."""
        # Stronger/deeper anchors first.
        if self.find_image("auto", haystack=haystack) or self.find_image("search_again", haystack=haystack):
            self._menu_action_fail_count = 0
            self.transition_to("ROOM_LIST")
            return False

        if self.find_image("enter_room_button", haystack=haystack):
            self._menu_action_fail_count = 0
            logger.info("MENU: Observed 'enter_room_button'. Correcting state.")
            self.transition_to("COOP_JOIN_CHOICE")
            return False

        quest_region = self.get_ui_region("quest_menu")
        if self.find_image(
            "open_coop_quest",
            confidence=self.config.CONF_HIGH,
            region=quest_region,
            haystack=haystack,
        ):
            clicked = self.smart_click(
                "open_coop_quest",
                "specific quest",
                confidence=self.config.CONF_HIGH,
                region=quest_region,
                haystack=haystack,
                post_click_sleep=0.2,
            )
            if clicked:
                next_anchor = self.wait_for_any(
                    ["enter_room_button", "auto", "search_again"],
                    timeout=2.0,
                )
                if next_anchor:
                    self._menu_action_fail_count = 0
                    if next_anchor in ["auto", "search_again"]:
                        self.transition_to("ROOM_LIST")
                    else:
                        self.transition_to("COOP_JOIN_CHOICE")
                    return True

            self._menu_action_fail_count += 1
            logger.warning(
                f"MENU: specific quest produced no next anchor ({self._menu_action_fail_count}/3)"
            )
            if self._menu_action_fail_count >= 3:
                self._menu_action_fail_count = 0
                self.transition_to("RECOVERY")
            return False

        if self.find_image(
            "coop_quest",
            confidence=self.config.CONF_HIGH,
            region=quest_region,
            haystack=haystack,
        ):
            return self.smart_click(
                "coop_quest",
                "expand menu",
                verify_key="open_coop_quest",
                wait_for_appearance=True,
                confidence=self.config.CONF_HIGH,
                region=quest_region,
                post_click_sleep=0.5,
                haystack=haystack,
            )

        if time.time() - self.last_state_change_time > self.config.TIMEOUT_LOBBY_EXPAND:
            logger.warning("MENU: Stuck in menu. Yielding to RECOVERY.")
            self.transition_to("RECOVERY")
            return False

        return False

    def handle_coop_join_choice(self, haystack: Optional[Image.Image] = None) -> bool:
        """
        Room list entry handler.
        """
        if self.find_image("auto", haystack=haystack) or self.find_image(
            "search_again", haystack=haystack
        ):
            logger.info(
                "COOP_JOIN_CHOICE: Observed room list anchors. Correcting state."
            )
            time.sleep(self.config.WAIT_ROOM_LOAD)
            self.transition_to("ROOM_LIST")
            return False

        if self.find_image("enter_room_button", haystack=haystack):
            if self.smart_click(
                "enter_room_button",
                "enter room list",
                haystack=haystack,
            ):
                if self.wait_for_any(
                    ["auto", "search_again"], timeout=self.config.TIMEOUT_VERIFY_UI
                ):
                    self.transition_to("ROOM_LIST")
                    return True
            return False

        if (
            time.time() - self.last_state_change_time
            > self.config.TIMEOUT_ROOM_LIST_LOAD
        ):
            logger.warning(
                "COOP_JOIN_CHOICE: Stuck in room list entry. Yielding to RECOVERY."
            )
            self.transition_to("RECOVERY")
            return False

        return False

    def room_search_all_auto_enabled(self) -> bool:
        return self.config.ROOM_SEARCH_MODE == "all_auto"

    @staticmethod
    def _candidate_key(auto: pyscreeze.Box) -> Tuple[int, int]:
        # Coarse key used only for de-duping matched vs auto-only candidates.
        return (round((auto.left + auto.width // 2) / 10), round((auto.top + auto.height // 2) / 10))

    @staticmethod
    def build_room_candidates(
        autos: List[pyscreeze.Box],
        rules: List[pyscreeze.Box],
        config: BotConfiguration,
        allow_all_auto: bool = False,
    ) -> List[Tuple[pyscreeze.Box, Optional[pyscreeze.Box], str]]:
        """Build room candidates from AUTO icons.

        strict_rules mode preserves the v6/v6-stable behavior: only AUTO rows
        with a nearby room_rules_valid anchor are eligible. all_auto mode is
        intentionally opt-in and includes unmatched AUTO rows after matched
        candidates. This is useful when room messages are arbitrary/player-made,
        but it can produce more room-not-met popups.
        """
        deduped = BBSBot.dedupe_autos(autos, config)
        matched_pairs = BBSBot.match_rooms(deduped, rules, config)
        candidates: List[Tuple[pyscreeze.Box, Optional[pyscreeze.Box], str]] = [
            (auto, rule, "rules_match") for auto, rule in matched_pairs
        ]
        if allow_all_auto:
            matched = {BBSBot._candidate_key(auto) for auto, _rule in matched_pairs}
            for auto in deduped:
                if BBSBot._candidate_key(auto) not in matched:
                    candidates.append((auto, None, "auto_only"))
        return candidates

    def build_snatch_target(
        self, auto: pyscreeze.Box, rule: Optional[pyscreeze.Box], source: str
    ) -> pyscreeze.Box:
        if rule is not None:
            px, py = (
                (auto.left + rule.left + rule.width) // 2,
                auto.top + auto.height // 2,
            )
            dw, dh = self.config.SNATCH_BOX_DIM
            ox, oy = self.config.SNATCH_BOX_OFFSET
            return pyscreeze.Box(px - ox, py - oy, dw, dh)

        # all_auto fallback: click the AUTO row/icon itself with a small box.
        # This is intentionally behind --allow-all-auto-rooms because it may
        # enter rooms whose free-text requirements are not met.
        dw, dh = self.config.ALL_AUTO_SNATCH_BOX_DIM
        px = auto.left + auto.width // 2 + self.config.ALL_AUTO_CLICK_OFFSET_X
        py = auto.top + auto.height // 2
        if self.region:
            rx, _ry, rw, _rh = self.region
            px = max(rx + dw // 2, min(px, rx + rw - dw // 2))
        return pyscreeze.Box(px - dw // 2, py - dh // 2, dw, dh)

    def handle_room_list(self, haystack: Optional[Image.Image] = None) -> bool:
        if self.find_image(
            "ready", confidence=self.config.CONF_READY, haystack=haystack
        ):
            self.transition_to("READY")
            return False

        # 1. Force Refresh (from v6_last_stable), but do not get stuck if
        # the game returns to a live room list without a visible refresh button.
        if self._force_refresh:
            if self.find_image("search_again", haystack=haystack):
                if self.smart_click(
                    "search_again",
                    "recovery refresh",
                    custom_delay=self.config.DELAY_POST_POPUP,
                    haystack=haystack,
                ):
                    self.search_start_time = time.time()
                    self._force_refresh = False
                    time.sleep(self.config.WAIT_REFRESH_COOLDOWN)
                    return True
            elif self.find_image("auto", haystack=haystack):
                logger.info(
                    "ROOM_LIST: force refresh requested, but live room list is visible; continuing scan."
                )
                self._force_refresh = False
            elif time.time() - self.search_start_time > self.config.WAIT_SEARCH_AGAIN:
                self._force_refresh = False
                self.transition_to("RECOVERY")
                return False
            else:
                return False

        if time.time() - self.search_start_time > self.config.TIMEOUT_SCAN_IDLE:
            logger.warning(
                f"ROOM_LIST: No activity for {self.config.TIMEOUT_SCAN_IDLE}s. Yielding to RECOVERY."
            )
            self.transition_to("RECOVERY")
            return False

        # 2. Local Anchor Validation (from v6_last_stable)
        autos_box = self.find_all(
            "auto", confidence=self.config.CONF_NORMAL, haystack=haystack
        )

        if autos_box and (
            time.time() - self.search_start_time > self.config.WAIT_ROOM_LOAD
        ):
            rules_box = self.find_all(
                "room_rules_valid", confidence=self.config.CONF_LOOSE, haystack=haystack
            )

            candidates = BBSBot.build_room_candidates(
                autos_box,
                rules_box,
                self.config,
                allow_all_auto=self.room_search_all_auto_enabled(),
            )

            self.emit_trace(
                "room_candidates",
                auto_count=len(autos_box),
                rule_count=len(rules_box),
                candidate_count=len(candidates),
                room_search_mode=self.config.ROOM_SEARCH_MODE,
            )

            if candidates:
                self.search_start_time = time.time()

            for auto, rule, source in candidates:
                # 3. Persistence Check: Ensure anchor is stable before clicking (from v6_last_stable)
                local_reg = (
                    auto.left - 5,
                    auto.top - 5,
                    auto.width + 10,
                    auto.height + 10,
                )
                # Note: find_image uses screen coordinates, so local_reg is fine if absolute
                if not self.find_image("auto", region=local_reg):
                    logger.warning(
                        "Local anchor lost. Room list shifted. Skipping snatch."
                    )
                    self.emit_trace("room_candidate_skipped", reason="local_anchor_lost", source=source)
                    continue

                target_box = self.build_snatch_target(auto, rule, source)

                self.emit_trace(
                    "room_candidate_selected",
                    source=source,
                    auto_box=[auto.left, auto.top, auto.width, auto.height],
                    rule_box=[rule.left, rule.top, rule.width, rule.height] if rule else None,
                    target_box=[target_box.left, target_box.top, target_box.width, target_box.height],
                )

                # 5. Snatch and transition to observation state (JOIN_PENDING)
                if self.smart_click(
                    target_box,
                    f"snatch room ({source})",
                    pre_click_delay=self.config.DELAY_SNIPE,
                    post_click_sleep=0.2,
                ):
                    self.transition_to("JOIN_PENDING")
                    return True

        # 6. Periodic Refresh
        if time.time() - self.search_start_time > self.config.WAIT_SEARCH_AGAIN:
            if self.find_image("search_again", haystack=haystack):
                if self.smart_click(
                    "search_again",
                    "search again",
                    post_click_sleep=self.config.WAIT_REFRESH_COOLDOWN,
                    haystack=haystack,
                ):
                    self.search_start_time = time.time()
                    return True

        return False

    def _room_list_stable(self, frames: Optional[int] = None) -> bool:
        """Only trust room-list kickback after stable fresh frames, not stale post-click pixels."""
        frames = frames or self.config.JOIN_LIST_STABLE_FRAMES
        if not self.region:
            return False
        for _ in range(frames):
            try:
                shot = pyautogui.screenshot(region=self.region)
            except Exception:
                return False
            if self.find_image("ready", confidence=self.config.CONF_READY, haystack=shot):
                return False
            if (
                self.find_image("closed_room_coop_quest_menu", haystack=shot)
                or self.find_image("unavailable_close", haystack=shot)
                or self.find_image("close", haystack=shot)
            ):
                return False
            if not (
                self.find_image("auto", haystack=shot)
                or self.find_image("search_again", haystack=shot)
            ):
                return False
            time.sleep(self.config.POLL_UI_VERIFY)
        return True

    def handle_join_pending(self, haystack: Optional[Image.Image] = None) -> bool:
        """
        Post-snatch outcome observer. Do not treat stale room-list pixels as kickback.
        v6 waited for real outcomes; v8 keeps that discipline with a short grace period.
        """
        elapsed = time.time() - self.last_state_change_time
        classification = self.classify_screen(haystack)
        if classification.popup_hits:
            return self.handle_global_popups(haystack, force=True)

        if self.find_image("ready", confidence=self.config.CONF_READY, haystack=haystack):
            logger.info("JOIN_PENDING: Success! Observed 'ready' button.")
            self.transition_to("READY")
            return False

        if elapsed > self.config.WAIT_JOIN_LIST_GRACE:
            if self.find_image("open_coop_quest", haystack=haystack) or self.find_image("coop_quest", haystack=haystack):
                logger.info("JOIN_PENDING: Reanchored to menu after join attempt.")
                self.transition_to("MENU")
                return False

            if self._room_list_stable():
                logger.info("JOIN_PENDING: Room list stable after grace; treating as kickback.")
                self._force_refresh = True
                self.search_start_time = time.time()
                self.transition_to("ROOM_LIST")
                return False

        if elapsed > self.config.TIMEOUT_LOBBY_JOIN:
            logger.warning("JOIN_PENDING: Timeout waiting for join outcome; returning to room search.")
            self._force_refresh = True
            self.search_start_time = time.time()
            self.transition_to("ROOM_LIST")
            return False

        return False

    @staticmethod
    def match_rooms(
        autos: List[pyscreeze.Box], rules: List[pyscreeze.Box], config: BotConfiguration
    ) -> List[Tuple[pyscreeze.Box, pyscreeze.Box]]:
        valid = []
        for a in BBSBot.dedupe_autos(autos, config):
            ax, ay = a.left + a.width // 2, a.top + a.height // 2
            best_r, min_d = None, float("inf")
            for r in rules:
                rx, ry = r.left + r.width // 2, r.top + r.height // 2
                dy = ry - ay
                if 0 < dy < 100:
                    d = abs(dy) + abs(rx - ax) * config.ROOM_MATCH_WEIGHT
                    if d < min_d and d < config.MAX_RULE_DISTANCE:
                        min_d, best_r = d, r
            if best_r:
                valid.append((a, best_r))
        return valid

    @staticmethod
    def dedupe_autos(
        matches: List[pyscreeze.Box], config: BotConfiguration
    ) -> List[pyscreeze.Box]:
        unique: List[pyscreeze.Box] = []
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

    def handle_ready(self, haystack: Optional[Image.Image] = None) -> bool:
        """
        Lobby ready handler. Ensures button is stable before clicking.
        """
        # Popup handling is now centralized in handle_global_popups

        if self.find_image(
            "ready", confidence=self.config.CONF_READY, haystack=haystack
        ):
            # Stable Frame Verification (from v6_last_stable)
            # We already have a snapshot hit, let's verify with a fresh check
            time.sleep(self.config.POLL_UI_VERIFY)
            if not self.find_image("ready", confidence=self.config.CONF_READY):
                logger.info("READY: Button flicker detected. Skipping click.")
                return False

            # Click transactionally and verify disappearance or transition
            if self.smart_click(
                "ready",
                "snap ready",
                verify_key="ready",
                wait_for_appearance=False,
                custom_delay=self.config.DELAY_READY,
            ):
                # Outcome classification for failed ready / kicked back screens
                next_anchor = self.wait_for_any(
                    [
                        "ingame_auto_on",
                        "ingame_auto_off",
                        "retire",
                        "ready",
                        "auto",
                        "search_again",
                        "enter_room_button",
                        "open_coop_quest",
                        "coop_quest",
                        "close",
                        "unavailable_close",
                        "closed_room_coop_quest_menu",
                    ],
                    timeout=self.config.TIMEOUT_VERIFY_UI,
                )

                if next_anchor in ["ingame_auto_on", "ingame_auto_off", "retire"]:
                    self.transition_to("CHECK_RUN_START")
                elif next_anchor == "ready":
                    self.transition_to("READY")
                elif next_anchor in ["auto", "search_again"]:
                    self.transition_to("ROOM_LIST")
                elif next_anchor == "enter_room_button":
                    self.transition_to("COOP_JOIN_CHOICE")
                elif next_anchor in ["open_coop_quest", "coop_quest"]:
                    self.transition_to("MENU")
                elif next_anchor in [
                    "close",
                    "unavailable_close",
                    "closed_room_coop_quest_menu",
                ]:
                    self.handle_global_popups(force=True)
                else:
                    self.transition_to("CHECK_RUN_START")
                return True
        else:
            # Evidence-driven fallbacks
            if (
                self.find_image("ingame_auto_off", haystack=haystack)
                or self.find_image("ingame_auto_on", haystack=haystack)
                or self.find_image("retire", haystack=haystack)
            ):
                logger.info("READY: Observed in-game anchors. Transitioning.")
                self.transition_to("CHECK_RUN_START")
                return False

        if time.time() - self.last_state_change_time > self.config.TIMEOUT_READY:
            logger.warning("READY: Stuck in lobby. Yielding to RECOVERY.")
            self.transition_to("RECOVERY")
            return False

        return False

    def handle_check_run_start(self, haystack: Optional[Image.Image] = None) -> bool:
        """Handler for the period between lobby and quest start."""
        classification = self.classify_screen(haystack)
        if classification.popup_hits:
            return self.handle_global_popups(haystack, force=True)

        if self.find_image("auto", haystack=haystack) or self.find_image("search_again", haystack=haystack):
            logger.info("CHECK_RUN_START: Kicked back to room list.")
            self.transition_to("ROOM_LIST")
            return False

        if self.find_image("enter_room_button", haystack=haystack):
            logger.info("CHECK_RUN_START: Kicked back to room entry.")
            self.transition_to("COOP_JOIN_CHOICE")
            return False

        quest_region = self.get_ui_region("quest_menu")
        if self.find_image("open_coop_quest", confidence=self.config.CONF_HIGH, region=quest_region, haystack=haystack) or self.find_image("coop_quest", confidence=self.config.CONF_HIGH, region=quest_region, haystack=haystack):
            logger.info("CHECK_RUN_START: Kicked back to menu.")
            self.transition_to("MENU")
            return False

        if self.find_image("ready", confidence=self.config.CONF_READY, haystack=haystack):
            self.transition_to("READY")
            return False

        if self.find_image("ingame_auto_on", confidence=self.config.AUTO_ON_CONFIDENCE, haystack=haystack):
            logger.info("CHECK_RUN_START: Quest started. Auto is ON.")
            self.transition_to("RUNNING")
            return False

        if self.find_image("ingame_auto_off", confidence=self.config.AUTO_MATCH_CONFIDENCE, haystack=haystack):
            if self.config.MANAGE_INGAME_AUTO:
                return self.smart_click(
                    "ingame_auto_off",
                    "enable auto",
                    verify_key="ingame_auto_on",
                    wait_for_appearance=True,
                    target_state="RUNNING",
                    confidence=self.config.AUTO_MATCH_CONFIDENCE,
                    haystack=haystack,
                )
            self.transition_to("RUNNING")
            return False

        if time.time() - self.last_state_change_time > self.config.TIMEOUT_RUN_START:
            logger.warning("CHECK_RUN_START: Quest start timeout. Retiring.")
            self.retire_from_quest(haystack)
            return True

        return False

    def handle_running(self, haystack: Optional[Image.Image] = None) -> bool:
        """
        Main in-game loop handler.
        """
        if self.config.MANAGE_INGAME_AUTO:
            if not self.find_image(
                "ingame_auto_on",
                confidence=self.config.AUTO_ON_CONFIDENCE,
                haystack=haystack,
            ):
                if self.find_image(
                    "ingame_auto_off",
                    confidence=self.config.AUTO_MATCH_CONFIDENCE,
                    haystack=haystack,
                ):
                    # Enable auto transactionally
                    return self.smart_click(
                        "ingame_auto_off",
                        "enable auto",
                        verify_key="ingame_auto_on",
                        wait_for_appearance=True,
                        confidence=self.config.AUTO_MATCH_CONFIDENCE,
                        haystack=haystack,
                    )

        # Look for finish anchors
        if (
            self.find_image("tap1", haystack=haystack)
            or self.find_image("tap2", haystack=haystack)
            or self.find_image("retry", haystack=haystack)
        ):
            logger.info("RUNNING: Observed finish anchors. Transitioning to FINISH.")
            self.transition_to("FINISH")
            return False

        if time.time() - self.last_state_change_time > self.config.TIMEOUT_QUEST_MAX:
            logger.warning(
                "RUNNING: Quest exceeded max duration. Yielding to RECOVERY."
            )
            self.transition_to("RECOVERY")
            return False

        return False

    def handle_finish(self, haystack: Optional[Image.Image] = None) -> bool:
        """
        Quest completion handler. Transactional rewards and retry.
        """
        found_key = None
        # Priority order for finish anchors
        for key in ["retry", "tap2", "tap1"]:
            if self.find_image(key, haystack=haystack):
                found_key = key
                break

        if found_key:
            if found_key in ["tap1", "tap2"]:
                # Reward screens: dismiss and wait for disappearance
                if self.smart_click(
                    found_key,
                    f"reward {found_key}",
                    verify_key=found_key,
                    wait_for_appearance=False,
                    custom_delay=0.4,
                    haystack=haystack,
                ):
                    self.quest_watchdog = time.time()
                    return True
                return False

            if found_key == "retry":
                # Final retry: click and verify outcome
                if not self._run_counted:
                    # We haven't counted this run yet
                    if self.smart_click(
                        "retry",
                        "retry quest",
                        verify_key="retry",
                        wait_for_appearance=False,
                        custom_delay=0.5,
                        haystack=haystack,
                    ):
                        next_anchor = self.wait_for_any(
                            [
                                "enter_room_button",
                                "auto",
                                "search_again",
                                "open_coop_quest",
                            ],
                            timeout=self.config.TIMEOUT_VERIFY_UI,
                        )
                        if next_anchor:
                            self.run_count += 1
                            self._run_counted = True
                            self.reset_quest_watchdog("run_completed")
                            self.consecutive_recovery_count = 0
                            self.disconnect_retry_count = 0
                            logger.info(f"Run #{self.run_count} complete.")

                            if self.run_count >= self.next_distraction_run:
                                self.transition_to("DISTRACTION")
                            elif next_anchor == "open_coop_quest":
                                self.transition_to("MENU")
                            elif next_anchor in ["auto", "search_again"]:
                                self.transition_to("ROOM_LIST")
                            else:
                                self.transition_to("COOP_JOIN_CHOICE")
                            return True
                        else:
                            logger.warning("No next anchor observed after retry.")
                            return False
                else:
                    # Already counted, but button still visible? Wait or re-click.
                    return self.smart_click(
                        "retry",
                        "retry quest (repeat)",
                        verify_key="retry",
                        wait_for_appearance=False,
                        custom_delay=0.5,
                        haystack=haystack,
                    )

        # Reset run_counted if we are no longer in FINISH state
        # (This is usually handled by transition_to if we add it there)

        if time.time() - self.last_state_change_time > self.config.TIMEOUT_TAP_VERIFY:
            logger.warning("FINISH: Stuck in reward sequence. Yielding to RECOVERY.")
            self.transition_to("RECOVERY")
            return False

        return False

    def _startup_click_ready(self, key: str, cooldown: float) -> bool:
        """Throttle slow startup clicks so verified-click failure does not spam stale anchors."""
        now = time.time()
        last = self._last_startup_click.get(key, 0.0)
        if now - last < cooldown:
            return False
        self._last_startup_click[key] = now
        return True

    def handle_startup_news_popup(
        self,
        haystack: Optional[Image.Image] = None,
        force_fresh: bool = False,
    ) -> bool:
        """
        Startup news must be handled outside the generic popup classifier.

        Live testing showed the news overlay can be visible while the generic
        startup flow still sees coop/game anchors. If we let the normal startup
        flow continue, the bot clicks coop behind/under the news instead of
        dismissing the overlay. This method is intentionally explicit and
        startup-specific:
        - use the startup_news top-band region first
        - optionally take a fresh screenshot so we do not rely on a stale loop
          snapshot after a slow startup animation
        - fall back to the full game region for close_news only during startup
        """
        if not self.region:
            return False

        shot = haystack
        if force_fresh or shot is None:
            try:
                shot = pyautogui.screenshot(region=self.region)
            except Exception:
                shot = haystack

        startup_region = self.get_ui_region("startup_news")
        box = self.find_image(
            "close_news",
            confidence=self.config.CONF_STARTUP,
            region=startup_region,
            haystack=shot,
        )

        # Last-resort startup-only fallback. This does not affect normal flow.
        if not box:
            box = self.find_image(
                "close_news",
                confidence=self.config.CONF_STARTUP,
                region=self.region,
                haystack=shot,
            )

        if not box:
            return False

        logger.warning("GAME_STARTUP: close_news visible; dismissing before startup navigation.")
        clicked = self.smart_click(
            box,
            "close news",
            verify_key="close_news",
            wait_for_appearance=False,
            verify_timeout=2.0,
            post_click_sleep=0.8,
            confidence=self.config.CONF_STARTUP,
            region=startup_region,
            haystack=shot,
        )
        if not clicked:
            logger.warning(
                "GAME_STARTUP: close_news click did not verify; consuming tick so startup does not click behind overlay."
            )
        return True

    def _startup_click_and_reanchor(
        self,
        key: str,
        description: str,
        expected: List[str],
        haystack: Optional[Image.Image] = None,
        cooldown: float = 2.5,
        wait_timeout: float = 2.5,
        confidence: Optional[float] = None,
    ) -> bool:
        """
        Startup screens animate slowly. Do not use the normal 0.7s disappearance
        verifier for game_start/coop navigation because it creates repeated stale
        clicks. Click once, wait briefly for any real next anchor, then let the
        main loop continue if the game is still transitioning.
        """
        if not self._startup_click_ready(key, cooldown):
            return False
        clicked = self.smart_click(
            key,
            description,
            confidence=confidence,
            haystack=haystack,
            post_click_sleep=0.3,
            non_transactional=True,
        )
        if not clicked:
            return False
        next_anchor = self.wait_for_any(expected, timeout=wait_timeout)
        if next_anchor == "close_news":
            self.handle_startup_news_popup(force_fresh=True)
        elif next_anchor in ["coop_quest", "open_coop_quest"]:
            self.transition_to("MENU")
        return True

    def handle_game_startup(self, haystack: Optional[Image.Image] = None) -> bool:
        """
        Game startup and navigation handler.

        Startup is intentionally not normal transactional verification. The game
        can take several seconds to animate after start/coop clicks, so a 0.7s
        disappearance verifier creates repeated stale clicks. This handler uses
        throttled clicks + short reanchor waits instead.
        """
        # News popup must be top priority. Use explicit startup handling, not
        # generic classifier flow, because news can coexist with coop anchors.
        if self.handle_startup_news_popup(haystack=haystack, force_fresh=True):
            return True

        # If we've reached the lobby/menu, startup is complete.
        quest_region = self.get_ui_region("quest_menu")
        if self.find_image(
            "coop_quest", confidence=self.config.CONF_HIGH, region=quest_region, haystack=haystack
        ) or self.find_image(
            "open_coop_quest", confidence=self.config.CONF_HIGH, region=quest_region, haystack=haystack
        ):
            logger.info("GAME_STARTUP: Lobby detected. Startup sequence complete.")
            self.transition_to("MENU")
            return True

        if self.find_image("game_start", haystack=haystack):
            return self._startup_click_and_reanchor(
                "game_start",
                "start button",
                ["close_news", "coop_1", "coop_2", "coop_quest", "open_coop_quest"],
                haystack=haystack,
                cooldown=3.0,
                wait_timeout=2.5,
            )

        if self.find_image("coop_1", confidence=self.config.CONF_STARTUP, haystack=haystack):
            return self._startup_click_and_reanchor(
                "coop_1",
                "coop navigation 1",
                ["close_news", "coop_2", "coop_quest", "open_coop_quest"],
                haystack=haystack,
                cooldown=2.0,
                wait_timeout=2.5,
                confidence=self.config.CONF_STARTUP,
            )

        if self.find_image("coop_2", confidence=self.config.CONF_STARTUP, haystack=haystack):
            return self._startup_click_and_reanchor(
                "coop_2",
                "coop navigation 2",
                ["close_news", "coop_quest", "open_coop_quest"],
                haystack=haystack,
                cooldown=2.0,
                wait_timeout=2.5,
                confidence=self.config.CONF_STARTUP,
            )

        if time.time() - self.last_state_change_time > self.config.TIMEOUT_GAME_START:
            logger.warning("GAME_STARTUP: Timeout. Yielding to RECOVERY.")
            self.transition_to("RECOVERY")
            return False

        return False

    def handle_recovery(self, haystack: Optional[Image.Image] = None) -> bool:
        """
        Recovery is classifier-assisted, not classifier-ruled.
        Known popups route deterministically. Weak menu anchors are region/high-confidence gated.
        """
        # V8.2: Enforce a small stability window to prevent rapid state-switching loops
        if not self.is_screen_stable(frames=2):
            return False

        elapsed = time.time() - self.last_state_change_time

        if int(elapsed) > 0 and int(elapsed) % 10 == 0:
            if int(elapsed) != self._last_recovery_log:
                logger.info(f"RECOVERY: Scanning for anchors... ({elapsed:.0f}s elapsed)")
                self._last_recovery_log = int(elapsed)

        if elapsed > self.config.TIMEOUT_STUCK:
            logger.error(f"RECOVERY: Stuck for {elapsed:.0f}s. Initiating hard recovery.")
            self.recover_game()
            return True

        classification = self.classify_screen(haystack=haystack)

        if classification.popup_hits:
            target = classification.popup_hits[0]
            logger.info(f"RECOVERY: Found popup '{target.key}'. Dismissing.")
            return self.handle_global_popups(haystack=haystack, force=True)

        # Strong/terminal anchors by priority.
        for key in ["tap1", "tap2", "retry"]:
            if self.find_image(key, haystack=haystack):
                self.transition_to("FINISH")
                return True

        if self.find_image("ready", confidence=self.config.CONF_READY, haystack=haystack):
            self.transition_to("READY")
            return True

        if self.find_image("ingame_auto_on", confidence=self.config.AUTO_ON_CONFIDENCE, haystack=haystack) or self.find_image("ingame_auto_off", confidence=self.config.AUTO_MATCH_CONFIDENCE, haystack=haystack):
            self.transition_to("RUNNING")
            return True

        if self.find_image("auto", haystack=haystack) or self.find_image("search_again", haystack=haystack):
            self.transition_to("ROOM_LIST")
            return True

        if self.find_image("enter_room_button", haystack=haystack):
            self.transition_to("COOP_JOIN_CHOICE")
            return True

        quest_region = self.get_ui_region("quest_menu")
        if self.find_image("open_coop_quest", confidence=self.config.CONF_HIGH, region=quest_region, haystack=haystack) or self.find_image("coop_quest", confidence=self.config.CONF_HIGH, region=quest_region, haystack=haystack):
            self.transition_to("MENU")
            return True

        if classification.ambiguous:
            logger.info(f"RECOVERY: Ambiguous classification ignored safely: {classification.reason}")

        return False

    def handle_distraction(self, haystack: Optional[Image.Image] = None) -> bool:
        assert self.config.CIRCADIAN_PROFILES is not None
        duration = random.randint(*self.config.DISTRACTION_DURATION)
        logger.info(f"DISTRACTION: Resting for {duration}s...")
        time.sleep(duration)
        self.next_distraction_run = 9999
        self.last_state_change_time = time.time()
        self.quest_watchdog = time.time()
        self.fatigue_start_time = time.time()
        self.active_profile = "SHIKAI_MAX"
        self.config._apply_profile(self.active_profile)
        self.next_profile_swap = (
            time.time()
            + random.randint(
                *self.config.CIRCADIAN_PROFILES[self.active_profile]["DURATION_MINS"]
            )
            * 60
        )  # type: ignore
        self.transition_to("RECOVERY")
        return True

    def retire_from_quest(self, haystack: Optional[Image.Image] = None) -> bool:
        """
        Forceful retirement sequence. This is the only place where okay is expected.
        Unknown okay elsewhere is forbidden because it can be a revive/orb prompt.
        """
        logger.warning("RETIRE: Initiating retirement sequence.")

        if self.find_image("retire", haystack=haystack):
            self.expected_okay_context = "RETIRE_CONFIRM"
            if self.smart_click(
                "retire",
                "click retire",
                verify_key="okay",
                wait_for_appearance=True,
                haystack=haystack,
            ):
                ok = self.smart_click(
                    "okay",
                    "confirm retirement",
                    verify_key="okay",
                    wait_for_appearance=False,
                    post_click_sleep=1.0,
                )
                self.expected_okay_context = None
                return ok
            self.expected_okay_context = None

        if self.find_image("okay", haystack=haystack):
            if self.expected_okay_context == "RETIRE_CONFIRM":
                ok = self.smart_click(
                    "okay",
                    "confirm retirement",
                    verify_key="okay",
                    wait_for_appearance=False,
                )
                self.expected_okay_context = None
                return ok
            logger.error("RETIRE: okay visible without expected retire context; refusing to click.")
            self.save_debug_screenshot("retire_unexpected_okay")
            return False

        if self.find_image("closed_room_coop_quest_menu", haystack=haystack):
            if self.smart_click(
                "closed_room_coop_quest_menu",
                "final confirm",
                verify_key="closed_room_coop_quest_menu",
                wait_for_appearance=False,
            ):
                self.transition_to("MENU")
                return True
        return False

    def reset_quest_watchdog(self, reason: str) -> None:
        """Reset the long-running quest/watchdog timer after proven lifecycle progress.

        Do not call this on every state transition: repeated SCAN/RECOVERY loops
        must still escalate to hard recovery. This is for lifecycle boundaries
        such as hard recovery start, successful game relaunch, menu arrival,
        run start, and run completion.
        """
        self.quest_watchdog = time.time()
        self.emit_trace("watchdog_reset", reason=reason)

    def recover_game(self) -> None:
        self.consecutive_recovery_count += 1
        self.disconnect_retry_count = 0
        self.disconnect_retry_limit = random.randint(*self.config.MAX_DISCONNECT_RETRIES)
        # Critical: a stale quest_watchdog must not immediately kill the
        # fresh recovery/startup attempt. v6 stable failed overnight in this
        # exact pattern: watchdog fired, recovery transitioned to startup, then
        # the still-expired watchdog fired again before startup could proceed.
        self.reset_quest_watchdog("hard_recovery_started")
        if self.consecutive_recovery_count > self.config.MAX_CONSECUTIVE_RECOVERIES:
            logger.error("FATAL: Exceeded maximum consecutive recoveries.")
            sys.exit(1)

        logger.warning(
            f"HARD RECOVERY initiated (Attempt {self.consecutive_recovery_count})..."
        )
        try:
            subprocess.run(
                ["pkill", "-f", "BleachBraveSouls.exe"], stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

        try:
            if hasattr(self, "disp") and self.disp:
                self.disp.close()
            self.disp = display.Display()
        except Exception:
            pass

        self.region, self.win_id = None, None
        time.sleep(self.config.WAIT_RESTART)
        subprocess.Popen(
            ["steam", "-applaunch", "1201240"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
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
            logger.error("Failed to find game window after restart.")
            sys.exit(1)
        self._startup_window_time = time.time()
        self.reset_quest_watchdog("hard_recovery_window_found")
        self.transition_to("GAME_STARTUP")

    def save_debug_screenshot(self, name: str) -> Optional[str]:
        if not self.config.TAKE_DEBUG_SCREENSHOTS or not self.region:
            return None
        try:
            os.makedirs("screenshots", exist_ok=True)
            ts = int(time.time())
            path = f"screenshots/debug_{self.state}_{name}_{ts}.png"
            pyautogui.screenshot(path, region=self.region)
            self._cleanup_screenshots()
            self._update_agent_latest_screenshot(path, alert=False)
            return path
        except Exception:
            return None

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
        except Exception:
            pass

    def transition_to(self, state: str) -> None:
        if self.state != state:
            old_state = self.state
            logger.info(f"TRANSITION [Run:{self.run_count}]: {old_state} -> {state}")
            shot = self.save_debug_screenshot(f"to_{state}")
            self.emit_trace("transition", from_state=old_state, to_state=state, screenshot=shot)

            # Reset run counted flag when entering new run
            if state in ["CHECK_RUN_START", "RUNNING"]:
                self._run_counted = False

            self.state = state
            self.last_state_change_time = time.time()
            # Do not reset disconnect_retry_count on every transition; that made
            # repeated disconnect popups impossible to escalate. Reset only after
            # clear forward progress into an actual run.
            if state == "RUNNING":
                self.disconnect_retry_count = 0
                self.disconnect_retry_limit = random.randint(*self.config.MAX_DISCONNECT_RETRIES)
                self.reset_quest_watchdog("entered_running")
            if state == "ROOM_LIST":
                self.search_start_time = time.time()
            if state == "MENU":
                self.reset_quest_watchdog("entered_menu")
                self.consecutive_recovery_count = 0

    def update_fatigue(self) -> None:
        elapsed = time.time() - self.fatigue_start_time
        self.fatigue_modifier = (
            self.config.FATIGUE_BASE
            + self.config.FATIGUE_AMPLITUDE
            * abs(math.sin(elapsed * (2 * math.pi / self.config.FATIGUE_PERIOD)))
        )

    def check_session_limit(self) -> None:
        if (time.time() - self.start_time) / 3600 >= self.config.SESSION_MAX_HOURS:
            logger.warning("SESSION LIMIT.")
            sys.exit(0)

    def check_quest_watchdog(self) -> None:
        if time.time() - self.quest_watchdog > self.config.TIMEOUT_QUEST_MAX:
            logger.error(
                f"WATCHDOG: Loop exceeded {self.config.TIMEOUT_QUEST_MAX}s. Hard Restarting."
            )
            self.recover_game()

    def ensure_window_ready(self) -> None:
        try:
            self.get_game_region()
            self.window_not_found_count = 0
        except Exception:
            self.win_id, self.region = None, None
            self.window_not_found_count += 1
            if self.window_not_found_count >= self.config.WINDOW_NOT_FOUND_RETRIES:
                self.recover_game()
                self.window_not_found_count = 0

    def get_game_region(self) -> Tuple[int, int, int, int]:
        try:
            now = time.time()
            if not self.win_id or (
                now - self._last_id_search > self.config.POLL_PROPERTY_SYNC
            ):
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
                    except Exception:
                        continue
                if valid_wid:
                    self.win_id = valid_wid
                self._last_id_search = now
            if not self.win_id:
                raise GameWindowNotFoundError()
            geo_lines = subprocess.check_output(
                ["xdotool", "getwindowgeometry", "--shell", self.win_id],
                text=True,
                stderr=subprocess.DEVNULL,
            ).splitlines()
            geo = {
                k: int(v)
                for k, v in (line.split("=") for line in geo_lines if "=" in line)
            }
            sw, sh = pyautogui.size()
            gx, gy, gw, gh = geo["X"], geo["Y"], geo["WIDTH"], geo["HEIGHT"]
            rx, ry = max(0, gx), max(0, gy)
            rw, rh = min(gw - (rx - gx), sw - rx), min(gh - (ry - gy), sh - ry)
            self.region = (rx, ry, rw, rh)
            return self.region
        except Exception as e:
            raise GameWindowNotFoundError(e)

    def setup_window_properties(self) -> None:
        if self.win_id and self.config.USE_WMCTRL_ALWAYS_ON_TOP:
            subprocess.run(
                ["wmctrl", "-i", "-r", self.win_id, "-b", "add,sticky,above"],
                check=False,
                stderr=subprocess.DEVNULL,
            )
            try:
                state = subprocess.check_output(
                    ["xprop", "-id", self.win_id, "WM_STATE"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                ).lower()
                if "iconic" in state:
                    subprocess.run(
                        ["xdotool", "windowraise", self.win_id],
                        check=False,
                        stderr=subprocess.DEVNULL,
                    )
            except Exception:
                pass

    def log_session_summary(self) -> None:
        elapsed = time.time() - self.start_time
        avg_run = (elapsed / 60.0) / self.run_count if self.run_count > 0 else 0.0
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        logger.info("--- SESSION SUMMARY ---")
        logger.info(f"Runs completed: {self.run_count}")
        logger.info(f"Elapsed: {hours:02d}:{minutes:02d}:{seconds:02d}")
        logger.info(f"Average minutes/run: {avg_run:.2f}")
        logger.info(f"State: {self.state} | Phase: {self.current_phase()} | Profile: {self.active_profile}")
        logger.info(f"Room search mode: {self.config.ROOM_SEARCH_MODE}")
        logger.info(f"Disconnect streak: {self.disconnect_retry_count}/{self.disconnect_retry_limit}")
        logger.info(f"Consecutive recoveries: {self.consecutive_recovery_count}")
        logger.info(f"Telemetry dir: {self.config.AGENT_TELEMETRY_DIR}")
        self.emit_trace(
            "session_summary",
            runs=self.run_count,
            elapsed_seconds=elapsed,
            avg_minutes_per_run=avg_run,
            state=self.state,
            phase=self.current_phase(),
            profile=self.active_profile,
            room_search_mode=self.config.ROOM_SEARCH_MODE,
        )

    def check_circadian_rhythm(self) -> None:
        assert self.config.CIRCADIAN_PROFILES is not None
        if time.time() > self.next_profile_swap:
            old_profile = self.active_profile
            self.active_profile = (
                "SHIKAI_NORMAL" if self.active_profile == "SHIKAI_MAX" else "SHIKAI_MAX"
            )
            self.config._apply_profile(self.active_profile)
            self.next_profile_swap = (
                time.time()
                + random.randint(
                    *self.config.CIRCADIAN_PROFILES[self.active_profile][
                        "DURATION_MINS"
                    ]
                )
                * 60
            )  # type: ignore

            if old_profile == "SHIKAI_MAX" and self.active_profile == "SHIKAI_NORMAL":
                self.next_distraction_run = (
                    self.run_count + random.randint(*self.config.CASUAL_LINGER_RUNS)
                    if hasattr(self.config, "CASUAL_LINGER_RUNS")
                    else self.run_count + random.randint(8, 16)
                )
            elif old_profile == "SHIKAI_NORMAL" and self.active_profile == "SHIKAI_MAX":
                self.next_distraction_run = 9999

            logger.info(f"CIRCADIAN SHIFT: {self.active_profile}")

    # === AI_SECTION: MAIN_PRIORITY_LOOP ===
    def run(self, test_restart: bool = False) -> None:
        try:
            if test_restart:
                self.recover_game()
            else:
                self.get_game_region()
                self.setup_window_properties()
        except Exception:
            self.recover_game()
        while True:
            self.ensure_window_ready()
            if time.time() - self._last_property_sync > self.config.POLL_PROPERTY_SYNC:
                self.setup_window_properties()
                self._last_property_sync = time.time()
            if self.region:
                try:
                    self.snapshot = pyautogui.screenshot(region=self.region)
                except Exception:
                    self.snapshot = None
            else:
                self.snapshot = None
            self.update_fatigue()
            self.check_circadian_rhythm()
            self.check_session_limit()
            self.check_quest_watchdog()
            if (
                getattr(self.config, "ENABLE_TELEMETRY", False)
                and time.time() - self._last_agent_heartbeat >= self.config.AGENT_HEARTBEAT_INTERVAL
            ):
                self._last_agent_heartbeat = time.time()
                self.emit_trace("heartbeat", snapshot_available=self.snapshot is not None)
            if self.handle_forbidden_confirmations(self.snapshot):
                continue

            # Startup news overlays can coexist with startup/coop anchors.
            # Handle them explicitly before generic popup/state handling.
            if self.state == "GAME_STARTUP" and self.handle_startup_news_popup(self.snapshot):
                continue

            if self.handle_global_popups(self.snapshot):
                continue
            handler = self.handlers.get(self.state)
            if handler:
                handler(self.snapshot)
            else:
                self.transition_to("RECOVERY")
            time.sleep(self.config.POLL_MAIN_LOOP)


# === AI_SECTION: CLI_ENTRYPOINT ===
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-ai-manifest", action="store_true", help="Print machine-readable AI behavior contract and exit")
    parser.add_argument("--write-ai-manifest", default=None, help="Write AI behavior contract JSON to this path and exit")
    parser.add_argument("--test-restart", action="store_true")
    parser.add_argument("--debug-screenshots", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--telemetry-dir", default=None, help="Folder for agent-readable telemetry files")
    parser.add_argument("--no-telemetry", action="store_true", help="Disable JSONL/current-state telemetry")
    parser.add_argument(
        "--room-search-mode",
        choices=["strict_rules", "all_auto"],
        default="strict_rules",
        help="strict_rules keeps v6-style room_rules_valid matching; all_auto clicks deduped AUTO rows even without rules.",
    )
    parser.add_argument(
        "--allow-all-auto-rooms",
        action="store_true",
        help="Alias for --room-search-mode all_auto. Experimental; may hit room-not-met more often.",
    )
    args = parser.parse_args()

    if args.print_ai_manifest or args.write_ai_manifest:
        payload = json.dumps(get_ai_manifest(), indent=2, sort_keys=True)
        if args.write_ai_manifest:
            with open(args.write_ai_manifest, "w", encoding="utf-8") as f:
                f.write(payload + "\n")
        if args.print_ai_manifest:
            print(payload)
        sys.exit(0)

    config = BotConfiguration()
    if args.debug_screenshots:
        config.TAKE_DEBUG_SCREENSHOTS = True
    if args.no_telemetry:
        config.ENABLE_TELEMETRY = False
    if args.telemetry_dir:
        config.AGENT_TELEMETRY_DIR = args.telemetry_dir
        config.TRACE_DIR = os.path.join(args.telemetry_dir, "traces")
    config.ROOM_SEARCH_MODE = "all_auto" if args.allow_all_auto_rooms else args.room_search_mode

    bot = BBSBot(config)
    if args.dry_run:
        logger.info("DRY RUN ENABLED.")
        bot._send_x11_click = lambda x, y: (logger.info(f"Click ({x}, {y})"), True)[1]  # type: ignore
    try:
        bot.run(test_restart=args.test_restart)
    except KeyboardInterrupt:
        bot.log_session_summary()
    except Exception as e:
        logger.exception(f"Fatal: {e}")
        bot.log_session_summary()
        sys.exit(1)
