import ollama
import numpy as np
import re
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict, deque
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class CoherenceSystem:
    """Advanced coherence system to improve LLama 3.1 8B consistency in long stories"""
    
    def __init__(self):
        self.client = ollama.Client(host=settings.OLLAMA_URL)
        
        # Coherence tracking
        self.character_tracker: Dict[str, dict] = defaultdict(dict)  # Track character attributes
        self.location_tracker: Dict[str, dict] = defaultdict(dict)   # Track location details
        self.object_tracker: Dict[str, dict] = defaultdict(dict)     # Track object properties
        self.mood_tracker = deque(maxlen=5)         # Track mood progression
        self.style_tracker = deque(maxlen=3)        # Track writing style consistency
        
        # Memory sliding window (keep last N beats for context)
        self.context_window = deque(maxlen=4)  # Last 4 beats
        self.story_bible: Dict[str, any] = {}  # Permanent story elements
        
        # Semantic similarity tracking (simple word overlap for now)
        self.key_phrases: Set[str] = set()
        self.forbidden_repetitions: Set[str] = set()
        
    def initialize_story_bible(self, bible_data: dict):
        """Initialize with story bible from outline (safe types only)"""
        try:
            # Safe copy with primitive keys
            self.story_bible = {}
            if isinstance(bible_data, dict):
                for key, value in bible_data.items():
                    self.story_bible[str(key)] = value
            
            # Extract key entities from bible
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
        """Add new beat to context window and update tracking"""
        try:
            beat_context = {
                'beat_id': int(beat_id),
                'text': str(beat_text or ''),
                'word_count': len((beat_text or '').split()),
                'info': beat_info if isinstance(beat_info, dict) else {}
            }
            self.context_window.append(beat_context)
            
            # Update entity tracking
            self._update_character_tracking(beat_context['text'], beat_context['beat_id'])
            self._update_location_tracking(beat_context['text'], beat_context['beat_id'])
            self._update_object_tracking(beat_context['text'], beat_context['beat_id'])
            self._update_mood_tracking(beat_context['text'], beat_info.get('mood_target', 8) if isinstance(beat_info, dict) else 8)
            self._update_style_tracking(beat_context['text'])
            
            # Check for repetitions
            self._detect_repetitions(beat_context['text'])
            
            logger.debug(f"Beat {beat_context['beat_id']} added to coherence system")
        except Exception as e:
            logger.warning(f"add_beat_context failed: {e}")
    
    def get_coherence_prompt_additions(self) -> str:
        """Generate additional prompt content to maintain coherence"""
        prompt_additions: List[str] = []
        
        # Character consistency reminders
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
        except Exception as e:
            logger.debug(f"character reminders failed: {e}")
        
        # Location consistency
        try:
            current_locations = [loc for loc, data in self.location_tracker.items() if data.get('currently_active', False)]
            if current_locations:
                prompt_additions.append(f"CURRENT SETTING: {', '.join(current_locations)}")
        except Exception as e:
            logger.debug(f"location reminders failed: {e}")
        
        # Object continuity
        try:
            active_objects = [obj for obj, data in self.object_tracker.items() if data.get('last_mentioned', 0) >= len(self.context_window) - 2]
            if active_objects:
                prompt_additions.append(f"OBJECTS IN SCENE: {', '.join(active_objects)}")
        except Exception as e:
            logger.debug(f"object reminders failed: {e}")
        
        # Mood consistency
        try:
            if self.mood_tracker:
                avg_mood = sum(self.mood_tracker) / len(self.mood_tracker)
                prompt_additions.append(f"MOOD BASELINE: {avg_mood:.1f}/10 (maintain consistency)")
        except Exception as e:
            logger.debug(f"mood reminders failed: {e}")
        
        # Style consistency warnings
        try:
            if len(self.style_tracker) >= 2 and self._detect_style_drift():
                prompt_additions.append("STYLE: Return to calm, flowing narrative style")
        except Exception as e:
            logger.debug(f"style drift check failed: {e}")
        
        # Repetition warnings
        try:
            if self.forbidden_repetitions:
                recent_reps = list(self.forbidden_repetitions)[-3:]
                prompt_additions.append(f"AVOID REPEATING: {', '.join(recent_reps)}")
        except Exception as e:
            logger.debug(f"repetition reminders failed: {e}")
        
        return "\n".join(prompt_additions)
    
    def validate_beat_coherence(self, new_beat: str, beat_id: int) -> Dict[str, any]:
        """Validate a new beat for coherence issues"""
        issues: List[str] = []
        warnings: List[str] = []
        score = 10.0
        
        try:
            last_beat_text = self.context_window[-1]['text'] if len(self.context_window) > 0 else ''
            repetition_score = self._calculate_repetition_overlap(last_beat_text, new_beat)
            if repetition_score > 0.4:
                issues.append(f"High repetition with previous beat: {repetition_score:.2f}")
                score -= 3.0
        except Exception as e:
            logger.debug(f"repetition check failed: {e}")
        
        try:
            char_issues = self._validate_character_consistency(new_beat)
            if char_issues:
                issues.extend(char_issues)
                score -= len(char_issues) * 1.5
        except Exception as e:
            logger.debug(f"character consistency check failed: {e}")
        
        try:
            loc_issues = self._validate_location_consistency(new_beat)
            if loc_issues:
                issues.extend(loc_issues)
                score -= len(loc_issues) * 1.0
        except Exception as e:
            logger.debug(f"location consistency check failed: {e}")
        
        mood_issue = self._validate_mood_consistency(new_beat)
        if mood_issue:
            warnings.append(mood_issue)
            score -= 0.5
        
        try:
            bible_issues = self._validate_bible_consistency(new_beat)
            if bible_issues:
                issues.extend(bible_issues)
                score -= len(bible_issues) * 2.0
        except Exception as e:
            logger.debug(f"bible consistency check failed: {e}")
        
        return {
            'coherence_score': max(0.0, score),
            'issues': issues,
            'warnings': warnings,
            'needs_revision': score < 7.0,
            'severe_issues': score < 5.0
        }
    
    def suggest_beat_improvements(self, beat_text: str, coherence_result: dict) -> Optional[str]:
        if not coherence_result.get('needs_revision'):
            return None
        improvements: List[str] = []
        if any('repetition' in issue.lower() for issue in coherence_result.get('issues', [])):
            improvements.append("use different words and phrases")
            improvements.append("introduce new sensory details")
        if any('character' in issue.lower() for issue in coherence_result.get('issues', [])):
            improvements.append("maintain established character traits")
        if any('location' in issue.lower() for issue in coherence_result.get('issues', [])):
            improvements.append("stay consistent with the established setting")
        if improvements:
            return f"Please revise this text to: {', '.join(improvements)}. {beat_text}"
        return f"Please improve the coherence and flow of: {beat_text}"
    
    def _extract_location_entities(self, setting_text: str):
        location_words = ['forest', 'beach', 'mountain', 'garden', 'lake', 'river','meadow', 'valley', 'hill', 'path', 'cave', 'cottage']
        for word in location_words:
            if isinstance(setting_text, str) and word in setting_text.lower():
                self.location_tracker[word] = {'introduced': True,'last_mentioned': 0,'currently_active': True}
    
    def _update_character_tracking(self, text: str, beat_id: int):
        try:
            characters = ['you', 'your']
            text_lower = text.lower() if isinstance(text, str) else ""
            for char in characters:
                char_str = str(char).strip()
                if char_str and char_str in text_lower:
                    if char_str not in self.character_tracker:
                        self.character_tracker[char_str] = {'introduced': True}
                    self.character_tracker[char_str]['last_mentioned'] = int(beat_id)
        except Exception as e:
            logger.warning(f"Character tracking failed: {e}")
    
    def _update_location_tracking(self, text: str, beat_id: int):
        try:
            for location in list(self.location_tracker.keys()):
                if location in (text.lower() if isinstance(text, str) else ""):
                    self.location_tracker[location]['last_mentioned'] = int(beat_id)
                    self.location_tracker[location]['currently_active'] = True
        except Exception as e:
            logger.debug(f"Location tracking failed: {e}")
    
    def _update_object_tracking(self, text: str, beat_id: int):
        try:
            for obj in list(self.object_tracker.keys()):
                if obj in (text.lower() if isinstance(text, str) else ""):
                    self.object_tracker[obj]['last_mentioned'] = int(beat_id)
                    if not self.object_tracker[obj].get('introduced'):
                        self.object_tracker[obj]['introduced'] = True
        except Exception as e:
            logger.debug(f"Object tracking failed: {e}")
    
    def _update_mood_tracking(self, text: str, target_mood: float):
        positive_words = ['peaceful', 'calm', 'gentle', 'warm', 'soft', 'beautiful', 'serene']
        negative_words = ['harsh', 'cold', 'rough', 'loud', 'sharp', 'bitter']
        text_lower = text.lower() if isinstance(text, str) else ""
        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)
        estimated_mood = target_mood + (pos_count * 0.5) - (neg_count * 1.0)
        estimated_mood = float(max(1.0, min(10.0, estimated_mood)))
        self.mood_tracker.append(estimated_mood)
    
    def _update_style_tracking(self, text: str):
        sentences = (text or '').split('.')
        avg_sentence_length = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
        descriptive_words = ['gently', 'slowly', 'softly', 'quietly', 'peacefully']
        text_lower = text.lower() if isinstance(text, str) else ""
        descriptive_count = sum(1 for word in descriptive_words if word in text_lower)
        style_metrics = {'avg_sentence_length': avg_sentence_length,'descriptive_density': descriptive_count / max(len((text or '').split()), 1),'paragraph_count': len((text or '').split('\n\n'))}
        self.style_tracker.append(style_metrics)
    
    def _detect_repetitions(self, text: str):
        try:
            words = (text or '').lower().split()
            for i in range(len(words) - 2):
                phrase = ' '.join(words[i:i+3]).strip()
                if phrase and len(phrase) > 5:
                    if phrase not in self.key_phrases:
                        self.key_phrases.add(phrase)
                    else:
                        self.forbidden_repetitions.add(phrase)
            if len(self.key_phrases) > 500:
                phrases_list = list(self.key_phrases)
                self.key_phrases = set(phrases_list[-400:])
        except Exception as e:
            logger.warning(f"Repetition detection failed: {e}")
            self.key_phrases = set()
            self.forbidden_repetitions = set()
    
    def _detect_style_drift(self) -> bool:
        if len(self.style_tracker) < 2:
            return False
        current = self.style_tracker[-1]
        previous = self.style_tracker[-2]
        length_change = abs(current['avg_sentence_length'] - previous['avg_sentence_length'])
        desc_change = abs(current['descriptive_density'] - previous['descriptive_density'])
        return length_change > 5.0 or desc_change > 0.1
    
    def _calculate_repetition_overlap(self, text1: str, text2: str) -> float:
        words1 = set((text1 or '').lower().split())
        words2 = set((text2 or '').lower().split())
        if not words1 or not words2:
            return 0.0
        overlap = len(words1.intersection(words2))
        total = len(words1.union(words2))
        return overlap / total if total > 0 else 0.0
    
    def _validate_character_consistency(self, text: str) -> List[str]:
        return []
    
    def _validate_location_consistency(self, text: str) -> List[str]:
        return []
    
    def _validate_mood_consistency(self, text: str) -> Optional[str]:
        if not self.mood_tracker:
            return None
        stress_words = ['suddenly', 'shocking', 'loud', 'fast,', 'quickly']
        text_lower = text.lower() if isinstance(text, str) else ""
        if any(word in text_lower for word in stress_words):
            return "Text contains potentially jarring elements for sleep content"
        return None
    
    def _validate_bible_consistency(self, text: str) -> List[str]:
        issues: List[str] = []
        try:
            if 'time_of_day' in self.story_bible:
                bible_time = self.story_bible['time_of_day']
                conflicting_times = {'dawn': ['midnight', 'evening', 'dusk'],'dusk': ['morning', 'dawn', 'noon'],'night': ['morning', 'noon', 'daylight']}
                text_lower = text.lower() if isinstance(text, str) else ""
                if bible_time in conflicting_times:
                    for conflict in conflicting_times[bible_time]:
                        if conflict in text_lower:
                            issues.append(f"Time inconsistency: story is set at {bible_time} but mentions {conflict}")
        except Exception as e:
            logger.debug(f"bible consistency failed: {e}")
        return issues
    
    def get_memory_stats(self) -> Dict[str, int]:
        return {'context_beats': len(self.context_window),'tracked_characters': len(self.character_tracker),'tracked_locations': len(self.location_tracker),'tracked_objects': len(self.object_tracker),'key_phrases': len(self.key_phrases),'forbidden_repetitions': len(self.forbidden_repetitions)}
