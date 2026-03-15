"""
core/executor.py — Skill Executor for K.I.T.E.

Looks up a skill by id from the registry, executes it either as a
local Python script or via an MCP server HTTP call, and returns the
result as a plain string.
"""

import importlib.util
import os
import sys
import json
import traceback
from pathlib import Path

import httpx

# ──────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PROJECT_ROOT / "skills"


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────
def _error_response(skill_id: str, message: str) -> dict:
    """Return a structured error dict conforming to the fallback spec."""
    return {
        "error": "true",
        "skill_id": skill_id,
        "message": message,
    }


def _lookup_skill(skill_id: str, skills_registry: list[dict]) -> dict | None:
    """Find a skill entry in the registry by its id."""
    for skill in skills_registry:
        if skill.get("id") == skill_id:
            return skill
    return None


# ──────────────────────────────────────────────
#  Local script execution
# ──────────────────────────────────────────────
def _run_local_skill(skill: dict, user_query: str) -> str:
    """
    Import and execute a local Python skill from the /skills directory.

    Convention: the skill module must expose a ``run(query: str) -> str``
    function.
    """
    skill_id: str = skill["id"]
    script_name = skill.get("script", f"{skill_id}.py")
    script_path = SKILLS_DIR / script_name

    if not script_path.exists():
        raise FileNotFoundError(
            f"Local skill script not found: {script_path}"
        )

    # Dynamically import the module
    spec = importlib.util.spec_from_file_location(
        f"skills.{skill_id}", str(script_path)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "run"):
        raise AttributeError(
            f"Skill script '{script_name}' does not expose a run(query) function."
        )

    result = module.run(user_query)
    return str(result)


# ──────────────────────────────────────────────
#  MCP server execution
# ──────────────────────────────────────────────
def _run_mcp_skill(skill: dict, user_query: str) -> str:
    """
    Call an MCP-compatible server over HTTP.

    Sends a JSON-RPC–style POST with the user query as tool input and
    returns the server's text response.
    """
    url: str = skill["mcp_server_url"]
    tool_name: str = skill.get("tool_name", skill["id"])

    payload = {
        "tool_name": tool_name,
        "input": {
            "query": user_query,
        },
    }

    response = httpx.post(
        url,
        json=payload,
        timeout=30.0,
    )
    response.raise_for_status()

    data = response.json()

    # The MCP server may return the result under a "result" key or as
    # the top-level body itself — handle both gracefully.
    if isinstance(data, dict) and "result" in data:
        return str(data["result"])
    return str(data)


# ──────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────
def execute_skill(
    skill_id: str,
    user_query: str,
    skills_registry: list[dict],
) -> str | dict:
    """
    Main entry-point for the executor.

    Parameters
    ----------
    skill_id : str
        The id of the skill to execute.
    user_query : str
        The natural-language query from the user.
    skills_registry : list[dict]
        The full skills registry (list of skill dicts).

    Returns
    -------
    str
        The plain-text result of the skill execution.
    dict
        A structured error dict if execution fails.
    """
    # 1. Look up the skill
    skill = _lookup_skill(skill_id, skills_registry)
    if skill is None:
        return _error_response(
            skill_id,
            f"Skill '{skill_id}' not found in the registry.",
        )

    try:
        mcp_url = skill.get("mcp_server_url")

        if mcp_url:
            # 2a. Remote MCP server call
            return _run_mcp_skill(skill, user_query)
        else:
            # 2b. Local Python script
            return _run_local_skill(skill, user_query)

    except FileNotFoundError as exc:
        return _error_response(skill_id, str(exc))
    except httpx.HTTPStatusError as exc:
        return _error_response(
            skill_id,
            f"MCP server returned HTTP {exc.response.status_code}: {exc.response.text}",
        )
    except httpx.RequestError as exc:
        return _error_response(
            skill_id,
            f"Failed to connect to MCP server at '{skill.get('mcp_server_url')}': {exc}",
        )
    except Exception as exc:
        return _error_response(
            skill_id,
            f"Unexpected error executing skill '{skill_id}': {traceback.format_exc()}",
        )


# ──────────────────────────────────────────────
#  __main__ test block
# ──────────────────────────────────────────────
if __name__ == "__main__":
    # --- Sample registry (mirrors registry/skills.json) ---
    sample_registry = [
        {
            "id": "filesystem",
            "name": "Filesystem Manager",
            "description": "Create, read, list, and delete files and folders.",
            "mcp_server_url": None,
            "script": "filesystem.py",
            "tool_name": "filesystem",
        },
        {
            "id": "web_search",
            "name": "Web Search",
            "description": "Search the web for information.",
            "mcp_server_url": "http://localhost:8001/mcp",
            "tool_name": "web_search",
        },
    ]

    print("=" * 60)
    print("  K.I.T.E. Executor — Test Run")
    print("=" * 60)

    # Test 1: Local skill (filesystem)
    print("\n[Test 1] Executing local skill 'filesystem'...")
    result = execute_skill("filesystem", "list files in the current directory", sample_registry)
    print(f"  Result: {result}")

    # Test 2: Unknown skill
    print("\n[Test 2] Executing unknown skill 'nonexistent'...")
    result = execute_skill("nonexistent", "do something", sample_registry)
    print(f"  Result: {json.dumps(result, indent=2)}")

    # Test 3: MCP skill (will fail without a running server — demonstrates error handling)
    print("\n[Test 3] Executing MCP skill 'web_search' (expects server at localhost:8001)...")
    result = execute_skill("web_search", "what is the weather today?", sample_registry)
    print(f"  Result: {result if isinstance(result, str) else json.dumps(result, indent=2)}")

    print("\n" + "=" * 60)
    print("  Tests complete.")
    print("=" * 60)
