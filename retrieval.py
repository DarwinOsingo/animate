"""
ERAS Phase 1 — Script 5: Query Decomposition & Retrieval
Takes a raw shot brief + registry snapshot, decomposes into targeted queries,
retrieves from both Qdrant collections, returns a clean context block
ready to inject into Phi-4's prompt.

Usage (standalone test):
    python 05_retrieval.py

Usage (imported by pipeline):
    from retrieval import retrieve_context
    context = retrieve_context(brief, registry)
"""

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
import re

QDRANT_PATH      = "./eras_qdrant"
COLLECTION_API   = "bpy_api_reference"
COLLECTION_PATT  = "shot_patterns"
EMBED_MODEL      = "all-MiniLM-L6-v2"

# How many chunks to pull per query from each collection
API_TOP_K        = 3
PATTERN_TOP_K    = 2

# Max total tokens to inject into Phi-4 prompt (stay under 1500)
MAX_CONTEXT_TOKENS = 1400


# ── Singleton model + client (loaded once, reused across shots) ───────────────
_client = None
_model  = None

def _get_client():
    global _client
    if _client is None:
        _client = QdrantClient(path=QDRANT_PATH)
    return _client

def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


# ── Query decomposition ───────────────────────────────────────────────────────

# Keywords that signal which bpy modules are needed
MODULE_SIGNALS = {
    "camera":       ["camera", "shot", "focal", "handheld", "cut", "close", "wide", "medium", "pan", "zoom"],
    "lighting":     ["light", "lighting", "mood", "shadow", "dark", "bright", "dusk", "dawn", "dramatic", "warm", "cold"],
    "character":    ["character", "stance", "pose", "facing", "position", "foreground", "background", "body"],
    "armature":     ["armature", "bone", "rig", "pose", "punch", "kick", "jump", "airborne", "offensive", "defensive"],
    "fx":           ["fx", "effect", "aura", "impact", "spawn", "particle", "smoke", "trail", "clone", "beam", "portal"],
    "movement":     ["move", "step", "void", "instant", "teleport", "dash", "rush", "arc", "path", "destination"],
    "object":       ["add", "place", "create", "delete", "scene", "object", "mesh"],
    "animation":    ["frame", "keyframe", "animation", "timing", "hold", "ease"],
    "render":       ["render", "output", "resolution", "eevee", "cycles", "frame_start", "frame_end"],
}

ACTION_PRIMITIVES = {
    "movement":       ["step", "move", "dash", "rush", "teleport", "instant", "arc", "path"],
    "attack":         ["punch", "kick", "strike", "hit", "slash", "attack", "throw"],
    "ability":        ["void", "jutsu", "gear", "transmission", "maneuver", "ability", "power"],
    "spawn":          ["clone", "summon", "portal", "beam", "copy", "spawn", "create"],
    "transformation": ["transform", "gear", "mode", "form", "change", "grow", "shrink"],
}


def decompose_brief(brief: str, registry: dict) -> dict:
    """
    Decompose a shot brief into targeted retrieval queries.

    Returns:
        {
            "api_queries":     [str, ...],   # queries for bpy_api_reference
            "pattern_queries": [str, ...],   # queries for shot_patterns
            "detected_modules": [str, ...],  # which bpy modules are relevant
            "action_primitive": str,         # movement|attack|ability|spawn|transformation
        }
    """
    brief_lower = brief.lower()

    # ── 1. Resolve aliases from registry ─────────────────────────────────────
    # Replace C1, V1, BG2 etc with their type so queries are semantic
    resolved = brief
    for alias, entry in registry.items():
        if alias in resolved:
            entity_type = entry.get("type", "entity")
            resolved = resolved.replace(alias, entity_type)

    # ── 2. Detect relevant modules ────────────────────────────────────────────
    detected_modules = []
    for module, keywords in MODULE_SIGNALS.items():
        if any(kw in brief_lower for kw in keywords):
            detected_modules.append(module)

    # Always include object and render — every shot needs them
    for required in ["object", "render"]:
        if required not in detected_modules:
            detected_modules.append(required)

    # ── 3. Detect action primitive ────────────────────────────────────────────
    action_primitive = "movement"  # default
    for primitive, keywords in ACTION_PRIMITIVES.items():
        if any(kw in brief_lower for kw in keywords):
            action_primitive = primitive
            break

    # ── 4. Build API queries (technical, module-specific) ─────────────────────
    api_queries = []

    if "camera" in detected_modules:
        shot_type = "medium"
        for st in ["wide", "close", "extreme_close", "medium"]:
            if st.replace("_", " ") in brief_lower or st in brief_lower:
                shot_type = st
        style = "handheld" if "handheld" in brief_lower else "static"
        api_queries.append(f"bpy camera setup {shot_type} shot {style}")

    if "lighting" in detected_modules:
        mood = "dramatic"
        for m in ["warm", "cold", "dusk", "neutral"]:
            if m in brief_lower:
                mood = m
        api_queries.append(f"bpy light add area spot {mood} three point")

    if "armature" in detected_modules or "character" in detected_modules:
        stance = "offensive" if any(w in brief_lower for w in ["attack", "punch", "offensive", "confront"]) else "idle"
        api_queries.append(f"bpy armature pose bone rotation {stance}")

    if "fx" in detected_modules:
        api_queries.append(f"bpy particle system emitter {action_primitive} effect spawn")

    if "movement" in detected_modules:
        api_queries.append(f"bpy object location keyframe {action_primitive} instant position")

    if "animation" in detected_modules:
        api_queries.append("bpy keyframe insert animation frame timing")

    # Always include scene object placement
    api_queries.append("bpy object add scene place character position")

    # ── 5. Build pattern queries (semantic, shot-level) ───────────────────────
    pattern_queries = []

    # Primary: full shot description
    pattern_queries.append(resolved)

    # Secondary: break into shot components
    if "camera" in detected_modules:
        shot_desc = next((w for w in ["handheld", "static", "wide", "close", "medium"] if w in brief_lower), "")
        pattern_queries.append(f"{shot_desc} camera shot setup")

    if "fx" in detected_modules or action_primitive in ["spawn", "ability"]:
        pattern_queries.append(f"fx particle {action_primitive} spawn effect")

    if len(registry) >= 2:
        pattern_queries.append("two character scene confrontation placement")

    return {
        "api_queries":      api_queries,
        "pattern_queries":  pattern_queries,
        "detected_modules": detected_modules,
        "action_primitive": action_primitive,
    }


# ── Retrieval ─────────────────────────────────────────────────────────────────

def _search(collection: str, query: str, top_k: int) -> list:
    client = _get_client()
    model  = _get_model()
    vec    = model.encode(query).tolist()
    return client.query_points(
        collection_name=collection,
        query=vec,
        limit=top_k,
    ).points


def retrieve_context(brief: str, registry: dict) -> dict:
    """
    Main retrieval function called by the pipeline per shot.

    Args:
        brief:    Raw shot brief string e.g. "C1 confronts V1 at BG2. Void Step, medium handheld."
        registry: ERAS entity registry dict

    Returns:
        {
            "api_chunks":       [{"module": str, "text": str, "score": float}],
            "pattern_scripts":  [{"filename": str, "shot_type": str, "script": str, "score": float}],
            "prompt_block":     str,   # formatted context ready to inject into Phi-4
            "detected_modules": [str],
            "action_primitive": str,
        }
    """
    decomposed = decompose_brief(brief, registry)

    # ── Retrieve API chunks ───────────────────────────────────────────────────
    seen_chunks = set()
    api_chunks  = []
    for query in decomposed["api_queries"]:
        results = _search(COLLECTION_API, query, API_TOP_K)
        for r in results:
            chunk_id = r.payload["chunk_id"]
            if chunk_id not in seen_chunks and r.score > 0.25:
                seen_chunks.add(chunk_id)
                api_chunks.append({
                    "module":  r.payload["module"],
                    "heading": r.payload["heading"],
                    "text":    r.payload["text"],
                    "score":   round(r.score, 3),
                })

    # Sort by score, keep top results
    api_chunks = sorted(api_chunks, key=lambda x: x["score"], reverse=True)[:6]

    # ── Retrieve pattern scripts ──────────────────────────────────────────────
    seen_patterns   = set()
    pattern_scripts = []
    for query in decomposed["pattern_queries"]:
        results = _search(COLLECTION_PATT, query, PATTERN_TOP_K)
        for r in results:
            fname = r.payload["filename"]
            if fname not in seen_patterns and r.score > 0.15:
                seen_patterns.add(fname)
                pattern_scripts.append({
                    "filename":  fname,
                    "shot_type": r.payload["shot_type"],
                    "script":    r.payload["script"],
                    "score":     round(r.score, 3),
                })

    pattern_scripts = sorted(pattern_scripts, key=lambda x: x["score"], reverse=True)[:2]

    # ── Build prompt block ────────────────────────────────────────────────────
    prompt_block = _build_prompt_block(brief, registry, api_chunks, pattern_scripts, decomposed)

    return {
        "api_chunks":       api_chunks,
        "pattern_scripts":  pattern_scripts,
        "prompt_block":     prompt_block,
        "detected_modules": decomposed["detected_modules"],
        "action_primitive": decomposed["action_primitive"],
    }


def _approx_tokens(text: str) -> int:
    return int(len(text.split()) / 0.75)


def _build_prompt_block(brief, registry, api_chunks, pattern_scripts, decomposed) -> str:
    """
    Assemble the final context block injected into Phi-4's prompt.
    Stays under MAX_CONTEXT_TOKENS.
    """
    lines = []

    # ── Registry aliases ──────────────────────────────────────────────────────
    lines.append("=== ENTITY REGISTRY ===")
    for alias, entry in registry.items():
        parts = [f"{alias}:"]
        for k, v in entry.items():
            if k != "alias":
                parts.append(f"{k}={v}")
        lines.append("  " + " ".join(parts))

    # ── Shot brief ────────────────────────────────────────────────────────────
    lines.append("\n=== SHOT BRIEF ===")
    lines.append(f"  {brief}")
    lines.append(f"  Action primitive: {decomposed['action_primitive']}")
    lines.append(f"  Relevant modules: {', '.join(decomposed['detected_modules'])}")

    # ── Pattern scripts (closest verified examples) ───────────────────────────
    lines.append("\n=== VERIFIED SCRIPT PATTERNS ===")
    token_budget = MAX_CONTEXT_TOKENS - _approx_tokens("\n".join(lines))

    for ps in pattern_scripts:
        header = f"-- {ps['filename']} (score={ps['score']}, type={ps['shot_type']}) --"
        # Truncate script to fit budget — first 800 chars gets the structure
        script_preview = ps["script"][:800]
        block = f"{header}\n{script_preview}\n"
        block_tokens = _approx_tokens(block)
        if token_budget - block_tokens > 200:
            lines.append(block)
            token_budget -= block_tokens

    # ── API reference chunks ──────────────────────────────────────────────────
    lines.append("=== BPY API REFERENCE ===")
    for chunk in api_chunks:
        header = f"-- {chunk['module']} (score={chunk['score']}) --"
        block  = f"{header}\n{chunk['text']}\n"
        block_tokens = _approx_tokens(block)
        if token_budget - block_tokens > 50:
            lines.append(block)
            token_budget -= block_tokens

    lines.append("=== END CONTEXT ===")
    return "\n".join(lines)


# ── Standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Simulate a registry snapshot
    TEST_REGISTRY = {
        "C1": {
            "alias": "C1", "name": "Kai", "type": "character",
            "appearance": "tall, red jacket, scar over left eye",
            "current_state": "injured left shoulder, emotionally guarded",
            "position": "foreground_left", "stance": "offensive",
        },
        "V1": {
            "alias": "V1", "name": "Reth", "type": "character",
            "appearance": "grey coat, mask, calm expression",
            "current_state": "undamaged, waiting",
            "position": "foreground_right", "stance": "defensive",
        },
        "BG2": {
            "alias": "BG2", "name": "Ruined courtyard", "type": "background",
            "lighting_mood": "dramatic",
        },
    }

    TEST_BRIEFS = [
        "C1 confronts V1 at BG2. C1 uses Void Step to close distance. Medium shot, handheld feel.",
        "Close shot of C1 face, dramatic lighting, dusk mood.",
        "V1 spawns three shadow clones at BG2. Wide shot, static camera.",
    ]

    print("=" * 60)
    print("ERAS Retrieval — Standalone Test")
    print("=" * 60)

    for brief in TEST_BRIEFS:
        print(f"\nBRIEF: {brief}")
        print("-" * 50)
        result = retrieve_context(brief, TEST_REGISTRY)
        print(f"Detected modules : {result['detected_modules']}")
        print(f"Action primitive : {result['action_primitive']}")
        print(f"API chunks       : {len(result['api_chunks'])} retrieved")
        for c in result['api_chunks']:
            print(f"  [{c['score']}] {c['module']} — {c['heading'][:50]}")
        print(f"Pattern scripts  : {len(result['pattern_scripts'])} retrieved")
        for p in result['pattern_scripts']:
            print(f"  [{p['score']}] {p['filename']} ({p['shot_type']})")
        print(f"\nPrompt block ({_approx_tokens(result['prompt_block'])} tokens):")
        print(result["prompt_block"][:600] + "...\n")