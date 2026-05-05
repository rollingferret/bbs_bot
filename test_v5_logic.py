
import unittest
from dataclasses import dataclass
from typing import List, Tuple
import pyscreeze

# Mock BotConfiguration to isolate logic
@dataclass
class MockConfig:
    ROOM_MATCH_WEIGHT: float = 0.1
    MAX_RULE_DISTANCE: int = 110
    AUTO_ICON_DEDUPE_DIST: int = 60

class MockBot:
    def __init__(self):
        self.config = MockConfig()
    
    def match_rooms(self, autos, rules):
        # Implementation copied from bbs_bot_v5.py for testing
        valid = []
        for a in self.dedupe_autos(autos):
            ax, ay = a.left + a.width//2, a.top + a.height//2
            best_r, min_d = None, float('inf')
            for r in rules:
                rx, ry = r.left + r.width//2, r.top + r.height//2
                if ry > ay:
                    d = abs(ry - ay) + abs(rx - ax) * self.config.ROOM_MATCH_WEIGHT
                    if d < min_d and d < self.config.MAX_RULE_DISTANCE:
                        min_d, best_r = d, r
            if best_r:
                valid.append((a, best_r))
        return valid

    def dedupe_autos(self, matches):
        # Implementation copied from bbs_bot_v5.py for testing
        unique = []
        for m in matches:
            cx, cy = m.left + m.width//2, m.top + m.height//2
            if not any(((cx-(u.left+u.width//2))**2 + (cy-(u.top+u.height//2))**2)**0.5 < self.config.AUTO_ICON_DEDUPE_DIST for u in unique):
                unique.append(m)
        return unique

class TestV5Logic(unittest.TestCase):
    def setUp(self):
        self.bot = MockBot()

    def test_dedupe_autos(self):
        # Overlapping icons
        matches = [
            pyscreeze.Box(100, 100, 50, 50),
            pyscreeze.Box(105, 105, 50, 50), # Duplicate
            pyscreeze.Box(300, 300, 50, 50)  # Unique
        ]
        unique = self.bot.dedupe_autos(matches)
        self.assertEqual(len(unique), 2)
        self.assertEqual(unique[0].left, 100)
        self.assertEqual(unique[1].left, 300)

    def test_match_rooms_basic(self):
        # 1 Auto, 1 Rule below it
        autos = [pyscreeze.Box(100, 100, 50, 50)]
        rules = [pyscreeze.Box(100, 160, 100, 20)] # Directly below
        
        valid = self.bot.match_rooms(autos, rules)
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0][0].left, 100)
        self.assertEqual(valid[0][1].top, 160)

    def test_match_rooms_too_far(self):
        # Rule is too far away
        autos = [pyscreeze.Box(100, 100, 50, 50)]
        rules = [pyscreeze.Box(100, 300, 100, 20)] # Too far (200px)
        
        valid = self.bot.match_rooms(autos, rules)
        self.assertEqual(len(valid), 0)

    def test_match_rooms_vertical_only(self):
        # Rule is above the auto icon (should be ignored)
        autos = [pyscreeze.Box(100, 200, 50, 50)]
        rules = [pyscreeze.Box(100, 100, 100, 20)] # Above
        
        valid = self.bot.match_rooms(autos, rules)
        self.assertEqual(len(valid), 0)

if __name__ == '__main__':
    unittest.main()
