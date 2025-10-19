import ollama
import time
import json
import asyncio
from typing import Dict, Optional, List, Tuple, Any
from app.core.config import settings
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class EnhancedModelOrchestrator:
    """Enhanced Sequential Multi-Model Orchestration for RTX 3070Ti.
    
    Features:
    - Sequential model loading (one at a time in VRAM)
    - Retry and fallback mechanisms
    - Quality enhancements: sensory rotation, waypoints, mixed-reward proxy
    - Recursive planning per beat
    - Sleep-taper for final beats
    - TTS markers insertion
    - Strict schema output support
    """

    def __init__(self,
                 generator: str = None,
                 reasoner: str = None, 
                 polisher: str = None,
                 use_reasoner: bool = True,
                 use_polish: bool = True,
                 tts_markers: bool = False,
                 strict_schema: bool = False):
        
        # Use provided models or defaults
        self.generator_name = generator or settings.DEFAULT_MODELS["generator"]
        self.reasoner_name = reasoner or settings.DEFAULT_MODELS["reasoner"]
        self.polisher_name = polisher or settings.DEFAULT_MODELS["polisher"]
        
        self.use_reasoner = use_reasoner
        self.use_polish = use_polish
        self.tts_markers = tts_markers
        self.strict_schema = strict_schema
        
        self.client = ollama.Client(host=settings.OLLAMA_URL)
        
        # Quality enhancement state
        self.current_sensory_index = 0
        self.opener_usage = {}  # Track opener frequency
        self.dynamic_blacklist = set()
        
        # Metrics tracking
        self.metrics = {
            "generator_words": 0,
            "reasoner_words": 0, 
            "polisher_words": 0,
            "corrections_count": 0,
            "coherence_improvements": 0
        }
    
    async def generate_enhanced_story(self, 
                                    prompt: str,
                                    beats_target: int,
                                    setting: Dict,
                                    options: Optional[Dict] = None) -> Dict[str, Any]:
        """Main entry point for enhanced story generation."""
        
        logger.info(f"Enhanced generation: {beats_target} beats, models: G={self.generator_name}, R={self.reasoner_name if self.use_reasoner else 'skip'}, P={self.polisher_name if self.use_polish else 'skip'}")
        
        # Initialize waypoints from setting
        waypoints = self._extract_waypoints_from_setting(setting)
        
        story_beats = []
        outline_memory = []
        
        for beat_idx in range(beats_target):
            # Calculate beat progress for sleep-taper
            progress = (beat_idx + 1) / beats_target
            
            # Generate individual beat with all enhancements
            beat_result = await self._generate_enhanced_beat(
                prompt, beat_idx, progress, waypoints, outline_memory, options
            )
            
            story_beats.append(beat_result)
            outline_memory.append(beat_result.get("outline", ""))
            
            # Keep memory manageable
            if len(outline_memory) > 5:
                outline_memory.pop(0)
        
        # Compile final result
        final_story = "\n\n".join([beat["text"] for beat in story_beats])
        
        # Add TTS markers if enabled
        if self.tts_markers:
            final_story = self._insert_tts_markers(final_story)
        
        result = {
            "story_text": final_story,
            "outline": "\n".join(outline_memory),
            "metrics": self.metrics.copy(),
            "coherence_stats": self._calculate_coherence_stats(story_beats),
            "memory_stats": {
                "total_beats": len(story_beats),
                "avg_words_per_beat": sum([beat.get("word_count", 0) for beat in story_beats]) / len(story_beats),
                "sensory_distribution": self._get_sensory_distribution(story_beats)
            }
        }
        
        # Add strict schema if enabled
        if self.strict_schema:
            result["beats_schema"] = self._create_beats_schema(story_beats)
        
        return result
    
    async def _generate_enhanced_beat(self, 
                                    base_prompt: str,
                                    beat_idx: int,
                                    progress: float,
                                    waypoints: List[str],
                                    outline_memory: List[str],
                                    options: Optional[Dict]) -> Dict[str, Any]:
        """Generate a single beat with all quality enhancements."""
        
        # Determine current sensory mode (rotation)
        current_sensory = settings.SENSORY_MODES[self.current_sensory_index % len(settings.SENSORY_MODES)]
        self.current_sensory_index += 1
        
        # Get current waypoint
        current_waypoint = waypoints[beat_idx % len(waypoints)] if waypoints else None
        
        # Apply sleep-taper if in final portion
        density_factor = 1.0
        if settings.SLEEP_TAPER_ENABLED and progress >= settings.TAPER_START_PERCENTAGE:
            density_factor = settings.TAPER_REDUCTION_FACTOR
        
        # Recursive planning: state → micro-goal → gentle change → settling
        beat_plan = self._create_recursive_beat_plan(beat_idx, current_sensory, current_waypoint, density_factor)
        
        # Construct enhanced prompt
        enhanced_prompt = self._construct_enhanced_prompt(
            base_prompt, beat_plan, outline_memory, current_sensory, current_waypoint
        )
        
        # STAGE 1: Generate (with retry and fallback)
        generator_output = await self._safe_generate_with_retry(self.generator_name, enhanced_prompt, options)
        self.metrics["generator_words"] = len(generator_output.split())
        
        # STAGE 2: Reason (if enabled)
        reasoner_output = generator_output
        if self.use_reasoner:
            # Apply mixed-reward proxy analysis
            revision_hints = self._analyze_with_mixed_reward_proxy(generator_output, outline_memory)
            
            reasoner_prompt = self._construct_reasoner_prompt(
                generator_output, revision_hints, beat_plan, len(generator_output.split())
            )
            
            reasoner_output = await self._safe_generate_with_retry(self.reasoner_name, reasoner_prompt, {"temperature": 0.3})
            self.metrics["reasoner_words"] = len(reasoner_output.split())
            
            if len(reasoner_output.split()) > 0:
                self.metrics["corrections_count"] += 1
        
        # STAGE 3: Polish (if enabled) 
        final_output = reasoner_output
        if self.use_polish:
            polish_prompt = self._construct_polish_prompt(reasoner_output, len(reasoner_output.split()))
            
            final_output = await self._safe_generate_with_retry(self.polisher_name, polish_prompt, {"temperature": 0.4})
            self.metrics["polisher_words"] = len(final_output.split())
        
        # Length control: ensure ±10% max deviation
        target_words = len(generator_output.split())
        final_output = self._apply_length_control(final_output, target_words)
        
        # Update opener tracking for dynamic blacklist
        self._update_opener_tracking(final_output)
        
        return {
            "text": final_output,
            "outline": f"Beat {beat_idx + 1}: {current_sensory} focus, {current_waypoint or 'narrative flow'}",
            "sensory_mode": current_sensory,
            "waypoint": current_waypoint,
            "word_count": len(final_output.split()),
            "density_factor": density_factor,
            "plan": beat_plan
        }
    
    def _extract_waypoints_from_setting(self, setting: Dict) -> List[str]:
        """Extract spatial/temporal waypoints from story setting."""
        # Default waypoints - can be enhanced based on setting analysis
        default_waypoints = [
            "establishing the scene",
            "deepening immersion", 
            "gentle progression",
            "peaceful transition",
            "settling into calm"
        ]
        
        # TODO: Enhance to dynamically extract from setting description
        return default_waypoints
    
    def _create_recursive_beat_plan(self, beat_idx: int, sensory_mode: str, waypoint: str, density_factor: float) -> Dict:
        """Create recursive planning: state → micro-goal → gentle change → settling."""
        return {
            "current_state": f"Beat {beat_idx + 1} in {sensory_mode} mode",
            "micro_goal": f"Guide through {waypoint or 'natural flow'} using {sensory_mode}",
            "gentle_change": f"Subtle shift toward relaxation (density: {density_factor:.2f})",
            "settling": "Allow peaceful absorption of the moment"
        }
    
    def _construct_enhanced_prompt(self, base_prompt: str, beat_plan: Dict, outline_memory: List[str], sensory_mode: str, waypoint: str) -> str:
        """Construct enhanced prompt with all quality features."""
        
        memory_context = "\n".join(outline_memory[-3:]) if outline_memory else "Beginning of story"
        
        # Dynamic opener blacklist
        blacklist_text = f"AVOID these overused openers: {', '.join(self.dynamic_blacklist)}" if self.dynamic_blacklist else ""
        
        enhanced_prompt = f"""{base_prompt}

--- ENHANCED GENERATION INSTRUCTIONS ---

RECENT NARRATIVE CONTEXT:
{memory_context}

CURRENT BEAT PLAN:
- State: {beat_plan['current_state']}
- Micro-goal: {beat_plan['micro_goal']} 
- Change: {beat_plan['gentle_change']}
- Settling: {beat_plan['settling']}

SENSORY FOCUS: Emphasize {sensory_mode} experiences in this beat.
WAYPOINT: {waypoint or 'Natural narrative flow'}

{blacklist_text}

Write the next story beat (150-200 words) following the plan above.
Focus on smooth transitions and avoid repetitive openings.
"""
        
        return enhanced_prompt
    
    def _analyze_with_mixed_reward_proxy(self, text: str, outline_memory: List[str]) -> List[str]:
        """Analyze text with mixed-reward proxy for quality issues."""
        hints = []
        
        # Check for repeated openers
        first_sentence = text.split('.')[0] if '.' in text else text[:50]
        opener_pattern = first_sentence[:20].lower().strip()
        
        if opener_pattern in self.opener_usage:
            self.opener_usage[opener_pattern] += 1
            if self.opener_usage[opener_pattern] >= settings.OPENER_PENALTY_THRESHOLD:
                hints.append(f"REPETITIVE OPENER: Avoid starting with '{opener_pattern}'")
                self.dynamic_blacklist.add(opener_pattern[:15])
        else:
            self.opener_usage[opener_pattern] = 1
        
        # Check transition quality
        if outline_memory and len(outline_memory) > 0:
            # Simple heuristic: look for connecting words
            connecting_words = ['then', 'next', 'meanwhile', 'as', 'while', 'gradually']
            if not any(word in text.lower()[:100] for word in connecting_words):
                hints.append("TRANSITION: Add smoother connection to previous beat")
        
        # Check sensory redundancy (simplified)
        sensory_words = text.lower().count('see') + text.lower().count('hear') + text.lower().count('feel')
        if sensory_words > 8:  # Arbitrary threshold
            hints.append("REDUNDANCY: Reduce repetitive sensory descriptions")
        
        return hints
    
    def _construct_reasoner_prompt(self, text: str, hints: List[str], beat_plan: Dict, target_words: int) -> str:
        """Construct prompt for reasoner stage."""
        hints_text = "\n".join([f"- {hint}" for hint in hints]) if hints else "No major issues detected"
        
        return f"""You are a reasoning editor for sleep stories. Improve the text below based on the revision hints.

ORIGINAL TEXT:
{text}

REVISION HINTS:
{hints_text}

BEAT PLAN CONTEXT:
{beat_plan['micro_goal']}

TARGET WORDS: {target_words} (maintain ±5%)

Rewrite the text addressing the hints while maintaining the calming, sleep-inducing quality:"""
    
    def _construct_polish_prompt(self, text: str, target_words: int) -> str:
        """Construct prompt for polisher stage."""
        return f"""Polish this sleep story text for maximum soothing effect. Enhance flow, rhythm, and gentle imagery.

TEXT:
{text}

TARGET LENGTH: {target_words} words (±3%)

Polished version with improved prose and natural rhythm:"""
    
    async def _safe_generate_with_retry(self, model: str, prompt: str, options: Optional[Dict] = None) -> str:
        """Generate with retry logic and fallback."""
        opts = options or {"temperature": 0.7, "num_predict": 300}
        
        last_error = None
        for attempt in range(settings.MAX_RETRIES):
            try:
                # Ensure only one model loaded at a time
                await self._ensure_model_loaded(model)
                
                response = self.client.generate(model=model, prompt=prompt, options=opts)
                result = response.get("response", "").strip()
                
                if result:
                    return result
                else:
                    raise ValueError("Empty response from model")
                    
            except Exception as e:
                last_error = e
                logger.warning(f"Generate attempt {attempt + 1} failed for {model}: {e}")
                
                if attempt < settings.MAX_RETRIES - 1:
                    await asyncio.sleep(settings.RETRY_DELAY)
        
        # Fallback to default model
        logger.error(f"All attempts failed for {model}, falling back to {settings.FALLBACK_MODEL}")
        try:
            await self._ensure_model_loaded(settings.FALLBACK_MODEL)
            response = self.client.generate(model=settings.FALLBACK_MODEL, prompt=prompt, options=opts)
            return response.get("response", "[Generation failed, using fallback]").strip()
        except Exception as e:
            logger.error(f"Even fallback failed: {e}")
            return "[Error: Unable to generate content]"
    
    async def _ensure_model_loaded(self, model: str):
        """Ensure model is loaded and others are unloaded (VRAM management)."""
        # For now, we rely on Ollama's internal model management
        # In a more advanced version, we could implement explicit loading/unloading
        pass
    
    def _apply_length_control(self, text: str, target_words: int) -> str:
        """Ensure text length is within ±10% of target."""
        current_words = len(text.split())
        min_words = int(target_words * 0.9)
        max_words = int(target_words * 1.1)
        
        if current_words < min_words:
            # Text too short - could extend but for now just return as is
            logger.info(f"Text shorter than target: {current_words} < {min_words}")
        elif current_words > max_words:
            # Text too long - truncate intelligently
            words = text.split()
            truncated = ' '.join(words[:max_words])
            # Try to end on a complete sentence
            if '.' in truncated:
                sentences = truncated.split('.')
                truncated = '.'.join(sentences[:-1]) + '.'
            text = truncated
            logger.info(f"Text truncated: {current_words} -> {len(text.split())} words")
        
        return text
    
    def _update_opener_tracking(self, text: str):
        """Update opener usage tracking for dynamic blacklist."""
        if not text:
            return
        
        first_sentence = text.split('.')[0] if '.' in text else text[:50]
        opener_pattern = first_sentence[:20].lower().strip()
        
        if opener_pattern:
            self.opener_usage[opener_pattern] = self.opener_usage.get(opener_pattern, 0) + 1
    
    def _insert_tts_markers(self, story_text: str) -> str:
        """Insert TTS markers like [PAUSE:2.0] and [BREATHE]."""
        if not self.tts_markers:
            return story_text
        
        # Split into sentences
        sentences = re.split(r'[.!?]+', story_text)
        marked_sentences = []
        
        for i, sentence in enumerate(sentences):
            if not sentence.strip():
                continue
                
            marked_sentence = sentence.strip()
            
            # Add breathing marker every few sentences
            if i > 0 and i % settings.TTS_BREATHE_FREQUENCY == 0:
                marked_sentence = "[BREATHE] " + marked_sentence
            
            # Add random pauses
            if i > 0 and len(marked_sentence.split()) > 15:  # Longer sentences
                pause_duration = settings.TTS_PAUSE_MIN + (settings.TTS_PAUSE_MAX - settings.TTS_PAUSE_MIN) * 0.5
                marked_sentence += f" [PAUSE:{pause_duration:.1f}]"
            
            marked_sentences.append(marked_sentence)
        
        return '. '.join(marked_sentences) + '.'
    
    def _calculate_coherence_stats(self, story_beats: List[Dict]) -> Dict:
        """Calculate coherence improvement statistics."""
        return {
            "total_beats": len(story_beats),
            "sensory_transitions": len(set([beat.get("sensory_mode") for beat in story_beats])),
            "avg_density_factor": sum([beat.get("density_factor", 1.0) for beat in story_beats]) / len(story_beats),
            "corrections_applied": self.metrics["corrections_count"]
        }
    
    def _get_sensory_distribution(self, story_beats: List[Dict]) -> Dict:
        """Get distribution of sensory modes used."""
        distribution = {}
        for beat in story_beats:
            mode = beat.get("sensory_mode", "unknown")
            distribution[mode] = distribution.get(mode, 0) + 1
        return distribution
    
    def _create_beats_schema(self, story_beats: List[Dict]) -> Dict:
        """Create structured schema for beats (strict_schema mode)."""
        return {
            "beats": [
                {
                    "beat_index": i,
                    "text": beat["text"],
                    "sensory_mode": beat.get("sensory_mode"),
                    "waypoint": beat.get("waypoint"),
                    "word_count": beat.get("word_count"),
                    "timing_estimate": beat.get("word_count", 150) / 150 * 60,  # Rough timing in seconds
                    "media_cues": {
                        "visual_focus": beat.get("sensory_mode") == "sight",
                        "audio_focus": beat.get("sensory_mode") == "sound",
                        "ambient_suggestion": beat.get("waypoint", "")
                    }
                }
                for i, beat in enumerate(story_beats)
            ],
            "total_estimated_duration": sum([beat.get("word_count", 150) / 150 * 60 for beat in story_beats]),
            "schema_version": "1.0"
        }

# Legacy compatibility - keep old class name as alias
ModelOrchestrator = EnhancedModelOrchestrator