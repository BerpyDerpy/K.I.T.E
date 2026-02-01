import router
import builder
import sys
import os
import importlib
import traceback
from utils.tts import get_tts, speak, stop
from utils.stt import get_stt, listen_for_voice, stop_listening, check_stt_availability

# Speech mode toggle
speech_enabled = False

# Voice input mode toggle
voice_enabled = False
voice_stt = None

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

def toggle_voice():
    """Toggle voice input mode on/off."""
    global voice_enabled, voice_stt
    
    if voice_enabled:
        # Turn off voice mode
        if voice_stt is not None:
            stop_listening()
            voice_stt = None
        voice_enabled = False
        print("[System] Voice input disabled")
    else:
        # Turn on voice mode - check availability first
        availability = check_stt_availability()
        
        if not availability.get("whisper_available"):
            print("[System] Voice input unavailable: faster-whisper not installed")
            print("         Run: pip install -r requirements.txt")
            return False
        
        if not availability.get("audio_available"):
            print("[System] Voice input unavailable: audio libraries not installed")
            print("         Run: pip install sounddevice webrtcvad")
            return False
        
        # Initialize STT and start listening
        voice_stt = get_stt()
        voice_stt.start_listening(on_voice_transcript)
        voice_enabled = True
        print("[System] Voice input enabled - speak your commands")
    
    return voice_enabled

def on_voice_transcript(text: str):
    """Callback when voice is transcribed to text."""
    global voice_enabled
    
    if not text or not text.strip():
        return
    
    print(f"\n🎤 You (voice): {text}")
    
    # Process the voice input through the router
    try:
        decision = router.run_router(text)
        
        if "error" in decision:
            print(f"[Error] Router failed: {decision['error']}")
            return

        action = decision.get("action")
        
        if action == "BUILD":
            print(f"[System] Action: BUILD ({decision.get('description')})")
            description = decision.get("description", text)
            
            # Call Builder
            args, filename = builder.build_and_parse(description, text)
            tool_name = filename.replace(".py", "")
            
            # Execute immediately
            load_and_run_skill(tool_name, args)

        elif action == "USE_TOOL":
            tool_name = decision.get("tool")
            print(f"[System] Action: USE_TOOL ({tool_name})")
            
            args = decision.get("args", {})
            
            # If args is empty, try to parse them
            if not args:
                print("[System] Llama didn't return args. Asking Builder to parse...")
                args = builder.parse_only(tool_name, text)
            
            load_and_run_skill(tool_name, args)

        else:
            print(f"[Error] Unknown action: {action}")
            print(f"Debug: {decision}")

    except Exception as e:
        print(f"[Error] Failed to process voice input: {e}")
        traceback.print_exc()

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
    print(" Commands: 'speech on/off/toggle', 'voice on/off/toggle', 'exit'")
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
            
            # Voice input toggle commands
            if user_input.lower() == "voice on":
                toggle_voice()
                continue
            elif user_input.lower() == "voice off":
                if voice_enabled:
                    toggle_voice()
                else:
                    print("[System] Voice input already disabled")
                continue
            elif user_input.lower() == "voice toggle":
                toggle_voice()
                continue
            
            if user_input.lower() in ["exit", "quit"]:
                # Clean up voice listening if active
                if voice_enabled:
                    stop_listening()
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
            # Clean up voice listening if active
            if voice_enabled:
                stop_listening()
            break
        except Exception as e:
            print(f"[Error] Unhandled exception in main loop: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    main()

