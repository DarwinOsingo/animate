"""
ERAS Phase 1 — Script 4: Index Verified Seed Scripts into shot_patterns
Reads seeds/verified/*.py, extracts metadata from docstring,
embeds the script, loads into Qdrant shot_patterns collection.

Run: python 04_index_shot_patterns.py
Re-run anytime you move a new verified script into seeds/verified/
"""

import os
import re
import json
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance, PayloadSchemaType
from sentence_transformers import SentenceTransformer

VERIFIED_DIR     = "./seeds/verified"
QDRANT_PATH      = "./eras_qdrant"
COLLECTION       = "shot_patterns"
EMBED_MODEL      = "all-MiniLM-L6-v2"
VECTOR_DIM       = 384


def extract_metadata(script_text: str, filename: str) -> dict:
    """
    Pull shot_type and tags from the script docstring.
    Expected format:
        Shot type: camera_setup
        Tags: camera, focal_length, handheld
    Falls back to filename-derived values if not found.
    """
    shot_type = "unknown"
    tags      = []

    shot_match = re.search(r"Shot type:\s*(.+)", script_text)
    tags_match = re.search(r"Tags:\s*(.+)",      script_text)

    if shot_match:
        shot_type = shot_match.group(1).strip()
    if tags_match:
        tags = [t.strip() for t in tags_match.group(1).split(",")]

    # Fallback: derive from filename e.g. seed_02_camera -> camera
    if shot_type == "unknown":
        parts = filename.replace(".py", "").split("_")
        shot_type = "_".join(parts[2:]) if len(parts) > 2 else filename

    return {"shot_type": shot_type, "tags": tags}


def embed_script(script_text: str, metadata: dict, model: SentenceTransformer) -> list:
    """
    Embed a script for retrieval.
    We embed: tags + shot_type + first 500 chars of script
    This makes retrieval work on natural language shot briefs.
    """
    retrieval_text = (
        f"shot type: {metadata['shot_type']} "
        f"tags: {' '.join(metadata['tags'])} "
        f"{script_text[:500]}"
    )
    return model.encode(retrieval_text).tolist()


def init_collection(client: QdrantClient):
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        print(f"Created collection: {COLLECTION}")
    else:
        print(f"Collection exists:  {COLLECTION}")


def main():
    if not os.path.exists(VERIFIED_DIR):
        print(f"No verified directory found at {VERIFIED_DIR}")
        print("Run seeds through Blender headless first, then move passing ones to seeds/verified/")
        return

    scripts = [f for f in os.listdir(VERIFIED_DIR) if f.endswith(".py")]
    if not scripts:
        print(f"No .py files found in {VERIFIED_DIR}")
        return

    print(f"Found {len(scripts)} verified scripts\n")

    client = QdrantClient(path=QDRANT_PATH)
    model  = SentenceTransformer(EMBED_MODEL)
    init_collection(client)

    # Get current count to generate unique IDs
    current_count = client.get_collection(COLLECTION).points_count or 0

    points = []
    for i, filename in enumerate(sorted(scripts)):
        path = os.path.join(VERIFIED_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            script_text = f.read()

        metadata = extract_metadata(script_text, filename)
        vector   = embed_script(script_text, metadata, model)

        point = PointStruct(
            id=current_count + i,
            vector=vector,
            payload={
                "filename":   filename,
                "shot_type":  metadata["shot_type"],
                "tags":       metadata["tags"],
                "script":     script_text,       # full script stored in payload
                "validated":  True,
                "pass_count": 1,
                "source":     "seed",            # 'seed' | 'pipeline' (auto-added later)
            },
        )
        points.append(point)
        print(f"  OK  {filename:45s} shot_type={metadata['shot_type']}")

    client.upsert(collection_name=COLLECTION, points=points)

    total = client.get_collection(COLLECTION).points_count
    print(f"\nshot_patterns collection: {total} scripts indexed")

    # Smoke test
    print("\n--- Smoke test ---")
    test_queries = [
        "handheld medium shot camera",
        "two characters facing each other confrontation",
        "dramatic three point lighting",
        "character armature offensive stance",
        "particle fx aura impact spawn",
    ]
    for q in test_queries:
        vec     = model.encode(q).tolist()
        results = client.query_points(
            collection_name=COLLECTION,
            query=vec,
            limit=1,
        ).points
        if results:
            r = results[0]
            print(f"  [{r.score:.3f}] '{q}'")
            print(f"          -> {r.payload['filename']} ({r.payload['shot_type']})")


if __name__ == "__main__":
    main()