# Enhanced Configuration for Multi-Model RTX 3070Ti Setup
import os
from typing import Dict, Optional, List
from pathlib import Path

class Settings:
    # Basic settings (existing)
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://ollama:11434")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "qwen2.5:7b")
    
    # Data paths (existing)
    DATA_PATH: str = "/app/data"
    OUTPUTS_PATH: str = "/app/data/outputs"
    LOGS_PATH: str = "/app/data/logs"
    TEMPLATES_PATH: str = "/app/data/templates"
    
    # MISSING CONSTANTS from original system (from project docs)
    MODEL_TEMPERATURE: float = float(os.getenv("MODEL_TEMPERATURE", "0.7"))
    TARGET_WPM: int = int(os.getenv("TARGET_WPM", "140"))  # Words per minute
    WORDS_PER_BEAT: int = int(os.getenv("WORDS_PER_BEAT", "600"))  # Words per story beat
    BEATS_PER_STORY: int = int(os.getenv("BEATS_PER_STORY", "12"))  # Total beats
    MAX_TOKENS_BEAT: int = int(os.getenv("MAX_TOKENS_BEAT", "800"))  # Max tokens per beat
    MAX_TOKENS_OUTLINE: int = int(os.getenv("MAX_TOKENS_OUTLINE", "1500"))  # Max tokens for outline
    
    # NEW: Multi-Model Configuration for RTX 3070Ti
    DEFAULT_MODELS = {
        "generator": "qwen2.5:7b",      # Main story generation
        "reasoner": "deepseek-r1:8b",   # Logic and coherence reasoning  
        "polisher": "mistral:7b"        # Final polish and refinement
    }
    
    # Model presets for UI
    MODEL_PRESETS = {
        "quality_high": {
            "generator": "qwen2.5:7b",
            "reasoner": "deepseek-r1:8b", 
            "polisher": "mistral:7b",
            "use_reasoner": True,
            "use_polish": True
        },
        "fast": {
            "generator": "qwen2.5:7b",
            "reasoner": None,
            "polisher": None,
            "use_reasoner": False,
            "use_polish": False
        }
    }
    
    # NEW: Quality Enhancement Settings
    SENSORY_ROTATION_ENABLED: bool = True
    SENSORY_MODES = ["sight", "sound", "touch", "smell", "proprioception"]
    
    # Mixed-reward proxy settings
    OPENER_PENALTY_THRESHOLD: int = 3  # Max repetitions before penalty
    TRANSITION_PENALTY_WEIGHT: float = 0.3
    REDUNDANCY_PENALTY_WEIGHT: float = 0.2
    
    # Recursive planning settings
    BEAT_PLANNING_ENABLED: bool = True
    BEAT_LENGTH_TOLERANCE: float = 0.1  # ±10% max
    
    # Sleep-taper settings
    SLEEP_TAPER_ENABLED: bool = True
    TAPER_START_PERCENTAGE: float = 0.8  # Start at 80% of story
    TAPER_REDUCTION_FACTOR: float = 0.7  # Reduce density by 30%
    
    # TTS Settings
    TTS_MARKERS_ENABLED: bool = False  # Default off
    TTS_PAUSE_MIN: float = 0.5
    TTS_PAUSE_MAX: float = 3.0
    TTS_BREATHE_FREQUENCY: int = 4  # Every 4 beats
    
    # Schema settings
    STRICT_SCHEMA_ENABLED: bool = False  # Default off
    
    # VRAM Management for RTX 3070Ti (8GB)
    MAX_CONCURRENT_MODELS: int = 1  # Sequential loading only
    MODEL_UNLOAD_DELAY: float = 2.0  # Seconds before unloading
    
    # Retry and fallback settings
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0
    FALLBACK_MODEL: str = "qwen2.5:7b"  # Always available fallback

# Global settings instance
settings = Settings()