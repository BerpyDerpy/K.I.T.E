# filename: router.py
import os
import sys
import json
import inspect
import importlib
import numpy as np
import ollama
from pydantic import BaseModel, Field, ValidationError
from typing import Literal, Optional, Dict, Any, List

# Configuration
EMBED_MODEL = "nomic-embed-text" 
ROUTER_MODEL = "qwen2.5-coder:7b"      

class RouterDecision(BaseModel):
    action: Literal["USE_TOOL", "BUILD", "CHAT"] = Field(
        ..., description="The action to take."
    )
    tool_name: Optional[str] = Field(
        None, description="The EXACT name of the tool to use if action is USE_TOOL."
    )
    args: Dict[str, Any] = Field(
        default_factory=dict, description="Arguments strictly matching the tool's signature."
    )
    response: Optional[str] = Field(
        None, description="The chat response if action is CHAT."
    )
    description: Optional[str] = Field(
        None, description="Precise description of code to write if action is BUILD."
    )

class SemanticRouter:
    def __init__(self, skills_dir="skills"):
        self.skills_dir = skills_dir
        self.tools_map = {}   # {name: signature_str}
        self.tool_names = []  # List[str]
        self.embeddings = None # Matrix (N, 768)
        
        # Initialize index
        self.refresh_index()

    def _get_embedding(self, text):
        """Generates vector embedding for text using Ollama."""
        try:
            response = ollama.embeddings(model=EMBED_MODEL, prompt=text)
            return response["embedding"]
        except Exception as e:
            print(f"[Router] ⚠️ Embedding failed: {e}. Is 'nomic-embed-text' pulled?")
            return [0.0] * 768 # Fallback empty vector

    def refresh_index(self):
        """Scans skills directory and builds vector index."""
        if not os.path.exists(self.skills_dir):
            os.makedirs(self.skills_dir)
            
        print("[Router] Indexing skills...")
        self.tools_map = {}
        self.tool_names = []
        vectors = []

        sys.path.append(os.path.abspath(self.skills_dir))

        for f in os.listdir(self.skills_dir):
            if f.endswith(".py") and f != "__init__.py":
                module_name = f[:-3]
                try:
                    module = importlib.import_module(f"skills.{module_name}")
                    importlib.reload(module)
                    
                    if hasattr(module, 'execute'):
                        # Extract signature and docstring for context
                        sig = inspect.signature(module.execute)
                        doc = inspect.getdoc(module.execute) or "No description."
                        signature_str = f"{module_name}.execute{sig} - {doc}"
                        
                        self.tools_map[module_name] = signature_str
                        self.tool_names.append(module_name)
                        
                        # Embed the signature + docstring
                        vectors.append(self._get_embedding(signature_str))
                except Exception as e:
                    print(f"[Router] Warning: Skipping {module_name}: {e}")

        if vectors:
            self.embeddings = np.array(vectors)
            print(f"[Router] Indexed {len(self.tool_names)} skills.")
        else:
            self.embeddings = None
            print("[Router] No skills found. Ready to build.")

    def find_top_k_tools(self, query, k=3):
        """Returns the top K most relevant tools using cosine similarity."""
        if self.embeddings is None or len(self.tools_map) == 0:
            return {}

        query_vec = np.array(self._get_embedding(query))
        
        # Cosine similarity: (A . B) / (||A|| * ||B||)
        scores = np.dot(self.embeddings, query_vec)
        
        # Get top k indices
        top_k_indices = np.argsort(scores)[-k:][::-1]
        
        relevant_tools = {}
        for idx in top_k_indices:
            name = self.tool_names[idx]
            relevant_tools[name] = self.tools_map[name]
            
        return relevant_tools

    def route(self, user_prompt):
        # Retrieve Context (RAG for Tools)
        relevant_tools = self.find_top_k_tools(user_prompt)
        
        # Construct System Prompt
        tools_json = json.dumps(relevant_tools, indent=2)
        
        system_prompt = f"""
        You are K.I.T.E, an intelligent operating system.
        
        RELEVANT TOOLS:
        {tools_json}
        
        INSTRUCTIONS:
        1. ANALYZE the user's request.
        2. DECIDE:
           - "USE_TOOL": ONLY if a tool in RELEVANT TOOLS matches EXACTLY.
           - "BUILD": If NO tool matches, or if the relevant tools are insufficient.
           - "CHAT": If the user is just saying hello or asking a general question.
        3. OUTPUT JSON adhering to this schema:
           {{
             "action": "USE_TOOL" | "BUILD" | "CHAT",
             "tool_name": "exact_tool_name" (only for USE_TOOL),
             "args": {{ "arg": value }} (only for USE_TOOL),
             "description": "what to build" (only for BUILD),
             "response": "chat message" (only for CHAT)
           }}
        """

        #  Call LLM
        print(f"[Router] Thinking... (Context: {len(relevant_tools)}/{len(self.tools_map)} tools)")
        try:
            response = ollama.chat(
                model=ROUTER_MODEL, 
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ], 
                format="json" 
            )
            content = response['message']['content']
            
            # Validate & Parse with Pydantic
            decision_data = json.loads(content)
            decision = RouterDecision(**decision_data)

            # GUARDRAIL:
            # If the LLM chose USE_TOOL, check if the tool actually exists.
            if decision.action == "USE_TOOL":
                # Check if the tool_name is in the loaded skills map
                if decision.tool_name not in self.tools_map:
                    print(f"[Router] 🛡️ Guardrail triggered: '{decision.tool_name}' does not exist. Switching to BUILD.")
                    
                    # Force switch to BUILD action
                    decision.action = "BUILD"
                    decision.description = f"Create a tool to handle: {user_prompt}"
                    decision.tool_name = None
                    decision.args = {}
            # -------------------------------------------

            return decision

        except json.JSONDecodeError:
            print(f"[Router] ❌ JSON Error: {content}")
            return RouterDecision(action="CHAT", response="Internal Error: Router output invalid JSON.")
        except ValidationError as ve:
            print(f"[Router] ❌ Schema Validation Error: {ve}")
            return RouterDecision(action="CHAT", response="Internal Error: Router violated schema.")