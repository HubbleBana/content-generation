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
  "atmosphere": "description",
  "spatial_waypoints": ["point1", "point2"],
  "sleep_elements": ["gentle rhythm", "calming imagery"],
  "sensory_opportunities": {{"sight": [], "sound": [], "touch": []}}
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
      "title": "Departure",
      "beats": [
        {{
          "beat_id": 1,
          "title": "Destination Promise",
          "target_words": 600,
          "description": "Establish a clear destination to walk toward tonight.",
          "sensory_focus": ["sight", "sound"],
          "waypoint": "entry path"
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

MOVEMENT SCAFFOLD (MANDATORY):
- Waypoint: {waypoint}
- Action (second person, present): verb of movement (e.g., "ti incammini", "attraversi")
- Consequent Perceptions: at least 2, one corporeal (feet, hands, breath), one environmental (light, sound, scent)
- Spatial Transition: one directional connector ("più avanti", "oltre il", "raggiungi")
- Downshift: breath slows / shoulders release / pace softens

DESTINATION PHASE: {destination_phase}
- If departure: introduce/recall the destination promise subtly
- If journey: include progress markers ("ti avvicini")
- If approach: add approach signals (glimpse, scent, sound of destination)
- If arrival: explicit arrival + settling actions + permission to rest

STYLE: Second person, present tense, slow pacing, causal sensory from action, NO lists, NO tension.

Generate next segment now:
'''

REASONER_EMBODIMENT_CHECKLIST = '''Ensure the text contains:
- At least one movement verb in second person
- One spatial transition connector
- Two consequent perceptions (corporeal + environmental)
- One downshift (breath, relaxation)
- Maintain strict second person, present tense
If missing, rewrite to include them without changing meaning.
'''

REASONER_DESTINATION_CHECKLIST = '''Ensure destination arc integrity:
- Early beats: clear destination promise
- Middle beats: progress markers toward destination
- Final beats: explicit arrival and settlement; invite rest/sleep
If missing, rewrite minimally to restore the arc.
'''

SELF_REFINE_PROMPT = '''Review this segment:
{text}

Score 1-10: Calmness, Sensory richness, Pacing, Coherence

IF all >= 8: "APPROVED"
ELSE: Specify improvements
'''
