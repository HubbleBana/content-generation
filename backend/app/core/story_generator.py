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
from app.core.prompts import THEME_ANALYSIS_PROMPT, OUTLINE_GENERATION_PROMPT
from app.core.embodiment_destination_validators import EmbodimentValidator, DestinationValidator

import logging
logger = logging.getLogger(__name__)

class StoryGenerator:
    """Enhanced Story Generator with multi-model support, embodiment and destination arc."""
    
    def __init__(self,
                 target_language: str = "en",
                 translation_quality: str = "high", 
                 models: Optional[dict] = None,
                 use_reasoner: bool = True,
                 use_polish: bool = True,
                 tts_markers: bool = False,
                 strict_schema: bool = False,
                 generation_params: Optional[dict] = None):
        
        self.client = ollama.Client(host=settings.OLLAMA_URL)
        self.generation_params = generation_params or {}
        
        self.orchestrator = EnhancedModelOrchestrator(
            generator=(models or {}).get('generator') if models else None,
            reasoner=(models or {}).get('reasoner') if models else None,
            polisher=(models or {}).get('polisher') if models else None,
            use_reasoner=use_reasoner,
            use_polish=use_polish,
            tts_markers=tts_markers,
            strict_schema=strict_schema
        )
        self.coherence_system = CoherenceSystem()
        self.tts_markers = tts_markers
        self.strict_schema = strict_schema
        
        self.embodiment_validator = EmbodimentValidator()
        self.destination_validator = DestinationValidator()
        
        logger.info(f"StoryGenerator initialized - Models: {models or 'defaults'}, TTS: {tts_markers}, Schema: {strict_schema}")
    
    async def generate_enhanced_story(self, 
                                    theme: str, 
                                    duration: int = 45, 
                                    description: Optional[str] = None,
                                    job_id: Optional[str] = None,
                                    update_callback: Optional[Callable] = None,
                                    custom_waypoints: Optional[List[str]] = None) -> Dict[str, Any]:
        start_time = datetime.now()
        
        def update(progress: float, step: str, step_num: int = 0, stage_metrics=None):
            if update_callback:
                update_callback(progress, step, step_num, stage_metrics)
            logger.info(f'Enhanced progress: {progress}% - {step}')
        
        # 1) Theme analysis
        update(5, 'Analyzing theme with enhanced AI understanding...', 1)
        enriched_theme = await self._analyze_theme_enhanced(theme, description)
        
        update(10, 'Generating enhanced story outline with waypoints...', 2)
        outline = await self._generate_outline_enhanced(enriched_theme, duration, custom_waypoints)
        
        # 2) Systems init
        update(15, 'Initializing coherence and memory systems...', 3)
        memory = MemorySystem(outline.get('story_bible', {}))
        self.coherence_system.initialize_story_bible(outline.get('story_bible', {}))
        
        acts = outline.get('acts', [])
        total_beats = sum(len(act.get('beats', [])) for act in acts) or settings.BEATS_PER_STORY
        target_words_total = duration * settings.TARGET_WPM
        controller = NarrativeController(total_beats=total_beats, target_words_total=target_words_total)
        
        # 3) Destination setup
        destination_ctx = self._setup_destination_promise(enriched_theme, outline)
        update(20, 'Beginning journey with destination promise...', 4)
        
        # Build setting context passed to orchestrator
        setting_info = {
            "theme": enriched_theme,
            "outline": outline,
            "custom_waypoints": custom_waypoints,
            "destination": destination_ctx,
            "generation_params": self.generation_params
        }
        
        enhanced_result = await self.orchestrator.generate_enhanced_story(
            prompt=self._create_base_prompt(enriched_theme, outline),
            beats_target=total_beats,
            setting=setting_info,
            options={"temperature": settings.MODEL_TEMPERATURE}
        )
        
        update(70, 'Validating embodiment and destination arc...', 5)
        beats = self._extract_beats_from_result(enhanced_result)
        missing_beats_idx: List[int] = []
        for idx, beat in enumerate(beats):
            v = self.embodiment_validator.validate_beat(beat.get("text", ""))
            if not v["ok"]:
                missing_beats_idx.append(idx)
        dest_check = self.destination_validator.validate_destination_arc(beats)
        
        if (missing_beats_idx or not dest_check["ok"]) and self.orchestrator.use_reasoner:
            update(75, 'Applying embodiment/destination corrections...', 6)
            beats = await self._reasoner_fix_beats(beats, missing_beats_idx, destination_ctx)
            dest_check = self.destination_validator.validate_destination_arc(beats)
        
        final_story_text = "\n\n".join([b.get("text", "") for b in beats])
        if not self.tts_markers and not self.strict_schema:
            final_story_text = self._final_polish(final_story_text)
        
        update(90, 'Calculating metrics and statistics...', 7)
        generation_time = (datetime.now() - start_time).total_seconds()
        english_word_count = len(final_story_text.split())
        target_words = target_words_total
        accuracy_percent = round(abs(english_word_count - target_words) / max(1, target_words) * 100, 2)
        duration_estimate = round(english_word_count / settings.TARGET_WPM, 1)
        
        coherence_stats = enhanced_result.get("coherence_stats", {})
        embodiment_scores = [self.embodiment_validator.validate_beat(b.get("text", ""))["score"] for b in beats]
        coherence_stats.update({
            "embodiment_score_avg": sum(embodiment_scores)/max(1,len(embodiment_scores)),
            "destination_completion": dest_check["ok"],
            "destination_missing": dest_check.get("missing", [])
        })
        
        combined_metrics = {
            'english_word_count': english_word_count,
            'target_words': target_words,
            'accuracy_percent': accuracy_percent,
            'duration_estimate_minutes': duration_estimate,
            'beats_generated': len(beats),
            'target_language': 'en',
            'generation_time_seconds': generation_time,
            'enhanced_features_used': {
                'multi_model': True,
                'embodiment_enforced': True,
                'destination_arc': True,
                'tts_markers': self.tts_markers,
                'strict_schema': self.strict_schema
            },
            **enhanced_result.get("metrics", {})
        }
        
        result = {
            'story_text': final_story_text,
            'outline': enhanced_result.get("outline", outline),
            'metrics': combined_metrics,
            'coherence_stats': coherence_stats,
            'memory_stats': enhanced_result.get("memory_stats", {}),
            'generation_info': {
                'models_used': {
                    'generator': self.orchestrator.generator_name,
                    'reasoner': self.orchestrator.reasoner_name if self.orchestrator.use_reasoner else None,
                    'polisher': self.orchestrator.polisher_name if self.orchestrator.use_polish else None
                },
                'destination': destination_ctx,
                'generation_params': self.generation_params
            }
        }
        if self.strict_schema and enhanced_result.get("beats_schema"):
            result["beats_schema"] = enhanced_result["beats_schema"]
        
        update(100, '✅ Enhanced generation complete!', 8)
        return result

    async def _reasoner_fix_beats(self, beats: List[Dict], missing_beats_idx: List[int], destination_ctx: Dict) -> List[Dict]:
        """Fix embodiment and destination issues in specific beats using reasoner model"""
        if not self.orchestrator.use_reasoner or not missing_beats_idx:
            return beats
        
        fixed_beats = beats.copy()
        
        # Get generation parameters for enforcing rules
        pov_enforce = self.generation_params.get('pov_enforce_second_person', settings.POV_ENFORCE_SECOND_PERSON)
        movement_required = self.generation_params.get('movement_verbs_required', settings.MOVEMENT_VERBS_REQUIRED)
        transition_required = self.generation_params.get('transition_tokens_required', settings.TRANSITION_TOKENS_REQUIRED)
        downshift_required = self.generation_params.get('downshift_required', settings.DOWNSHIFT_REQUIRED)
        
        for idx in missing_beats_idx:
            if idx < len(fixed_beats):
                original_text = fixed_beats[idx].get("text", "")
                
                # Construct correction prompt with parameters
                correction_prompt = f"""Fix embodiment and destination arc issues in this sleep story beat:

ORIGINAL TEXT:
{original_text}

REQUIREMENTS:
- POV: {'Enforce strict 2nd person present tense' if pov_enforce else 'Prefer 2nd person but allow flexibility'}
- Movement: Include at least {movement_required} movement verb(s) (walk, move, approach, etc.)
- Transitions: Add at least {transition_required} spatial transition(s) (beyond, through, toward, etc.)
- Downshift: {'Include relaxation cues (breath slows, shoulders ease)' if downshift_required else 'Optional relaxation elements'}
- Maintain destination promise: {destination_ctx.get('promise', 'peaceful rest')}
- Keep soothing, sleep-inducing tone
- Target sensory coupling: {self.generation_params.get('sensory_coupling', settings.SENSORY_COUPLING)} sensory elements

CORRECTED VERSION:"""

                try:
                    def _call():
                        return self.client.generate(
                            model=self.orchestrator.reasoner_name,
                            prompt=correction_prompt,
                            options={"temperature": 0.3, "num_predict": 300}
                        ).get('response', original_text)
                    
                    corrected = await asyncio.to_thread(_call)
                    if corrected and len(corrected.split()) > 20:
                        fixed_beats[idx]["text"] = corrected.strip()
                        logger.info(f"Fixed embodiment issues in beat {idx}")
                except Exception as e:
                    logger.warning(f"Failed to fix beat {idx}: {e}")
        
        return fixed_beats

    # Helpers restored
    def _extract_beats_from_result(self, enhanced_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        beats_schema = enhanced_result.get("beats_schema", {})
        if isinstance(beats_schema, dict) and "beats" in beats_schema:
            return [{"text": b.get("text", "")} for b in beats_schema.get("beats", [])]
        text = enhanced_result.get("story_text", "")
        parts = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]
        return [{"text": p} for p in parts] or [{"text": text}]

    async def _analyze_theme_enhanced(self, theme: str, description: Optional[str]) -> Dict[str, Any]:
        # Include generation parameters in analysis
        prompt = THEME_ANALYSIS_PROMPT.format(
            theme=theme, 
            description=description or 'None',
            pov_mode='second_person' if self.generation_params.get('pov_enforce_second_person', settings.POV_ENFORCE_SECOND_PERSON) else 'flexible',
            sensory_coupling=self.generation_params.get('sensory_coupling', settings.SENSORY_COUPLING),
            movement_style='embodied_journey' if self.generation_params.get('movement_verbs_required', settings.MOVEMENT_VERBS_REQUIRED) > 0 else 'gentle_flow'
        )
        def _call():
            r = self.client.generate(model=self.orchestrator.generator_name, prompt=prompt, options={'temperature': 0.7, 'num_predict': 800})
            return r.get('response','')
        text = await asyncio.to_thread(_call)
        json_text = self._extract_json(text)
        try:
            data = json.loads(json_text) if json_text else {}
            if 'spatial_waypoints' not in data:
                data['spatial_waypoints'] = ['entry path','gentle bend','small clearing','wooden bridge','soft moss hollow']
            return data
        except Exception:
            return {"setting": theme, "sensory_elements": ["sight","sound"], "spatial_waypoints": ['entry path','gentle bend','small clearing','wooden bridge','soft moss hollow']}

    async def _generate_outline_enhanced(self, enriched_theme: Dict[str, Any], duration: int, custom_waypoints: Optional[List[str]]) -> Dict[str, Any]:
        target_words = duration * settings.TARGET_WPM
        
        # Include generation parameters in outline
        prompt = OUTLINE_GENERATION_PROMPT.format(
            theme=json.dumps(enriched_theme), 
            duration=duration, 
            target_words=target_words, 
            beats=settings.BEATS_PER_STORY,
            pov_enforce=self.generation_params.get('pov_enforce_second_person', settings.POV_ENFORCE_SECOND_PERSON),
            embodiment_level=self.generation_params.get('movement_verbs_required', settings.MOVEMENT_VERBS_REQUIRED),
            sensory_coupling=self.generation_params.get('sensory_coupling', settings.SENSORY_COUPLING),
            destination_required=self.generation_params.get('closure_required', settings.CLOSURE_REQUIRED)
        )
        def _call():
            r = self.client.generate(model=self.orchestrator.generator_name, prompt=prompt, options={'temperature': 0.6, 'num_predict': settings.MAX_TOKENS_OUTLINE})
            return r.get('response','')
        text = await asyncio.to_thread(_call)
        json_text = self._extract_json(text)
        try:
            outline = json.loads(json_text) if json_text else {}
            return outline or {"story_bible": {"setting": enriched_theme.get('setting','')}, "acts": []}
        except Exception:
            return {"story_bible": {"setting": enriched_theme.get('setting','')}, "acts": []}

    def _create_base_prompt(self, enriched_theme: Dict, outline: Dict) -> str:
        # Include generation parameters in base prompt
        param_instructions = []
        
        if self.generation_params.get('pov_enforce_second_person', settings.POV_ENFORCE_SECOND_PERSON):
            param_instructions.append("Maintain strict second person present tense throughout.")
        
        if self.generation_params.get('movement_verbs_required', settings.MOVEMENT_VERBS_REQUIRED) > 0:
            param_instructions.append(f"Include at least {self.generation_params.get('movement_verbs_required', settings.MOVEMENT_VERBS_REQUIRED)} movement verb(s) per beat for embodied journey.")
        
        if self.generation_params.get('sensory_coupling', settings.SENSORY_COUPLING) > 1:
            param_instructions.append(f"Couple at least {self.generation_params.get('sensory_coupling', settings.SENSORY_COUPLING)} sensory elements per beat.")
        
        if self.generation_params.get('tts_optimized', False):
            param_instructions.append("Optimize pacing and pauses for text-to-speech synthesis.")
        
        param_text = "\n".join(param_instructions) if param_instructions else "Follow natural storytelling flow."
        
        return f"""Generate a soothing sleep story based on this enhanced theme and outline.

ENRICHED THEME:
{json.dumps(enriched_theme, indent=2)}

STORY OUTLINE:
{json.dumps(outline, indent=2)}

GENERATION PARAMETERS:
{param_text}

Create a calming, immersive narrative that guides the listener toward sleep. Focus on gentle pacing, vivid but peaceful imagery, smooth transitions."""

    def _final_polish(self, story: str) -> str:
        lines = [line.strip() for line in story.split('\n') if line.strip()]
        polished = '\n\n'.join(lines)
        polished = re.sub(r'\[PAUSE:\d+\.\d+\]', '', polished)
        polished = re.sub(r'\[BREATHE\]', '', polished)
        return polished

    def _extract_json(self, text: str) -> str:
        json_marker = '```json'; code_marker = '```'
        if json_marker in text:
            start = text.find(json_marker) + len(json_marker)
            end = text.find(code_marker, start)
            if end > start: return text[start:end].strip()
        if code_marker in text:
            start = text.find(code_marker) + len(code_marker)
            end = text.find(code_marker, start)
            if end > start:
                candidate = text[start:end].strip()
                if candidate.startswith('{'): return candidate
        m = re.search(r'\{[\s\S]*\}', text)
        return m.group(0) if m else '{}'

    def _setup_destination_promise(self, enriched_theme: Dict[str, Any], outline: Dict[str, Any]) -> Dict[str, Any]:
        archetypes = getattr(settings, 'DESTINATION_ARCHETYPES', {
            'safe_shelter': ['cottage','cabin','sanctuary','grove'],
            'peaceful_vista': ['meadow','clearing','overlook','garden'],
            'restorative_water': ['pool','stream','cove','spring'],
            'sacred_space': ['temple','circle','altar','threshold']
        })
        try:
            first_key = next(iter(archetypes))
            name = archetypes[first_key][0]
        except Exception:
            name = 'grove'
        return {'name': name, 'promise': 'a safe, soft place to rest', 'appeal': 'warmth, protection, quiet'}