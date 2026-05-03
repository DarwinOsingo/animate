"""
ERAS Phase 1 — Script 6 (Groq): bpy Script Generator via Groq API
Takes a shot brief + registry, retrieves context via retrieval.py,
calls Groq LLM, validates via Blender headless.

Setup:
    Create ~/animate/.env with:
        GROQ_API_KEY=gsk_your_key_here

Usage (standalone test):
    python 06_generate_script_groq.py

Usage (imported by pipeline):
    from generate_script_groq import generate_bpy_script
    result = generate_bpy_script(brief, registry, shot_alias)
"""

import os
import re
import sys
import subprocess
import tempfile
import requests

# Load .env manually — no python-dotenv needed
def load_env(path=".env"):
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()  # always override

load_env()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from retrieval import retrieve_context, _approx_tokens

# ── Config ────────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
MODEL        = "llama-3.3-70b-versatile"   # fast, great at code, free tier
BLENDER_BIN  = os.path.expanduser("~/blender51/blender")
TIMEOUT      = 60   # Groq is fast — 60s is generous


# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert Blender 5.1 Python (bpy) script writer for the ERAS animation pipeline.

Your job: given a shot brief and context, write a complete, executable bpy Python script.

STRICT RULES:
1. Output ONLY valid Python code. No explanation, no markdown, no ```python fences.
2. The script must run headless: blender --background --python <script>
3. Always call clear_scene() first.
4. Always set render engine to 'BLENDER_EEVEE' (not BLENDER_EEVEE_NEXT).
5. Use ERAS alias conventions: CHAR_C1, CHAR_V1, LIGHT_key, CAM_main, FX_alias_type.
6. Tag every object: obj["eras_alias"] = "C1" and obj["eras_type"] = "character".
7. Use the verified script patterns in the context as structural templates.
8. Use the bpy API reference chunks for correct function signatures.
9. Always end with main() call and if __name__ == "__main__": main()
10. Print [ERAS] prefixed status lines so the pipeline can parse progress.

BLENDER 5.1 KNOWN ISSUES — avoid these:
- Render engine: use 'BLENDER_EEVEE' not 'BLENDER_EEVEE_NEXT'
- No action.fcurves on new actions — insert keyframes first then iterate
- Handheld shake: use keyframe_insert() with random offsets per frame, not noise modifiers
- import mathutils separately when using Vector or Matrix
- scene.eevee for EEVEE settings, not scene.render.eevee"""


# ── Prompt builder ────────────────────────────────────────────────────────────
def build_prompt(brief: str, registry: dict, context_block: str, shot_alias: str, error: str = "") -> str:
    registry_lines = []
    for alias, entry in registry.items():
        registry_lines.append(
            f"  {alias}: " + ", ".join(f"{k}={v}" for k, v in entry.items() if k != "alias")
        )

    error_block = ""
    if error:
        error_block = f"\n\nPREVIOUS ATTEMPT FAILED:\n{error[:400]}\nFix these errors in your new script."

    return f"""SHOT: {shot_alias}
BRIEF: {brief}

REGISTRY:
{chr(10).join(registry_lines)}

CONTEXT:
{context_block}

Write a complete Blender 5.1 bpy Python script for this shot.
Must execute headless without errors.
Output only Python code, nothing else.{error_block}"""


# ── Groq API call ─────────────────────────────────────────────────────────────
def call_groq(prompt: str) -> str | None:
    if not GROQ_API_KEY:
        print("[ERAS] ERROR: GROQ_API_KEY not set in .env")
        return None

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens":  2048,
        "top_p":       0.9,
    }

    try:
        print(f"[ERAS] Calling {MODEL} via Groq...")
        r = requests.post(GROQ_URL, headers=headers, json=payload, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        print(f"[ERAS] ERROR: Groq timed out after {TIMEOUT}s")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"[ERAS] ERROR: Groq HTTP {r.status_code} — {r.text[:200]}")
        return None
    except Exception as e:
        print(f"[ERAS] ERROR calling Groq: {e}")
        return None


# ── Script extraction ─────────────────────────────────────────────────────────
def extract_script(raw: str) -> str:
    if not raw:
        return ""
    # Strip markdown fences
    fenced = re.search(r"```(?:python)?\n(.*?)```", raw, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    stripped = raw.strip()
    if stripped.startswith(("import ", '"""', "def ", "#")):
        return stripped
    match = re.search(r"^(import |from )", raw, re.MULTILINE)
    if match:
        return raw[match.start():].strip()
    return stripped


# ── Headless validation ───────────────────────────────────────────────────────
def validate_headless(script: str, shot_alias: str) -> dict:
    if not os.path.exists(BLENDER_BIN):
        print(f"[ERAS] WARNING: Blender not found at {BLENDER_BIN} — skipping validation")
        return {"passed": False, "output": "", "errors": "Blender binary not found"}

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=f"_{shot_alias}.py",
        prefix="eras_val_", delete=False
    ) as f:
        f.write(script)
        tmp_path = f.name

    try:
        print(f"[ERAS] Validating headless...")
        result = subprocess.run(
            [BLENDER_BIN, "--background", "--python", tmp_path],
            capture_output=True, text=True, timeout=60,
        )
        passed = result.returncode == 0 and "Traceback" not in result.stdout
        if passed:
            # Extract [ERAS] lines for clean progress reporting
            eras_lines = [l for l in result.stdout.splitlines() if "[ERAS]" in l]
            print("\n".join(eras_lines))
        return {
            "passed":  passed,
            "output":  result.stdout,
            "errors":  result.stderr if not passed else "",
        }
    except subprocess.TimeoutExpired:
        return {"passed": False, "output": "", "errors": "Blender headless timed out"}
    except Exception as e:
        return {"passed": False, "output": "", "errors": str(e)}
    finally:
        os.unlink(tmp_path)


# ── Main generation function ──────────────────────────────────────────────────
def generate_bpy_script(
    brief: str,
    registry: dict,
    shot_alias: str,
    validate: bool = True,
    max_retries: int = 2,
) -> dict:
    print(f"\n{'='*60}")
    print(f"[ERAS] Generating: {shot_alias}")
    print(f"[ERAS] Brief: {brief}")
    print(f"{'='*60}")

    # Retrieve context
    print("[ERAS] Retrieving context...")
    context = retrieve_context(brief, registry)
    print(f"[ERAS] Context: {len(context['api_chunks'])} API chunks, "
          f"{len(context['pattern_scripts'])} patterns, "
          f"~{_approx_tokens(context['prompt_block'])} tokens")

    script     = ""
    passed     = False
    attempts   = 0
    validation = {}
    error      = ""

    for attempt in range(1, max_retries + 2):
        attempts = attempt
        print(f"\n[ERAS] Attempt {attempt}/{max_retries + 1}")

        prompt = build_prompt(
            brief, registry, context["prompt_block"], shot_alias, error
        )

        raw = call_groq(prompt)
        if not raw:
            continue

        script = extract_script(raw)
        if not script:
            print("[ERAS] Could not extract Python from model output")
            continue

        lines = len(script.splitlines())
        print(f"[ERAS] Script: {lines} lines, ~{_approx_tokens(script)} tokens")

        if validate:
            validation = validate_headless(script, shot_alias)
            if validation["passed"]:
                print(f"[ERAS] ✓ PASSED on attempt {attempt}")
                passed = True
                break
            else:
                print(f"[ERAS] ✗ FAILED on attempt {attempt}")
                # Pull traceback for retry prompt
                tb = re.search(r"Traceback.*", validation["output"], re.DOTALL)
                error = tb.group(0)[:400] if tb else validation["errors"][:400]
                if error:
                    print(f"[ERAS] Error snippet: {error[:150]}")
        else:
            passed = True
            break

    return {
        "shot_alias": shot_alias,
        "script":     script,
        "passed":     passed,
        "attempts":   attempts,
        "context":    context,
        "validation": validation,
    }


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
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

    result = generate_bpy_script(
        brief="C1 confronts V1 at BG2. Medium shot, handheld feel, dramatic lighting.",
        registry=TEST_REGISTRY,
        shot_alias="shot_test_01",
        validate=True,
        max_retries=2,
    )

    print(f"\n{'='*60}")
    print(f"[ERAS] {'PASSED ✓' if result['passed'] else 'FAILED ✗'} — {result['attempts']} attempt(s)")
    print(f"{'='*60}")

    if result["script"]:
        out_dir = "./generated"
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{result['shot_alias']}.py")
        with open(out_path, "w") as f:
            f.write(result["script"])
        print(f"[ERAS] Script saved: {out_path}")

    if not result["passed"] and result.get("validation", {}).get("errors"):
        print(f"\n[ERAS] Final error:\n{result['validation']['errors'][:400]}")