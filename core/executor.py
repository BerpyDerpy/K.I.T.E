"""
core/executor.py — Skill Executor for K.I.T.E.

Uses the official MCP Python SDK to connect to skill servers.
- Local skills  → launched as a subprocess via stdio transport
- Remote skills → connected via SSE transport using the registry URL

The executor opens a ClientSession, discovers the first available tool,
calls it with the user_query, and returns the result as a plain string.
"""

import sys
import asyncio
import json
from pathlib import Path

# ─── MCP SDK imports ───────────────────────────
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.sse import sse_client

# ──────────────────────────────────────────────
#  Constants
# ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PROJECT_ROOT / "skills"


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────
def _error_response(skill_id: str, message: str) -> dict:
    """Return a structured error dict when something goes wrong."""
    return {
        "error": True,
        "skill_id": skill_id,
        "message": message,
    }


def _lookup_skill(skill_id: str, skills_registry: list[dict]) -> dict | None:
    """Find a skill entry in the registry by its id."""
    for skill in skills_registry:
        if skill.get("id") == skill_id:
            return skill
    return None


def _build_tool_arguments(tool, user_query: str) -> dict:
    """
    Inspect a tool's inputSchema to map user_query to the right parameter.

    Strategy:
      - Look at the tool's inputSchema for 'required' string fields.
      - Pass user_query as the value of the first required string param.
      - If no schema / no required fields, fall back to {"query": user_query}.
    """
    schema = getattr(tool, "inputSchema", None) or {}
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    # Find the first required string parameter
    for param_name in required:
        param_info = properties.get(param_name, {})
        if param_info.get("type", "string") == "string":
            return {param_name: user_query}

    # Fallback: if there's any property at all, use the first one
    if properties:
        first_param = list(properties.keys())[0]
        return {first_param: user_query}

    # Last resort
    return {"query": user_query}


# ──────────────────────────────────────────────
#  Transport helpers
# ──────────────────────────────────────────────
async def _call_via_stdio(skill: dict, user_query: str) -> str:
    """
    Launch a local skill script as a subprocess and talk to it
    over stdio using the MCP SDK.

    Steps:
      1. Build StdioServerParameters pointing at the skill script
      2. Open a stdio_client  → gives us (read_stream, write_stream)
      3. Create a ClientSession and initialize it
      4. List the tools the server exposes
      5. Call the *first* available tool with the user query
      6. Return the result text
    """
    skill_id = skill["id"]
    script_name = skill.get("script", f"{skill_id}.py")
    script_path = SKILLS_DIR / script_name

    if not script_path.exists():
        raise FileNotFoundError(f"Skill script not found: {script_path}")

    # Configure the subprocess command
    server_params = StdioServerParameters(
        command=sys.executable,            # e.g. "python3"
        args=[str(script_path)],           # run the skill file
    )

    # Connect via stdio transport
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Handshake with the MCP server
            await session.initialize()

            # Discover available tools
            tools_result = await session.list_tools()
            tools = tools_result.tools

            if not tools:
                raise RuntimeError(f"Skill '{skill_id}' exposes no tools.")

            # Pick the first tool and call it
            first_tool = tools[0]
            print(f"  ↳ Calling tool '{first_tool.name}' on skill '{skill_id}'")

            # Build arguments from the tool's schema
            arguments = _build_tool_arguments(first_tool, user_query)
            print(f"  ↳ Arguments: {arguments}")

            call_result = await session.call_tool(
                first_tool.name,
                arguments=arguments,
            )

            # Extract plain text from the result
            # call_result.content is a list of content blocks
            parts = []
            for block in call_result.content:
                if hasattr(block, "text"):
                    parts.append(block.text)
            return "\n".join(parts) if parts else str(call_result)


async def _call_via_sse(skill: dict, user_query: str) -> str:
    """
    Connect to a remote MCP server over SSE and call its first tool.

    Same flow as stdio, but uses sse_client for transport.
    """
    skill_id = skill["id"]
    url = skill["mcp_server_url"]

    # Connect via SSE transport
    async with sse_client(url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            tools = tools_result.tools

            if not tools:
                raise RuntimeError(f"Remote skill '{skill_id}' exposes no tools.")

            first_tool = tools[0]
            print(f"  ↳ Calling tool '{first_tool.name}' on remote skill '{skill_id}'")

            arguments = _build_tool_arguments(first_tool, user_query)
            print(f"  ↳ Arguments: {arguments}")

            call_result = await session.call_tool(
                first_tool.name,
                arguments=arguments,
            )

            parts = []
            for block in call_result.content:
                if hasattr(block, "text"):
                    parts.append(block.text)
            return "\n".join(parts) if parts else str(call_result)


# ──────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────
async def execute_skill(
    skill_id: str,
    user_query: str,
    skills_registry: list[dict],
) -> str | dict:
    """
    Main entry-point for the executor.

    Parameters
    ----------
    skill_id : str
        The id of the skill to execute (must match an entry in the registry).
    user_query : str
        The natural-language query from the user.
    skills_registry : list[dict]
        The full skills registry (list of skill dicts from skills.json).

    Returns
    -------
    str   — The plain-text result from the tool.
    dict  — A structured error dict if anything fails.
    """
    # Step 1: Look up the skill
    skill = _lookup_skill(skill_id, skills_registry)
    if skill is None:
        return _error_response(skill_id, f"Skill '{skill_id}' not found in registry.")

    try:
        # Step 2: Pick the right transport
        mcp_url = skill.get("mcp_server_url")

        if mcp_url:
            # Remote skill → SSE transport
            result = await _call_via_sse(skill, user_query)
        else:
            # Local skill → stdio transport (subprocess)
            result = await _call_via_stdio(skill, user_query)

        return result

    except Exception as exc:
        # Step 3: On any failure, return a structured error
        return _error_response(skill_id, f"{type(exc).__name__}: {exc}")


# ──────────────────────────────────────────────
#  __main__ test block
# ──────────────────────────────────────────────
if __name__ == "__main__":
    """
    Smoke-tests using the REAL skills.json registry.

    Tests:
      1. file_reader   — real tool, reads ./README.md via stdio
      2. datetime_utils — stub tool, returns "not yet implemented"
      3. system_info    — stub tool, returns "not yet implemented"
      4. nonexistent    — unknown skill, should return error dict
      5. web_fetcher    — has mcp_server_url, will try SSE (fails gracefully)
    """

    # ─── Load the real registry ────────────────
    import os
    registry_path = PROJECT_ROOT / "registry" / "skills.json"
    with open(registry_path, "r") as f:
        skills_registry = json.load(f)

    print(f"  Loaded {len(skills_registry)} skills from {registry_path.name}")

    # ─── Helper to run one test ────────────────
    async def run_test(label: str, skill_id: str, query: str):
        """Run a single test case and print the result."""
        print(f"\n{'─' * 60}")
        print(f"  {label}")
        print(f"  skill_id  = {skill_id}")
        print(f"  query     = {query}")
        print(f"{'─' * 60}")

        result = await execute_skill(skill_id, query, skills_registry)

        if isinstance(result, dict):
            # Error response
            print(f"  ❌ Error: {json.dumps(result, indent=4)}")
        else:
            # Success
            print(f"  ✅ Result ({type(result).__name__}):")
            # Indent the output for readability
            for line in str(result).splitlines():
                print(f"     {line}")

    # ─── Run all tests ─────────────────────────
    async def main():
        print("=" * 60)
        print("  K.I.T.E. Executor — Full Registry Test")
        print("=" * 60)

        # Test 1: Real filesystem skill (stdio transport)
        # filesystem.py exposes read_file, write_file, list_directory
        # The executor picks the first tool (read_file) and maps
        # user_query → {"path": "./README.md"}
        await run_test(
            label="Test 1: file_reader (real tool, stdio)",
            skill_id="file_reader",
            query="./README.md",
        )

        # Test 2: Stub skill — datetime_utils (stdio transport)
        # The stub has a zero-argument tool, so _build_tool_arguments
        # will pass an empty-ish dict — the stub ignores args anyway.
        await run_test(
            label="Test 2: datetime_utils (stub, stdio)",
            skill_id="datetime_utils",
            query="what time is it?",
        )

        # Test 3: Stub skill — system_info (stdio transport)
        await run_test(
            label="Test 3: system_info (stub, stdio)",
            skill_id="system_info",
            query="how much disk space is left?",
        )

        # Test 4: Unknown skill — should return error dict
        await run_test(
            label="Test 4: nonexistent (error case)",
            skill_id="nonexistent",
            query="do something impossible",
        )

        # Test 5: Remote skill — web_fetcher has mcp_server_url set
        # No server is running, so SSE connect will fail gracefully
        await run_test(
            label="Test 5: web_fetcher (SSE, expected to fail)",
            skill_id="web_fetcher",
            query="https://example.com",
        )

        print("\n" + "=" * 60)
        print("  All tests complete.")
        print("=" * 60)

    asyncio.run(main())
