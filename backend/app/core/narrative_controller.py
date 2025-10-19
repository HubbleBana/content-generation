import ollama
from typing import Optional, Callable, List, Dict
import json
import re

from app.core.config import settings
from app.core.memory_system import MemorySystem
from app.core.coherence_system import CoherenceSystem
from app.core.prompts import BEAT_GENERATION_PROMPT

import logging
logger = logging.getLogger(__name__)

class NarrativeController:
    """Controls per-beat targets, opener variation, and progression waypoints"""
    def __init__(self, total_beats: int, target_words_total: int):
        self.total_beats = max(1, total_beats)
        self.target_words_total = max(200, target_words_total)
        self.opener_blacklist = [
            "As you ", "You breathe", "You take", "As your", "You step",
        ]
        self.progress_waypoints = []  # e.g., [["path"],["rows of vines"],["cellar"],["stream"],["inside cottage"]]
        self._targets = self._distribute_targets_progressive()
    
    def set_waypoints(self, waypoints: List[List[str]]):
        self.progress_waypoints = waypoints or []
    
    def _distribute_targets_progressive(self) -> List[int]:
        base = self.target_words_total // self.total_beats
        targets = []
        for i in range(self.total_beats):
            # Slight taper for sleep effect (start a bit higher, end a bit lower)
            multiplier = 1.15 - (0.30 * i / max(1, self.total_beats - 1))
            targets.append(int(base * multiplier))
        # Normalize to exact total
        diff = self.target_words_total - sum(targets)
        if diff != 0:
            step = 1 if diff > 0 else -1
            idx = 0
            while diff != 0:
                targets[idx % self.total_beats] += step
                diff -= step
                idx += 1
        return targets
    
    def target_for(self, beat_index: int) -> int:
        return self._targets[min(max(beat_index-1, 0), self.total_beats-1)]
    
    def vary_openers(self, text: str) -> str:
        if not text:
            return text
        for bad in self.opener_blacklist:
            if text.startswith(bad):
                # Replace with gentler ambient-first opening
                replacements = [
                    "The air carries ",
                    "From the distance, ",
                    "Around you, ",
                    "Along the path, ",
                    "In the hush, ",
                ]
                # Pick first deterministic replacement to keep reproducibility
                return text.replace(bad, replacements[0], 1)
        return text
    
    def enforce_exact_length(self, text: str, target_words: int, client: ollama.Client) -> str:
        words = len(text.split())
        if abs(words - target_words) <= int(0.10 * target_words):
            return text
        if words < target_words:
            prompt = (
                f"Expand to EXACTLY {target_words} words by adding gentle sensory details, "
                f"keep the same style and content. Original text:\n{text}\n\nRewritten (EXACT {target_words} words):"
            )
        else:
            prompt = (
                f"Condense to EXACTLY {target_words} words while preserving essence and flow. "
                f"Avoid lists and keep calm pacing. Original text:\n{text}\n\nRewritten (EXACT {target_words} words):"
            )
        try:
            resp = client.generate(model=settings.MODEL_NAME, prompt=prompt, options={'temperature': 0.4, 'num_predict': target_words*2})
            out = resp['response'].strip()
            return out
        except Exception as e:
            logger.warning(f"length_enforce_failed: {e}")
            return text

