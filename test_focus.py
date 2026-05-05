import subprocess

def get_window_class(wid):
    try:
        return subprocess.check_output(["xprop", "-id", wid, "WM_CLASS"], text=True).strip()
    except:
        return ""

print("Test script ready.")
