import ollama
import os
import json
import glob

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "skills")
MODEL_ROUTER = "llama3.2:3b"

def get_available_tools():
    files = glob.glob(os.path.join(SKILLS_DIR, "*.py"))
    tools = []
    for f in files:
        basename = os.path.basename(f)
        if basename != "__init__.py":
            tools.append(basename.replace(".py", ""))
    return tools

def run_router(user_input):
    """
    Decides whether to use an existing tool or build a new one.
    """
    tools = get_available_tools()
    tools_list_str = ", ".join(tools) if tools else "None"

    print(f"[Router] Thinking... (Available tools: {tools_list_str})")

    messages = [
        {
            'role': 'system',
            'content': (
                "You are an intent classifier and router for an AI agent.\n"
                f"Available tools: [{tools_list_str}]\n"
                "Your job is to parse the User Input and return a JSON object.\n"
                "Rules:\n"
                "1. If the user asks for a task that can be done by an existing tool, return:\n"
                "   {\"action\": \"USE_TOOL\", \"tool\": \"<tool_name_without_py>\", \"args\": {<extracted_args>}}\n"
                "2. If the tool is MISSING or the request is new, return:\n"
                "   {\"action\": \"BUILD\", \"description\": \"<concise_task_description>\"}\n"
                "3. Return ONLY JSON. Do not output markdown or conversational text."
            )
        },
        {'role': 'user', 'content': user_input}
    ]

    try:
        response = ollama.chat(model=MODEL_ROUTER, messages=messages)
        content = response['message']['content'].strip()
        
        # Clean up common Llama formatting issues
        content = content.replace("```json", "").replace("```", "").strip()
        if not content.startswith("{"):
             # Sometimes Llama adds text before the JSON
             start_idx = content.find("{")
             if start_idx != -1:
                 content = content[start_idx:]
        if not content.endswith("}"):
             end_idx = content.rfind("}")
             if end_idx != -1:
                 content = content[:end_idx+1]

        data = json.loads(content)
        return data

    except json.JSONDecodeError:
        print(f"[Router] JSON Parse Error. Raw content: {content}")
        # Fail safe: Prompt user or default to build? 
        # For now, let's assume if it failed, it might be a build request if no tools exist
        if not tools:
            return {"action": "BUILD", "description": user_input}
        return {"error": "Failed to parse router response"}
    except Exception as e:
        print(f"[Router] Error: {e}")
        return {"error": str(e)}
