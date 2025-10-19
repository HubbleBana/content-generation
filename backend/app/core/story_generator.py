import ollama
from typing import Optional, Callable
import json
import re

from app.core.config import settings
from app.core.memory_system import MemorySystem
from app.core.prompts import THEME_ANALYSIS_PROMPT, OUTLINE_GENERATION_PROMPT, BEAT_GENERATION_PROMPT, SELF_REFINE_PROMPT

import logging
logger = logging.getLogger(__name__)

class StoryGenerator:
    def __init__(self):
        self.client = ollama.Client(host=settings.OLLAMA_URL)
    
    async def generate_full_story(self, theme: str, duration: int = 45, description: Optional[str] = None, job_id: Optional[str] = None, update_callback: Optional[Callable] = None) -> dict:
        logger.info(f'story_start, theme={theme}, duration={duration}')
        
        def update(progress: float, step: str):
            if update_callback:
                update_callback(progress, step)
            logger.info(f'progress, progress={progress}, step={step}')
        
        try:
            update(5, 'Analyzing theme')
            enriched_theme = await self._analyze_theme_validated(theme, description)
            
            update(10, 'Generating outline')
            outline = await self._generate_outline_validated(enriched_theme, duration)
            
            update(15, 'Initializing memory')
            memory = MemorySystem(outline.get('story_bible', {}))
            
            full_story = ''
            acts = outline.get('acts', [])
            total_beats = sum(len(act.get('beats', [])) for act in acts)
            beat_index = 0
            
            for act in acts:
                for beat in act.get('beats', []):
                    beat_index += 1
                    progress = 15 + (60 * beat_index / total_beats)
                    beat_title = beat.get('title', 'Beat ' + str(beat_index))
                    update(progress, 'Writing: ' + beat_title + ' (' + str(beat_index) + '/' + str(total_beats) + ')')
                    
                    beat_text = await self._generate_beat_with_tuning(beat, memory)
                    memory.add_beat(beat.get('beat_id', beat_index), beat_text)
                    full_story += beat_text + '\n\n'
            
            update(80, 'Validating')
            update(90, 'Polish')
            full_story = self._final_polish(full_story)
            
            word_count = len(full_story.split())
            target_words = duration * settings.TARGET_WPM
            
            result = {
                'story_text': full_story,
                'outline': outline,
                'metrics': {
                    'word_count': word_count,
                    'target_words': target_words,
                    'accuracy_percent': round(abs(word_count - target_words) / target_words * 100, 2),
                    'duration_estimate_minutes': round(word_count / settings.TARGET_WPM, 1),
                    'beats_generated': total_beats
                },
                'memory_stats': memory.get_metrics()
            }
            
            update(100, 'Complete!')
            logger.info(f'complete, words={word_count}')
            return result
            
        except Exception as e:
            logger.error(f'failed error={str(e)}')
            raise
    
    async def _analyze_theme_validated(self, theme: str, description: Optional[str]) -> dict:
        prompt = THEME_ANALYSIS_PROMPT.format(theme=theme, description=description or 'None')
        
        for attempt in range(3):
            try:
                response = self.client.generate(model=settings.MODEL_NAME, prompt=prompt, options={'temperature': settings.MODEL_TEMPERATURE, 'num_predict': 800})
                json_text = self._extract_json(response['response'])
                enriched = json.loads(json_text)
                required = ['setting', 'mood', 'sensory_elements']
                if all(k in enriched for k in required):
                    logger.info(f'theme_ok, attempt={attempt+1}')
                    return enriched
                else:
                    raise ValueError('Missing fields')
            except Exception as e:
                logger.warning(f'theme_retry, attempt={attempt+1}, error={str(e)}')
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
                        logger.info(f'outline_ok, beats={total_beats}')
                        return outline
                    raise ValueError('Not enough beats')
                raise ValueError('Missing structure')
            except Exception as e:
                logger.warning(f'outline_retry, attempt={attempt+1}, error={str(e)}')
                if attempt == 2:
                    return self._fallback_outline(theme, duration)
                prompt = 'Generate valid JSON outline with story_bible and acts array'
        return self._fallback_outline(theme, duration)
    
    async def _generate_beat_with_tuning(self, beat: dict, memory: MemorySystem) -> str:
        context = memory.get_context_for_beat(beat.get('beat_id', 0))
        target_words = beat.get('target_words', 600)
        prompt = BEAT_GENERATION_PROMPT.format(story_bible=json.dumps(context.get('story_bible', {})), previous_text=context.get('last_500_words', 'Start'), beat_title=beat.get('title', 'Continue'), beat_description=beat.get('description', 'Continue'), target_words=target_words, sensory_focus=', '.join(beat.get('sensory_focus', ['sight'])))
        
        response = self.client.generate(model=settings.MODEL_NAME, prompt=prompt, options={'temperature': settings.MODEL_TEMPERATURE, 'repetition_penalty': settings.MODEL_REPETITION_PENALTY, 'num_predict': settings.MAX_TOKENS_BEAT})
        beat_text = response['response'].strip()
        
        actual_words = len(beat_text.split())
        deviation = abs(actual_words - target_words) / target_words
        
        if deviation > 0.20 and settings.AUTO_RETRY_ENABLED:
            logger.info(f'tuning, actual={actual_words}, target={target_words}')
            if actual_words < target_words * 0.8:
                tune_prompt = 'Expand this to ' + str(target_words) + ' words with more details: ' + beat_text
            else:
                tune_prompt = 'Condense this to ' + str(target_words) + ' words: ' + beat_text
            response = self.client.generate(model=settings.MODEL_NAME, prompt=tune_prompt, options={'temperature': 0.6, 'num_predict': settings.MAX_TOKENS_BEAT})
            beat_text = response['response'].strip()
        
        return beat_text
    
    def _final_polish(self, story: str) -> str:
        lines = [line.strip() for line in story.split('\n') if line.strip()]
        return '\n\n'.join(lines)
    
    def _extract_json(self, text: str) -> str:
        # Define markers as variables to avoid confusion
        json_marker = '```json'
        code_marker = '```'
        
        # Try to extract from ```json ... ```
        if json_marker in text:
            start = text.find(json_marker) + len(json_marker)
            end = text.find(code_marker, start)
            if end > start:
                return text[start:end].strip()
        
        # Try to extract from ``` ... ```
        if code_marker in text:
            start = text.find(code_marker) + len(code_marker)
            end = text.find(code_marker, start)
            if end > start:
                return text[start:end].strip()
        
        # Try regex to find JSON object
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json_match.group(0)
        
        # If nothing works, return original text
        return text.strip()

        
    def _fallback_theme(self, theme: str) -> dict:
        return {'setting': theme, 'time_of_day': 'dawn', 'mood': 'peaceful', 'sensory_elements': ['visual', 'audio'], 'key_objects': [], 'atmosphere': 'calm'}
    
    def _fallback_outline(self, theme: dict, duration: int) -> dict:
        target_words = duration * settings.TARGET_WPM
        words_per_beat = target_words // 12
        return {'story_bible': {'setting': theme.get('setting', 'location'), 'time_of_day': 'dawn', 'mood_baseline': 8, 'key_objects': []}, 'acts': [{'act_number': i, 'title': ['Arrival', 'Exploration', 'Rest'][i-1], 'beats': [{'beat_id': (i-1)*4 + j, 'title': 'Beat ' + str((i-1)*4 + j), 'description': 'Continue', 'target_words': words_per_beat, 'sensory_focus': ['sight', 'sound']} for j in range(1, 5)]} for i in range(1, 4)]}
