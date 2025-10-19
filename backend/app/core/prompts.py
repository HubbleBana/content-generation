THEME_ANALYSIS_PROMPT = '''You are a creative analyst for sleep stories.

Given theme: {theme}
Additional description: {description}

Analyze and extract sensory elements and output as JSON:
{{
  "setting": "detailed location",
  "time_of_day": "dawn/dusk/night",
  "mood": "peaceful",
  "sensory_elements": ["visual", "audio"],
  "key_objects": ["list", "of", "objects"],
  "atmosphere": "description"
}}
'''

OUTLINE_GENERATION_PROMPT = '''You are a master storyteller for calming sleep narratives.

TASK: Create a 3-act outline for a {duration}-minute sleep story.

THEME: {theme}
TARGET WORDS: {target_words} ({duration} min x 140 wpm)
BEATS: {beats} total

OUTPUT strict JSON:
{{
  "story_bible": {{
    "setting": "location",
    "time_of_day": "dawn/dusk/night",
    "key_objects": ["object1", "object2"],
    "mood_baseline": 8
  }},
  "acts": [
    {{
      "act_number": 1,
      "title": "Arrival",
      "beats": [
        {{
          "beat_id": 1,
          "title": "First glimpse",
          "target_words": 600,
          "description": "You arrive...",
          "sensory_focus": ["sight", "sound"]
        }}
      ]
    }}
  ]
}}
'''

BEAT_GENERATION_PROMPT = '''CONTEXT:
{story_bible}

PREVIOUS TEXT (last 500 words):
{previous_text}

CURRENT BEAT:
Title: {beat_title}
Description: {beat_description}
Target: ~{target_words} words
Sensory: {sensory_focus}

STYLE: Second person, present tense, slow pacing, rich sensory details, NO tension.

Generate next segment now:
'''

SELF_REFINE_PROMPT = '''Review this segment:
{text}

Score 1-10: Calmness, Sensory richness, Pacing, Coherence

IF all >= 8: "APPROVED"
ELSE: Specify improvements
'''
