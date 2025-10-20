import ollama
import numpy as np
import re
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict, deque
import logging
from app.core.config import settings
from app.core.embodiment_destination_validators import EmbodimentValidator, DestinationValidator

logger = logging.getLogger(__name__)

class CoherenceSystem:
    """Advanced coherence system with embodiment & destination scoring"""
    
    def __init__(self):
        self.client = ollama.Client(host=settings.OLLAMA_URL)
        self.character_tracker: Dict[str, dict] = defaultdict(dict)
        self.location_tracker: Dict[str, dict] = defaultdict(dict)
        self.object_tracker: Dict[str, dict] = defaultdict(dict)
        self.mood_tracker = deque(maxlen=5)
        self.style_tracker = deque(maxlen=3)
        self.context_window = deque(maxlen=4)
        self.story_bible: Dict[str, any] = {}
        self.key_phrases: Set[str] = set()
        self.forbidden_repetitions: Set[str] = set()
        # New validators
        self._embodiment_validator = EmbodimentValidator()
        self._destination_validator = DestinationValidator()
    
    def initialize_story_bible(self, bible_data: dict):
        try:
            self.story_bible = {}
            if isinstance(bible_data, dict):
                for key, value in bible_data.items():
                    self.story_bible[str(key)] = value
            setting = self.story_bible.get('setting', '')
            if isinstance(setting, str) and setting:
                self._extract_location_entities(setting)
            key_objects = self.story_bible.get('key_objects', [])
            if isinstance(key_objects, list):
                for obj in key_objects:
                    obj_str = str(obj).strip() if obj is not None else ""
                    if obj_str:
                        self.object_tracker[obj_str] = {'introduced': False, 'last_mentioned': 0}
            logger.info(f"Story bible initialized with {len(self.object_tracker)} objects")
        except Exception as e:
            logger.error(f"Failed to initialize story bible: {e}")
            self.story_bible = {'setting': 'unknown', 'key_objects': []}
            self.object_tracker = defaultdict(dict)
    
    def add_beat_context(self, beat_id: int, beat_text: str, beat_info: dict):
        try:
            beat_context = {
                'beat_id': int(beat_id),
                'text': str(beat_text or ''),
                'word_count': len((beat_text or '').split()),
                'info': beat_info if isinstance(beat_info, dict) else {}
            }
            self.context_window.append(beat_context)
            self._update_character_tracking(beat_context['text'], beat_context['beat_id'])
            self._update_location_tracking(beat_context['text'], beat_context['beat_id'])
            self._update_object_tracking(beat_context['text'], beat_context['beat_id'])
            self._update_mood_tracking(beat_context['text'], beat_info.get('mood_target', 8) if isinstance(beat_info, dict) else 8)
            self._update_style_tracking(beat_context['text'])
            self._detect_repetitions(beat_context['text'])
            logger.debug(f"Beat {beat_context['beat_id']} added to coherence system")
        except Exception as e:
            logger.warning(f"add_beat_context failed: {e}")
    
    def get_coherence_prompt_additions(self) -> str:
        prompt_additions: List[str] = []
        try:
            char_reminders = []
            for char, attrs in self.character_tracker.items():
                if attrs.get('last_mentioned', 0) > 0:
                    char_desc = f"{char}"
                    if 'description' in attrs and isinstance(attrs['description'], str):
                        char_desc += f" ({attrs['description']})"
                    char_reminders.append(char_desc)
            if char_reminders:
                prompt_additions.append(f"CHARACTERS ESTABLISHED: {', '.join(char_reminders)}")
        except Exception:
            pass
        try:
            current_locations = [loc for loc, data in self.location_tracker.items() if data.get('currently_active', False)]
            if current_locations:
                prompt_additions.append(f"CURRENT SETTING: {', '.join(current_locations)}")
        except Exception:
            pass
        try:
            active_objects = [obj for obj, data in self.object_tracker.items() if data.get('last_mentioned', 0) >= len(self.context_window) - 2]
            if active_objects:
                prompt_additions.append(f"OBJECTS IN SCENE: {', '.join(active_objects)}")
        except Exception:
            pass
        try:
            if self.mood_tracker:
                avg_mood = sum(self.mood_tracker) / len(self.mood_tracker)
                prompt_additions.append(f"MOOD BASELINE: {avg_mood:.1f}/10 (maintain consistency)")
        except Exception:
            pass
        try:
            if len(self.style_tracker) >= 2 and self._detect_style_drift():
                prompt_additions.append("STYLE: Return to calm, flowing narrative style")
        except Exception:
            pass
        try:
            if self.forbidden_repetitions:
                recent_reps = list(self.forbidden_repetitions)[-3:]
                prompt_additions.append(f"AVOID REPEATING: {', '.join(recent_reps)}")
        except Exception:
            pass
        return "\n".join(prompt_additions)
    
    def validate_beat_coherence(self, new_beat: str, beat_id: int) -> Dict[str, any]:
        issues: List[str] = []
        warnings: List[str] = []
        score = 10.0
        try:
            last_beat_text = self.context_window[-1]['text'] if len(self.context_window) > 0 else ''
            repetition_score = self._calculate_repetition_overlap(last_beat_text, new_beat)
            if repetition_score > 0.4:
                issues.append(f"High repetition with previous beat: {repetition_score:.2f}")
                score -= 3.0
        except Exception:
            pass
        try:
            char_issues = self._validate_character_consistency(new_beat)
            if char_issues:
                issues.extend(char_issues)
                score -= len(char_issues) * 1.5
        except Exception:
            pass
        try:
            loc_issues = self._validate_location_consistency(new_beat)
            if loc_issues:
                issues.extend(loc_issues)
                score -= len(loc_issues) * 1.0
        except Exception:
            pass
        mood_issue = self._validate_mood_consistency(new_beat)
        if mood_issue:
            warnings.append(mood_issue)
            score -= 0.5
        try:
            bible_issues = self._validate_bible_consistency(new_beat)
            if bible_issues:
                issues.extend(bible_issues)
                score -= len(bible_issues) * 2.0
        except Exception:
            pass
        return {'coherence_score': max(0.0, score),'issues': issues,'warnings': warnings,'needs_revision': score < 7.0,'severe_issues': score < 5.0}
    
    # NEW: Embodiment & Destination stats directly
    def compute_embodiment_destination_stats(self, beats: List[Dict[str, str]]) -> Dict[str, any]:
        scores = [self._embodiment_validator.validate_beat(b.get('text',''))['score'] for b in beats]
        dest = self._destination_validator.validate_destination_arc(beats)
        return {
            'embodiment_score_avg': (sum(scores)/max(1,len(scores))) if scores else 0.0,
            'destination_completion': bool(dest.get('ok', False)),
            'destination_missing': dest.get('missing', [])
        }

    # === existing helper methods unchanged ===
    def _extract_location_entities(self, setting_text: str):
        location_words = ['forest', 'beach', 'mountain', 'garden', 'lake', 'river','meadow', 'valley', 'hill', 'path', 'cave', 'cottage']
        for word in location_words:
            if isinstance(setting_text, str) and word in setting_text.lower():
                self.location_tracker[word] = {'introduced': True,'last_mentioned': 0,'currently_active': True}
    # ... other helper methods remain the same ...
