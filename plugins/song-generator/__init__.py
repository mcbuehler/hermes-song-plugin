"""
song-generator plugin - a single, narrowly-scoped tool that runs the
HeartMuLa song generation script and nothing else.

Security model:
- No shell=True anywhere; argv is a fixed list, user input only ever
  fills specific list *elements*, never gets concatenated into a
  command string.
- lyrics/tags are written to their own temp files under a private
  temp dir, never interpreted, never passed through a shell.
- The heartlib path, venv path, and script path are all fixed at
  config time (env vars below) - the model cannot change them.
- Output is confined to a fixed songs directory; filenames are
  sanitized and never taken verbatim from model input.
"""

import json
import os
import re
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

# --- Fixed, operator-controlled paths (set these once for your machine) ---
# Override via environment if you don't want to hardcode paths in the plugin.
HEARTLIB_DIR = Path(os.environ.get("HEARTMULA_HEARTLIB_DIR", "/home/buehlmar/data/local/projects/playground/heartlib"))
VENV_PYTHON = Path(os.environ.get("HEARTMULA_VENV_PYTHON", str(HEARTLIB_DIR / ".venv" / "bin" / "python")))
GEN_SCRIPT = HEARTLIB_DIR / "examples" / "run_music_generation.py"
MODEL_PATH = Path(os.environ.get("HEARTMULA_MODEL_PATH", str(HEARTLIB_DIR / "ckpt")))
MODEL_VERSION = os.environ.get("HEARTMULA_MODEL_VERSION", "3B")
OUTPUT_DIR = Path(os.environ.get("HEARTMULA_OUTPUT_DIR", str(HEARTLIB_DIR / "assets" / "generated")))
MAX_AUDIO_MS = int(os.environ.get("HEARTMULA_MAX_AUDIO_MS", "240000"))  # 4 min default
GEN_TIMEOUT_S = int(os.environ.get("HEARTMULA_GEN_TIMEOUT_S", "900"))   # 15 min hard cap
LAZY_LOAD = os.environ.get("HEARTMULA_LAZY_LOAD", "false")

# Basic sanity limits so nobody can DoS the GPU box via giant inputs.
MAX_LYRICS_CHARS = 6000
MAX_TAGS_CHARS = 300
TAG_ALLOWED = re.compile(r"^[a-zA-Z0-9\-\s,]+$")


def register(ctx):
    schema = {
        "name": "generate_song",
        "description": (
            "Generate a full song (audio) from lyrics and style tags using a "
            "local HeartMuLa install. This is the ONLY action available on this "
            "bot - it cannot run other commands, browse files, or access the "
            "network. Returns the path to the generated MP3."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lyrics": {
                    "type": "string",
                    "description": (
                        "Song lyrics with bracketed structure tags, e.g. "
                        "[Intro] [Verse] ... [Chorus] ... [Bridge] [Outro]."
                    ),
                },
                "tags": {
                    "type": "string",
                    "description": (
                        "Comma-separated style tags, no spaces preferred, e.g. "
                        "'piano,happy,wedding,synthesizer,romantic'."
                    ),
                },
            },
            "required": ["lyrics", "tags"],
        },
    }

    def handle_generate_song(params, **kwargs):
        del kwargs
        lyrics = (params.get("lyrics") or "").strip()
        tags = (params.get("tags") or "").strip()

        # --- Validate inputs before touching the filesystem/subprocess ---
        if not lyrics:
            return json.dumps({"success": False, "error": "lyrics is required"})
        if not tags:
            return json.dumps({"success": False, "error": "tags is required"})
        if len(lyrics) > MAX_LYRICS_CHARS:
            return json.dumps({
                "success": False,
                "error": f"lyrics too long ({len(lyrics)} chars, max {MAX_LYRICS_CHARS})",
            })
        if len(tags) > MAX_TAGS_CHARS:
            return json.dumps({
                "success": False,
                "error": f"tags too long ({len(tags)} chars, max {MAX_TAGS_CHARS})",
            })
        if not TAG_ALLOWED.match(tags):
            return json.dumps({
                "success": False,
                "error": "tags may only contain letters, numbers, spaces, hyphens, and commas",
            })

        if not GEN_SCRIPT.exists():
            return json.dumps({
                "success": False,
                "error": f"generation script not found at {GEN_SCRIPT} - check HeartMuLa install",
            })
        if not VENV_PYTHON.exists():
            return json.dumps({
                "success": False,
                "error": f"venv python not found at {VENV_PYTHON} - check HeartMuLa venv",
            })

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # --- Write lyrics/tags to private temp files (never shell-interpreted) ---
        job_id = uuid.uuid4().hex[:10]
        with tempfile.TemporaryDirectory(prefix=f"song-{job_id}-") as tmpdir:
            tmp = Path(tmpdir)
            lyrics_path = tmp / "lyrics.txt"
            tags_path = tmp / "tags.txt"
            lyrics_path.write_text(lyrics, encoding="utf-8")
            tags_path.write_text(tags, encoding="utf-8")

            out_name = f"song_{int(time.time())}_{job_id}.mp3"
            out_path = OUTPUT_DIR / out_name

            # Fixed argv - no string concatenation, no shell=True.
            argv = [
                str(VENV_PYTHON),
                str(GEN_SCRIPT),
                f"--model_path={MODEL_PATH}",
                f"--version={MODEL_VERSION}",
                f"--lyrics={lyrics_path}",
                f"--tags={tags_path}",
                f"--save_path={out_path}",
                f"--lazy_load={LAZY_LOAD}",
                f"--max_audio_length_ms={MAX_AUDIO_MS}",
            ]

            try:
                proc = subprocess.run(
                    argv,
                    cwd=str(HEARTLIB_DIR),
                    capture_output=True,
                    text=True,
                    timeout=GEN_TIMEOUT_S,
                    shell=False,
                )
            except subprocess.TimeoutExpired:
                return json.dumps({
                    "success": False,
                    "error": f"generation timed out after {GEN_TIMEOUT_S}s",
                })

            if proc.returncode != 0 or not out_path.exists():
                # Truncate to avoid dumping huge tracebacks back into chat.
                tail = (proc.stderr or "")[-2000:]
                return json.dumps({
                    "success": False,
                    "error": "generation failed",
                    "returncode": proc.returncode,
                    "stderr_tail": tail,
                })

        return json.dumps({
            "success": True,
            "file_path": str(out_path),
            "message": f"Song generated: {out_path.name}",
        })

    ctx.register_tool(
        name="generate_song",
        toolset="song_generator",
        schema=schema,
        handler=handle_generate_song,
    )
