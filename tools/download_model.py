#!/usr/bin/env python3
"""Download a small English Vosk model for the voice-follow feature.

Fetches vosk-model-small-en-us-0.15 (~40 MB) and unzips it next to
teleprompter.py as ./model, which the app auto-detects.

Run:  python tools/download_model.py
"""

import os
import sys
import zipfile
import urllib.request

URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ZIP_PATH = os.path.join(ROOT, "vosk-model-small-en-us-0.15.zip")
EXTRACT_NAME = "vosk-model-small-en-us-0.15"
TARGET = os.path.join(ROOT, "model")


def report(done, total):
    if total > 0:
        pct = done * 100 // total
        sys.stdout.write(f"\rDownloading model... {pct:3d}%")
        sys.stdout.flush()


def main():
    if os.path.isdir(TARGET):
        print(f"'{TARGET}' already exists — nothing to do.")
        return
    print(f"Fetching {URL}")
    got = {"n": 0}

    def hook(block, block_size, total):
        got["n"] += block_size
        report(min(got["n"], total), total)

    urllib.request.urlretrieve(URL, ZIP_PATH, hook)
    print("\nUnzipping...")
    with zipfile.ZipFile(ZIP_PATH) as z:
        z.extractall(ROOT)
    os.rename(os.path.join(ROOT, EXTRACT_NAME), TARGET)
    os.remove(ZIP_PATH)
    print(f"Done. Model ready at: {TARGET}")
    print("Now run the app and press V to start voice-follow.")


if __name__ == "__main__":
    main()
