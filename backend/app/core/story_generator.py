import ollama
from typing import Optional, Callable
import json
import re

from app.core.config import settings
from app.core.memory_system import MemorySystem
from app.core.coherence_system import CoherenceSystem
from app.core.narrative_controller import NarrativeController
from app.core.prompts import THEME_ANALYSIS_PROMPT, OUTLINE_GENERATION_PROMPT, BEAT_GENERATION_PROMPT

import logging
logger = logging.getLogger(__name__)

class StoryGenerator:
    def __init__(self, target_language: str = "en", translation_quality: str = "high"):
        self.client = ollama.Client(host=settings.OLLAMA_URL)
        self.target_language = target_language
        # translation removed per request (focus English only)
        self.coherence_system = CoherenceSystem()
        logger.info(f"StoryGenerator initialized - English focus")
    
    async def generate_full_story(self, theme: str, duration: int = 45, description: Optional[str] = None, job_id: Optional[str] = None, update_callback: Optional[Callable] = None) -> dict:
        def update(progress: float, step: str, step_num: int = 0):
            if update_callback:
                update_callback(progress, step, step_num)
            logger.info(f'progress, progress={progress}, step={step}')
        
        # 1) Theme & Outline
        update(5, 'Analyzing theme and creating story concept...', 1)
        enriched_theme = await self._analyze_theme_validated(theme, description)
        
        update(10, 'Generating detailed story outline...', 2)
        outline = await self._generate_outline_validated(enriched_theme, duration)
        
        # 2) Initialize systems
        update(15, 'Initializing coherence and memory systems...', 3)
        memory = MemorySystem(outline.get('story_bible', {}))
        self.coherence_system.initialize_story_bible(outline.get('story_bible', {}))
        acts = outline.get('acts', [])
        total_beats = sum(len(act.get('beats', [])) for act in acts)
        target_words_total = duration * settings.TARGET_WPM
        controller = NarrativeController(total_beats=total_beats, target_words_total=target_words_total)
        
        # Optional: inject simple waypoints if vineyard, forest, beach are in setting
        setting_text = str(outline.get('story_bible', {}).get('setting', '')).lower()
        if any(k in setting_text for k in ['vineyard','forest','beach','mountain','garden']):
            controller.set_waypoints([
                ['path','trail','entrance'],
                ['rows','leaves','canopy'],
                ['clearing','opening','meadow'],
                ['stream','brook','water'],
                ['cottage','cellar','shelter']
            ])
        
        # 3) Generate beats
        update(20, 'Generating English story content...', 4)
        full_story_english = ''
        beat_index = 0
        for act in acts:
            for beat in act.get('beats', []):
                beat_index += 1
                progress = 20 + (50 * beat_index / max(1,total_beats))
                beat_title = beat.get('title', f'Beat {beat_index}')
                update(progress, f'Writing: {beat_title} ({beat_index}/{total_beats})', 4)
                
                # Per-beat target from controller
                per_target = controller.target_for(beat_index)
                beat['target_words'] = per_target
                
                # Generate beat (with coherence guidance)
                text = await self._generate_beat(beat, memory)
                
                # Vary repetitive openers
                text = controller.vary_openers(text)
                
                # Enforce exact length (±10% then rewrite to exact)
                text = controller.enforce_exact_length(text, per_target, self.client)
                
                # Update systems
                memory.add_beat(beat.get('beat_id', beat_index), text)
                self.coherence_system.add_beat_context(beat_index, text, beat)
                full_story_english += text + '\n\n'
        
        # 4) Final polish and metrics
        update(70, 'Polishing English version...', 5)
        full_story_english = self._final_polish(full_story_english)
        
        update(95, 'Validating final output and calculating metrics...', 7)
        english_word_count = len(full_story_english.split())
        target_words = target_words_total
        accuracy_percent = round(abs(english_word_count - target_words) / max(1,target_words) * 100, 2)
        duration_estimate = round(english_word_count / settings.TARGET_WPM, 1)
        
        result = {
            'story_text': full_story_english,
            'outline': outline,
            'metrics': {
                'english_word_count': english_word_count,
                'target_words': target_words,
                'accuracy_percent': accuracy_percent,
                'duration_estimate_minutes': duration_estimate,
                'beats_generated': total_beats,
                'target_language': 'en'
            },
            'coherence_stats': self.coherence_system.get_memory_stats(),
            'memory_stats': memory.get_metrics()
        }
        
        update(100, '✅ Generation complete!', 8)
        return result
    
    async def _analyze_theme_validated(self, theme: str, description: Optional[str]) -> dict:
        prompt = THEME_ANALYSIS_PROMPT.format(theme=theme, description=description or 'None')
        for attempt in range(3):
            try:
                response = self.client.generate(model=settings.MODEL_NAME, prompt=prompt, options={'temperature': settings.MODEL_TEMPERATURE, 'num_predict': 800})
                json_text = self._extract_json(response['response'])
                enriched = json.loads(json_text)
                if all(k in enriched for k in ['setting','mood','sensory_elements']):
                    return enriched
                raise ValueError('Missing fields')
            except Exception:
                if attempt == 2:
                    return self._fallback_theme(theme)
                prompt = 'Output valid JSON with: setting, time_of_day, mood, sensory_elements, key_objects, atmosphere'
        return self._fallback_theme(theme)
    
    async def _generate_outline_validated(self, theme: dict, duration: int) -> dict:
        target_words = duration * settings.TARGET_WPM
        prompt = OUTLINE_GENERATION_PROMPT.format(theme=json.dumps(theme), duration=duration, target_words=target_words, beats=settings.BEATS_PER_STORY)
        for attempt in range(3):
            try:
                response = self.client.generate(model=settings.MODEL_NAME, prompt=prompt, options={'temperature': settings.MODEL_TEMPERATURE, 'num_predict': settings.MAX_TOKENS_OUTLINE})
                json_text = self._extract_json(response['response'])
                outline = json.loads(json_text)
                if 'story_bible' in outline and 'acts' in outline:
                    total_beats = sum(len(act.get('beats', [])) for act in outline.get('acts', []))
                    if total_beats >= 8:
                        return outline
                    raise ValueError('Not enough beats')
                raise ValueError('Missing structure')
            except Exception:
                if attempt == 2:
                    return self._fallback_outline(theme, duration)
                prompt = 'Generate valid JSON outline with story_bible and acts array'
        return self._fallback_outline(theme, duration)
    
    async def _generate_beat(self, beat: dict, memory: MemorySystem) -> str:
        context = memory.get_context_for_beat(beat.get('beat_id', 0))
        target_words = beat.get('target_words', 600)
        coherence_additions = self.coherence_system.get_coherence_prompt_additions()
        
        guidance = ''
        if coherence_additions:
            guidance = f"\n\nCOHERENCE REQUIREMENTS:\n{coherence_additions}\n\n"
        
        prompt = BEAT_GENERATION_PROMPT.format(
            story_bible=json.dumps(context.get('story_bible', {})),
            previous_text=context.get('last_500_words', 'Start'),
            beat_title=beat.get('title', 'Continue'),
            beat_description=beat.get('description', 'Continue'),
            target_words=target_words,
            sensory_focus=', '.join(beat.get('sensory_focus', ['sight']))
        ) + guidance + f"EXACT WORD COUNT: {target_words}. Avoid repeated openers."
        
        response = self.client.generate(model=settings.MODEL_NAME, prompt=prompt, options={'temperature': settings.MODEL_TEMPERATURE, 'num_predict': settings.MAX_TOKENS_BEAT})
        text = response['response'].strip()
        return text
    
    def _final_polish(self, story: str) -> str:
        lines = [line.strip() for line in story.split('\n') if line.strip()]
        return '\n\n'.join(lines)
    
    def _extract_json(self, text: str) -> str:
        json_marker = '```json'
        code_marker = '```'
        if json_marker in text:
            start = text.find(json_marker) + len(json_marker)
            end = text.find(code_marker, start)
            if end > start:
                return text[start:end].strip()
        if code_marker in text:
            start = text.find(code_marker) + len(code_marker)
            end = text.find(code_marker, start)
            if end > start:
                return text[start:end].strip()
        m = re.search(r'\{.*\}', text, re.DOTALL)
        return m.group(0) if m else text.strip()
    
    def _fallback_theme(self, theme: str) -> dict:
        return {'setting': theme, 'time_of_day': 'dawn', 'mood': 'peaceful', 'sensory_elements': ['visual','audio'], 'key_objects': [], 'atmosphere': 'calm'}
    
    def _fallback_outline(self, theme: dict, duration: int) -> dict:
        target_words = duration * settings.TARGET_WPM
        words_per_beat = max(80, target_words // 12)
        return {'story_bible': {'setting': theme.get('setting', 'location'), 'time_of_day': 'dawn', 'mood_baseline': 8, 'key_objects': []}, 'acts': [{'act_number': i, 'title': ['Arrival','Exploration','Rest'][i-1], 'beats': [{'beat_id': (i-1)*4 + j, 'title': f'Beat {(i-1)*4 + j}', 'description': 'Continue the peaceful journey', 'target_words': words_per_beat, 'sensory_focus': ['sight','sound']} for j in range(1,5)]} for i in range(1,4)]}
