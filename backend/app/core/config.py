from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    # Ollama
    OLLAMA_URL: str = "http://ollama:11434"
    
    # Paths (tutto nel volume)
    DATA_PATH: str = "/app/data"
    
    @property
    def OUTPUTS_PATH(self):
        return os.path.join(self.DATA_PATH, "outputs")
    
    @property
    def LOGS_PATH(self):
        return os.path.join(self.DATA_PATH, "logs")
    
    @property
    def TEMPLATES_PATH(self):
        return os.path.join(self.DATA_PATH, "templates")
    
    # Model Settings
    MODEL_NAME: str = "llama3.1:8b"
    MODEL_TEMPERATURE: float = 0.7
    MODEL_REPETITION_PENALTY: float = 1.15
    CONTEXT_WINDOW: int = 128000
    MAX_TOKENS_OUTLINE: int = 3000
    MAX_TOKENS_BEAT: int = 900
    
    # Story Generation
    DEFAULT_DURATION: int = 45
    TARGET_WPM: int = 140
    WORDS_PER_BEAT: int = 600
    BEATS_PER_STORY: int = 12
    
    # System
    LOG_LEVEL: str = "INFO"
    MAX_CONCURRENT_JOBS: int = 1
    AUTO_RETRY_ENABLED: bool = True
    MAX_RETRIES: int = 2
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
