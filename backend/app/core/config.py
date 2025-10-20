# Enhanced Configuration for Multi-Model RTX 3070Ti Setup
import os

class Settings:
    # Basic settings
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://ollama:11434")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "qwen3:8b")  # default generator

    # Data paths
    DATA_PATH: str = "/app/data"
    OUTPUTS_PATH: str = "/app/data/outputs"
    LOGS_PATH: str = "/app/data/logs"
    TEMPLATES_PATH: str = "/app/data/templates"

    # Generation targets
    MODEL_TEMPERATURE: float = float(os.getenv("MODEL_TEMPERATURE", "0.7"))
    TARGET_WPM: int = int(os.getenv("TARGET_WPM", "140"))
    WORDS_PER_BEAT: int = int(os.getenv("WORDS_PER_BEAT", "600"))
    BEATS_PER_STORY: int = int(os.getenv("BEATS_PER_STORY", "12"))
    MAX_TOKENS_BEAT: int = int(os.getenv("MAX_TOKENS_BEAT", "800"))
    MAX_TOKENS_OUTLINE: int = int(os.getenv("MAX_TOKENS_OUTLINE", "1500"))

    # Model defaults (fixed)
    DEFAULT_MODELS = {
        "generator": "qwen3:8b",
        "reasoner": "deepseek-r1:8b",
        "polisher": "mistral:7b"
    }

    # Presets exposed to UI
    MODEL_PRESETS = {
        "quality_high": {
            "generator": "qwen3:8b",
            "reasoner": "deepseek-r1:8b",
            "polisher": "mistral:7b",
            "use_reasoner": True,
            "use_polish": True,
            "temps": {"generator": 0.7, "reasoner": 0.3, "polisher": 0.4},
            "beats": 12,
            "words_per_beat": 600,
            "tolerance": 0.10,
            "taper": {"start_pct": 0.80, "reduction": 0.70},
            "rotation": True,
        },
        "fast": {
            "generator": "qwen3:8b",
            "reasoner": None,
            "polisher": None,
            "use_reasoner": False,
            "use_polish": False,
            "temps": {"generator": 0.65, "reasoner": 0.3, "polisher": 0.4},
            "beats": 8,
            "words_per_beat": 400,
            "tolerance": 0.12,
            "taper": {"start_pct": 0.80, "reduction": 0.70},
            "rotation": True,
        },
        "smoke_test_5m": {
            "generator": "qwen3:8b",
            "reasoner": None,
            "polisher": "mistral:7b",
            "use_reasoner": False,
            "use_polish": True,
            "temps": {"generator": 0.6, "reasoner": 0.3, "polisher": 0.35},
            "beats": 6,
            "words_per_beat": 100,
            "tolerance": 0.10,
            "taper": {"start_pct": 0.70, "reduction": 0.60},
            "rotation": True,
        },
        "ultra_relax": {
            "generator": "qwen3:8b",
            "reasoner": "deepseek-r1:8b",
            "polisher": "mistral:7b",
            "use_reasoner": True,
            "use_polish": True,
            "temps": {"generator": 0.6, "reasoner": 0.3, "polisher": 0.35},
            "beats": 12,
            "words_per_beat": 600,
            "tolerance": 0.08,
            "taper": {"start_pct": 0.70, "reduction": 0.60},
            "rotation": True,
        },
    }

    # Quality enhancement settings
    SENSORY_ROTATION_ENABLED: bool = True
    SENSORY_MODES = ["sight", "sound", "touch", "smell", "proprioception"]

    # Mixed-reward proxy settings
    OPENER_PENALTY_THRESHOLD: int = 3
    TRANSITION_PENALTY_WEIGHT: float = 0.3
    REDUNDANCY_PENALTY_WEIGHT: float = 0.2

    # Planning and control
    BEAT_PLANNING_ENABLED: bool = True
    BEAT_LENGTH_TOLERANCE: float = 0.10

    # Sleep-taper
    SLEEP_TAPER_ENABLED: bool = True
    TAPER_START_PERCENTAGE: float = 0.80
    TAPER_REDUCTION_FACTOR: float = 0.70

    # TTS
    TTS_MARKERS_ENABLED: bool = False
    TTS_PAUSE_MIN: float = 0.5
    TTS_PAUSE_MAX: float = 3.0
    TTS_BREATHE_FREQUENCY: int = 4

    # VRAM / retry
    MAX_CONCURRENT_MODELS: int = 1
    MODEL_UNLOAD_DELAY: float = 2.0
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0
    FALLBACK_MODEL: str = "qwen3:8b"

    # Embodied Journey
    MOVEMENT_VERBS_REQUIRED: int = int(os.getenv("MOVEMENT_VERBS_REQUIRED", "1"))
    TRANSITION_TOKENS_REQUIRED: int = int(os.getenv("TRANSITION_TOKENS_REQUIRED", "1"))
    SENSORY_COUPLING: int = int(os.getenv("SENSORY_COUPLING", "2"))
    DOWNSHIFT_REQUIRED: bool = os.getenv("DOWNSHIFT_REQUIRED", "true").lower() == "true"
    POV_ENFORCE_SECOND_PERSON: bool = os.getenv("POV_ENFORCE_SECOND_PERSON", "true").lower() == "true"

    MOVEMENT_VERBS = [
        "incammin", "avanz", "attravers", "super", "raggiung", "scend", "risal", "volt", "prosegu", "sost"
    ]
    TRANSITION_TOKENS = [
        "più avanti", "oltre il", "svolti", "superi", "raggiungi", "scendi", "risali", "appena dopo", "di fronte", "poco più in là"
    ]

    # Destination Architecture
    DESTINATION_PROMISE_BEAT: int = int(os.getenv("DESTINATION_PROMISE_BEAT", "1"))
    ARRIVAL_SIGNALS_START: float = float(os.getenv("ARRIVAL_SIGNALS_START", "0.7"))
    SETTLEMENT_BEATS: int = int(os.getenv("SETTLEMENT_BEATS", "2"))
    CLOSURE_REQUIRED: bool = os.getenv("CLOSURE_REQUIRED", "true").lower() == "true"

    DESTINATION_ARCHETYPES = {
        "safe_shelter": ["cottage", "cabin", "sanctuary", "grove"],
        "peaceful_vista": ["meadow", "clearing", "overlook", "garden"],
        "restorative_water": ["pool", "stream", "cove", "spring"],
        "sacred_space": ["temple", "circle", "altar", "threshold"]
    }

settings = Settings()
