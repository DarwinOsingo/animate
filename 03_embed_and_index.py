"""
ERAS Phase 1 — Script 3: Embed & Index into Qdrant
Reads ./chunks/chunks.jsonl, embeds each chunk, loads into Qdrant (embedded mode).
Two collections:
  - bpy_api_reference   : Blender API docs (this script)
  - shot_patterns       : Verified working scripts (populated by pipeline later)

Run: python 03_embed_and_index.py

Qdrant persists to ./eras_qdrant/ — no server, no Docker needed.
"""

import json
import os
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    PayloadSchemaType,
)
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

CHUNKS_FILE   = "./chunks/chunks.jsonl"
QDRANT_PATH   = "./eras_qdrant"

# Collection names — keep these as constants, referenced by the pipeline too
COLLECTION_API      = "bpy_api_reference"
COLLECTION_PATTERNS = "shot_patterns"

# Embedding model
# all-MiniLM-L6-v2: 384-dim, 80MB, fast on CPU — good for Phase 1
# Upgrade to BAAI/bge-base-en if you get GPU headroom later
EMBED_MODEL = "all-MiniLM-L6-v2"
VECTOR_DIM  = 384

BATCH_SIZE = 64  # chunks per embedding batch


def load_chunks(path: str) -> list[dict]:
    chunks = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


def init_qdrant(path: str) -> QdrantClient:
    client = QdrantClient(path=path)
    print(f"Qdrant storage: {os.path.abspath(path)}")

    # API reference collection
    existing = [c.name for c in client.get_collections().collections]

    if COLLECTION_API not in existing:
        client.create_collection(
            collection_name=COLLECTION_API,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        # Index payload fields for fast filtering
        client.create_payload_index(COLLECTION_API, "module",    PayloadSchemaType.KEYWORD)
        client.create_payload_index(COLLECTION_API, "validated", PayloadSchemaType.BOOL)
        print(f"Created collection: {COLLECTION_API}")
    else:
        print(f"Collection exists:  {COLLECTION_API}")

    # Shot patterns collection (empty for now, pipeline populates it)
    if COLLECTION_PATTERNS not in existing:
        client.create_collection(
            collection_name=COLLECTION_PATTERNS,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        client.create_payload_index(COLLECTION_PATTERNS, "shot_type",  PayloadSchemaType.KEYWORD)
        client.create_payload_index(COLLECTION_PATTERNS, "validated",  PayloadSchemaType.BOOL)
        client.create_payload_index(COLLECTION_PATTERNS, "pass_count", PayloadSchemaType.INTEGER)
        print(f"Created collection: {COLLECTION_PATTERNS}")
    else:
        print(f"Collection exists:  {COLLECTION_PATTERNS}")

    return client


def embed_and_index(chunks: list[dict], client: QdrantClient, model: SentenceTransformer):
    print(f"\nEmbedding {len(chunks)} chunks with {EMBED_MODEL}...")

    points = []
    texts  = [c["text"] for c in chunks]

    # Embed in batches
    for i in tqdm(range(0, len(texts), BATCH_SIZE), desc="Embedding"):
        batch_texts   = texts[i : i + BATCH_SIZE]
        batch_chunks  = chunks[i : i + BATCH_SIZE]
        batch_vectors = model.encode(batch_texts, show_progress_bar=False).tolist()

        for chunk, vector in zip(batch_chunks, batch_vectors):
            # Use a stable integer ID from chunk index
            point_id = i + batch_chunks.index(chunk)
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "chunk_id":  chunk["id"],
                        "module":    chunk["module"],
                        "heading":   chunk["heading"],
                        "text":      chunk["text"],
                        "tokens":    chunk["tokens"],
                        "validated": chunk["validated"],
                    },
                )
            )

    print(f"Uploading {len(points)} points to Qdrant...")
    # Upload in batches to avoid memory spikes
    for i in tqdm(range(0, len(points), 256), desc="Indexing"):
        client.upsert(
            collection_name=COLLECTION_API,
            points=points[i : i + 256],
        )

    count = client.get_collection(COLLECTION_API).points_count
    print(f"\nCollection '{COLLECTION_API}': {count} points indexed")


def smoke_test(client: QdrantClient, model: SentenceTransformer):
    """Quick retrieval test to confirm the index works."""
    print("\n--- Smoke test ---")
    queries = [
        "add object to scene",
        "set camera location rotation",
        "create armature and add bones",
    ]
    for q in queries:
        vec = model.encode(q).tolist()
        results = client.query_points(
            collection_name=COLLECTION_API,
            query=vec,
            limit=2,
        ).points
        print(f"\nQuery: '{q}'")
        for r in results:
            print(f"  [{r.score:.3f}] {r.payload['module']} — {r.payload['heading'][:60]}")


def main():
    if not os.path.exists(CHUNKS_FILE):
        print(f"Chunks file not found: {CHUNKS_FILE}")
        print("Run 02_chunk_docs.py first.")
        return

    chunks = load_chunks(CHUNKS_FILE)
    print(f"Loaded {len(chunks)} chunks from {CHUNKS_FILE}")

    client = init_qdrant(QDRANT_PATH)
    model  = SentenceTransformer(EMBED_MODEL)

    embed_and_index(chunks, client, model)
    smoke_test(client, model)

    print("\nAll done. Qdrant index ready for the pipeline.")
    print(f"Storage path: {os.path.abspath(QDRANT_PATH)}")


if __name__ == "__main__":
    main()