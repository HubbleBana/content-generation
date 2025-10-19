from typing import Dict, List, Optional
import structlog

import logging
logger = logging.getLogger(__name__)


class MemorySystem:
    def __init__(self, story_bible: dict):
        self.story_bible = story_bible
        self.entities = {}
        self.timeline = []
        self.beats_text = []
        
        for obj in story_bible.get("key_objects", []):
            self.entities[obj] = {
                "type": "object",
                "mentions": [],
                "first_beat": None
            }
        
        logger.info(f"memory_initialized entities={len(self.entities)}")
    
    def get_context_for_beat(self, beat_id: int) -> dict:
        return {
            "story_bible": self.story_bible,
            "last_500_words": self._get_last_text(500),
            "active_entities": list(self.entities.keys()),
            "previous_beats_summary": self._summarize_last_beats(3),
            "beat_count": len(self.beats_text)
        }
    
    def add_beat(self, beat_id: int, text: str):
        self.beats_text.append(text)
        self.timeline.append(beat_id)
        self._extract_entities(text)
        logger.debug(f"beat_added , beat_id={beat_id}, total={len(self.beats_text)}")
    
    def _get_last_text(self, words: int) -> str:
        if not self.beats_text:
            return ""
        full_text = " ".join(self.beats_text)
        return " ".join(full_text.split()[-words:])
    
    def _summarize_last_beats(self, count: int) -> str:
        if not self.beats_text:
            return "This is the beginning of the story."
        recent = self.beats_text[-count:]
        return " ".join(recent)
    
    def _extract_entities(self, text: str):
        for entity_name in self.entities:
            if entity_name.lower() in text.lower():
                self.entities[entity_name]["mentions"].append(len(self.beats_text))
    
    def get_metrics(self) -> dict:
        return {
            "total_beats": len(self.beats_text),
            "total_words": sum(len(beat.split()) for beat in self.beats_text),
            "entities_tracked": len(self.entities)
        }
