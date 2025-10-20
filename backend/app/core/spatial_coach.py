import ollama
import time
import json
import asyncio
from typing import Dict, Optional, List, Tuple, Any
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class SpatialCoach:
    """Optional micro-brief generator to stabilize long-journey regularity."""
    def __init__(self, host: str = None, model: str = None):
        self.client = ollama.Client(host=host or settings.OLLAMA_URL)
        self.model = model or settings.DEFAULT_MODELS.get('reasoner', 'deepseek-r1:8b')

    def brief(self, text: str, waypoint: str, phase: str) -> str:
        prompt = f"""You are a spatial journey coach. Create a 1-2 sentence brief that enforces: 
- second person movement (one movement verb)
- one consequent perception (corporeal) + one environmental
- one spatial transition connector coherent with phase ({phase})
- if phase is arrival: include settling + permission to rest

WAYPOINT: {waypoint}
TEXT:
{text}

Return ONLY the brief, no preface:
"""
        try:
            r = self.client.generate(model=self.model, prompt=prompt, options={"temperature":0.2, "num_predict":150})
            return (r.get('response','') or '').strip()
        except Exception as e:
            logger.warning(f"SpatialCoach brief failed: {e}")
            return "Maintain 2nd person movement, consequent perceptions, a spatial transition, and if arriving, settle and invite rest."
