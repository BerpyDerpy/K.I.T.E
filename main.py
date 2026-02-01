import sys
import importlib
import traceback
import builder
from router import SemanticRouter

def load_and_run_skill(tool_name, args):
    try:
        module_name = f"skills.{tool_name}"
        if module_name in sys.modules:
            module = importlib.reload(sys.modules[module_name])
        else:
            module = importlib.import_module(module_name)
        
        if not hasattr(module, 'execute'):
            print(f"[Error] Skill {tool_name} missing execute().")
            return

        print(f"[System] Executing {tool_name} with args: {args}")
        result = module.execute(**args)
        
        if result is not None:
            print(f"[Output] {result}")

    except Exception as e:
        print(f"[Error] Execution failed: {e}")
        traceback.print_exc()


def main():
    print("--------------------------------------------------")
    print(" K.I.T.E: Kernel Integrated Task Engine")
    print(" Architecture: Semantic Router + Dynamic Builder")
    print("--------------------------------------------------")
    
    # Initialize Semantic Router (Loads index)
    kite_router = SemanticRouter()
    
    while True:
        try:
            print("\n")
            user_input = input("You: ").strip()
            if not user_input: continue
            if user_input.lower() in ["exit", "quit"]:
                break

            # Route
            decision = kite_router.route(user_input)
            
            #  Act
            if decision.action == "CHAT":
                print(f"[KITE] {decision.response}")

            elif decision.action == "BUILD":
                print(f"[System] Action: BUILD -> {decision.description}")
                description = decision.description or user_input
                
                # Build the new skill
                args, filename = builder.build_and_parse(description, user_input)
                tool_name = filename.replace(".py", "")
                
                # Refresh router index so it knows about the new tool next time
                kite_router.refresh_index()
                
                # Execute immediately
                load_and_run_skill(tool_name, args)

            elif decision.action == "USE_TOOL":
                print(f"[System] Action: USE_TOOL ({decision.tool_name})")
                
                # Failsafe: Use Builder parser if LLM dropped args
                if not decision.args:
                    print("[System] Args missing. Using Builder to extract...")
                    decision.args = builder.parse_only(decision.tool_name, user_input)
                
                load_and_run_skill(decision.tool_name, decision.args)

        except KeyboardInterrupt:
            print("\n[System] Exiting.")
            break
        except Exception as e:
            print(f"[Critial Error] {e}")
            traceback.print_exc()

if __name__ == "__main__":
    main()