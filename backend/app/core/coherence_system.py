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
        self.character_tracker = defaultdict(dict)  # Track character attributes
        self.location_tracker = defaultdict(dict)   # Track location details
        self.object_tracker = defaultdict(dict)     # Track object properties
        self.mood_tracker = deque(maxlen=5)         # Track mood progression
        self.style_tracker = deque(maxlen=3)        # Track writing style consistency
        
        # Memory sliding window (keep last N beats for context)
        self.context_window = deque(maxlen=4)  # Last 4 beats
        self.story_bible = {}  # Permanent story elements
        
        # Semantic similarity tracking (simple word overlap for now)
        self.key_phrases = set()
        self.forbidden_repetitions = set()
        
    def initialize_story_bible(self, bible_data: dict):
        """Initialize with story bible from outline"""
        try:
            # Safe copy with type checking
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
                    # Ensure obj is string
                    obj_str = str(obj).strip() if obj else ""
                    if obj_str and len(obj_str) > 1:
                        self.object_tracker[obj_str] = {'introduced': False, 'last_mentioned': 0}
            
            logger.info(f"Story bible initialized with {len(self.object_tracker)} objects")
            
        except Exception as e:
            logger.error(f"Failed to initialize story bible: {e}")
            # Initialize with safe defaults
            self.story_bible = {'setting': 'unknown', 'key_objects': []}
            self.object_tracker = {}
    
    def add_beat_context(self, beat_id: int, beat_text: str, beat_info: dict):
        """Add new beat to context window and update tracking"""
        
        # Add to sliding context window
        beat_context = {
            'beat_id': beat_id,
            'text': beat_text,
            'word_count': len(beat_text.split()),
            'info': beat_info
        }
        self.context_window.append(beat_context)
        
        # Update entity tracking
        self._update_character_tracking(beat_text, beat_id)
        self._update_location_tracking(beat_text, beat_id)
        self._update_object_tracking(beat_text, beat_id)
        self._update_mood_tracking(beat_text, beat_info.get('mood_target', 8))
        self._update_style_tracking(beat_text)
        
        # Check for repetitions
        self._detect_repetitions(beat_text)
        
        logger.debug(f"Beat {beat_id} added to coherence system")
    
    def get_coherence_prompt_additions(self) -> str:
        """Generate additional prompt content to maintain coherence"""
        
        prompt_additions = []
        
        # Character consistency reminders
        if self.character_tracker:
            char_reminders = []
            for char, attrs in self.character_tracker.items():
                if attrs.get('last_mentioned', 0) > 0:  # Only if mentioned before
                    char_desc = f"{char}"
                    if 'description' in attrs:
                        char_desc += f" ({attrs['description']})"
                    char_reminders.append(char_desc)
            
            if char_reminders:
                prompt_additions.append(f"CHARACTERS ESTABLISHED: {', '.join(char_reminders)}")
        
        # Location consistency
        current_locations = [loc for loc, data in self.location_tracker.items() 
                           if data.get('currently_active', False)]
        if current_locations:
            prompt_additions.append(f"CURRENT SETTING: {', '.join(current_locations)}")
        
        # Object continuity
        active_objects = [obj for obj, data in self.object_tracker.items()
                         if data.get('last_mentioned', 0) >= len(self.context_window) - 2]
        if active_objects:
            prompt_additions.append(f"OBJECTS IN SCENE: {', '.join(active_objects)}")
        
        # Mood consistency
        if self.mood_tracker:
            avg_mood = sum(self.mood_tracker) / len(self.mood_tracker)
            prompt_additions.append(f"MOOD BASELINE: {avg_mood:.1f}/10 (maintain consistency)")
        
        # Style consistency warnings
        if len(self.style_tracker) >= 2:
            if self._detect_style_drift():
                prompt_additions.append("STYLE: Return to calm, flowing narrative style")
        
        # Repetition warnings
        if self.forbidden_repetitions:
            recent_reps = list(self.forbidden_repetitions)[-3:]  # Last 3 repetitions
            prompt_additions.append(f"AVOID REPEATING: {', '.join(recent_reps)}")
        
        return "\n".join(prompt_additions)
    
    def validate_beat_coherence(self, new_beat: str, beat_id: int) -> Dict[str, any]:
        """Validate a new beat for coherence issues"""
        
        issues = []
        warnings = []
        score = 10.0  # Start with perfect score
        
        # Check for immediate repetition
        if len(self.context_window) > 0:
            last_beat = self.context_window[-1]['text']
            repetition_score = self._calculate_repetition_overlap(last_beat, new_beat)
            if repetition_score > 0.4:  # 40% overlap is concerning
                issues.append(f"High repetition with previous beat: {repetition_score:.2f}")
                score -= 3.0
        
        # Check character consistency
        char_issues = self._validate_character_consistency(new_beat)
        if char_issues:
            issues.extend(char_issues)
            score -= len(char_issues) * 1.5
        
        # Check location consistency
        loc_issues = self._validate_location_consistency(new_beat)
        if loc_issues:
            issues.extend(loc_issues)
            score -= len(loc_issues) * 1.0
        
        # Check mood consistency
        mood_issue = self._validate_mood_consistency(new_beat)
        if mood_issue:
            warnings.append(mood_issue)
            score -= 0.5
        
        # Check for story bible violations
        bible_issues = self._validate_bible_consistency(new_beat)
        if bible_issues:
            issues.extend(bible_issues)
            score -= len(bible_issues) * 2.0
        
        return {
            'coherence_score': max(0.0, score),
            'issues': issues,
            'warnings': warnings,
            'needs_revision': score < 7.0,
            'severe_issues': score < 5.0
        }
    
    def suggest_beat_improvements(self, beat_text: str, coherence_result: dict) -> Optional[str]:
        """Suggest improvements for a beat with coherence issues"""
        
        if not coherence_result['needs_revision']:
            return None
        
        improvements = []
        
        # Address repetition
        if any('repetition' in issue.lower() for issue in coherence_result['issues']):
            improvements.append("use different words and phrases")
            improvements.append("introduce new sensory details")
        
        # Address character issues
        if any('character' in issue.lower() for issue in coherence_result['issues']):
            improvements.append("maintain established character traits")
        
        # Address location issues
        if any('location' in issue.lower() for issue in coherence_result['issues']):
            improvements.append("stay consistent with the established setting")
        
        if improvements:
            return f"Please revise this text to: {', '.join(improvements)}. {beat_text}"
        
        return f"Please improve the coherence and flow of: {beat_text}"
    
    def _extract_location_entities(self, setting_text: str):
        """Extract location entities from setting description"""
        # Simple entity extraction - could be enhanced with NER
        location_words = ['forest', 'beach', 'mountain', 'garden', 'lake', 'river', 
                         'meadow', 'valley', 'hill', 'path', 'cave', 'cottage']
        
        for word in location_words:
            if word in setting_text.lower():
                self.location_tracker[word] = {
                    'introduced': True,
                    'last_mentioned': 0,
                    'currently_active': True
                }
    
    def _update_character_tracking(self, text: str, beat_id: int):
        """Update character mentions and consistency"""
        try:
            # Simple character detection - look for 'you' and common names
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
        """Update location mentions"""
        for location in self.location_tracker.keys():
            if location in text.lower():
                self.location_tracker[location]['last_mentioned'] = beat_id
                self.location_tracker[location]['currently_active'] = True
    
    def _update_object_tracking(self, text: str, beat_id: int):
        """Update object mentions"""
        for obj in self.object_tracker.keys():
            if obj in text.lower():
                self.object_tracker[obj]['last_mentioned'] = beat_id
                if not self.object_tracker[obj]['introduced']:
                    self.object_tracker[obj]['introduced'] = True
    
    def _update_mood_tracking(self, text: str, target_mood: float):
        """Update mood progression tracking"""
        # Simple mood detection based on word sentiment
        positive_words = ['peaceful', 'calm', 'gentle', 'warm', 'soft', 'beautiful', 'serene']
        negative_words = ['harsh', 'cold', 'rough', 'loud', 'sharp', 'bitter']
        
        pos_count = sum(1 for word in positive_words if word in text.lower())
        neg_count = sum(1 for word in negative_words if word in text.lower())
        
        # Estimate mood based on word sentiment
        estimated_mood = target_mood + (pos_count * 0.5) - (neg_count * 1.0)
        estimated_mood = max(1.0, min(10.0, estimated_mood))
        
        self.mood_tracker.append(estimated_mood)
    
    def _update_style_tracking(self, text: str):
        """Track writing style consistency"""
        # Analyze sentence structure
        sentences = text.split('.')
        avg_sentence_length = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
        
        # Count descriptive elements
        descriptive_words = ['gently', 'slowly', 'softly', 'quietly', 'peacefully']
        descriptive_count = sum(1 for word in descriptive_words if word in text.lower())
        
        style_metrics = {
            'avg_sentence_length': avg_sentence_length,
            'descriptive_density': descriptive_count / max(len(text.split()), 1),
            'paragraph_count': len(text.split('\n\n'))
        }
        
        self.style_tracker.append(style_metrics)
    
    def _detect_repetitions(self, text: str):
        """Detect and track repetitive phrases"""
        try:
            # Extract phrases (3-4 words)
            words = text.lower().split()
            
            for i in range(len(words) - 2):
                phrase = ' '.join(words[i:i+3])
                # Assicurati che phrase sia sempre string
                phrase = str(phrase).strip()
                
                if phrase and len(phrase) > 5:  # Solo frasi significative
                    if phrase not in self.key_phrases:
                        self.key_phrases.add(phrase)
                    else:
                        self.forbidden_repetitions.add(phrase)
            
            # Limit memory usage
            if len(self.key_phrases) > 500:
                # Convert to list, sort, and keep newest
                phrases_list = list(self.key_phrases)
                self.key_phrases = set(phrases_list[-400:])  # Keep last 400
                
        except Exception as e:
            logger.warning(f"Repetition detection failed: {e}")
            # Initialize empty sets if corrupted
            self.key_phrases = set()
            self.forbidden_repetitions = set()
    
    def _detect_style_drift(self) -> bool:
        """Detect if writing style is drifting from established pattern"""
        if len(self.style_tracker) < 2:
            return False
        
        # Compare current vs previous style metrics
        current = self.style_tracker[-1]
        previous = self.style_tracker[-2]
        
        # Check for significant changes
        length_change = abs(current['avg_sentence_length'] - previous['avg_sentence_length'])
        desc_change = abs(current['descriptive_density'] - previous['descriptive_density'])
        
        return length_change > 5.0 or desc_change > 0.1
    
    def _calculate_repetition_overlap(self, text1: str, text2: str) -> float:
        """Calculate word overlap between two texts"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        overlap = len(words1.intersection(words2))
        total = len(words1.union(words2))
        
        return overlap / total if total > 0 else 0.0
    
    def _validate_character_consistency(self, text: str) -> List[str]:
        """Check for character consistency issues"""
        issues = []
        # Implementation would check for character trait consistency
        # For now, just basic checks
        return issues
    
    def _validate_location_consistency(self, text: str) -> List[str]:
        """Check for location consistency issues"""
        issues = []
        # Check if new locations are introduced without context
        # Implementation would be more sophisticated
        return issues
    
    def _validate_mood_consistency(self, text: str) -> Optional[str]:
        """Check for mood consistency"""
        if not self.mood_tracker:
            return None
        
        # Simple mood validation
        recent_avg = sum(list(self.mood_tracker)[-2:]) / 2 if len(self.mood_tracker) >= 2 else self.mood_tracker[-1]
        
        # Check for jarring mood shifts in sleep content
        stress_words = ['suddenly', 'shocking', 'loud', 'fast', 'quickly']
        if any(word in text.lower() for word in stress_words):
            return "Text contains potentially jarring elements for sleep content"
        
        return None
    
    def _validate_bible_consistency(self, text: str) -> List[str]:
        """Check consistency with story bible"""
        issues = []
        
        # Check time consistency
        if 'time_of_day' in self.story_bible:
            bible_time = self.story_bible['time_of_day']
            conflicting_times = {
                'dawn': ['midnight', 'evening', 'dusk'],
                'dusk': ['morning', 'dawn', 'noon'],
                'night': ['morning', 'noon', 'daylight']
            }
            
            if bible_time in conflicting_times:
                for conflict in conflicting_times[bible_time]:
                    if conflict in text.lower():
                        issues.append(f"Time inconsistency: story is set at {bible_time} but mentions {conflict}")
        
        return issues
    
    def get_memory_stats(self) -> Dict[str, int]:
        """Get memory usage statistics"""
        return {
            'context_beats': len(self.context_window),
            'tracked_characters': len(self.character_tracker),
            'tracked_locations': len(self.location_tracker),
            'tracked_objects': len(self.object_tracker),
            'key_phrases': len(self.key_phrases),
            'forbidden_repetitions': len(self.forbidden_repetitions)
        }