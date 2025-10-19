import ollama
import time
from typing import Dict, Optional
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class ModelOrchestrator:
    """Sequential multi-model orchestration for RTX 3070Ti (8GB).
    Runs one model at a time to keep VRAM within limits.
    Stages:
      - generator (creative): default qwen3:8b
      - reasoner (coherence): default deepseek-r1:8b
      - polisher (style):   default llama3.3:8b
    """

    def __init__(self,
                 generator: str = "qwen3:8b",
                 reasoner: str = "deepseek-r1:8b",
                 polisher: str = "llama3.3:8b",
                 use_reasoner: bool = True,
                 use_polish: bool = True):
        self.generator_name = generator
        self.reasoner_name = reasoner
        self.polisher_name = polisher
        self.use_reasoner = use_reasoner
        self.use_polish = use_polish
        self.client = ollama.Client(host=settings.OLLAMA_URL)

    def generate(self, prompt: str, options: Optional[Dict] = None) -> str:
        opts = options or {"temperature": settings.MODEL_TEMPERATURE,
                           "num_predict": settings.MAX_TOKENS_BEAT}
        logger.info(f"orchestrator_generate model={self.generator_name}")
        return self._safe_generate(self.generator_name, prompt, opts)

    def reason(self, text: str, outline_hint: str, target_words: int) -> str:
        if not self.use_reasoner:
            return text
        prompt = (
            "You are a reasoning editor. Improve coherence, remove repeated openers, "
            "maintain narrative progression, and keep calm pacing.\n\n"
            f"OUTLINE HINT:\n{outline_hint}\n\n"
            f"TARGET WORDS: {target_words} (must keep within ±5%).\n\n"
            f"TEXT:\n{text}\n\n"
            "Rewritten text (same content, improved coherence, similar length):"
        )
        logger.info(f"orchestrator_reason model={self.reasoner_name}")
        out = self._safe_generate(self.reasoner_name, prompt, {"temperature": 0.3, "num_predict": target_words*2})
        return out

    def polish(self, text: str, target_words: int) -> str:
        if not self.use_polish:
            return text
        prompt = (
            "Polish the prose for smooth, soothing style and natural rhythm. "
            "Keep the same meaning and approximately the same length (±3%). "
            "Avoid listy phrasing; prefer flowing sentences.\n\n"
            f"TEXT:\n{text}\n\nPolished text:"
        )
        logger.info(f"orchestrator_polish model={self.polisher_name}")
        out = self._safe_generate(self.polisher_name, prompt, {"temperature": 0.4, "num_predict": target_words*2})
        return out

    def _safe_generate(self, model: str, prompt: str, options: Dict) -> str:
        # Basic retry for robustness
        last_err = None
        for attempt in range(3):
            try:
                resp = self.client.generate(model=model, prompt=prompt, options=options)
                return resp.get("response", "").strip()
            except Exception as e:
                last_err = e
                logger.warning(f"ollama_generate_failed model={model} attempt={attempt+1} err={e}")
                time.sleep(0.5)
        logger.error(f"ollama_generate_failed_final model={model} err={last_err}")
        # Fallback: return prompt tail to avoid hard failure
        return prompt[-1000:]
