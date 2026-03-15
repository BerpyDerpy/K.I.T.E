"""
K.I.T.E. TTS Module
"""
import sys

IS_SPEAKING = False

_pipeline = None

try:
    from kokoro import KPipeline
    # Initializes a Kokoro pipeline with model id 'a' (American English)
    _pipeline = KPipeline(lang_code='a')
except Exception:
    _pipeline = None


def speak(text: str):
    """
    Generates audio for the given text and plays it using sounddevice.
    Blocks until playback is complete.
    """
    global IS_SPEAKING
    IS_SPEAKING = True
    
    try:
        if _pipeline is None:
            print(f"[TTS FALLBACK] {text}")
            return
            
        import sounddevice as sd
        
        # Generate audio using voice 'af_heart'
        generator = _pipeline(text, voice='af_heart', speed=1)
        
        for _graphemes, _phonemes, audio in generator:
            if audio is not None:
                # Play audio in real time, blocking execution
                sd.play(audio, samplerate=24000)
                sd.wait()
                
    except Exception as e:
        print(f"[TTS FALLBACK] {text}")
    finally:
        IS_SPEAKING = False


if __name__ == "__main__":
    speak("KITE is online. Awaiting your query.")
