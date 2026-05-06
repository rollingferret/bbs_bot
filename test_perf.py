import time
import subprocess

start = time.time()
for i in range(10):
    subprocess.check_output(
        ["xdotool", "search", "--onlyvisible", "--name", "Bleach"],
        stderr=subprocess.DEVNULL,
    )
print("Time taken for 10 searches:", time.time() - start)
