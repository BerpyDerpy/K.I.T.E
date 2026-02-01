# filename: speak.py
"""
Speak Skill for K.I.T.E
Vocalizes text to the user using TTS.
"""

import sys
import os

# Add parent directory to path for utils import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.tts import get_tts, interrupt, speak


def execute(text: str = None, interrupt_current: bool = False, **kwargs) -> str:
    """
    Speak the given text aloud.
    
    Args:
        text: The text to speak (required)
        interrupt_current: If True, interrupt any current speech before speaking
        **kwargs: Additional arguments (flexible parsing from LLM)
    
    Returns:
        Confirmation message
    """
    # Handle flexible input - accept 'text' or any other string parameter
    if text is None:
        # Try to find the first string argument
        for key, value in kwargs.items():
            if isinstance(value, str) and len(value) > 0:
                text = value
                break
        else:
            return "[Error] No text provided to speak. Please specify text to speak."
    
    # Clean up the text
    text = text.strip()
    if not text:
        return "[Error] Empty text provided to speak."
    
    # Interrupt current speech if requested
    if interrupt_current:
        interrupt()
    
    # Get TTS and speak
    tts = get_tts()
    tts.speak(text)
    
    return f"[Spoke] {text[:100]}{'...' if len(text) > 100 else ''}"

