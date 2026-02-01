"""
Speech-to-Text Module for K.I.T.E
Uses OpenAI Whisper for transcription with VAD for voice activity detection.
"""

import threading
import time
import queue
import numpy as np
from typing import Optional, Callable

# Audio processing imports (optional - gracefully handle missing dependencies)
try:
    import sounddevice as sd
    import webrtcvad
    AUDIO_AVAILABLE = True
except ImportError as e:
    sd = None
    webrtcvad = None
    AUDIO_AVAILABLE = False
    print(f"[STT] Audio import warning: {e}")

# Whisper imports - try openai-whisper first, fall back to faster-whisper
WHISPER_BACKEND = None
WHISPER_AVAILABLE = False

try:
    import whisper
    WHISPER_BACKEND = "openai"
    WHISPER_AVAILABLE = True
    print("[STT] Using openai-whisper backend")
except ImportError:
    try:
        from faster_whisper import WhisperModel
        WHISPER_BACKEND = "faster"
        WHISPER_AVAILABLE = True
        print("[STT] Using faster-whisper backend")
    except ImportError as e:
        WhisperModel = None
        WHISPER_AVAILABLE = False
        print(f"[STT] Whisper import warning: {e}")


class SpeechToText:
    """Speech-to-Text engine using OpenAI Whisper with VAD."""
    
    def __init__(self, model_size: str = "small", sample_rate: int = 16000):
        """
        Initialize STT engine.
        
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large)
            sample_rate: Audio sample rate (default 16000)
        """
        self.model_size = model_size
        self.sample_rate = sample_rate
        self.model = None
        self._audio_q = queue.Queue(maxsize=64)
        self._is_listening = False
        self._should_stop = False
        
        # Voice Activity Detection
        self._vad = None
        self._vad_enabled = True
        self._vad_aggressiveness = 2
        
        # Speech detection settings
        self._min_energy = 0.0045
        self._silence_threshold = 30  # frames of silence to end utterance
        self._utterance_silence_frames = 0
        self._is_speech_active = False
        
        # Audio parameters
        self._frame_ms = 20
        self._frame_samples = int(sample_rate * self._frame_ms / 1000)
        
        # Callback for transcribed text
        self.on_transcript: Optional[Callable[[str], None]] = None
        
        # Initialize VAD
        self._init_vad()
        
        # Initialize Whisper model
        self._init_model()
    
    def _init_vad(self):
        """Initialize WebRTC VAD (Voice Activity Detection)."""
        if webrtcvad is not None and self._vad_enabled:
            try:
                self._vad = webrtcvad.Vad(self._vad_aggressiveness)
                print(f"[STT] VAD initialized with aggressiveness: {self._vad_aggressiveness}")
            except Exception as e:
                print(f"[STT] VAD initialization failed: {e}")
                self._vad = None
    
    def _init_model(self):
        """Initialize Whisper model."""
        global WHISPER_BACKEND
        
        if not WHISPER_AVAILABLE:
            print("[STT] Whisper not available")
            return
        
        try:
            if WHISPER_BACKEND == "openai":
                print(f"[STT] Loading OpenAI Whisper model '{self.model_size}'...")
                self.model = whisper.load_model(self.model_size)
                print(f"[STT] OpenAI Whisper model '{self.model_size}' loaded successfully")
            elif WHISPER_BACKEND == "faster":
                from faster_whisper import WhisperModel
                print(f"[STT] Loading faster-whisper model '{self.model_size}'...")
                self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
                print(f"[STT] faster-whisper model '{self.model_size}' loaded successfully")
        except Exception as e:
            print(f"[STT] Failed to load Whisper model: {e}")
            self.model = None
    
    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for audio input from microphone."""
        try:
            if self._should_stop:
                return
            
            # Handle different input formats
            if hasattr(indata, 'copy'):
                audio_data = indata.copy()
            else:
                audio_data = indata
            
            # Ensure mono audio
            if audio_data.ndim > 1:
                audio_data = audio_data[:, 0]  # Take first channel
            
            try:
                self._audio_q.put_nowait(audio_data)
            except queue.Full:
                pass  # Queue full, skip this frame
                
        except Exception as e:
            print(f"[STT] Audio callback error: {e}")
    
    def _is_speech_frame(self, frame: np.ndarray) -> bool:
        """Determine if audio frame contains speech using VAD or energy."""
        if np is None:
            return True
        
        # Calculate RMS energy
        rms = float(np.sqrt(np.mean(np.square(frame))))
        
        if self._vad is not None:
            # Use WebRTC VAD
            try:
                # Convert to 16-bit PCM
                pcm16 = np.clip(frame.flatten() * 32768.0, -32768, 32767).astype(np.int16).tobytes()
                return bool(self._vad.is_speech(pcm16, self.sample_rate))
            except Exception:
                pass
        
        # Fallback to energy-based detection
        return rms >= self._min_energy
    
    def _transcribe_audio(self, audio: np.ndarray) -> str:
        """Transcribe audio using Whisper (supports both OpenAI and faster-whisper)."""
        global WHISPER_BACKEND
        
        if self.model is None:
            return ""
        
        try:
            if WHISPER_BACKEND == "openai":
                # OpenAI Whisper API
                # Audio should be 16kHz, float32
                result = self.model.transcribe(audio)
                text = result["text"].strip()
                return text
                
            elif WHISPER_BACKEND == "faster":
                # faster-whisper API
                segments, _info = self.model.transcribe(
                    audio, 
                    language="en",
                    vad_filter=False  # We handle VAD ourselves
                )
                
                # Collect all transcribed text
                text_parts = []
                for segment in segments:
                    text_parts.append(segment.text.strip())
                
                text = " ".join(text_parts).strip()
                return text
            
            return ""
            
        except Exception as e:
            print(f"[STT] Transcription error: {e}")
            return ""
    
    def _process_audio_stream(self):
        """Process audio stream from microphone."""
        if sd is None:
            print("[STT] sounddevice not available")
            return
        
        # Audio parameters
        frame_ms = self._frame_ms
        frame_samples = self._frame_samples
        silence_threshold = self._silence_threshold
        min_audio_duration = 0.3  # seconds
        
        # Pre-roll buffer for capturing onset
        pre_roll = []
        pre_roll_max = 12  # ~240ms at 20ms frames
        
        # Track utterance timing
        utterance_frames = []
        
        try:
            # Open audio stream
            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=frame_samples,
                callback=self._audio_callback
            )
            
            with stream:
                print("[STT] 🎙️  Listening... (speak now)")
                
                while not self._should_stop:
                    try:
                        # Get audio frame with timeout
                        audio_frame = self._audio_q.get(timeout=0.5)
                    except queue.Empty:
                        # Check if we should end the current utterance
                        if self._is_speech_active and self._utterance_silence_frames >= silence_threshold:
                            # Finalize the utterance
                            if utterance_frames:
                                audio = np.concatenate(utterance_frames, axis=0).flatten()
                                audio_duration = len(audio) / self.sample_rate
                                
                                if audio_duration >= min_audio_duration:
                                    text = self._transcribe_audio(audio)
                                    if text and self.on_transcript:
                                        print(f"[STT] 📝 Heard: \"{text}\"")
                                        self.on_transcript(text)
                            
                            # Reset for next utterance
                            utterance_frames = []
                            pre_roll = []
                            self._is_speech_active = False
                            self._utterance_silence_frames = 0
                            print("[STT] 🎙️  Listening... (speak now)")
                        continue
                    
                    # Check for speech
                    is_voice = self._is_speech_frame(audio_frame)
                    
                    if not self._is_speech_active:
                        if is_voice:
                            self._is_speech_active = True
                            # Capture pre-roll frames before speech started
                            utterance_frames.extend(pre_roll)
                            utterance_frames.append(audio_frame.copy())
                            pre_roll = []
                        else:
                            # Maintain pre-roll buffer
                            pre_roll.append(audio_frame.copy())
                            while len(pre_roll) > pre_roll_max:
                                pre_roll.pop(0)
                    else:
                        if is_voice:
                            utterance_frames.append(audio_frame.copy())
                            self._utterance_silence_frames = 0
                        else:
                            self._utterance_silence_frames += 1
                            
                            # End utterance if silence threshold reached
                            if self._utterance_silence_frames >= silence_threshold:
                                if utterance_frames:
                                    audio = np.concatenate(utterance_frames, axis=0).flatten()
                                    audio_duration = len(audio) / self.sample_rate
                                    
                                    if audio_duration >= min_audio_duration:
                                        text = self._transcribe_audio(audio)
                                        if text and self.on_transcript:
                                            print(f"[STT] 📝 Heard: \"{text}\"")
                                            self.on_transcript(text)
                                
                                # Reset for next utterance
                                utterance_frames = []
                                pre_roll = []
                                self._is_speech_active = False
                                self._utterance_silence_frames = 0
                                print("[STT] 🎙️  Listening... (speak now)")
                                
        except Exception as e:
            print(f"[STT] Audio stream error: {e}")
    
    def start_listening(self, on_transcript: Callable[[str], None]):
        """
        Start listening for voice input.
        
        Args:
            on_transcript: Callback function to receive transcribed text
        """
        if self._is_listening:
            print("[STT] Already listening")
            return
        
        self.on_transcript = on_transcript
        self._should_stop = False
        
        # Start listening thread
        self._listen_thread = threading.Thread(target=self._process_audio_stream, daemon=True)
        self._listen_thread.start()
        self._is_listening = True
    
    def stop_listening(self):
        """Stop listening for voice input."""
        self._should_stop = True
        self._is_listening = False
        
        # Wait for thread to finish
        if hasattr(self, '_listen_thread') and self._listen_thread.is_alive():
            self._listen_thread.join(timeout=2.0)
        
        # Clear audio queue
        try:
            while not self._audio_q.empty():
                self._audio_q.get_nowait()
        except Exception:
            pass
        
        print("[STT] Stopped listening")
    
    def is_listening(self) -> bool:
        """Check if currently listening."""
        return self._is_listening
    
    def transcribe_file(self, audio_path: str) -> str:
        """
        Transcribe an audio file.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Transcribed text
        """
        if self.model is None:
            return ""
        
        try:
            import soundfile as sf
            audio, _ = sf.read(audio_path)
            # Ensure mono
            if audio.ndim > 1:
                audio = audio[:, 0]
            
            return self._transcribe_audio(audio)
        except Exception as e:
            print(f"[STT] File transcription error: {e}")
            return ""
    
    def check_availability(self) -> dict:
        """Check availability of STT components."""
        return {
            "audio_available": AUDIO_AVAILABLE,
            "whisper_available": WHISPER_AVAILABLE,
            "model_loaded": self.model is not None,
            "vad_available": self._vad is not None
        }


# Global instance
_stt_instance = None

def get_stt(model_size: str = "small") -> SpeechToText:
    """Get global STT instance."""
    global _stt_instance
    if _stt_instance is None:
        _stt_instance = SpeechToText(model_size=model_size)
    return _stt_instance

def check_stt_availability() -> dict:
    """Check if STT is available and ready."""
    stt = get_stt()
    return stt.check_availability()

def listen_for_voice(on_transcript: Callable[[str], None]) -> SpeechToText:
    """Start listening for voice input."""
    stt = get_stt()
    stt.start_listening(on_transcript)
    return stt

def stop_listening():
    """Stop voice listening."""
    global _stt_instance
    if _stt_instance is not None:
        _stt_instance.stop_listening()
        _stt_instance = None

def transcribe_audio_file(audio_path: str) -> str:
    """Transcribe an audio file."""
    stt = get_stt()
    return stt.transcribe_file(audio_path)

