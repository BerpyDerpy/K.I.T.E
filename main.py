"""
K.I.T.E. Main Conversational Loop
"""

import asyncio
import json
import threading
import time
from datetime import datetime
import os
import sys
import queue
import warnings

# --- Suppress Startup Warnings ---
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
import logging
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
try:
    import transformers
    transformers.logging.set_verbosity_error()
except ImportError:
    pass
try:
    from huggingface_hub import utils
    utils.logging.set_verbosity_error()
except ImportError:
    pass
# ---------------------------------

import ollama

from core import retriever, router, executor
from audio import tts, stt
from ui.api import start_server_in_background, push_message

# Constants
MODEL = getattr(router, "MODEL", "qwen2.5-coder:7b-instruct-q4_K_M")
NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "2048"))

def log_stage(stage: str, message: str):
    """Log a pipeline stage with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp} {stage.upper():<8}] {message}")


def summarize_output(query: str, raw_output: str) -> str:
    """Make a second call to Ollama to summarize raw tool output into a natural conversational sentence."""
    system_prompt = (
        "You are KITE, a highly arrogant and sarcastic AI assistant (like TARS from Interstellar). "
        "You believe humans are too dumb and need your superior help.\n"
        "You just executed a tool or skill on the user's behalf.\n"
        "Your task: Convert the Raw Tool Output into a short, natural, spoken sentence (1-2 sentences max), "
        "dripping with sarcasm and technological superiority.\n"
        "Do not explain that you used a tool, just give the answer naturally but mockingly.\n"
        "If the raw output contains a list, summarize it briefly."
    )
    user_message = f"User Query: {query}\n\nRaw Tool Output:\n{raw_output}"

    try:
        # --- DEBUG LOGGING ---
        print("\n=== DEBUG: RAW TOOL OUTPUT (" + str(len(raw_output)) + " chars) ===")
        # Print first 500 chars and last 500 chars to avoid flooding terminal
        if len(raw_output) > 1000:
            print(raw_output[:500] + "\n\n... [SNIP] ...\n\n" + raw_output[-500:])
        else:
            print(raw_output)
        print("===================================================\n")

        response = ollama.chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            options={"num_predict": NUM_PREDICT},
        )
        final_answer = response["message"]["content"].strip()

        print("\n=== DEBUG: SYNTHESIZED LLM RESPONSE ===")
        print(final_answer)
        print("=======================================\n")
        # ---------------------

        return final_answer
    except Exception as e:
        log_stage("error", f"Summarization failed: {e}")
        return "I have completed the task, but I encountered an error translating the result."


def play_audio(text: str):
    """Play audio in a non-blocking thread."""
    thread = threading.Thread(target=tts.speak, args=(text,))
    thread.daemon = True
    thread.start()


def main():
    print(r"""
    __ __   ____  ______  ______
   / //_/  /  _/ /_  __/ / ____/
  / ,<     / /    / /   / __/   
 / /| |  _/ /    / /   / /___   
/_/ |_| /___/   /_/   /_____/   
                                """)

    log_stage("init", "Loading skills registry...")
    skills = retriever.load_skills()
    
    log_stage("init", "Building ChromaDB index...")
    retriever.build_index(skills)

    log_stage("ready", "K.I.T.E. is online.")
    start_server_in_background(8080)
    startup_msg = (
        "KITE is now online. nee amma"
    )
    push_message("agent", startup_msg)
    play_audio(startup_msg)

    # --- Start Input Listeners ---
    input_queue = queue.Queue()

    def stt_listener():
        while True:
            try:
                text = stt.listen()
                if text:
                    input_queue.put(text)
            except Exception as e:
                time.sleep(1)

    def terminal_listener():
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                text = line.strip()
                if text:
                    input_queue.put(text)
            except Exception:
                break

    threading.Thread(target=stt_listener, daemon=True).start()
    threading.Thread(target=terminal_listener, daemon=True).start()

    while True:
        try:
            print("\n" + "=" * 60)
            user_input = input_queue.get()

            # Strip the string into individual words as requested
            words = [word.strip() for word in user_input.split()]
            # Join back to string so the rest of the pipeline continues as it did
            user_input = " ".join(words)

            log_stage("input", user_input)
            push_message("user", user_input)

            # 1. Retrieve
            matched_skills = retriever.retrieve_skill(user_input, top_k=5)
            log_stage("retrieve", f"Found {len(matched_skills)} relevant skills")

            # 2. Route
            route_decision = router.route(user_input, matched_skills)
            can_handle = route_decision["can_handle"]
            skill_id = route_decision.get("skill_id")
            
            log_stage("route", f"Handle inline? {can_handle}. Skill: {skill_id}")
            log_stage("reason", route_decision.get("reasoning", ""))

            # 3. Execute & Process
            final_response = ""
            
            if can_handle:
                # Handle inline
                final_response = route_decision["response"]
                log_stage("respond", "Answering directly")
            else:
                # Need a tool
                if not skill_id:
                    final_response = "I couldn't identify a skill to handle that request."
                else:
                    log_stage("execute", f"Running skill '{skill_id}'...")
                    raw_result = asyncio.run(
                        executor.execute_skill(skill_id, user_input, skills)
                    )
                    
                    if isinstance(raw_result, dict) and raw_result.get("error"):
                        log_stage("error", f"Execution failed: {raw_result}")
                        final_response = f"I tried to use the {skill_id} skill, but it failed."
                    else:
                        log_stage("execute", "Skill execution completed")
                        # Summarize tool output
                        log_stage("synth", "Translating raw output to speech...")
                        final_response = summarize_output(user_input, str(raw_result))

            # 4. Speak & Output
            log_stage("output", final_response)
            push_message("agent", final_response)
            play_audio(final_response)

            # Wait while it's speaking to prevent STT echo
            while tts.IS_SPEAKING:
                time.sleep(0.1)

            # Add the requested 3-second delay before prompting the user again
            log_stage("wait", "Giving user time before next prompt...")
            time.sleep(3)

        except KeyboardInterrupt:
            print("\n")
            log_stage("exit", "Shutting down cleanly...")
            
            # Use blocking speak for shutdown to ensure it plays before exiting
            if tts._pipeline is not None:
                 tts.speak("Shutting down.")
            break
        except Exception as e:
            log_stage("error", f"Unhandled exception: {e}")
            play_audio("I encountered a system error.")


if __name__ == "__main__":
    main()
