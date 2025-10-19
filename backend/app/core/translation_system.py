import ollama
import re
import asyncio
from typing import List, Dict, Optional, Tuple
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class TranslationSystem:
    """High-quality English->Italian translation system optimized for sleep stories"""
    
    def __init__(self, quality_mode: str = "high"):
        self.client = ollama.Client(host=settings.OLLAMA_URL)
        self.quality_mode = quality_mode  # "high" or "fast"
        self.translation_cache = {}  # Cache for common phrases
        
        # Pace-preserving patterns for Italian translation
        self.pace_patterns = {
            # Ellipses and pauses
            r'\.\.\.': '...',
            r'\,\s+': ', ',
            # Breathing spaces
            r'\s+and\s+': ' e ',
            r'\s+but\s+': ' ma ',
            r'\s+or\s+': ' o ',
            # Soft transitions
            r'\bgently\b': 'dolcemente',
            r'\bslowly\b': 'lentamente', 
            r'\bquietly\b': 'silenziosamente',
            r'\bsoftly\b': 'soavemente'
        }
        
        # Italian sleep story vocabulary optimization
        self.sleep_vocabulary = {
            'breathe': 'respira',
            'relax': 'rilassati',
            'peaceful': 'pacifico',
            'gentle': 'dolce',
            'calm': 'calma',
            'serenity': 'serenità',
            'tranquil': 'tranquillo',
            'whisper': 'sussurro',
            'embrace': 'abbraccio',
            'warm': 'tiepido',
            'soft': 'morbido',
            'flowing': 'che scorre',
            'distant': 'lontano',
            'horizon': 'orizzonte'
        }
    
    async def translate_story_with_pace_preservation(
        self, 
        english_text: str, 
        update_callback: Optional = None
    ) -> Dict[str, any]:
        """Translate full story while preserving pace and flow"""
        
        logger.info(f"Starting translation - mode: {self.quality_mode}")
        
        # Split into manageable chunks (preserve paragraph structure)
        chunks = self._split_into_chunks(english_text)
        translated_chunks = []
        
        total_chunks = len(chunks)
        
        for i, chunk in enumerate(chunks):
            if update_callback:
                progress = 75 + (20 * i / total_chunks)  # Translation happens 75-95%
                step = f"Translating chunk {i+1}/{total_chunks}..."
                update_callback(progress, step, 7)
            
            translated_chunk = await self._translate_chunk_high_quality(chunk)
            translated_chunks.append(translated_chunk)
            
            # Small delay to prevent overloading Ollama
            await asyncio.sleep(0.1)
        
        # Join and apply final pace adjustments
        italian_text = "\n\n".join(translated_chunks)
        italian_text = self._apply_pace_preservation(italian_text)
        italian_text = self._final_italian_polish(italian_text)
        
        # Calculate metrics
        english_words = len(english_text.split())
        italian_words = len(italian_text.split())
        pace_ratio = italian_words / english_words if english_words > 0 else 1.0
        
        return {
            'translated_text': italian_text,
            'original_text': english_text,
            'translation_metrics': {
                'english_words': english_words,
                'italian_words': italian_words,
                'pace_ratio': round(pace_ratio, 3),
                'chunks_processed': total_chunks,
                'quality_mode': self.quality_mode
            }
        }
    
    def _split_into_chunks(self, text: str, max_chunk_size: int = 800) -> List[str]:
        """Split text into chunks while preserving paragraph boundaries"""
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            # If adding this paragraph would exceed limit, save current chunk
            if len(current_chunk) + len(paragraph) > max_chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = paragraph
            else:
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph
        
        # Add remaining chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    async def _translate_chunk_high_quality(self, chunk: str) -> str:
        """High-quality translation of a single chunk"""
        
        if self.quality_mode == "fast":
            return await self._translate_chunk_fast(chunk)
        
        # High-quality mode with context and style preservation
        prompt = f"""You are a professional translator specializing in sleep stories and meditation content.

Translate this English text to Italian while preserving:
1. The EXACT same pacing and rhythm (pauses, ellipses, breathing spaces)
2. Poetic and soothing language suitable for relaxation
3. Natural Italian flow without being too literal
4. All punctuation that creates pauses (..., commas, periods)

IMPORTANT: Maintain the same sentence structure and length to preserve the calming rhythm.

English text:
{chunk}

Italian translation:"""

        try:
            response = self.client.generate(
                model=settings.MODEL_NAME,
                prompt=prompt,
                options={
                    'temperature': 0.3,  # Lower temperature for consistency
                    'num_predict': len(chunk.split()) * 2,  # Allow for Italian expansion
                    'repetition_penalty': 1.1
                }
            )
            
            translated = response['response'].strip()
            
            # Clean up common translation artifacts
            translated = self._clean_translation_artifacts(translated)
            
            return translated
            
        except Exception as e:
            logger.warning(f"High-quality translation failed, falling back: {e}")
            return await self._translate_chunk_fast(chunk)
    
    async def _translate_chunk_fast(self, chunk: str) -> str:
        """Fast translation for when high-quality fails or fast mode is selected"""
        
        prompt = f"Translate to Italian (keep same pacing): {chunk}"
        
        try:
            response = self.client.generate(
                model=settings.MODEL_NAME,
                prompt=prompt,
                options={'temperature': 0.2, 'num_predict': len(chunk.split()) * 2}
            )
            
            return response['response'].strip()
            
        except Exception as e:
            logger.error(f"Fast translation failed: {e}")
            # Fallback: basic word replacement for critical cases
            return self._emergency_translation(chunk)
    
    def _clean_translation_artifacts(self, text: str) -> str:
        """Remove common translation artifacts and improve flow"""
        
        # Remove translation prompts that sometimes leak through
        text = re.sub(r'^(Italian translation:|Traduzione italiana:)\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^(Translation:|Traduzione:)\s*', '', text, flags=re.IGNORECASE)
        
        # Fix common over-translations
        text = re.sub(r'\btanto\s+tanto\b', 'molto', text)  # "so so" -> "very"
        text = re.sub(r'\bmolto\s+molto\b', 'estremamente', text)
        
        # Improve Italian flow
        text = re.sub(r'\be\s+e\b', 'e', text)  # Remove double "and"
        text = re.sub(r'\bil\s+il\b', 'il', text)  # Remove double articles
        
        return text.strip()
    
    def _apply_pace_preservation(self, text: str) -> str:
        """Apply pace-preserving patterns to maintain rhythm"""
        
        for pattern, replacement in self.pace_patterns.items():
            text = re.sub(pattern, replacement, text)
        
        # Preserve ellipses spacing
        text = re.sub(r'\s+\.\.\.\s+', ' ... ', text)
        text = re.sub(r'\.\.\.([a-zA-Z])', r'... \1', text)
        
        # Ensure proper spacing around commas (Italian style)
        text = re.sub(r'\s*,\s*', ', ', text)
        
        return text
    
    def _final_italian_polish(self, text: str) -> str:
        """Final polish for natural Italian flow"""
        
        # Apply sleep-specific vocabulary improvements
        for eng, ita in self.sleep_vocabulary.items():
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(eng) + r'\b'
            text = re.sub(pattern, ita, text, flags=re.IGNORECASE)
        
        # Italian-specific punctuation adjustments
        text = re.sub(r'\s+\.', '.', text)  # Remove space before periods
        text = re.sub(r'\s+,', ',', text)   # Remove space before commas
        text = re.sub(r'\s+;', ';', text)   # Remove space before semicolons
        
        # Ensure proper capitalization after periods
        text = re.sub(r'\. +([a-z])', lambda m: '. ' + m.group(1).upper(), text)
        
        # Clean up multiple spaces
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _emergency_translation(self, text: str) -> str:
        """Emergency fallback translation using basic word replacement"""
        
        logger.warning("Using emergency translation - quality will be reduced")
        
        # Basic word replacement for critical sleep story terms
        emergency_dict = {
            'you': 'tu',
            'your': 'il tuo',
            'the': 'il',
            'and': 'e',
            'are': 'sei',
            'is': 'è',
            'water': 'acqua',
            'light': 'luce',
            'wind': 'vento',
            'tree': 'albero',
            'sky': 'cielo',
            'sun': 'sole',
            'moon': 'luna'
        }
        
        for eng, ita in emergency_dict.items():
            text = re.sub(r'\b' + eng + r'\b', ita, text, flags=re.IGNORECASE)
        
        return text
    
    def estimate_translation_time(self, text_length: int) -> float:
        """Estimate translation time in seconds"""
        words = text_length // 5  # Rough word estimate
        
        if self.quality_mode == "high":
            return words * 0.1  # ~0.1 seconds per word for high quality
        else:
            return words * 0.05  # ~0.05 seconds per word for fast mode