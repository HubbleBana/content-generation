import ollama
import time
import json
import asyncio
from typing import Dict, Optional, List, Tuple, Any
from app.core.config import settings
import logging
import re
from datetime import datetime

from app.core.prompts import (
    BEAT_GENERATION_PROMPT, 
    REASONER_EMBODIMENT_CHECKLIST, 
    REASONER_DESTINATION_CHECKLIST,
    format_generation_parameters,
    format_style_requirements,
    format_action_style,
    format_perception_requirements,
    format_transition_requirements,
    format_downshift_requirements
)

logger = logging.getLogger(__name__)

class EnhancedModelOrchestrator:
    """Enhanced Sequential Multi-Model Orchestration with full parameter support."""

    def __init__(self,
                 generator: str = None,
                 reasoner: str = None, 
                 polisher: str = None,
                 use_reasoner: bool = True,
                 use_polish: bool = True,
                 tts_markers: bool = False,
                 strict_schema: bool = False,
                 generation_params: Optional[dict] = None):
        self.generator_name = generator or settings.DEFAULT_MODELS["generator"]
        self.reasoner_name = reasoner or settings.DEFAULT_MODELS["reasoner"]
        self.polisher_name = polisher or settings.DEFAULT_MODELS["polisher"]
        self.use_reasoner = use_reasoner
        self.use_polish = use_polish
        self.tts_markers = tts_markers
        self.strict_schema = strict_schema
        self.generation_params = generation_params or {}
        
        self.client = ollama.Client(host=settings.OLLAMA_URL)
        self.current_sensory_index = 0
        self.opener_usage = {}
        self.dynamic_blacklist = set()
        self.metrics = {
            "generator_words": 0, 
            "reasoner_words": 0, 
            "polisher_words": 0, 
            "corrections_count": 0, 
            "coherence_improvements": 0,
            "parameter_compliance_score": 0.0
        }
        
        logger.info(f"EnhancedModelOrchestrator initialized with params: {self.generation_params}")
    
    async def generate_enhanced_story(self, prompt: str, beats_target: int, setting: Dict, options: Optional[Dict] = None) -> Dict[str, Any]:
        waypoints = self._extract_waypoints_from_setting(setting)
        destination_ctx = (setting or {}).get("destination", {})
        generation_params = (setting or {}).get("generation_params", self.generation_params)
        
        story_beats = []
        outline_memory = []
        
        for beat_idx in range(beats_target):
            progress = (beat_idx + 1) / beats_target
            phase = self._destination_phase(progress)
            
            beat_result = await self._generate_enhanced_beat(
                prompt, beat_idx, progress, waypoints, outline_memory, 
                options, destination_ctx, phase, generation_params
            )
            story_beats.append(beat_result)
            outline_memory.append(beat_result.get("outline", ""))
            
            if len(outline_memory) > 5:
                outline_memory.pop(0)
        
        final_story = "\n\n".join([beat["text"] for beat in story_beats])
        if self.tts_markers:
            final_story = self._insert_tts_markers(final_story)
        
        # Calculate parameter compliance score
        self.metrics["parameter_compliance_score"] = self._calculate_parameter_compliance(story_beats, generation_params)
        
        result = {
            "story_text": final_story,
            "outline": "\n".join(outline_memory),
            "metrics": self.metrics.copy(),
            "coherence_stats": self._calculate_coherence_stats(story_beats),
            "memory_stats": {
                "total_beats": len(story_beats),
                "avg_words_per_beat": sum([b.get("word_count", 0) for b in story_beats]) / max(1, len(story_beats)),
                "sensory_distribution": self._get_sensory_distribution(story_beats),
                "parameter_compliance": self.metrics["parameter_compliance_score"]
            }
        }
        if self.strict_schema:
            result["beats_schema"] = self._create_beats_schema(story_beats)
        return result

    async def _generate_enhanced_beat(self, base_prompt: str, beat_idx: int, progress: float, 
                                     waypoints: List[str], outline_memory: List[str], 
                                     options: Optional[Dict], destination_ctx: Dict, 
                                     destination_phase: str, generation_params: Dict) -> Dict[str, Any]:
        
        current_sensory = settings.SENSORY_MODES[self.current_sensory_index % len(settings.SENSORY_MODES)]
        self.current_sensory_index += 1
        current_waypoint = waypoints[beat_idx % len(waypoints)] if waypoints else None
        
        # Apply sleep taper based on parameters
        density_factor = 1.0
        taper_start = generation_params.get('taper_start_pct', settings.TAPER_START_PERCENTAGE)
        taper_reduction = generation_params.get('taper_reduction', settings.TAPER_REDUCTION_FACTOR)
        
        if settings.SLEEP_TAPER_ENABLED and progress >= taper_start:
            density_factor = taper_reduction
        
        beat_plan = self._create_recursive_beat_plan(beat_idx, current_sensory, current_waypoint, density_factor)
        memory_context = "\n".join(outline_memory[-3:]) if outline_memory else "Beginning of story"
        
        # Build parameter-aware prompt
        enhanced_prompt = BEAT_GENERATION_PROMPT.format(
            story_bible=base_prompt,
            previous_text=memory_context,
            beat_title=f"Beat {beat_idx+1}",
            beat_description=beat_plan['micro_goal'],
            target_words=generation_params.get('words_per_beat', 180),
            sensory_focus=current_sensory,
            waypoint=current_waypoint or 'natural flow',
            destination_phase=destination_phase,
            generation_parameters=format_generation_parameters(generation_params),
            action_style=format_action_style(generation_params),
            perception_requirements=format_perception_requirements(generation_params),
            transition_requirements=format_transition_requirements(generation_params),
            downshift_requirements=format_downshift_requirements(generation_params),
            style_requirements=format_style_requirements(generation_params),
            departure_instructions="introduce/recall the destination promise subtly",
            journey_instructions="include progress markers ('ti avvicini')",
            approach_instructions="add approach signals (glimpse, scent, sound of destination)",
            arrival_instructions="explicit arrival + settling actions + permission to rest"
        )
        
        # Generator stage
        generator_output = await self._safe_generate_with_retry(
            self.generator_name, enhanced_prompt, options
        )
        self.metrics["generator_words"] += len(generator_output.split())
        
        # Reasoner stage (parameter-aware)
        reasoner_output = generator_output
        if self.use_reasoner:
            reasoner_prompt = self._build_reasoner_prompt(generator_output, generation_params)
            reasoner_output = await self._safe_generate_with_retry(
                self.reasoner_name, reasoner_prompt, {"temperature": 0.3}
            )
            self.metrics["reasoner_words"] += len(reasoner_output.split())
            if reasoner_output and reasoner_output != generator_output:
                self.metrics["corrections_count"] += 1
        
        # Polisher stage (parameter-aware)
        final_output = reasoner_output
        if self.use_polish:
            polish_prompt = self._build_polish_prompt(reasoner_output, generation_params)
            final_output = await self._safe_generate_with_retry(
                self.polisher_name, polish_prompt, {"temperature": 0.4}
            )
            self.metrics["polisher_words"] += len(final_output.split())
        
        target_words = generation_params.get('words_per_beat', len(generator_output.split()) or 180)
        final_output = self._apply_length_control(final_output, target_words)
        self._update_opener_tracking(final_output)
        
        return {
            "text": final_output,
            "outline": f"Beat {beat_idx + 1}: {current_sensory} focus, {current_waypoint or 'narrative flow'}",
            "sensory_mode": current_sensory,
            "waypoint": current_waypoint,
            "word_count": len(final_output.split()),
            "density_factor": density_factor,
            "plan": beat_plan,
            "parameter_compliance": self._validate_beat_parameters(final_output, generation_params)
        }
    
    def _build_reasoner_prompt(self, text: str, params: Dict) -> str:
        """Build parameter-aware reasoner prompt"""
        embodiment_check = REASONER_EMBODIMENT_CHECKLIST.format(
            movement_verbs_required=params.get('movement_verbs_required', settings.MOVEMENT_VERBS_REQUIRED),
            transition_tokens_required=params.get('transition_tokens_required', settings.TRANSITION_TOKENS_REQUIRED),
            sensory_coupling=params.get('sensory_coupling', settings.SENSORY_COUPLING),
            pov_enforce=params.get('pov_enforce_second_person', settings.POV_ENFORCE_SECOND_PERSON),
            downshift_required=params.get('downshift_required', settings.DOWNSHIFT_REQUIRED)
        )
        
        destination_check = REASONER_DESTINATION_CHECKLIST.format(
            closure_required=params.get('closure_required', settings.CLOSURE_REQUIRED)
        )
        
        return f"""You are a structural editor for parameter-compliant sleep stories.

TEXT:
{text}

PARAMETER REQUIREMENTS:
{embodiment_check}

{destination_check}

Rewrite minimally to satisfy ALL parameter requirements while preserving the soothing, sleep-inducing tone."""
    
    def _build_polish_prompt(self, text: str, params: Dict) -> str:
        """Build parameter-aware polish prompt"""
        style_reqs = format_style_requirements(params)
        
        return f"""Polish this sleep story text for maximum soothing effect while maintaining parameter compliance.

TEXT:
{text}

STYLE REQUIREMENTS:
{style_reqs}

Polished version (maintain all parameter requirements):"""
    
    def _validate_beat_parameters(self, text: str, params: Dict) -> Dict[str, Any]:
        """Validate beat compliance with generation parameters"""
        validation = {
            "pov_compliant": True,
            "movement_verbs_count": 0,
            "transitions_count": 0,
            "sensory_elements_count": 0,
            "downshift_present": False,
            "overall_score": 0.0
        }
        
        text_lower = text.lower()
        
        # POV validation
        if params.get('pov_enforce_second_person', settings.POV_ENFORCE_SECOND_PERSON):
            first_person = len(re.findall(r'\b(i|me|my|mine|myself)\b', text_lower))
            third_person = len(re.findall(r'\b(he|she|they|him|her|them)\b', text_lower))
            validation["pov_compliant"] = (first_person + third_person) == 0
        
        # Movement verbs
        movement_verbs = settings.MOVEMENT_VERBS
        for verb in movement_verbs:
            validation["movement_verbs_count"] += len(re.findall(verb, text_lower))
        
        # Transitions
        transitions = settings.TRANSITION_TOKENS
        for trans in transitions:
            validation["transitions_count"] += len(re.findall(re.escape(trans.lower()), text_lower))
        
        # Sensory elements (basic detection)
        sensory_words = ['see', 'hear', 'feel', 'touch', 'smell', 'taste', 'sense', 'notice', 'perceive']
        for word in sensory_words:
            validation["sensory_elements_count"] += len(re.findall(f'\\b{word}', text_lower))
        
        # Downshift detection
        downshift_words = ['breath', 'relax', 'ease', 'slow', 'settle', 'calm', 'gentle']
        validation["downshift_present"] = any(word in text_lower for word in downshift_words)
        
        # Calculate overall score
        score_components = []
        
        if validation["pov_compliant"]:
            score_components.append(1.0)
        else:
            score_components.append(0.0)
        
        movement_req = params.get('movement_verbs_required', settings.MOVEMENT_VERBS_REQUIRED)
        if validation["movement_verbs_count"] >= movement_req:
            score_components.append(1.0)
        else:
            score_components.append(validation["movement_verbs_count"] / max(1, movement_req))
        
        transition_req = params.get('transition_tokens_required', settings.TRANSITION_TOKENS_REQUIRED)
        if validation["transitions_count"] >= transition_req:
            score_components.append(1.0)
        else:
            score_components.append(validation["transitions_count"] / max(1, transition_req))
        
        sensory_req = params.get('sensory_coupling', settings.SENSORY_COUPLING)
        if validation["sensory_elements_count"] >= sensory_req:
            score_components.append(1.0)
        else:
            score_components.append(validation["sensory_elements_count"] / max(1, sensory_req))
        
        if params.get('downshift_required', settings.DOWNSHIFT_REQUIRED):
            score_components.append(1.0 if validation["downshift_present"] else 0.0)
        
        validation["overall_score"] = sum(score_components) / len(score_components)
        return validation
    
    def _calculate_parameter_compliance(self, story_beats: List[Dict], params: Dict) -> float:
        """Calculate overall parameter compliance score for the story"""
        if not story_beats:
            return 0.0
        
        compliance_scores = []
        for beat in story_beats:
            compliance = beat.get("parameter_compliance", {})
            score = compliance.get("overall_score", 0.0)
            compliance_scores.append(score)
        
        return sum(compliance_scores) / len(compliance_scores)

    def _extract_waypoints_from_setting(self, setting: Dict) -> List[str]:
        default_waypoints = ["entry path", "gentle bend", "small clearing", "wooden bridge", "soft moss hollow"]
        return setting.get("theme", {}).get("spatial_waypoints", default_waypoints)

    def _destination_phase(self, progress: float) -> str:
        if progress < 0.3: return "departure"
        if progress < 0.7: return "journey"
        if progress < 0.9: return "approach"
        return "arrival"

    def _create_recursive_beat_plan(self, beat_idx: int, sensory_mode: str, waypoint: Optional[str], density_factor: float) -> Dict[str, str]:
        return {
            "current_state": f"Beat {beat_idx + 1} in {sensory_mode} mode",
            "micro_goal": f"Guide through {waypoint or 'natural flow'} using {sensory_mode}",
            "gentle_change": f"Subtle shift toward relaxation (density: {density_factor:.2f})",
            "settling": "Allow peaceful absorption of the moment"
        }

    def _calculate_coherence_stats(self, story_beats: List[Dict]) -> Dict:
        return {
            "total_beats": len(story_beats),
            "sensory_transitions": len(set([b.get("sensory_mode") for b in story_beats])),
            "avg_density_factor": sum([b.get("density_factor", 1.0) for b in story_beats]) / max(1, len(story_beats)),
            "corrections_applied": self.metrics.get("corrections_count", 0),
            "parameter_compliance_avg": sum([b.get("parameter_compliance", {}).get("overall_score", 0.0) for b in story_beats]) / max(1, len(story_beats))
        }

    def _get_sensory_distribution(self, story_beats: List[Dict]) -> Dict:
        dist: Dict[str, int] = {}
        for b in story_beats:
            m = b.get("sensory_mode", "unknown")
            dist[m] = dist.get(m, 0) + 1
        return dist

    def _create_beats_schema(self, story_beats: List[Dict]) -> Dict:
        return {
            "beats": [
                {
                    "beat_index": i,
                    "text": b.get("text", ""),
                    "sensory_mode": b.get("sensory_mode"),
                    "waypoint": b.get("waypoint"),
                    "word_count": b.get("word_count"),
                    "timing_estimate": b.get("word_count", 150) / 150 * 60,
                    "media_cues": {
                        "visual_focus": b.get("sensory_mode") == "sight",
                        "audio_focus": b.get("sensory_mode") == "sound",
                        "ambient_suggestion": b.get("waypoint", "")
                    },
                    "parameter_compliance": b.get("parameter_compliance", {})
                } for i, b in enumerate(story_beats)
            ],
            "total_estimated_duration": sum([b.get("word_count", 150) / 150 * 60 for b in story_beats]),
            "schema_version": "2.0-enhanced",
            "parameter_summary": {
                "avg_compliance_score": sum([b.get("parameter_compliance", {}).get("overall_score", 0.0) for b in story_beats]) / max(1, len(story_beats))
            }
        }

    async def _safe_generate_with_retry(self, model: str, prompt: str, options: Optional[Dict] = None) -> str:
        opts = options or {"temperature": 0.7, "num_predict": 300}
        last_error = None
        for attempt in range(settings.MAX_RETRIES):
            try:
                response = self.client.generate(model=model, prompt=prompt, options=opts)
                result = response.get("response", "").strip()
                if result:
                    return result
                else:
                    raise ValueError("Empty response from model")
            except Exception as e:
                last_error = e
                logger.warning(f"Generate attempt {attempt+1} failed for {model}: {e}")
                if attempt < settings.MAX_RETRIES - 1:
                    await asyncio.sleep(settings.RETRY_DELAY)
        logger.error(f"All attempts failed for {model}")
        return "[Error: Unable to generate content]"

    def _apply_length_control(self, text: str, target_words: int) -> str:
        cur = len(text.split())
        tolerance = 0.1  # 10% tolerance
        mi = int(target_words * (1 - tolerance))
        ma = int(target_words * (1 + tolerance))
        
        if cur > ma:
            words = text.split()
            trunc = ' '.join(words[:ma])
            if '.' in trunc:
                s = trunc.split('.')
                trunc = '.'.join(s[:-1]) + '.'
            return trunc
        return text

    def _update_opener_tracking(self, text: str):
        if not text:
            return
        first = text.split('.')[0] if '.' in text else text[:50]
        pattern = first[:20].lower().strip()
        if pattern:
            self.opener_usage[pattern] = self.opener_usage.get(pattern, 0) + 1

    def _insert_tts_markers(self, story_text: str) -> str:
        if not self.tts_markers:
            return story_text
        sentences = re.split(r'[.!?]+', story_text)
        marked = []
        for i, s in enumerate(sentences):
            if not s.strip():
                continue
            t = s.strip()
            if i > 0 and i % settings.TTS_BREATHE_FREQUENCY == 0:
                t = "[BREATHE] " + t
            if i > 0 and len(t.split()) > 15:
                pause = settings.TTS_PAUSE_MIN + (settings.TTS_PAUSE_MAX - settings.TTS_PAUSE_MIN) * 0.5
                t += f" [PAUSE:{pause:.1f}]"
            marked.append(t)
        return '. '.join(marked) + '.'