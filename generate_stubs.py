import json
import os

with open('registry/skills.json', 'r') as f:
    skills = json.load(f)

# Skip the ones handled by filesystem.py
handled_ids = {'file_reader', 'file_writer', 'directory_manager'}
remaining_skills = [s for s in skills if s['id'] not in handled_ids]

os.makedirs('.skills', exist_ok=True)

for skill in remaining_skills:
    skill_id = skill['id']
    skill_name = skill['name']
    
    code = f'''from mcp.server.fastmcp import FastMCP

mcp = FastMCP("{skill_name}")

@mcp.tool(name="{skill_id}")
def {skill_id}() -> str:
    """Stub tool for {skill_name}"""
    return "Stub: {skill_name} not yet implemented"

if __name__ == "__main__":
    mcp.run()
'''
    with open(f'.skills/{skill_id}.py', 'w') as f:
        f.write(code)

print(f"Re-generated {len(remaining_skills)} stubs in .skills/ with strict tool names")
