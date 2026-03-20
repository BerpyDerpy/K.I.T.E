import whisper
import sounddevice as sd
import numpy as np
import warnings

# Suppress FP16 warning on CPU and other Whisper warnings
warnings.filterwarnings("ignore", category=UserWarning)

# Load the model once when the module is imported to save time
# 'base' is a good balance of speed and accuracy. 'tiny' is faster but less accurate.
try:
    print("[STT] Loading Whisper model...")
    _model = whisper.load_model("base")
    print("[STT] Whisper model loaded.")
except Exception as e:
    print(f"[STT] Failed to load Whisper model: {e}")
    _model = None

def listen() -> str:
    """
    Records audio from the default microphone and transcribes it using Whisper.
    Returns the transcribed text as a stripped string.
    """
    if _model is None:
        print("[STT] Error: Whisper model not loaded. Falling back to keyboard input.")
        return input("> ").strip()

    # Audio recording parameters
    samplerate = 16000  # Whisper expects 16kHz audio
    channels = 1
    
    print("\n[STT] Waiting for UI microphone toggle...")
    from ui.api import API_STATE
    import time
    
    while not API_STATE.get("listen_active", False):
        time.sleep(0.1)
    
    # We'll record in chunks until interrupted
    recorded_frames = []
    
    from . import tts
    
    def callback(indata, frames, time_info, status):
        # Ignore audio frames if the agent itself is speaking
        if tts.IS_SPEAKING:
            return
            
        if status:
            print(f"[STT] Recording status: {status}")
        recorded_frames.append(indata.copy())

    try:
        # Start recording stream
        with sd.InputStream(samplerate=samplerate, channels=channels, callback=callback):
            print("[STT] Listening... (Toggle off in UI to stop recording)")
            while API_STATE.get("listen_active", False):
                sd.sleep(100)
    except KeyboardInterrupt:
        # User pressed Ctrl+C to stop recording
        pass
    except Exception as e:
        print(f"[STT] Recording error: {e}")
        return ""

    if not recorded_frames:
        return ""

    print("\n[STT] Processing audio...")
    
    # Concatenate all recorded chunks into a single NumPy array
    audio_data = np.concatenate(recorded_frames, axis=0)
    
    # Whisper expects a 1D array of float32, normalized between -1 and 1
    # sounddevice already gives float32 by default
    audio_data = audio_data.flatten()

    try:
        # Transcribe
        result = _model.transcribe(audio_data, fp16=False)
        text = result.get("text", "").strip()
        print(f"[STT] Transcribed: '{text}'")
        return text
    except Exception as e:
        print(f"[STT] Transcription error: {e}")
        return ""