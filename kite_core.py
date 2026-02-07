from typing import Optional, Dict
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from kite_builder import build_mcp_server

# CONFIGURATION

from kite_model import model

# DEFINE SCHEMA

class ToolType(str, Enum):
    MCP_EXISTING = "use_mcp_tool"
    BUILD_NEW = "build_new_tool"
    CONVERSATIONAL = "chat"



class RouterResponse(BaseModel):
    thinking_process: str = Field(..., description="Brief reasoning about what the user wants.")
    decision: ToolType
    # We keep it optional for the schema, but enforce it via logic/prompting
    tool_name: Optional[str] = Field(None, description="REQUIRED if decision is 'use_mcp_tool'. The exact name of the tool.")
    parameters: Dict = Field(default_factory=dict, description="Arguments for the tool.")
    builder_instructions: Optional[str] = Field(None, description="REQUIRED if decision is 'build_new_tool'. Detailed technical spec for the code generator.")

    @model_validator(mode='after')
    def check_consistency(self):
        # This validator ensures the model logic is sound
        if self.decision == ToolType.BUILD_NEW and not self.builder_instructions:
            # If the model failed to generate instructions,
            #  we populate it from thinking_process if empty
            self.builder_instructions = f"Build a tool to satisfy: {self.thinking_process}"
        return self

# GENERATOR FUNCTION

def route_request(user_prompt: str, available_tools_context: str) -> RouterResponse:
    system_prompt = f"""You are KITE, an intelligent kernel agent.
    
    available_tools_context:
    {available_tools_context}
    
    INSTRUCTIONS:
    1. Check if the user's request can be fulfilled by a tool in the 'available_tools_context' list.
    2. If YES, select 'use_mcp_tool', output the tool_name exactly as listed, and generate arguments.
    3. If NO suitable tool exists in the list, you MUST select 'build_new_tool'.
    4. If the user is just chatting, select 'chat'.
    
    CRITICAL RULES:
    - NEVER invent tool names. Only use tools explicitly listed in 'available_tools_context'.
    - If the tool is missing, use 'build_new_tool'. Do NOT try to use 'mcp' or 'python' as a tool name.
    """
    
    prompt = f"{system_prompt}\n\nUser: {user_prompt}\nResponse:"
    
    #  Generate the raw JSON string using the schema constraint
    raw_json_string = model(prompt, output_type=RouterResponse, max_tokens=1000)
    print(f"DEBUG RAW OUTPUT: {raw_json_string}")

    # 3. Manually parse the string into the Pydantic object
    response_obj = RouterResponse.model_validate_json(raw_json_string) # turms json string back into pydantic object
    
    return response_obj


async def execute_new_skill(script_path: str, tool_name: str, args: dict):
    #  Define how to run the script
    server_params = StdioServerParameters(
        command="python3",
        args=[script_path], #  "skills/nmap_scanner.py"
    )

    # Connect and Execute
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=args)
            return result

        
# TEST RUN

if __name__ == "__main__":
    mock_db_context = "- 'weather_lookup': Gets current weather for a city."
    
    print("KITE System Ready. Type 'exit' to quit.")
    
    while True:
        try:
            user_input = input("\nUser: ")
            if user_input.lower() in ['exit', 'quit']:
                print("Goodbye!")
                break
                
            # 1. Router decides what to do
            response = route_request(user_input, mock_db_context)
            
            print(f"Thinking: {response.thinking_process}")
            print(f"Decision: {response.decision.value}")
            
            # Handle Existing Tool
            if response.decision == ToolType.MCP_EXISTING:
                print(f"Action: Calling Existing Tool '{response.tool_name}'")
                print(f"Params: {response.parameters}")
                
            # Handle New Build
            elif response.decision == ToolType.BUILD_NEW:
                print(f"Tool missing. Initiating Builder Protocol...")
                
                if response.builder_instructions:
                    print(f"Instructions: {response.builder_instructions}")
                    
                    # CALL BUILDER
                    tool_result = build_mcp_server(response.builder_instructions)
                    
                    print(f"SUCCESS: Tool built at 'skills/{tool_result.filename}'")
                    print(f"Tool Name: {tool_result.tool_name}")
                    
                    # Update Context
                    new_tool_desc = f"- '{tool_result.tool_name}': {tool_result.description} (File: {tool_result.filename})"
                    mock_db_context += f"\n{new_tool_desc}"
                    
                    print(f"   Context updated. Re-attempting task with new tool...")
                    
                    # RECURSIVE CALL (One-level depth for now)
                    # We simply loop back? No, let's just call route_request again right here
                    retry_response = route_request(user_input, mock_db_context)
                    
                    if retry_response.decision == ToolType.MCP_EXISTING:
                         print(f"Action: Calling New Tool '{retry_response.tool_name}'")
                         # Actually Execute
                         try:
                             import asyncio
                             skill_path = f"skills/{tool_result.filename}"
                             # We need to run the async function in this sync loop.
                             # For simplicity in this script, we'll just print.
                             print(f"EXECUTION: Running {skill_path} with {retry_response.parameters}")
                             # asyncio.run(execute_new_skill(skill_path, retry_response.tool_name, retry_response.parameters))
                         except Exception as e:
                             print(f"Execution Error: {e}")

                else:
                    print("❌ Error: Router decided to build but provided no instructions.")
                    
            # Handle Conversational
            elif response.decision == ToolType.CONVERSATIONAL:
                print(f"KITE: {response.thinking_process}") # Or just respond naturally
                
        except Exception as e:
            print(f"Error processing request: {e}")

"""
--> dynamic input
--> nomic-embed-text:latest
--> audio i/o
--> new skill verification loop

improvements:
--> better execution Engine
--> UI
--> faster runtime
--> dynamic personalization
--> better error handling
"""