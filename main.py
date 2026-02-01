import router
import builder
import sys
import os
import importlib
import traceback
from utils.tts import get_tts, speak, stop

# Speech mode toggle
speech_enabled = False

def toggle_speech():
    """Toggle speech mode on/off."""
    global speech_enabled
    speech_enabled = not speech_enabled
    tts = get_tts()
    if speech_enabled:
        tts.start()
        print("[System] Speech enabled - Jarvis will speak responses")
    else:
        print("[System] Speech disabled")
    return speech_enabled

def speak_response(text: str):
    """Speak the model response if speech is enabled."""
    if speech_enabled and text:
        speak(text)

def load_and_run_skill(tool_name, args):
    try:
        module_name = f"skills.{tool_name}"
        if module_name in sys.modules:
            print(f"[System] Reloading module {module_name}...")
            module = importlib.reload(sys.modules[module_name])
        else:
            print(f"[System] Loading module {module_name}...")
            module = importlib.import_module(module_name)
        
        if not hasattr(module, 'execute'):
            print(f"[Error] Skill {tool_name} does not have an execute() function.")
            return

        print(f"[System] Executing {tool_name} with args: {args}")
        result = module.execute(**args)
        if result is not None:
            print(f"[Output] {result}")
            # Speak the result if speech is enabled
            speak_response(str(result))
        print(f"[System] Execution finished.")

    except Exception as e:
        print(f"[Error] Failed to execute skill {tool_name}:")
        traceback.print_exc()

def main():
    print("--------------------------------------------------")
    print(" K.I.T.E: Kernel Integrated Task Engine")
    print(" Models: Llama 3.2 & Qwen 2.5")
    print(" Commands: 'speech on', 'speech off', 'speech toggle'")
    print("--------------------------------------------------")
    
    while True:
        try:
            print("\n")
            user_input = input("You: ").strip()
            if not user_input:
                continue
            
            # Speech toggle commands
            if user_input.lower() == "speech on":
                toggle_speech()
                continue
            elif user_input.lower() == "speech off":
                speech_enabled = False
                print("[System] Speech disabled")
                continue
            elif user_input.lower() == "speech toggle":
                toggle_speech()
                continue
            
            if user_input.lower() in ["exit", "quit"]:
                print("[System] Shutting down.")
                break

            # 1. Route
            decision = router.run_router(user_input)
            
            if "error" in decision:
                print(f"[Error] Router failed: {decision['error']}")
                continue

            action = decision.get("action")
            
            if action == "BUILD":
                print(f"[System] Action: BUILD ({decision.get('description')})")
                description = decision.get("description", user_input)
                
                # Call Builder
                args, filename = builder.build_and_parse(description, user_input)
                tool_name = filename.replace(".py", "")
                
                # Execute immediately
                load_and_run_skill(tool_name, args)

            elif action == "USE_TOOL":
                tool_name = decision.get("tool")
                print(f"[System] Action: USE_TOOL ({tool_name})")
                
                args = decision.get("args", {})
                
                # If Llama failed to extract args (empty), double check with Qwen if input seems like it needs args?
                # For now, just trust Llama or if args is empty but input is long, maybe failover?
                # Simple failover logic: if args is empty, let's just ask Qwen to be safe? 
                # User config says: "failover if needed".
                # Let's verify existing args. if empty, maybe try parse_only.
                if not args:
                     print("[System] Llama didn't return args. Asking Builder to parse...")
                     args = builder.parse_only(tool_name, user_input)
                
                load_and_run_skill(tool_name, args)

            else:
                print(f"[Error] Unknown action: {action}")
                print(f"Debug: {decision}")

        except KeyboardInterrupt:
            print("\n[System] Interrupted. Exiting.")
            break
        except Exception as e:
            print(f"[Error] Unhandled exception in main loop: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    main()

