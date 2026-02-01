import ollama
import os
import re
import json

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "skills")

MODEL_BUILDER = "qwen2.5-coder:7b" 

def build_and_parse(task_description, original_prompt):
    """
    Uses Qwen to generate a new Python skill and extract arguments for it.
    """
    print(f"[Builder] Generating new skill for: {task_description}")
    
    os.makedirs(SKILLS_DIR, exist_ok=True)

    build_prompt = (
        f"Write a Python module that implements: {task_description}.\n"
        "Requirements:\n"
        "1. It MUST have an `execute(...)` function.\n"
        "2. The `execute` function MUST use EXPLICIT arguments with type hints (e.g., `def execute(filename: str, count: int)`).\n"
        "3. Do NOT use `**kwargs` or `*args`. Define every variable explicitly.\n"
        "4. It MUST be a valid Python file.\n"
        "5. Do NOT use any external libraries unless standard (os, sys, json, math) or 'ollama'.\n"
        "6. The FIRST line of the file MUST be a comment `# filename: <name_of_file>.py`.\n"
        "7. Output ONLY the code, no markdown backticks, no explanations."
    )

    messages = [
        {'role': 'system', 'content': 'You are a Python coding expert. Write clean, explicitly typed code.'},
        {'role': 'user', 'content': build_prompt}
    ]

    print(f"[Builder] Asking {MODEL_BUILDER} to write code...")
    try:
        response = ollama.chat(model=MODEL_BUILDER, messages=messages)
        content = response['message']['content']
    except Exception as e:
        print(f"[Builder] ❌ Model Generation Failed: {e}")
        return {}, "error.py"
    
    # Clean up content (strip markdown)
    clean_code = content.strip()
    if clean_code.startswith("```python"):
        clean_code = clean_code.replace("```python", "", 1)
    elif clean_code.startswith("```"):
         clean_code = clean_code.replace("```", "", 1)
    if clean_code.endswith("```"):
        clean_code = clean_code.rsplit("```", 1)[0]
    
    clean_code = clean_code.strip()

    # Extract filename
    filename_match = re.search(r"^#\s*filename:\s*([\w_]+\.py)", clean_code, re.IGNORECASE)
    if filename_match:
        filename = filename_match.group(1)
    else:
        filename = "generated_skill.py"
        print(f"[Builder] ⚠️ Warning: No filename comment found. Defaulting to {filename}")

    file_path = os.path.join(SKILLS_DIR, filename)
    
    with open(file_path, "w") as f:
        f.write(clean_code)
    
    print(f"[Builder] Saved skill to {file_path}")

    # Parse arguments
    # feed the code back to the model so it knows exactly what args `execute` ended up having.
    parse_prompt = (
        f"Analyze the code you just wrote.\n"
        f"Extract the arguments strictly required by the `execute` function from this user prompt: \"{original_prompt}\".\n"
        "Return the result as a valid JSON object `{\"arg_name\": value}`.\n"
        "Do NOT return markdown. Return ONLY JSON."
    )
    
    messages.append({'role': 'assistant', 'content': content})
    messages.append({'role': 'user', 'content': parse_prompt})

    print("[Builder] Parsing arguments...")
    try:
        response_parse = ollama.chat(model=MODEL_BUILDER, messages=messages)
        parse_content = response_parse['message']['content'].strip()
        
        # Clean up JSON markdown
        parse_content = parse_content.replace('```json', '').replace('```', '').strip()
        
        args = json.loads(parse_content)
    except json.JSONDecodeError:
        print(f"[Builder] ❌ Error parsing JSON arguments: {parse_content}")
        args = {}
    except Exception as e:
        print(f"[Builder] ❌ Error during parsing: {e}")
        args = {}

    return args, filename

def parse_only(tool_name, user_prompt):
    """
    Uses Qwen to extract arguments for an existing tool.
    """
    try:
        with open(os.path.join(SKILLS_DIR, f"{tool_name}.py"), 'r') as f:
            code = f.read()
    except FileNotFoundError:
        return {}

    messages = [
        {'role': 'system', 'content': 'You are a helper that extracts arguments from text for python functions.'},
        {'role': 'user', 'content': f"Here is the code for `{tool_name}`:\n\n{code}\n\nExtract arguments for `execute` from: \"{user_prompt}\". Return ONLY JSON."}
    ]
    
    try:
        response = ollama.chat(model=MODEL_BUILDER, messages=messages)
        content = response['message']['content'].strip()
        content = content.replace('```json', '').replace('```', '').strip()
        return json.loads(content)
    except:
        return {}