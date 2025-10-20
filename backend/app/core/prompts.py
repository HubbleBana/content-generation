# Enhanced prompts with full parameter support for all configuration options

THEME_ANALYSIS_PROMPT = '''You are a creative analyst for sleep stories with advanced parameter awareness.

Given theme: {theme}
Additional description: {description}
POV Mode: {pov_mode}
Sensory Coupling Level: {sensory_coupling}
Movement Style: {movement_style}

Analyze and extract sensory elements optimized for the specified parameters, output as JSON:
{{
  "setting": "detailed location matching movement style",
  "time_of_day": "dawn/dusk/night",
  "mood": "peaceful",
  "sensory_elements": ["visual", "audio", "tactile", "olfactory"],
  "key_objects": ["list", "of", "objects"],
  "atmosphere": "description emphasizing {pov_mode} perspective",
  "spatial_waypoints": ["point1", "point2", "point3", "point4", "point5"],
  "sleep_elements": ["gentle rhythm", "calming imagery"],
  "sensory_opportunities": {{"sight": [], "sound": [], "touch": [], "smell": [], "proprioception": []}},
  "movement_opportunities": ["embodied actions for {movement_style}"],
  "pov_considerations": "specific guidance for {pov_mode} narration"
}}\n'''

OUTLINE_GENERATION_PROMPT = '''You are a master storyteller for calming sleep narratives with parameter-aware planning.

TASK: Create a 3-act outline for a {duration}-minute sleep story.

THEME: {theme}
TARGET WORDS: {target_words} ({duration} min x 140 wpm)
BEATS: {beats} total

GENERATION PARAMETERS:
- POV Enforcement: {pov_enforce}
- Embodiment Level: {embodiment_level} movement verbs per beat
- Sensory Coupling: {sensory_coupling} senses per beat
- Destination Required: {destination_required}

OUTPUT strict JSON with parameter compliance:
{{
  "story_bible": {{
    "setting": "location",
    "time_of_day": "dawn/dusk/night",
    "key_objects": ["object1", "object2"],
    "mood_baseline": 8,
    "pov_style": "strict_second_person" if {pov_enforce} else "flexible",
    "embodiment_requirements": {{
      "movement_verbs_per_beat": {embodiment_level},
      "spatial_transitions_required": true,
      "destination_arc_enabled": {destination_required}
    }},
    "sensory_requirements": {{
      "coupling_level": {sensory_coupling},
      "rotation_enabled": true
    }}
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
          "description": "Establish clear destination with {embodiment_level} movement verbs, {sensory_coupling} sensory elements",
          "sensory_focus": ["sight", "sound"],
          "waypoint": "entry path",
          "pov_instructions": "Use strict 2nd person present" if {pov_enforce} else "Prefer 2nd person",
          "embodiment_checklist": ["movement verb", "spatial transition", "consequent perception"]
        }}
      ]
    }}
  ]
}}\n'''

BEAT_GENERATION_PROMPT = '''PARAMETER-AWARE BEAT GENERATION

CONTEXT:
{story_bible}

PREVIOUS TEXT (last 500 words):
{previous_text}

CURRENT BEAT:
Title: {beat_title}
Description: {beat_description}
Target: ~{target_words} words
Sensory Focus: {sensory_focus}

GENERATION PARAMETERS:
{generation_parameters}

MOVEMENT SCAFFOLD (MANDATORY per parameters):
- Waypoint: {waypoint}
- Action: {action_style}
- Consequent Perceptions: {perception_requirements}
- Spatial Transition: {transition_requirements}
- Downshift: {downshift_requirements}

DESTINATION PHASE: {destination_phase}
- If departure: {departure_instructions}
- If journey: {journey_instructions}
- If approach: {approach_instructions}
- If arrival: {arrival_instructions}

STYLE ENFORCEMENT:
{style_requirements}

Generate next segment with strict parameter compliance:
'''

REASONER_EMBODIMENT_CHECKLIST = '''EMBODIMENT VALIDATION (Parameter-Aware):

REQUIRED ELEMENTS:
- Movement verbs: minimum {movement_verbs_required}
- Spatial transitions: minimum {transition_tokens_required}
- Consequent perceptions: minimum {sensory_coupling}
- POV consistency: ''' + "strict 2nd person present" + ''' if {pov_enforce} else ''' + "flexible but prefer 2nd person" + '''
- Downshift elements: ''' + "required (breath/relaxation cues)" + ''' if {downshift_required} else ''' + "optional" + '''

IF MISSING ANY REQUIRED ELEMENTS:
Rewrite to include all required elements while preserving meaning and sleep-inducing tone.

IF ALL REQUIREMENTS MET:
Respond with: "EMBODIMENT_VALIDATED"
'''

REASONER_DESTINATION_CHECKLIST = '''DESTINATION ARC VALIDATION:

REQUIRED BY PHASE:
- Early beats (0-30%): Clear destination promise established
- Middle beats (30-70%): Progress markers ("approaching", "drawing closer")
- Final beats (70-100%): Explicit arrival + settlement + rest invitation
- Closure requirement: {closure_required}

IF ARC INCOMPLETE:
Add missing elements with minimal changes to existing content.

IF ARC COMPLETE:
Respond with: "DESTINATION_VALIDATED"
'''

SELF_REFINE_PROMPT = '''PARAMETER-COMPLIANT QUALITY REVIEW

Review this segment against generation parameters:
{text}

PARAMETER CHECKLIST:
{parameter_checklist}

SCORE (1-10) FOR:
- Parameter Compliance: __/10
- Calmness: __/10  
- Sensory Richness: __/10
- Pacing: __/10
- Coherence: __/10

IF ALL SCORES >= 8: "APPROVED"
ELSE: Specify required improvements for parameter compliance
'''

# Helper functions unchanged...
from typing import Dict

def format_generation_parameters(params: dict) -> str:
    formatted = []
    if params.get('pov_enforce_second_person', True):
        formatted.append("POV: Strict second person present tense (you walk, you see, you feel)")
    else:
        formatted.append("POV: Flexible but prefer second person")
    movement_req = params.get('movement_verbs_required', 1)
    if movement_req > 0:
        formatted.append(f"Movement: Minimum {movement_req} embodied action verb(s) per beat")
    sensory_req = params.get('sensory_coupling', 2)
    formatted.append(f"Sensory: Couple {sensory_req} sensory elements (sight+sound+touch)")
    if params.get('transition_tokens_required', 1) > 0:
        formatted.append(f"Transitions: Include {params['transition_tokens_required']} spatial connector(s)")
    if params.get('downshift_required', True):
        formatted.append("Downshift: Include relaxation cues (breath slows, shoulders ease)")
    if params.get('tts_markers', False):
        formatted.append("TTS: Include [PAUSE:x.x] and [BREATHE] markers")
    if params.get('strict_schema', False):
        formatted.append("Schema: Maintain structured beat format for video production")
    return "\n".join(formatted)

def format_style_requirements(params: dict) -> str:
    style_rules = []
    if params.get('pov_enforce_second_person', True):
        style_rules.append("NEVER use first person (I/me) or third person (he/she/they)")
        style_rules.append("ALWAYS use second person present: 'You walk', 'You notice', 'You feel'")
    style_rules.append("NO lists or bullet points")
    style_rules.append("NO tension, conflict, or stimulating content")
    style_rules.append("Slow pacing with natural pauses between actions")
    style_rules.append("Causal sensory descriptions (action → perception)")
    if params.get('tts_markers', False):
        style_rules.append("Natural breathing spaces marked with [BREATHE]")
        style_rules.append("Longer pauses marked with [PAUSE:2.0] for contemplation")
    return "\n".join(style_rules)

def format_action_style(params: dict) -> str:
    movement_req = params.get('movement_verbs_required', 1)
    pov_strict = params.get('pov_enforce_second_person', True)
    if movement_req > 1:
        action_style = f"Include {movement_req} distinct movement verbs in {'strict 2nd person' if pov_strict else 'preferred 2nd person'}"
    elif movement_req == 1:
        action_style = f"One clear movement verb in {'strict 2nd person present' if pov_strict else 'preferred 2nd person'}"
    else:
        action_style = "Gentle, minimal movement focus"
    return action_style

def format_perception_requirements(params: dict) -> str:
    coupling = params.get('sensory_coupling', 2)
    if coupling >= 3:
        return f"at least {coupling} sensory perceptions (corporeal + environmental + additional)"
    elif coupling == 2:
        return "at least 2 sensory perceptions (one corporeal like feet/hands/breath, one environmental like light/sound/scent)"
    else:
        return "minimal sensory focus, emphasis on peaceful flow"

def format_transition_requirements(params: dict) -> str:
    transitions = params.get('transition_tokens_required', 1)
    if transitions > 1:
        return f"{transitions} directional connectors (e.g., 'più avanti', 'oltre il', 'raggiungi')"
    elif transitions == 1:
        return "one spatial transition (beyond, through, toward, etc.)"
    else:
        return "smooth narrative flow without forced transitions"

def format_downshift_requirements(params: dict) -> str:
    if params.get('downshift_required', True):
        return "explicit relaxation cues (breath slows, shoulders release, pace softens)"
    else:
        return "optional gentle relaxation elements"
