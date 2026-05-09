import pyautogui
from PIL import Image
import os
import subprocess

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
    shot.save("check_menu.png")
    for key in ["coop_quest", "open_coop_quest"]:
        path = f"images/{key}.png"
        template = Image.open(path).convert("RGB")
        try:
            import pyscreeze
            # find max confidence
            import cv2
            import numpy as np
            needle = np.array(template)[:, :, ::-1].copy()
            haystack = np.array(shot)[:, :, ::-1].copy()
            result = cv2.matchTemplate(haystack, needle, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            print(f"{key}: {max_val:.4f} at {max_loc}")
        except Exception as e:
            print(f"{key}: Error {e}")
