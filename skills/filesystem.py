"""
skills/filesystem.py — Local filesystem skill for K.I.T.E.

Exposes a ``run(query)`` function that performs basic filesystem
operations based on the user's natural-language query.
"""

import os
from pathlib import Path


def run(query: str) -> str:
    """
    Execute a filesystem operation based on the user query.

    Supported intents (keyword-matched for simplicity):
      • list / ls          → list files in cwd
      • read <path>        → read a file's contents
      • create <path>      → create an empty file
      • mkdir <path>       → create a directory
      • delete / rm <path> → delete a file
    """
    query_lower = query.lower().strip()
    tokens = query.split()

    # ── List files ────────────────────────────
    if any(kw in query_lower for kw in ("list", "ls", "dir")):
        target = "."
        # Try to extract a path after the keyword
        for i, tok in enumerate(tokens):
            if tok.lower() in ("list", "ls", "dir") and i + 1 < len(tokens):
                candidate = tokens[i + 1]
                if os.path.isdir(candidate):
                    target = candidate
                break
        entries = os.listdir(target)
        return "\n".join(entries) if entries else "(empty directory)"

    # ── Read file ─────────────────────────────
    if "read" in query_lower:
        for tok in tokens:
            if os.path.isfile(tok):
                return Path(tok).read_text(encoding="utf-8")
        return "Error: Could not identify a valid file path to read."

    # ── Create file ───────────────────────────
    if "create" in query_lower or "touch" in query_lower:
        for tok in tokens:
            if tok.lower() not in ("create", "touch", "file", "a", "an", "the"):
                Path(tok).touch()
                return f"Created file: {tok}"
        return "Error: No filename provided."

    # ── Make directory ────────────────────────
    if "mkdir" in query_lower:
        for tok in tokens:
            if tok.lower() != "mkdir":
                os.makedirs(tok, exist_ok=True)
                return f"Created directory: {tok}"
        return "Error: No directory name provided."

    # ── Delete file ───────────────────────────
    if any(kw in query_lower for kw in ("delete", "rm", "remove")):
        for tok in tokens:
            if os.path.isfile(tok):
                os.remove(tok)
                return f"Deleted file: {tok}"
        return "Error: Could not identify a valid file to delete."

    return f"Filesystem skill could not understand the query: '{query}'"
