"""
K.I.T.E. Main Conversational Loop
"""

import asyncio
import json
import threading
from datetime import datetime
import ollama

from core import retriever, router, executor
from audio import tts

# Constants
MODEL = getattr(router, "MODEL", "qwen2.5-coder:7b-instruct-q4_K_M")


def log_stage(stage: str, message: str):
    """Log a pipeline stage with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp} {stage.upper():<8}] {message}")


def summarize_output(query: str, raw_output: str) -> str:
    """Make a second call to Ollama to summarize raw tool output into a natural conversational sentence."""
    system_prompt = (
        "You are KITE, a helpful voice assistant. You just executed a tool or skill on the user's behalf.\n"
        "Your task: Convert the Raw Tool Output into a short, natural, spoken sentence (1-2 sentences max).\n"
        "Do not explain that you used a tool, just give the answer naturally.\n"
        "If the raw output contains a list, summarize it briefly."
    )
    user_message = f"User Query: {query}\n\nRaw Tool Output:\n{raw_output}"

    try:
        response = ollama.chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response["message"]["content"].strip()
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
    play_audio("KITE is online.")

    while True:
        try:
            print("\n" + "=" * 60)
            user_input = input("> ").strip()
            if not user_input:
                continue

            log_stage("input", user_input)

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
            play_audio(final_response)

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
