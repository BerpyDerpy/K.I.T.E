"""
core/router.py — Intent Router for K.I.T.E.

Receives a user query and a list of retrieved MCP skills, asks the
local Qwen model (via Ollama) whether it can handle the query inline
or needs to invoke a skill, and returns a validated routing decision.
"""

import json
import os

import ollama
from dotenv import load_dotenv

# ──────────────────────────────────────────────
#  Config
# ──────────────────────────────────────────────
load_dotenv()
MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b-instruct-q4_K_M")


# ──────────────────────────────────────────────
#  Prompt builder
# ──────────────────────────────────────────────
def _build_system_prompt(skills: list[dict]) -> str:
    """
    Build the system prompt that tells the model it is KITE,
    lists available skills, and enforces the JSON response schema.
    """
    skills_block = ""
    for s in skills:
        skills_block += (
            f"  - id: {s['id']}\n"
            f"    name: {s['name']}\n"
            f"    description: {s['description']}\n"
        )

    return f"""\
You are KITE, a local AI agent. You can answer questions directly OR delegate tasks to skills (tools).

IMPORTANT: You are a language model. You CANNOT perform real-world actions yourself.
Only set "can_handle" to true for pure knowledge questions, explanations, or conversation.
Any task that requires acting on the user's system (files, web access, running code, etc.) MUST be delegated to a skill. When in doubt, delegate.

Available skills:
{skills_block if skills_block else "  (none)"}

Respond ONLY with JSON matching this schema:
{{
  "can_handle": true/false,
  "skill_id": "<skill id or null>",
  "response": "<your answer if can_handle, otherwise a short note on why the skill is needed>",
  "reasoning": "<one-line explanation of your decision>"
}}

Rules:
- Output valid JSON only, no extra text.
- "skill_id" must be null when "can_handle" is true.
- "skill_id" must be one of the listed skill ids when "can_handle" is false.
"""


# ──────────────────────────────────────────────
#  Response validation
# ──────────────────────────────────────────────
REQUIRED_KEYS = {"can_handle", "skill_id", "response", "reasoning"}


def _validate(data: dict) -> dict:
    """
    Validate the parsed JSON against the expected schema.
    Raises ValueError on any mismatch.
    """
    missing = REQUIRED_KEYS - set(data.keys())
    if missing:
        raise ValueError(f"Missing keys: {missing}")

    if not isinstance(data["can_handle"], bool):
        raise ValueError(f"'can_handle' must be bool, got {type(data['can_handle']).__name__}")

    if data["can_handle"] and data["skill_id"] is not None:
        raise ValueError("'skill_id' should be null when 'can_handle' is true")

    if not data["can_handle"] and not data["skill_id"]:
        raise ValueError("'skill_id' must be set when 'can_handle' is false")

    return data


# ──────────────────────────────────────────────
#  Ollama call + retry
# ──────────────────────────────────────────────
def _call_ollama(system_prompt: str, user_message: str) -> dict:
    """
    Send the prompt to Ollama with format='json' and return the
    parsed dict.  Raises ValueError if the response isn't valid JSON.
    """
    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        format="json",
    )
    text = response["message"]["content"]
    return json.loads(text)


def _retry_with_correction(system_prompt: str, user_message: str, error: str) -> dict:
    """
    Retry the call with an explicit correction prompt appended.
    """
    correction = (
        f"Your previous response was invalid JSON or did not match the schema.\n"
        f"Error: {error}\n"
        f"Please respond again with ONLY a valid JSON object matching the schema."
    )
    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": "(invalid response)"},
            {"role": "user", "content": correction},
        ],
        format="json",
    )
    text = response["message"]["content"]
    return json.loads(text)


# ──────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────
def route(user_query: str, retrieved_skills: list[dict]) -> dict:
    """
    Route a user query.

    Parameters
    ----------
    user_query : str
        The natural-language query from the user.
    retrieved_skills : list[dict]
        Up to 5 skill dicts (each with at least id, name, description),
        already retrieved via semantic search.

    Returns
    -------
    dict
        A validated routing decision:
        {can_handle, skill_id, response, reasoning}
    """
    system_prompt = _build_system_prompt(retrieved_skills)

    # --- First attempt ---
    try:
        data = _call_ollama(system_prompt, user_query)
        return _validate(data)
    except (json.JSONDecodeError, ValueError) as first_error:
        print(f"  [router] First attempt failed: {first_error}")

    # --- Retry once ---
    try:
        data = _retry_with_correction(system_prompt, user_query, str(first_error))
        return _validate(data)
    except (json.JSONDecodeError, ValueError) as second_error:
        print(f"  [router] Retry also failed: {second_error}")
        # Return a safe fallback so the pipeline doesn't crash
        return {
            "can_handle": False,
            "skill_id": None,
            "response": "Router failed to produce a valid decision.",
            "reasoning": f"Parse errors: 1st={first_error}, 2nd={second_error}",
        }


# ──────────────────────────────────────────────
#  __main__ test block
# ──────────────────────────────────────────────
if __name__ == "__main__":
    # Sample retrieved skills (as if returned by the retriever)
    sample_skills = [
        {
            "id": "filesystem",
            "name": "Filesystem Manager",
            "description": "Create, read, list, and delete files and folders.",
        },
        {
            "id": "web_search",
            "name": "Web Search",
            "description": "Search the web for current information, news, and facts.",
        },
    ]

    test_queries = [
        # 1. Model can handle inline — general knowledge
        "What is the capital of France?",
        # 2. Needs a skill — file operation
        "Create a folder called 'projects' on my desktop",
        # 3. Ambiguous — could go either way
        "Find me some information about Python decorators",
    ]

    print("=" * 60)
    print("  K.I.T.E. Intent Router — Test Run")
    print(f"  Model: {MODEL}")
    print("=" * 60)

    for i, query in enumerate(test_queries, 1):
        print(f"\n{'─' * 60}")
        print(f"  Test {i}: \"{query}\"")
        print(f"{'─' * 60}")
        result = route(query, sample_skills)
        print(json.dumps(result, indent=2))

    print("\n" + "=" * 60)
    print("  Tests complete.")
    print("=" * 60)
