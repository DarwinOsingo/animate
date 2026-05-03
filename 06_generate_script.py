"""
ERAS Phase 1 — Script 6: Phi-4 bpy Script Generator
Takes a shot brief + registry, retrieves context via 05_retrieval.py,
calls Phi-4 via Ollama, returns a verified bpy Python script.

Requirements:
    ollama serve          (running in background)
    ollama pull phi4      (or whichever model you have)

Usage (standalone test):
    python 06_generate_script.py

Usage (imported by pipeline):
    from generate_script import generate_bpy_script
    result = generate_bpy_script(brief, registry, shot_alias)
"""

import requests
import re
import os
import sys
import subprocess
import tempfile

# Add parent dir so we can import retrieval
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from retrieval import retrieve_context, _approx_tokens

OLLAMA_URL   = "http://localhost:11434/api/generate"
MODEL        = "qwen3:4b"
BLENDER_BIN  = os.path.expanduser("~/blender51/blender")
TIMEOUT      = 300             # seconds to wait for model response


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert Blender 5.1 Python (bpy) script writer for the ERAS animation pipeline.

Your job: given a shot brief and context, write a complete, executable bpy Python script.

STRICT RULES:
1. Output ONLY valid Python code. No explanation, no markdown, no ```python fences.
2. The script must run headless: blender --background --python <script>
3. Always call clear_scene() first.
4. Always set render engine to 'BLENDER_EEVEE' (not BLENDER_EEVEE_NEXT).
5. Use ERAS alias conventions: CHAR_C1, CHAR_V1, LIGHT_key, CAM_main, FX_alias_type.
6. Tag every object with obj["eras_alias"] = "C1" and obj["eras_type"] = "character".
7. Use the verified script patterns in the context as structural templates.
8. Use the bpy API reference chunks in the context for correct function signatures.
9. Always end with a main() call and if __name__ == "__main__": main()
10. Print [ERAS] prefixed status lines so the pipeline can parse progress.

BLENDER 5.1 KNOWN CHANGES:
- Render engine: 'BLENDER_EEVEE' not 'BLENDER_EEVEE_NEXT'
- No action.fcurves — use keyframe_insert() then iterate action.fcurves after keys exist
- scene.eevee not scene.render.eevee
- mathutils imported separately: import mathutils"""


# ── Prompt builder ────────────────────────────────────────────────────────────

def build_prompt(brief: str, registry: dict, context_block: str, shot_alias: str) -> str:
    """Assemble the full user prompt sent to Phi-4."""
    registry_lines = []
    for alias, entry in registry.items():
        registry_lines.append(f"  {alias}: " + ", ".join(f"{k}={v}" for k, v in entry.items() if k != "alias"))

    return f"""SHOT: {shot_alias}
BRIEF: {brief}

REGISTRY:
{chr(10).join(registry_lines)}

CONTEXT:
{context_block}

Write a complete Blender 5.1 bpy Python script for this shot.
The script must execute headless without errors.
Use the verified patterns and API reference above.
Output only the Python code, nothing else."""


# ── Ollama call ───────────────────────────────────────────────────────────────

def call_phi4(prompt: str) -> str | None:
    """Call Phi-4 via Ollama. Returns raw model output or None on failure."""
    payload = {
        "model":  MODEL,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
            "num_ctx": 4096,
            "num_predict": 2048,
            "think": False,        # disable qwen3 thinking mode — much faster
        },
    }
    try:
        print(f"[ERAS] Calling {MODEL} via Ollama...")
        r = requests.post(OLLAMA_URL, json=payload, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json().get("response", "")
    except requests.exceptions.ConnectionError:
        print(f"[ERAS] ERROR: Cannot connect to Ollama at {OLLAMA_URL}")
        print("[ERAS] Make sure Ollama is running: ollama serve")
        return None
    except requests.exceptions.Timeout:
        print(f"[ERAS] ERROR: Phi-4 timed out after {TIMEOUT}s")
        return None
    except Exception as e:
        print(f"[ERAS] ERROR calling Ollama: {e}")
        return None


# ── Script extraction ─────────────────────────────────────────────────────────

def extract_script(raw_output: str) -> str:
    """
    Pull clean Python from model output.
    Handles cases where model wraps in ```python``` despite instructions.
    """
    if not raw_output:
        return ""

    # Strip markdown fences if present
    fenced = re.search(r"```(?:python)?\n(.*?)```", raw_output, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()

    # If output starts with import or def, it's already clean
    stripped = raw_output.strip()
    if stripped.startswith(("import ", "\"\"\"", "def ", "#")):
        return stripped

    # Find first import statement
    match = re.search(r"^(import |from )", raw_output, re.MULTILINE)
    if match:
        return raw_output[match.start():].strip()

    return stripped


# ── Headless validation ───────────────────────────────────────────────────────

def validate_headless(script: str, shot_alias: str) -> dict:
    """
    Run the generated script in Blender headless.
    Returns {"passed": bool, "output": str, "errors": str}
    """
    if not os.path.exists(BLENDER_BIN):
        print(f"[ERAS] WARNING: Blender not found at {BLENDER_BIN}")
        print("[ERAS] Skipping headless validation")
        return {"passed": False, "output": "", "errors": "Blender binary not found"}

    # Write script to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=f"_{shot_alias}.py",
        prefix="eras_validate_", delete=False
    ) as f:
        f.write(script)
        tmp_path = f.name

    try:
        print(f"[ERAS] Validating headless: {os.path.basename(tmp_path)}")
        result = subprocess.run(
            [BLENDER_BIN, "--background", "--python", tmp_path],
            capture_output=True, text=True, timeout=60,
        )
        passed = result.returncode == 0 and "Traceback" not in result.stdout
        return {
            "passed": passed,
            "output": result.stdout,
            "errors": result.stderr if not passed else "",
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
    """
    Full generation pipeline for one shot.

    Returns:
        {
            "shot_alias":  str,
            "script":      str,      # final bpy script
            "passed":      bool,     # headless validation result
            "attempts":    int,
            "context":     dict,     # retrieval result
            "validation":  dict,     # headless output
        }
    """
    print(f"\n{'='*60}")
    print(f"[ERAS] Generating script for: {shot_alias}")
    print(f"[ERAS] Brief: {brief}")
    print(f"{'='*60}")

    # ── Retrieve context ──────────────────────────────────────────────────────
    print("[ERAS] Retrieving context...")
    context = retrieve_context(brief, registry)
    print(f"[ERAS] Context: {len(context['api_chunks'])} API chunks, "
          f"{len(context['pattern_scripts'])} pattern scripts, "
          f"~{_approx_tokens(context['prompt_block'])} tokens")

    script   = ""
    passed   = False
    attempts = 0
    validation = {}

    for attempt in range(1, max_retries + 2):
        attempts = attempt
        print(f"\n[ERAS] Generation attempt {attempt}/{max_retries + 1}")

        # ── Build prompt ──────────────────────────────────────────────────────
        # On retry, append the error to help model self-correct
        extra = ""
        if attempt > 1 and validation.get("errors"):
            error_lines = validation["errors"][:500]
            extra = f"\n\nPREVIOUS ATTEMPT FAILED WITH:\n{error_lines}\nFix these errors in your new script."

        prompt = build_prompt(brief, registry, context["prompt_block"], shot_alias) + extra

        # ── Call Phi-4 ────────────────────────────────────────────────────────
        raw = call_phi4(prompt)
        if not raw:
            print(f"[ERAS] Model call failed on attempt {attempt}")
            continue

        script = extract_script(raw)
        if not script:
            print("[ERAS] Could not extract valid Python from model output")
            continue

        token_count = _approx_tokens(script)
        print(f"[ERAS] Script extracted — ~{token_count} tokens, {len(script.splitlines())} lines")

        # ── Validate ──────────────────────────────────────────────────────────
        if validate:
            validation = validate_headless(script, shot_alias)
            if validation["passed"]:
                print(f"[ERAS] ✓ Headless validation PASSED on attempt {attempt}")
                passed = True
                break
            else:
                print(f"[ERAS] ✗ Headless validation FAILED on attempt {attempt}")
                # Extract just the traceback for the retry prompt
                tb = re.search(r"Traceback.*", validation["output"], re.DOTALL)
                if tb:
                    validation["errors"] = tb.group(0)[:500]
                    print(f"[ERAS] Error: {validation['errors'][:200]}")
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

    TEST_BRIEF = "C1 confronts V1 at BG2. Medium shot, handheld feel, dramatic lighting."

    result = generate_bpy_script(
        brief=TEST_BRIEF,
        registry=TEST_REGISTRY,
        shot_alias="shot_test_01",
        validate=True,
        max_retries=2,
    )

    print(f"\n{'='*60}")
    print(f"[ERAS] Result: {'PASSED' if result['passed'] else 'FAILED'}")
    print(f"[ERAS] Attempts: {result['attempts']}")
    print(f"[ERAS] Script length: {len(result['script'].splitlines())} lines")
    print(f"{'='*60}")

    if result["script"]:
        out_path = f"./generated/{result['shot_alias']}.py"
        os.makedirs("./generated", exist_ok=True)
        with open(out_path, "w") as f:
            f.write(result["script"])
        print(f"[ERAS] Script saved to: {out_path}")

    if not result["passed"] and result["validation"].get("errors"):
        print(f"\n[ERAS] Final error:\n{result['validation']['errors'][:400]}")