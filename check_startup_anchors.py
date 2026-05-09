import pyautogui
from PIL import Image
import os
import subprocess
import cv2
import numpy as np

def get_region():
    try:
        wid = subprocess.check_output(["xdotool", "search", "--name", "Bleach: Brave Souls"]).decode().strip().split()[-1]
        geo = subprocess.check_output(["xdotool", "getwindowgeometry", "--shell", wid]).decode().splitlines()
        g = {line.split("=")[0]: int(line.split("=")[1]) for line in geo if "=" in line}
        return (g["X"], g["Y"], g["WIDTH"], g["HEIGHT"])
    except:
        return None

reg = get_region()
print(f"Region: {reg}")
if reg:
    shot = pyautogui.screenshot(region=reg)
    haystack = np.array(shot)[:, :, ::-1].copy()
    for key in ["coop_1", "coop_2", "game_start", "close_news"]:
        path = f"images/{key.replace('_', '-') if 'coop' in key else key}.png"
        if not os.path.exists(path):
             # check alternative path
             if key == "coop_1": path = "images/coop-1.png"
             if key == "coop_2": path = "images/coop-2.png"
        
        if os.path.exists(path):
            template = Image.open(path).convert("RGB")
            needle = np.array(template)[:, :, ::-1].copy()
            result = cv2.matchTemplate(haystack, needle, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            print(f"{key}: {max_val:.4f} at {max_loc}")
        else:
            print(f"{key}: MISSING FILE {path}")
