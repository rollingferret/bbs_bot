
import unittest
from typing import List, Tuple
import pyscreeze
from bbs_bot_v5 import BBSBot, BotConfiguration

class TestV5Logic(unittest.TestCase):
    def setUp(self):
        self.config = BotConfiguration()
        # Ensure test constants are stable and match the logic we want to verify
        self.config.ROOM_MATCH_WEIGHT = 0.1
        self.config.MAX_RULE_DISTANCE = 110
        self.config.AUTO_ICON_DEDUPE_DIST = 60

    def test_dedupe_autos(self):
        # Overlapping icons
        matches = [
            pyscreeze.Box(100, 100, 50, 50),
            pyscreeze.Box(105, 105, 50, 50), # Duplicate
            pyscreeze.Box(300, 300, 50, 50)  # Unique
        ]
        unique = BBSBot.dedupe_autos(matches, self.config)
        self.assertEqual(len(unique), 2)
        self.assertEqual(unique[0].left, 100)
        self.assertEqual(unique[1].left, 300)

    def test_match_rooms_basic(self):
        # 1 Auto, 1 Rule below it
        autos = [pyscreeze.Box(100, 100, 50, 50)]
        rules = [pyscreeze.Box(100, 160, 100, 20)] # Directly below
        
        valid = BBSBot.match_rooms(autos, rules, self.config)
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0][0].left, 100)
        self.assertEqual(valid[0][1].top, 160)

    def test_match_rooms_too_far(self):
        # Rule is too far away
        autos = [pyscreeze.Box(100, 100, 50, 50)]
        rules = [pyscreeze.Box(100, 300, 100, 20)] # Too far (200px)
        
        valid = BBSBot.match_rooms(autos, rules, self.config)
        self.assertEqual(len(valid), 0)

    def test_match_rooms_vertical_only(self):
        # Rule is above the auto icon (should be ignored)
        autos = [pyscreeze.Box(100, 200, 50, 50)]
        rules = [pyscreeze.Box(100, 100, 100, 20)] # Above
        
        valid = BBSBot.match_rooms(autos, rules, self.config)
        self.assertEqual(len(valid), 0)

if __name__ == '__main__':
    unittest.main()
