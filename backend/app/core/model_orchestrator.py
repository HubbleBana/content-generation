import ollama
import time
import json
import asyncio
from typing import Dict, Optional, List, Tuple, Any
from app.core.config import settings
import logging
import re
from datetime import datetime

from app.core.prompts import BEAT_GENERATION_PROMPT, REASONER_EMBODIMENT_CHECKLIST, REASONER_DESTINATION_CHECKLIST

logger = logging.getLogger(__name__)

class EnhancedModelOrchestrator:
    """Enhanced Sequential Multi-Model Orchestration with Embodiment & Destination support."""

    def __init__(self,
                 generator: str = None,
                 reasoner: str = None, 
                 polisher: str = None,
                 use_reasoner: bool = True,
                 use_polish: bool = True,
                 tts_markers: bool = False,
                 strict_schema: bool = False):
        self.generator_name = generator or settings.DEFAULT_MODELS["generator"]
        self.reasoner_name = reasoner or settings.DEFAULT_MODELS["reasoner"]
        self.polisher_name = polisher or settings.DEFAULT_MODELS["polisher"]
        self.use_reasoner = use_reasoner
        self.use_polish = use_polish
        self.tts_markers = tts_markers
        self.strict_schema = strict_schema
        self.client = ollama.Client(host=settings.OLLAMA_URL)
        self.current_sensory_index = 0
        self.opener_usage = {}
        self.dynamic_blacklist = set()
        self.metrics = {"generator_words":0, "reasoner_words":0, "polisher_words":0, "corrections_count":0, "coherence_improvements":0}
    
    async def generate_enhanced_story(self, prompt: str, beats_target: int, setting: Dict, options: Optional[Dict] = None) -> Dict[str, Any]:
        waypoints = self._extract_waypoints_from_setting(setting)
        destination_ctx = (setting or {}).get("destination", {})
        story_beats = []
        outline_memory = []
        for beat_idx in range(beats_target):
            progress = (beat_idx + 1) / beats_target
            phase = self._destination_phase(progress)
            beat_result = await self._generate_enhanced_beat(prompt, beat_idx, progress, waypoints, outline_memory, options, destination_ctx, phase)
            story_beats.append(beat_result)
            outline_memory.append(beat_result.get("outline", ""))
            if len(outline_memory) > 5:
                outline_memory.pop(0)
        final_story = "\n\n".join([beat["text"] for beat in story_beats])
        if self.tts_markers:
            final_story = self._insert_tts_markers(final_story)
        result = {
            "story_text": final_story,
            "outline": "\n".join(outline_memory),
            "metrics": self.metrics.copy(),
            "coherence_stats": self._calculate_coherence_stats(story_beats),
            "memory_stats": {
                "total_beats": len(story_beats),
                "avg_words_per_beat": sum([b.get("word_count",0) for b in story_beats])/max(1,len(story_beats)),
                "sensory_distribution": self._get_sensory_distribution(story_beats)
            }
        }
        if self.strict_schema:
            result["beats_schema"] = self._create_beats_schema(story_beats)
        return result

    async def _generate_enhanced_beat(self, base_prompt: str, beat_idx: int, progress: float, waypoints: List[str], outline_memory: List[str], options: Optional[Dict], destination_ctx: Dict, destination_phase: str) -> Dict[str, Any]:
        current_sensory = settings.SENSORY_MODES[self.current_sensory_index % len(settings.SENSORY_MODES)]
        self.current_sensory_index += 1
        current_waypoint = waypoints[beat_idx % len(waypoints)] if waypoints else None
        density_factor = 1.0
        if settings.SLEEP_TAPER_ENABLED and progress >= settings.TAPER_START_PERCENTAGE:
            density_factor = settings.TAPER_REDUCTION_FACTOR
        beat_plan = self._create_recursive_beat_plan(beat_idx, current_sensory, current_waypoint, density_factor)
        memory_context = "\n".join(outline_memory[-3:]) if outline_memory else "Beginning of story"
        enhanced_prompt = BEAT_GENERATION_PROMPT.format(
            story_bible=base_prompt,
            previous_text=memory_context,
            beat_title=f"Beat {beat_idx+1}",
            beat_description=beat_plan['micro_goal'],
            target_words=180,
            sensory_focus=current_sensory,
            waypoint=current_waypoint or 'natural flow',
            destination_phase=destination_phase
        )
        generator_output = await self._safe_generate_with_retry(self.generator_name, enhanced_prompt, options)
        self.metrics["generator_words"] += len(generator_output.split())
        reasoner_output = generator_output
        if self.use_reasoner:
            reasoner_prompt = f"""You are a structural editor for embodiment and destination arcs.\n\nTEXT:\n{generator_output}\n\nCHECKLISTS:\n{REASONER_EMBODIMENT_CHECKLIST}\n{REASONER_DESTINATION_CHECKLIST}\n\nRewrite minimally to satisfy the checklists while keeping tone and pace.\n"""
            reasoner_output = await self._safe_generate_with_retry(self.reasoner_name, reasoner_prompt, {"temperature":0.3})
            self.metrics["reasoner_words"] += len(reasoner_output.split())
            if reasoner_output and reasoner_output != generator_output:
                self.metrics["corrections_count"] += 1
        final_output = reasoner_output
        if self.use_polish:
            polish_prompt = f"Polish for soothing flow, keep 2nd person present and causal sensory from action.\n\nTEXT:\n{reasoner_output}\n\nPolished version:"
            final_output = await self._safe_generate_with_retry(self.polisher_name, polish_prompt, {"temperature":0.4})
            self.metrics["polisher_words"] += len(final_output.split())
        target_words = len(generator_output.split()) or 180
        final_output = self._apply_length_control(final_output, target_words)
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
        default_waypoints = ["entry path", "gentle bend", "small clearing", "wooden bridge", "soft moss hollow"]
        return setting.get("theme", {}).get("spatial_waypoints", default_waypoints)

    def _destination_phase(self, progress: float) -> str:
        if progress < 0.3: return "departure"
        if progress < 0.7: return "journey"
        if progress < 0.9: return "approach"
        return "arrival"

    # Missing helpers restored
    def _calculate_coherence_stats(self, story_beats: List[Dict]) -> Dict:
        return {
            "total_beats": len(story_beats),
            "sensory_transitions": len(set([b.get("sensory_mode") for b in story_beats])),
            "avg_density_factor": sum([b.get("density_factor", 1.0) for b in story_beats])/max(1,len(story_beats)),
            "corrections_applied": self.metrics.get("corrections_count", 0)
        }

    def _get_sensory_distribution(self, story_beats: List[Dict]) -> Dict:
        dist: Dict[str,int] = {}
        for b in story_beats:
            m = b.get("sensory_mode","unknown")
            dist[m] = dist.get(m,0)+1
        return dist

    def _create_beats_schema(self, story_beats: List[Dict]) -> Dict:
        return {
            "beats": [
                {
                    "beat_index": i,
                    "text": b.get("text",""),
                    "sensory_mode": b.get("sensory_mode"),
                    "waypoint": b.get("waypoint"),
                    "word_count": b.get("word_count"),
                    "timing_estimate": b.get("word_count",150)/150*60,
                    "media_cues": {
                        "visual_focus": b.get("sensory_mode") == "sight",
                        "audio_focus": b.get("sensory_mode") == "sound",
                        "ambient_suggestion": b.get("waypoint","")
                    }
                } for i,b in enumerate(story_beats)
            ],
            "total_estimated_duration": sum([b.get("word_count",150)/150*60 for b in story_beats]),
            "schema_version": "1.0"
        }

    async def _safe_generate_with_retry(self, model: str, prompt: str, options: Optional[Dict] = None) -> str:
        opts = options or {"temperature": 0.7, "num_predict": 300}
        last_error = None
        for attempt in range(settings.MAX_RETRIES):
            try:
                response = self.client.generate(model=model, prompt=prompt, options=opts)
                result = response.get("response","").strip()
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
        cur = len(text.split()); mi = int(target_words*0.9); ma = int(target_words*1.1)
        if cur > ma:
            words = text.split(); trunc = ' '.join(words[:ma])
            if '.' in trunc:
                s = trunc.split('.')
                trunc = '.'.join(s[:-1]) + '.'
            return trunc
        return text

    def _update_opener_tracking(self, text: str):
        if not text: return
        first = text.split('.')[0] if '.' in text else text[:50]
        pattern = first[:20].lower().strip()
        if pattern:
            self.opener_usage[pattern] = self.opener_usage.get(pattern,0)+1

    def _insert_tts_markers(self, story_text: str) -> str:
        if not self.tts_markers: return story_text
        sentences = re.split(r'[.!?]+', story_text)
        marked = []
        for i, s in enumerate(sentences):
            if not s.strip(): continue
            t = s.strip()
            if i>0 and i % settings.TTS_BREATHE_FREQUENCY == 0:
                t = "[BREATHE] " + t
            if i>0 and len(t.split())>15:
                pause = settings.TTS_PAUSE_MIN + (settings.TTS_PAUSE_MAX - settings.TTS_PAUSE_MIN) * 0.5
                t += f" [PAUSE:{pause:.1f}]"
            marked.append(t)
        return '. '.join(marked) + '.'
