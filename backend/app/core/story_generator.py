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
from app.core.prompts import THEME_ANALYSIS_PROMPT, OUTLINE_GENERATION_PROMPT, BEAT_GENERATION_PROMPT, REASONER_EMBODIMENT_CHECKLIST, REASONER_DESTINATION_CHECKLIST
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
                 strict_schema: bool = False):
        
        self.client = ollama.Client(host=settings.OLLAMA_URL)
        self.orchestrator = EnhancedModelOrchestrator(
            generator=models.get('generator') if models else None,
            reasoner=models.get('reasoner') if models else None,
            polisher=models.get('polisher') if models else None,
            use_reasoner=use_reasoner,
            use_polish=use_polish,
            tts_markers=tts_markers,
            strict_schema=strict_schema
        )
        self.coherence_system = CoherenceSystem()
        self.tts_markers = tts_markers
        self.strict_schema = strict_schema
        
        # New validators
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
        """Enhanced story generation with embodiment + destination architecture."""
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
        total_beats = sum(len(act.get('beats', [])) for act in acts)
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
            "destination": destination_ctx
        }
        
        # Use orchestrator to generate beats with movement/destination scaffolding
        enhanced_result = await self.orchestrator.generate_enhanced_story(
            prompt=self._create_base_prompt(enriched_theme, outline),
            beats_target=total_beats,
            setting=setting_info,
            options={"temperature": settings.MODEL_TEMPERATURE}
        )
        
        update(70, 'Validating embodiment and destination arc...', 5)
        # Validate embodiment per beat and destination arc
        beats = self._extract_beats_from_result(enhanced_result)
        missing_beats_idx: List[int] = []
        for idx, beat in enumerate(beats):
            v = self.embodiment_validator.validate_beat(beat.get("text", ""))
            if not v["ok"]:
                missing_beats_idx.append(idx)
        dest_check = self.destination_validator.validate_destination_arc(beats)
        
        # If issues and reasoner enabled, request targeted rewrites
        if (missing_beats_idx or not dest_check["ok"]) and self.orchestrator.use_reasoner:
            update(75, 'Applying embodiment/destination corrections...', 6)
            beats = await self._reasoner_fix_beats(beats, missing_beats_idx, destination_ctx)
            # Recompute destination after fixes
            dest_check = self.destination_validator.validate_destination_arc(beats)
        
        # Compile final story
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
        # Add embodiment/destination metrics
        embodiment_scores = []
        for b in beats:
            embodiment_scores.append(self.embodiment_validator.validate_beat(b.get("text", ""))["score"])
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
                'destination': destination_ctx
            }
        }
        if self.strict_schema and enhanced_result.get("beats_schema"):
            result["beats_schema"] = enhanced_result["beats_schema"]
        
        update(100, '✅ Enhanced generation complete!', 8)
        return result

    def _extract_beats_from_result(self, enhanced_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        beats_schema = enhanced_result.get("beats_schema", {})
        if isinstance(beats_schema, dict) and "beats" in beats_schema:
            # If schema exists, use it
            return [{"text": b.get("text", "")} for b in beats_schema.get("beats", [])]
        # Fallback: split story text heuristically (not ideal)
        text = enhanced_result.get("story_text", "")
        parts = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]
        return [{"text": p} for p in parts]

    def _setup_destination_promise(self, theme: Dict, outline: Dict) -> Dict:
        archetypes = getattr(settings, 'DESTINATION_ARCHETYPES', {
            'safe_shelter': ['cottage','cabin','sanctuary','grove'],
            'peaceful_vista': ['meadow','clearing','overlook','garden'],
            'restorative_water': ['pool','stream','cove','spring'],
            'sacred_space': ['temple','circle','altar','threshold']
        })
        # Simple heuristic choose
        chosen = list(archetypes.values())[0][0]
        return {
            "name": chosen,
            "promise": "luogo sicuro e morbido dove riposare",
            "appeal": "calore, protezione, quiete"
        }
