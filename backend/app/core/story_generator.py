import ollama
from typing import Optional, Callable
import json
import re
import asyncio

from app.core.config import settings
from app.core.memory_system import MemorySystem
from app.core.translation_system import TranslationSystem
from app.core.coherence_system import CoherenceSystem
from app.core.prompts import THEME_ANALYSIS_PROMPT, OUTLINE_GENERATION_PROMPT, BEAT_GENERATION_PROMPT, SELF_REFINE_PROMPT

import logging
logger = logging.getLogger(__name__)

class StoryGenerator:
    def __init__(self, target_language: str = "en", translation_quality: str = "high"):
        self.client = ollama.Client(host=settings.OLLAMA_URL)
        self.target_language = target_language
        self.translation_quality = translation_quality
        
        # Initialize advanced systems
        self.translator = TranslationSystem(quality_mode=translation_quality) if target_language != "en" else None
        self.coherence_system = None
        
        logger.info(f"StoryGenerator initialized - Language: {target_language}, Translation: {translation_quality}")
    
    async def generate_full_story(self, theme: str, duration: int = 45, description: Optional[str] = None, job_id: Optional[str] = None, update_callback: Optional[Callable] = None) -> dict:
        logger.info(f'story_start, theme={theme}, duration={duration}, language={self.target_language}')
        
        def update(progress: float, step: str, step_num: int = 0):
            if update_callback:
                update_callback(progress, step, step_num)
            logger.info(f'progress, progress={progress}, step={step}')
        
        try:
            # Step 1: Theme Analysis
            update(5, 'Analyzing theme and creating story concept...', 1)
            enriched_theme = await self._analyze_theme_validated(theme, description)
            
            # Step 2: Outline Generation
            update(10, 'Generating detailed story outline...', 2)
            outline = await self._generate_outline_validated(enriched_theme, duration)
            
            # Step 3: Initialize Systems
            update(15, 'Initializing coherence and memory systems...', 3)
            memory = MemorySystem(outline.get('story_bible', {}))
            #self.coherence_system.initialize_story_bible(outline.get('story_bible', {}))
            
            # Step 4: Generate English Story
            update(20, 'Generating English story content...', 4)
            full_story_english = ''
            acts = outline.get('acts', [])
            total_beats = sum(len(act.get('beats', [])) for act in acts)
            beat_index = 0
            
            # Generate each beat with enhanced coherence
            for act in acts:
                for beat in act.get('beats', []):
                    beat_index += 1
                    progress = 20 + (50 * beat_index / total_beats)  # 20-70% for generation
                    beat_title = beat.get('title', 'Beat ' + str(beat_index))
                    update(progress, f'Writing: {beat_title} ({beat_index}/{total_beats})', 4)
                    
                    # Generate beat with coherence system
                    beat_text = await self._generate_beat_with_enhanced_coherence(
                        beat, memory, beat_index
                    )
                    
                    # Update systems
                    memory.add_beat(beat.get('beat_id', beat_index), beat_text)
                    #self.coherence_system.add_beat_context(
                    #    beat_index, beat_text, beat
                    #)
                    
                    full_story_english += beat_text + '\n\n'
            
            # Step 5: Final Polish (English)
            update(70, 'Polishing English version...', 5)
            full_story_english = self._final_polish(full_story_english)
            
            # Step 6: Translation (if needed)
            if self.target_language != "en" and self.translator:
                update(75, 'Translating to Italian with pace preservation...', 6)
                
                translation_result = await self.translator.translate_story_with_pace_preservation(
                    full_story_english, update_callback
                )
                
                full_story_translated = translation_result['translated_text']
                translation_metrics = translation_result['translation_metrics']
            else:
                full_story_translated = full_story_english
                translation_metrics = {'note': 'No translation performed'}
            
            # Step 7: Final Validation
            update(95, 'Validating final output and calculating metrics...', 7)
            
            # Calculate metrics for both versions
            english_word_count = len(full_story_english.split())
            final_word_count = len(full_story_translated.split())
            target_words = duration * settings.TARGET_WPM
            
            # Use English word count for accuracy since that's what we targeted
            accuracy_percent = round(abs(english_word_count - target_words) / target_words * 100, 2)
            duration_estimate = round(final_word_count / settings.TARGET_WPM, 1)
            
            # Compile results
            result = {
                'story_text': full_story_translated,  # Final translated version
                'story_text_english': full_story_english,  # Original English version
                'outline': outline,
                'metrics': {
                    'english_word_count': english_word_count,
                    'final_word_count': final_word_count,
                    'target_words': target_words,
                    'accuracy_percent': accuracy_percent,
                    'duration_estimate_minutes': duration_estimate,
                    'beats_generated': total_beats,
                    'target_language': self.target_language
                },
                'translation_metrics': translation_metrics,
                'coherence_stats': self.coherence_system.get_memory_stats(),
                'memory_stats': memory.get_metrics()
            }
            
            update(100, '✅ Generation complete!', 8)
            logger.info(f'complete, english_words={english_word_count}, final_words={final_word_count}, language={self.target_language}')
            return result
            
        except Exception as e:
            logger.error(f'failed error={str(e)}')
            raise
    
    async def _analyze_theme_validated(self, theme: str, description: Optional[str]) -> dict:
        prompt = THEME_ANALYSIS_PROMPT.format(theme=theme, description=description or 'None')
        
        for attempt in range(3):
            try:
                response = self.client.generate(
                    model=settings.MODEL_NAME, 
                    prompt=prompt, 
                    options={
                        'temperature': settings.MODEL_TEMPERATURE, 
                        'num_predict': 800
                    }
                )
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
        prompt = OUTLINE_GENERATION_PROMPT.format(
            theme=json.dumps(theme), 
            duration=duration, 
            target_words=target_words, 
            beats=settings.BEATS_PER_STORY
        )
        
        for attempt in range(3):
            try:
                response = self.client.generate(
                    model=settings.MODEL_NAME, 
                    prompt=prompt, 
                    options={
                        'temperature': settings.MODEL_TEMPERATURE, 
                        'num_predict': settings.MAX_TOKENS_OUTLINE
                    }
                )
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
    
    async def _generate_beat_with_enhanced_coherence(self, beat: dict, memory: MemorySystem, beat_id: int) -> str:
        """Generate beat with enhanced coherence system"""
        
        context = memory.get_context_for_beat(beat.get('beat_id', beat_id))
        target_words = beat.get('target_words', 600)
        
        # Get coherence additions for the prompt
        coherence_additions = self.coherence_system.get_coherence_prompt_additions()
        
        # Enhanced prompt with coherence information
        base_prompt = BEAT_GENERATION_PROMPT.format(
            story_bible=json.dumps(context.get('story_bible', {})),
            previous_text=context.get('last_500_words', 'Start'),
            beat_title=beat.get('title', 'Continue'),
            beat_description=beat.get('description', 'Continue'),
            target_words=target_words,
            sensory_focus=', '.join(beat.get('sensory_focus', ['sight']))
        )
        
        if coherence_additions:
            prompt = f"{base_prompt}\n\nCOHERENCE REQUIREMENTS:\n{coherence_additions}\n\nGenerate next segment now:"
        else:
            prompt = base_prompt
        
        # Generate initial beat
        response = self.client.generate(
            model=settings.MODEL_NAME,
            prompt=prompt,
            options={
                'temperature': settings.MODEL_TEMPERATURE,
                'num_predict': settings.MAX_TOKENS_BEAT
            }
        )
        beat_text = response['response'].strip()
        
        # Validate coherence
        coherence_result = self.coherence_system.validate_beat_coherence(beat_text, beat_id)
        
        # If coherence is poor, try to fix it
        if coherence_result['needs_revision'] and settings.AUTO_RETRY_ENABLED:
            logger.info(f'coherence_retry, beat={beat_id}, score={coherence_result["coherence_score"]:.2f}')
            
            improvement_prompt = self.coherence_system.suggest_beat_improvements(
                beat_text, coherence_result
            )
            
            if improvement_prompt:
                try:
                    response = self.client.generate(
                        model=settings.MODEL_NAME,
                        prompt=improvement_prompt,
                        options={
                            'temperature': 0.4,  # Lower temperature for revision
                            'num_predict': settings.MAX_TOKENS_BEAT
                        }
                    )
                    revised_text = response['response'].strip()
                    
                    # Use revised version if it's better
                    revised_coherence = self.coherence_system.validate_beat_coherence(
                        revised_text, beat_id
                    )
                    
                    if revised_coherence['coherence_score'] > coherence_result['coherence_score']:
                        beat_text = revised_text
                        logger.info(f'coherence_improved, {coherence_result["coherence_score"]:.2f} -> {revised_coherence["coherence_score"]:.2f}')
                    
                except Exception as e:
                    logger.warning(f'coherence_revision_failed: {e}')
        
        # Standard length tuning (existing logic)
        actual_words = len(beat_text.split())
        deviation = abs(actual_words - target_words) / target_words
        
        if deviation > 0.20 and settings.AUTO_RETRY_ENABLED:
            logger.info(f'length_tuning, actual={actual_words}, target={target_words}')
            if actual_words < target_words * 0.8:
                tune_prompt = f'Expand this to approximately {target_words} words with more sensory details: {beat_text}'
            else:
                tune_prompt = f'Condense this to approximately {target_words} words while keeping the essence: {beat_text}'
            
            try:
                response = self.client.generate(
                    model=settings.MODEL_NAME,
                    prompt=tune_prompt,
                    options={
                        'temperature': 0.6,
                        'num_predict': settings.MAX_TOKENS_BEAT
                    }
                )
                beat_text = response['response'].strip()
            except Exception as e:
                logger.warning(f'length_tuning_failed: {e}')
        
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
        return {
            'setting': theme, 
            'time_of_day': 'dawn', 
            'mood': 'peaceful', 
            'sensory_elements': ['visual', 'audio'], 
            'key_objects': [], 
            'atmosphere': 'calm'
        }
    
    def _fallback_outline(self, theme: dict, duration: int) -> dict:
        target_words = duration * settings.TARGET_WPM
        words_per_beat = target_words // 12
        return {
            'story_bible': {
                'setting': theme.get('setting', 'location'), 
                'time_of_day': 'dawn', 
                'mood_baseline': 8, 
                'key_objects': []
            }, 
            'acts': [
                {
                    'act_number': i, 
                    'title': ['Arrival', 'Exploration', 'Rest'][i-1], 
                    'beats': [
                        {
                            'beat_id': (i-1)*4 + j, 
                            'title': f'Beat {(i-1)*4 + j}', 
                            'description': 'Continue the peaceful journey', 
                            'target_words': words_per_beat, 
                            'sensory_focus': ['sight', 'sound']
                        } for j in range(1, 5)
                    ]
                } for i in range(1, 4)
            ]
        }