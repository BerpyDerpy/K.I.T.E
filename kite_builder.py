import os
from pydantic import BaseModel, Field, field_validator
import re

from kite_model import model 

# SCHEMA
class MCPServerCode(BaseModel):
    filename: str = Field(..., description="The filename for the tool (e.g., 'network_tools.py')")
    tool_name: str = Field(..., description=" The name of the function decorated with @mcp.tool()")
    description: str = Field(..., description="A short description of what the tool does.")
    dependencies: list[str] = Field(..., description="List of pip packages required.")
    code: str = Field(..., description="The complete, runnable Python code.")

    @field_validator('code')
    @classmethod
    def clean_code_block(cls, v: str) -> str:
        # 1. Fix literal escaped newlines (turn string "\n" into actual newline)
        v = v.replace('\\n', '\n')
        
        # 2. Unescape double-escaped quotes if present
        v = v.replace('\\"', '"')

        # 3. Remove start/end quotes if the model wrapped the whole block
        # e.g. "import..." -> import...
        v = v.strip().strip('"').strip("'")
        
        # 4. Fix specific hallucination: Stray quote before decorators
        # Changes "@mcp.tool() to @mcp.tool()
        v = re.sub(r'^"@mcp', '@mcp', v, flags=re.MULTILINE)
        
        # 5. Fallback: If imports are messy (leading dots), clean them
        if not v.startswith("from") and not v.startswith("import"):
            match = re.search(r'(from\s+|import\s+)', v)
            if match:
                v = v[match.start():]

        return v

# BUILDER GENERATOR

def build_mcp_server(instructions: str):
    print(f"Builder Activated: {instructions}")
    
    # STAGE 1: Generate just the code (simple prompt)
    code_prompt = f"""You are writing a new MCP tool. Write Python code for: {instructions}

    Template:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("ToolName")

    @mcp.tool()
    def function_name(param: str) -> str:
        return result

    if __name__ == "__main__":
        mcp.run()

    Code:"""
    
    raw_code = model(code_prompt, max_tokens=1500)
    
    # Clean up repetition (cut at "if __name__" if it appears twice)
    parts = raw_code.split('if __name__')
    if len(parts) > 2:
        raw_code = parts[0] + 'if __name__' + parts[1]
    
    # Ensure ending
    if "mcp.run()" not in raw_code:
        raw_code += '\n\nif __name__ == "__main__":\n    mcp.run()'
    
    # STAGE 2: Extract metadata (simple schema, short output)
    metadata_prompt = f"""Code: {raw_code[:500]}

Give filename, tool_name, description, and dependencies as JSON:
{{"filename": "name.py", "tool_name": "function_name", "description": "Short description", "dependencies": ["pkg1"]}}"""
    
    metadata_json = model(metadata_prompt, output_type=MCPServerCode, max_tokens=200)
    metadata = MCPServerCode.model_validate_json(metadata_json)
    
    # Combine
    result = MCPServerCode(
        filename=metadata.filename,
        tool_name=metadata.tool_name,
        description=metadata.description,
        dependencies=metadata.dependencies,
        code=raw_code
    )
    
    # Save
    os.makedirs("skills", exist_ok=True)
    filepath = os.path.join("skills", result.filename)
    with open(filepath, "w") as f:
        clean = result.code.replace("```python", "").replace("```", "").strip()
        f.write(clean)
        
    print(f"{filepath}")
    print(f"{result.dependencies}")
    return result