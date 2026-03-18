import sys
import os
import time
import soundfile as sf
import numpy as np
from ui.api import notify_audio_updated

IS_SPEAKING = False

_pipeline = None

try:
    from kokoro import KPipeline
    # Initializes a Kokoro pipeline with model id 'a' (American English)
    _pipeline = KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M')
except Exception:
    _pipeline = None


def speak(text: str):
    """
    Generates audio for the given text, saves it as a WAV file, and updates the local server.
    Emulates block playback wait by sleeping the length of generated audio.
    """
    global IS_SPEAKING
    IS_SPEAKING = True
    
    try:
        if _pipeline is None:
            print(f"[TTS FALLBACK] {text}")
            return
            
        # Generate audio using voice 'af_heart'
        generator = _pipeline(text, voice='af_heart', speed=1)
        
        audio_chunks = []
        for _graphemes, _phonemes, audio in generator:
            if audio is not None:
                audio_chunks.append(audio)
                
        if audio_chunks:
            full_audio = np.concatenate(audio_chunks)
            
            # Save to ui/latest.wav
            ui_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ui')
            wav_path = os.path.join(ui_dir, 'latest.wav')
            
            sf.write(wav_path, full_audio, 24000)
            
            # Tell backend that new audio is ready
            notify_audio_updated()
            
            # Wait for roughly the duration of the audio to mimic blocking playback
            duration = len(full_audio) / 24000
            time.sleep(duration)
                
    except Exception as e:
        print(f"[TTS FALLBACK ERROR] {text} - {e}")
    finally:
        IS_SPEAKING = False


if __name__ == "__main__":
    speak("KITE is online. Awaiting your query.")
