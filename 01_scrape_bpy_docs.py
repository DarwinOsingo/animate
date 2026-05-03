"""
ERAS Phase 1 — Script 1: Scrape Blender bpy API Docs
Scrapes docs.blender.org for the modules you'll actually hit in Phase 1.
Output: ./raw_docs/<module>.txt  (one file per module page)

Run: python 01_scrape_bpy_docs.py
"""

import requests
from bs4 import BeautifulSoup
import os
import time

# Blender version — change if you're on 4.1 or 4.2
BLENDER_VERSION = "5.1"
BASE_URL = f"https://docs.blender.org/api/{BLENDER_VERSION}"

# Phase 1 modules — the ones Phi-4 will actually call
# Expand this list as you add shot types
TARGET_MODULES = [
    "bpy.ops.object",
    "bpy.ops.mesh",
    "bpy.ops.armature",
    "bpy.ops.pose",
    "bpy.ops.anim",
    "bpy.ops.render",
    "bpy.ops.scene",
    "bpy.data",
    "bpy.context",
    "bpy.types.Object",
    "bpy.types.Scene",
    "bpy.types.Camera",
    "bpy.types.Light",
    "bpy.types.Armature",
    "bpy.types.Material",
    "mathutils",
]

OUTPUT_DIR = "./raw_docs"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def module_to_url(module: str) -> str:
    """Convert module name to docs URL."""
    # e.g. bpy.ops.object -> bpy.ops.object.html
    return f"{BASE_URL}/{module}.html"


def scrape_module(module: str) -> str | None:
    url = module_to_url(module)
    print(f"  Fetching {url}")
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            print(f"  !! {module} returned {r.status_code} — skipping")
            return None

        soup = BeautifulSoup(r.text, "lxml")

        # Remove nav, footer, sidebar — keep only the API content
        for tag in soup.select("nav, footer, .sphinxsidebar, .related, #searchbox"):
            tag.decompose()

        # Main content div
        content = soup.find("div", {"class": "body"}) or soup.find("div", role="main")
        if not content:
            content = soup.body

        text = content.get_text(separator="\n", strip=True)

        # Basic cleanup
        lines = [l.strip() for l in text.splitlines()]
        lines = [l for l in lines if l]  # drop blank lines
        return "\n".join(lines)

    except Exception as e:
        print(f"  !! Error fetching {module}: {e}")
        return None


def main():
    print(f"Scraping Blender {BLENDER_VERSION} API docs")
    print(f"Target: {len(TARGET_MODULES)} modules\n")

    success = 0
    failed = []

    for module in TARGET_MODULES:
        text = scrape_module(module)
        if text:
            filename = module.replace(".", "_") + ".txt"
            path = os.path.join(OUTPUT_DIR, filename)
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"MODULE: {module}\nSOURCE: {module_to_url(module)}\n\n")
                f.write(text)
            char_count = len(text)
            print(f"  OK  {module} ({char_count:,} chars) -> {filename}")
            success += 1
        else:
            failed.append(module)

        time.sleep(0.5)  # be polite to the docs server

    print(f"\nDone: {success}/{len(TARGET_MODULES)} modules scraped")
    if failed:
        print(f"Failed: {failed}")
    print(f"Raw docs saved to: {os.path.abspath(OUTPUT_DIR)}/")


if __name__ == "__main__":
    main()