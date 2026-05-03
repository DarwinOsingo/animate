"""
ERAS Phase 1 — Script 2: Chunk bpy Docs
Reads ./raw_docs/*.txt and splits into ~300-token chunks with metadata.
Output: ./chunks/chunks.jsonl  (one JSON object per line)

Run: python 02_chunk_docs.py
"""

import os
import json
import re
import tiktoken

INPUT_DIR  = "./raw_docs"
OUTPUT_DIR = "./chunks"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "chunks.jsonl")

TARGET_TOKENS  = 300   # target chunk size
OVERLAP_TOKENS = 50    # token overlap between chunks (context continuity)

os.makedirs(OUTPUT_DIR, exist_ok=True)

enc = tiktoken.get_encoding("cl100k_base")  # close enough for any LLM


def count_tokens(text: str) -> int:
    return len(enc.encode(text))


def split_into_sections(text: str) -> list[tuple[str, str]]:
    """
    Split raw doc text into (heading, body) pairs.
    Blender docs use patterns like:
        bpy.ops.object.some_function(...)
        bpy.types.SomeType.property
    We treat each function/class definition as a natural boundary.
    """
    # Patterns that signal a new API entry
    section_pattern = re.compile(
        r"^(bpy\.\S+|mathutils\.\S+)",
        re.MULTILINE
    )

    matches = list(section_pattern.finditer(text))
    if not matches:
        # No clear API boundaries — treat whole text as one section
        return [("", text)]

    sections = []
    for i, match in enumerate(matches):
        heading = match.group(0)
        start   = match.start()
        end     = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body    = text[start:end].strip()
        sections.append((heading, body))

    return sections


def chunk_text(text: str, source_module: str) -> list[dict]:
    """
    Chunk a doc text into ~TARGET_TOKENS pieces with OVERLAP_TOKENS overlap.
    Returns list of chunk dicts ready for JSONL.
    """
    sections = split_into_sections(text)
    chunks   = []
    chunk_id = 0

    for heading, body in sections:
        tokens = enc.encode(body)

        if len(tokens) <= TARGET_TOKENS:
            # Section fits in one chunk
            chunks.append({
                "id":       f"{source_module}_{chunk_id:04d}",
                "module":   source_module,
                "heading":  heading,
                "text":     body,
                "tokens":   len(tokens),
                "validated": False,   # True once a script using this chunk passes headless
            })
            chunk_id += 1
        else:
            # Section too large — slide a window through it
            step   = TARGET_TOKENS - OVERLAP_TOKENS
            start  = 0
            while start < len(tokens):
                window = tokens[start : start + TARGET_TOKENS]
                text_window = enc.decode(window)
                chunks.append({
                    "id":       f"{source_module}_{chunk_id:04d}",
                    "module":   source_module,
                    "heading":  heading,
                    "text":     text_window,
                    "tokens":   len(window),
                    "validated": False,
                })
                chunk_id += 1
                start += step

    return chunks


def main():
    raw_files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".txt")]
    if not raw_files:
        print(f"No .txt files found in {INPUT_DIR}/")
        print("Run 01_scrape_bpy_docs.py first.")
        return

    print(f"Chunking {len(raw_files)} module files\n")

    all_chunks = []
    for filename in sorted(raw_files):
        path = os.path.join(INPUT_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()

        # Extract module name from first line (written by scraper)
        module = filename.replace("_", ".").replace(".txt", "")
        first_line = text.splitlines()[0]
        if first_line.startswith("MODULE:"):
            module = first_line.replace("MODULE:", "").strip()

        chunks = chunk_text(text, module)
        all_chunks.extend(chunks)
        print(f"  {module:40s}  {len(chunks):3d} chunks")

    # Write JSONL
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk) + "\n")

    total_tokens = sum(c["tokens"] for c in all_chunks)
    print(f"\nTotal chunks : {len(all_chunks)}")
    print(f"Total tokens : {total_tokens:,}")
    print(f"Avg per chunk: {total_tokens // len(all_chunks) if all_chunks else 0}")
    print(f"Output       : {os.path.abspath(OUTPUT_FILE)}")


if __name__ == "__main__":
    main()