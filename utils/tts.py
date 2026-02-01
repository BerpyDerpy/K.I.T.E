"""
Text-to-Speech Module for K.I.T.E
Cross-platform TTS using macOS native Speech Synthesis.
"""
import sys
import objc


class TextToSpeech:
    """macOS native TTS using NSSpeechSynthesizer."""
    
    def __init__(self, enabled: bool = True, rate: int = 200, voice_id: int = None):
        self.enabled = enabled
        self.rate = rate
        self._synth = None
        self._use_native = False
        self._use_pyttsx3 = False
        self._init_synthesizer()
    
    def _init_synthesizer(self):
        """Initialize speech synthesizer."""
        try:
            # Try native macOS speech first
            from AppKit import NSSpeechSynthesizer
            self._synth = NSSpeechSynthesizer.alloc().init()
            self._synth.setRate_(self.rate)
            
            # Get default voice
            voice = self._synth.voice()
            if voice:
                self._synth.setVoice_(voice)
                self._use_native = True
                print(f"[TTS] Using native macOS speech with voice: {voice}")
            else:
                raise Exception("No default voice available")
                
        except Exception as e:
            # Fallback to pyttsx3
            try:
                import pyttsx3
                self._engine = pyttsx3.init()
                self._engine.setProperty('rate', self.rate)
                self._use_pyttsx3 = True
                voices = self._engine.getProperty('voices')
                print(f"[TTS] Using pyttsx3 fallback with {len(voices)} voices")
            except Exception as e2:
                print(f"[TTS] All TTS methods failed: {e2}")
    
    def speak(self, text: str) -> None:
        """Speak the given text."""
        if not self.enabled or not text or not text.strip():
            return
        
        # Clean text
        text = self._preprocess_for_speech(text)
        if not text:
            return
        
        try:
            if self._use_pyttsx3:
                self._engine.say(text)
                self._engine.runAndWait()
            elif self._use_native and self._synth:
                self._synth.startSpeakingString_(text)
        except Exception as e:
            print(f"[TTS] Speech error: {e}")
    
    def stop(self) -> None:
        """Stop current speech."""
        try:
            if self._use_pyttsx3:
                self._engine.stop()
            elif self._use_native and self._synth:
                self._synth.stopSpeaking()
        except Exception:
            pass
    
    def is_speaking(self) -> bool:
        """Check if currently speaking."""
        if self._use_native and self._synth:
            return self._synth.isSpeaking()
        return False
    
    def _preprocess_for_speech(self, text: str) -> str:
        """Clean text for speech."""
        import re
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        text = re.sub(r'https?://[^\s<>"]+', '', text)
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text


# Global instance
_tts_instance = None

def get_tts() -> TextToSpeech:
    """Get global TTS instance."""
    global _tts_instance
    if _tts_instance is None:
        _tts_instance = TextToSpeech()
    return _tts_instance

def speak(text: str) -> None:
    """Speak text."""
    tts = get_tts()
    tts.speak(text)

def stop() -> None:
    """Stop speech."""
    tts = get_tts()
    tts.stop()

def interrupt() -> None:
    """Interrupt current speech."""
    stop()

def create_tts_engine(enabled: bool = True, rate: int = 200, voice_id: int = None):
    """Factory function to create TTS engine."""
    return TextToSpeech(enabled=enabled, rate=rate, voice_id=voice_id)

