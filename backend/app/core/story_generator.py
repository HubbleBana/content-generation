import ollama
from typing import Optional, Callable, Dict, List, Any
import json
import re
import asyncio
from datetime import datetime

from app.core.config import settings
from app.core.memory_system import MemorySystem
from app.core.coherence_system import CoherenceSystem
from app.core.narrative_controller import NarrativeController
from app.core.model_orchestrator import EnhancedModelOrchestrator
from app.core.prompts import THEME_ANALYSIS_PROMPT, OUTLINE_GENERATION_PROMPT, BEAT_GENERATION_PROMPT

import logging
logger = logging.getLogger(__name__)

class StoryGenerator:
    """Enhanced Story Generator with multi-model support and quality features."""
    
    def __init__(self,
                 target_language: str = "en",
                 translation_quality: str = "high", 
                 models: Optional[dict] = None,
                 use_reasoner: bool = True,
                 use_polish: bool = True,
                 tts_markers: bool = False,
                 strict_schema: bool = False):
        
        self.client = ollama.Client(host=settings.OLLAMA_URL)
        
        # Enhanced orchestrator with all new features
        self.orchestrator = EnhancedModelOrchestrator(
            generator=models.get('generator') if models else None,
            reasoner=models.get('reasoner') if models else None,
            polisher=models.get('polisher') if models else None,
            use_reasoner=use_reasoner,
            use_polish=use_polish,
            tts_markers=tts_markers,
            strict_schema=strict_schema
        )
        
        # Enhanced systems
        self.coherence_system = CoherenceSystem()
        self.tts_markers = tts_markers
        self.strict_schema = strict_schema
        
        logger.info(f"Enhanced StoryGenerator initialized - Models: {models or 'defaults'}, TTS: {tts_markers}, Schema: {strict_schema}")
    
    async def generate_enhanced_story(self, 
                                    theme: str, 
                                    duration: int = 45, 
                                    description: Optional[str] = None,
                                    job_id: Optional[str] = None,
                                    update_callback: Optional[Callable] = None,
                                    custom_waypoints: Optional[List[str]] = None) -> Dict[str, Any]:
        """Enhanced story generation with all new quality features."""
        
        start_time = datetime.now()
        
        def update(progress: float, step: str, step_num: int = 0, stage_metrics=None):
            if update_callback:
                update_callback(progress, step, step_num, stage_metrics)
            logger.info(f'Enhanced progress: {progress}% - {step}')
        
        # 1) Enhanced Theme Analysis
        update(5, 'Analyzing theme with enhanced AI understanding...', 1)
        enriched_theme = await self._analyze_theme_enhanced(theme, description)
        
        update(10, 'Generating enhanced story outline with waypoints...', 2)
        outline = await self._generate_outline_enhanced(enriched_theme, duration, custom_waypoints)
        
        # 2) Enhanced Initialization
        update(15, 'Initializing enhanced coherence and memory systems...', 3)
        memory = MemorySystem(outline.get('story_bible', {}))
        self.coherence_system.initialize_story_bible(outline.get('story_bible', {}))
        
        acts = outline.get('acts', [])
        total_beats = sum(len(act.get('beats', [])) for act in acts)
        target_words_total = duration * settings.TARGET_WPM
        
        controller = NarrativeController(total_beats=total_beats, target_words_total=target_words_total)
        
        # 3) Enhanced Multi-Model Generation
        update(20, 'Beginning enhanced multi-model story generation...', 4)
        
        # Prepare setting for waypoint extraction
        setting_info = {
            "theme": enriched_theme,
            "outline": outline,
            "custom_waypoints": custom_waypoints
        }
        
        # Use enhanced orchestrator for full story generation
        enhanced_result = await self.orchestrator.generate_enhanced_story(
            prompt=self._create_base_prompt(enriched_theme, outline),
            beats_target=total_beats,
            setting=setting_info,
            options={"temperature": settings.MODEL_TEMPERATURE}
        )
        
        # Update progress as story generates
        update(70, 'Applying final quality enhancements...', 5)
        
        # 4) Enhanced Final Processing
        final_story_text = enhanced_result["story_text"]
        
        # Additional processing if needed
        if not self.tts_markers and not self.strict_schema:
            # Apply traditional final polish for backward compatibility
            final_story_text = self._final_polish(final_story_text)
        
        update(90, 'Calculating enhanced metrics and statistics...', 6)
        
        # 5) Enhanced Metrics and Results
        generation_time = (datetime.now() - start_time).total_seconds()
        english_word_count = len(final_story_text.split())
        target_words = target_words_total
        accuracy_percent = round(abs(english_word_count - target_words) / max(1, target_words) * 100, 2)
        duration_estimate = round(english_word_count / settings.TARGET_WPM, 1)
        
        # Combine traditional and enhanced metrics
        combined_metrics = {
            # Traditional metrics (for compatibility)
            'english_word_count': english_word_count,
            'target_words': target_words,
            'accuracy_percent': accuracy_percent,
            'duration_estimate_minutes': duration_estimate,
            'beats_generated': total_beats,
            'target_language': 'en',
            
            # Enhanced metrics
            'generation_time_seconds': generation_time,
            'enhanced_features_used': {
                'multi_model': True,
                'sensory_rotation': settings.SENSORY_ROTATION_ENABLED,
                'waypoints': bool(custom_waypoints),
                'mixed_reward_proxy': True,
                'recursive_planning': settings.BEAT_PLANNING_ENABLED,
                'sleep_taper': settings.SLEEP_TAPER_ENABLED,
                'tts_markers': self.tts_markers,
                'strict_schema': self.strict_schema
            },
            
            # Stage-specific metrics from orchestrator
            **enhanced_result["metrics"]
        }
        
        # Enhanced result structure
        result = {
            'story_text': final_story_text,
            'outline': enhanced_result.get("outline", outline),
            'metrics': combined_metrics,
            'coherence_stats': enhanced_result["coherence_stats"],
            'memory_stats': enhanced_result["memory_stats"],
            'generation_info': {
                'models_used': {
                    'generator': self.orchestrator.generator_name,
                    'reasoner': self.orchestrator.reasoner_name if self.orchestrator.use_reasoner else None,
                    'polisher': self.orchestrator.polisher_name if self.orchestrator.use_polish else None
                },
                'features_enabled': combined_metrics['enhanced_features_used'],
                'generation_timestamp': start_time.isoformat(),
                'total_generation_time': generation_time
            }
        }
        
        # Add strict schema if enabled
        if self.strict_schema and "beats_schema" in enhanced_result:
            result["beats_schema"] = enhanced_result["beats_schema"]
        
        update(100, '✅ Enhanced generation complete!', 8)
        return result
    
    # Legacy method for backward compatibility
    async def generate_full_story(self, theme: str, duration: int = 45, description: Optional[str] = None, job_id: Optional[str] = None, update_callback: Optional[Callable] = None) -> dict:
        """Legacy story generation method for backward compatibility."""
        logger.info("Using legacy generate_full_story - consider migrating to generate_enhanced_story")
        
        # Call enhanced version with default settings
        return await self.generate_enhanced_story(
            theme=theme,
            duration=duration,
            description=description,
            job_id=job_id,
            update_callback=update_callback
        )
    
    def _create_base_prompt(self, enriched_theme: Dict, outline: Dict) -> str:
        """Create enhanced base prompt for story generation."""
        return f"""Generate a soothing sleep story based on this enhanced theme and outline.

ENRICHED THEME:
{json.dumps(enriched_theme, indent=2)}

STORY OUTLINE:
{json.dumps(outline, indent=2)}

Create a calming, immersive narrative that guides the listener toward sleep.
Focus on gentle pacing, vivid but peaceful imagery, and smooth transitions."""
    
    async def _analyze_theme_enhanced(self, theme: str, description: Optional[str]) -> Dict[str, Any]:
        """Enhanced theme analysis with better validation and fallbacks."""
        
        enhanced_prompt = f"""{THEME_ANALYSIS_PROMPT.format(theme=theme, description=description or 'None')}

ENHANCED REQUIREMENTS:
- Include spatial waypoints for progression
- Suggest sensory rotation opportunities
- Identify sleep-inducing elements
- Consider TTS-friendly phrasing

Return detailed JSON with all standard fields plus:
- spatial_waypoints: ["point1", "point2", ...]
- sensory_opportunities: {{"sight": [...], "sound": [...], "touch": [...]}}
- sleep_elements: ["element1", "element2", ...]
"""
        
        for attempt in range(3):
            try:
                response = self.client.generate(
                    model=self.orchestrator.generator_name,
                    prompt=enhanced_prompt,
                    options={'temperature': 0.7, 'num_predict': 1000}
                )
                
                json_text = self._extract_json(response['response'])
                enriched = json.loads(json_text)
                
                # Validate enhanced fields
                required_fields = ['setting', 'mood', 'sensory_elements']
                if all(k in enriched for k in required_fields):
                    # Add default enhanced fields if missing
                    if 'spatial_waypoints' not in enriched:
                        enriched['spatial_waypoints'] = self._generate_default_waypoints(theme)
                    if 'sensory_opportunities' not in enriched:
                        enriched['sensory_opportunities'] = self._generate_default_sensory_opportunities()
                    if 'sleep_elements' not in enriched:
                        enriched['sleep_elements'] = ['gentle rhythm', 'calming imagery', 'peaceful atmosphere']
                    
                    return enriched
                    
            except Exception as e:
                logger.warning(f"Enhanced theme analysis attempt {attempt + 1} failed: {e}")
                if attempt == 2:
                    return self._fallback_theme_enhanced(theme)
        
        return self._fallback_theme_enhanced(theme)
    
    async def _generate_outline_enhanced(self, theme: Dict, duration: int, custom_waypoints: Optional[List[str]] = None) -> Dict[str, Any]:
        """Enhanced outline generation with waypoints and quality features."""
        
        target_words = duration * settings.TARGET_WPM
        waypoints = custom_waypoints or theme.get('spatial_waypoints', [])
        
        enhanced_prompt = f"""{OUTLINE_GENERATION_PROMPT.format(
            theme=json.dumps(theme), 
            duration=duration, 
            target_words=target_words, 
            beats=settings.BEATS_PER_STORY
        )}

ENHANCED OUTLINE REQUIREMENTS:
- Integrate spatial waypoints: {waypoints}
- Plan sensory rotation across beats
- Design sleep-taper progression (gentle reduction in final 20%)
- Include TTS-friendly pacing markers
- Structure for recursive beat planning

Add to each beat:
- waypoint: which spatial/temporal waypoint
- sensory_primary: main sensory focus
- sleep_intensity: 1-10 (higher = more sleep-inducing)
- tts_pacing: "slow"|"medium"|"very_slow"
"""
        
        for attempt in range(3):
            try:
                response = self.client.generate(
                    model=self.orchestrator.generator_name,
                    prompt=enhanced_prompt,
                    options={'temperature': 0.6, 'num_predict': settings.MAX_TOKENS_OUTLINE}
                )
                
                json_text = self._extract_json(response['response'])
                outline = json.loads(json_text)
                
                if 'story_bible' in outline and 'acts' in outline:
                    total_beats = sum(len(act.get('beats', [])) for act in outline.get('acts', []))
                    if total_beats >= 8:
                        # Enhance beats with missing fields
                        outline = self._enhance_outline_beats(outline, waypoints)
                        return outline
                        
            except Exception as e:
                logger.warning(f"Enhanced outline generation attempt {attempt + 1} failed: {e}")
                if attempt == 2:
                    return self._fallback_outline_enhanced(theme, duration, waypoints)
        
        return self._fallback_outline_enhanced(theme, duration, waypoints)
    
    def _generate_default_waypoints(self, theme: str) -> List[str]:
        """Generate default spatial waypoints based on theme."""
        # Simple heuristic based on theme keywords
        theme_lower = theme.lower()
        
        if any(word in theme_lower for word in ['forest', 'wood', 'tree']):
            return ['forest edge', 'deeper woods', 'clearing', 'ancient grove', 'peaceful center']
        elif any(word in theme_lower for word in ['ocean', 'sea', 'beach', 'wave']):
            return ['shoreline', 'shallow waters', 'calm depths', 'underwater garden', 'peaceful abyss']
        elif any(word in theme_lower for word in ['mountain', 'hill', 'peak']):
            return ['foothills', 'winding path', 'meadow rest', 'summit view', 'peaceful descent']
        else:
            return ['arrival', 'exploration', 'discovery', 'immersion', 'peaceful settling']
    
    def _generate_default_sensory_opportunities(self) -> Dict[str, List[str]]:
        """Generate default sensory opportunities."""
        return {
            "sight": ["gentle colors", "soft lighting", "natural textures", "peaceful movement"],
            "sound": ["gentle sounds", "natural rhythms", "soothing tones", "quiet whispers"],
            "touch": ["soft textures", "gentle warmth", "cooling breeze", "comfortable support"],
            "smell": ["fresh air", "natural scents", "clean atmosphere", "subtle fragrances"],
            "proprioception": ["body awareness", "gentle positioning", "natural alignment", "peaceful rest"]
        }
    
    def _enhance_outline_beats(self, outline: Dict, waypoints: List[str]) -> Dict:
        """Enhance outline beats with missing enhanced fields."""
        sensory_modes = settings.SENSORY_MODES
        beat_count = 0
        
        for act in outline.get('acts', []):
            for beat in act.get('beats', []):
                # Add waypoint
                if 'waypoint' not in beat and waypoints:
                    beat['waypoint'] = waypoints[beat_count % len(waypoints)]
                
                # Add sensory focus
                if 'sensory_primary' not in beat:
                    beat['sensory_primary'] = sensory_modes[beat_count % len(sensory_modes)]
                
                # Add sleep intensity (increases toward end)
                if 'sleep_intensity' not in beat:
                    total_beats = sum(len(a.get('beats', [])) for a in outline.get('acts', []))
                    intensity = min(10, 5 + int((beat_count / max(1, total_beats - 1)) * 5))
                    beat['sleep_intensity'] = intensity
                
                # Add TTS pacing
                if 'tts_pacing' not in beat:
                    if beat.get('sleep_intensity', 5) >= 8:
                        beat['tts_pacing'] = 'very_slow'
                    elif beat.get('sleep_intensity', 5) >= 6:
                        beat['tts_pacing'] = 'slow'
                    else:
                        beat['tts_pacing'] = 'medium'
                
                beat_count += 1
        
        return outline
    
    def _fallback_theme_enhanced(self, theme: str) -> Dict[str, Any]:
        """Enhanced fallback theme with additional fields."""
        return {
            'setting': theme,
            'time_of_day': 'dawn',
            'mood': 'peaceful',
            'sensory_elements': ['visual', 'audio', 'tactile'],
            'key_objects': [],
            'atmosphere': 'calm',
            'spatial_waypoints': self._generate_default_waypoints(theme),
            'sensory_opportunities': self._generate_default_sensory_opportunities(),
            'sleep_elements': ['gentle rhythm', 'calming imagery', 'peaceful atmosphere']
        }
    
    def _fallback_outline_enhanced(self, theme: Dict, duration: int, waypoints: List[str]) -> Dict[str, Any]:
        """Enhanced fallback outline with quality features."""
        target_words = duration * settings.TARGET_WPM
        words_per_beat = max(80, target_words // 12)
        
        waypoints = waypoints or self._generate_default_waypoints(theme.get('setting', 'peaceful place'))
        sensory_modes = settings.SENSORY_MODES
        
        acts = []
        beat_id = 0
        
        for i in range(3):  # 3 acts
            act_beats = []
            for j in range(4):  # 4 beats per act
                beat_id += 1
                
                act_beats.append({
                    'beat_id': beat_id,
                    'title': f'Beat {beat_id}',
                    'description': 'Continue the peaceful journey with enhanced quality',
                    'target_words': words_per_beat,
                    'sensory_focus': [sensory_modes[(beat_id - 1) % len(sensory_modes)]],
                    'waypoint': waypoints[(beat_id - 1) % len(waypoints)],
                    'sensory_primary': sensory_modes[(beat_id - 1) % len(sensory_modes)],
                    'sleep_intensity': min(10, 5 + int(((beat_id - 1) / 11) * 5)),
                    'tts_pacing': 'slow' if beat_id > 8 else 'medium'
                })
            
            acts.append({
                'act_number': i + 1,
                'title': ['Gentle Arrival', 'Peaceful Exploration', 'Restful Settlement'][i],
                'beats': act_beats
            })
        
        return {
            'story_bible': {
                'setting': theme.get('setting', 'peaceful location'),
                'time_of_day': 'dawn',
                'mood_baseline': 8,
                'key_objects': [],
                'enhanced_features': {
                    'waypoints_integrated': True,
                    'sensory_rotation': True,
                    'sleep_taper_planned': True
                }
            },
            'acts': acts,
            'enhanced_outline': True
        }
    
    # Utility methods (same as before but enhanced)
    def _final_polish(self, story: str) -> str:
        """Enhanced final polish with better formatting."""
        lines = [line.strip() for line in story.split('\n') if line.strip()]
        polished = '\n\n'.join(lines)
        
        # Remove any accidental TTS markers if not enabled
        if not self.tts_markers:
            polished = re.sub(r'\[PAUSE:\d+\.\d+\]', '', polished)
            polished = re.sub(r'\[BREATHE\]', '', polished)
        
        return polished
    
    def _extract_json(self, text: str) -> str:
        """Enhanced JSON extraction with better error handling."""
        # Try JSON code blocks first
        json_marker = '```json'
        code_marker = '```'
        
        if json_marker in text:
            start = text.find(json_marker) + len(json_marker)
            end = text.find(code_marker, start)
            if end > start:
                return text[start:end].strip()
        
        # Try regular code blocks
        if code_marker in text:
            start = text.find(code_marker) + len(code_marker)
            end = text.find(code_marker, start)
            if end > start:
                candidate = text[start:end].strip()
                if candidate.startswith('{'):
                    return candidate
        
        # Try to find JSON object
        json_pattern = re.compile(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', re.DOTALL)
        matches = json_pattern.findall(text)
        
        for match in matches:
            try:
                json.loads(match)  # Test if it's valid JSON
                return match
            except:
                continue
        
        # Last resort - return the whole text if it looks like JSON
        text = text.strip()
        if text.startswith('{') and text.endswith('}'):
            return text
        
        # Ultimate fallback
        return '{}'

# Legacy compatibility alias
class LegacyStoryGenerator(StoryGenerator):
    """Alias for backward compatibility."""
    pass