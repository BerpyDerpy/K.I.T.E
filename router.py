import ollama
import os
import json
import glob

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "skills")
MODEL_ROUTER = "llama3.2:3b"

# Keywords that indicate a speech request
SPEECH_KEYWORDS = ['say', 'speak', 'talk', 'voice', 'pronounce', 'utter', 'verbalize', 'tell me']

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

    # Check if this is a speech request FIRST - handle it directly
    is_speech_request = any(keyword in user_input.lower() for keyword in SPEECH_KEYWORDS)
    
    if is_speech_request and 'speak' in tools:
        print(f"[Router] Detected speech request - routing to 'speak' tool")
        # Extract the text to speak from user input
        clean_text = user_input
        for kw in SPEECH_KEYWORDS:
            clean_text = clean_text.lower().replace(kw, '').strip()
        clean_text = clean_text.strip(' :.-')
        if not clean_text:
            clean_text = user_input
        return {
            "action": "USE_TOOL",
            "tool": "speak",
            "args": {"text": clean_text}
        }

    messages = [
        {
            'role': 'system',
            'content': (
                "You are an intent classifier and router for an AI agent.\n"
                f"Available tools: [{tools_list_str}]\n"
                "Your job is to parse the User Input and return a JSON object.\n"
                "CRITICAL RULES:\n"
                "1. If the user asks for a task that can be done by an existing tool, return:\n"
                "   {\"action\": \"USE_TOOL\", \"tool\": \"<tool_name>\", \"args\": {<extracted_args>}}\n"
                "2. If the tool is MISSING or the request is new, return:\n"
                "   {\"action\": \"BUILD\", \"description\": \"<concise_task_description>\"}\n"
                "3. Return ONLY valid JSON. No markdown, no explanations."
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
        
        # Validate the response format
        if "action" not in data:
            print(f"[Router] Missing 'action' in response: {data}")
            return {"error": "Missing action in router response"}
        
        # Ensure USE_TOOL has a tool name
        if data.get("action") == "USE_TOOL" and "tool" not in data:
            print(f"[Router] Missing 'tool' in USE_TOOL response: {data}")
            return {"error": "Missing tool in USE_TOOL response"}
        
        return data

    except json.JSONDecodeError:
        print(f"[Router] JSON Parse Error. Raw content: {content}")
        # Fail safe: If no tools, build. Otherwise, try to build.
        return {"action": "BUILD", "description": user_input}
    except Exception as e:
        print(f"[Router] Error: {e}")
        return {"error": str(e)}

