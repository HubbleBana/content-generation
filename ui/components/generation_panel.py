"""Generation panel components for Sleep Stories AI.

Updated for Gradio 4.44+ compatibility.
"""

import gradio as gr
from typing import Dict, Any, List, Tuple, Optional

def create_basic_settings() -> Tuple:
    """Create basic generation settings components."""
    with gr.Group():
        gr.Markdown("### 🎨 Basic Settings")
        
        theme = gr.Textbox(
            label="Theme / Setting",
            placeholder="e.g., Moonlit forest path, Cozy mountain cabin, Ocean waves...",
            value="A peaceful mountain meadow at dawn",
            lines=2
        )
        
        description = gr.Textbox(
            label="Additional Description (Optional)",
            placeholder="Add specific details, mood, or sensory elements...",
            lines=3
        )
        
        with gr.Row():
            duration = gr.Slider(
                minimum=5,
                maximum=180,
                value=45,
                step=5,
                label="Duration (minutes)"
            )
            
            preset = gr.Dropdown(
                choices=["quality_high", "balanced", "fast", "custom"],
                value="balanced",
                label="Quality Preset"
            )
    
    return theme, description, duration, preset

def create_model_settings() -> Tuple:
    """Create model configuration components."""
    with gr.Group():
        gr.Markdown("### 🤖 Model Configuration")
        
        with gr.Row():
            use_custom_models = gr.Checkbox(
                label="Use Custom Models",
                value=False
            )
            
            refresh_models_btn = gr.Button(
                "🔄 Refresh Models",
                size="sm",
                variant="secondary"
            )
        
        with gr.Column(visible=False) as model_config:
            generator_model = gr.Dropdown(
                label="Generator Model",
                choices=[],
                allow_custom_value=True,
                info="Primary story generation model"
            )
            
            reasoner_model = gr.Dropdown(
                label="Reasoner Model",
                choices=[],
                allow_custom_value=True,
                info="Logic and coherence enhancement"
            )
            
            polisher_model = gr.Dropdown(
                label="Polisher Model",
                choices=[],
                allow_custom_value=True,
                info="Style refinement and flow"
            )
        
        with gr.Row():
            use_reasoner = gr.Checkbox(
                label="Enable Reasoner",
                value=True,
                info="Improve story coherence and logic"
            )
            
            use_polisher = gr.Checkbox(
                label="Enable Polisher",
                value=True,
                info="Refine style and flow"
            )
        
        # Show/hide model config based on checkbox - Gradio 4.44+ compatible
        def toggle_model_config(show_models):
            return gr.update(visible=show_models)
        
        use_custom_models.change(
            fn=toggle_model_config,
            inputs=[use_custom_models],
            outputs=[model_config]
        )
    
    return (
        use_custom_models, generator_model, reasoner_model, polisher_model,
        use_reasoner, use_polisher, refresh_models_btn
    )

def create_quality_settings() -> Tuple:
    """Create quality and enhancement settings."""
    with gr.Group():
        gr.Markdown("### ✨ Quality Enhancements")
        
        with gr.Row():
            tts_markers = gr.Checkbox(
                label="TTS Markers",
                value=False,
                info="Insert pause and breathing markers for speech synthesis"
            )
            
            strict_schema = gr.Checkbox(
                label="Strict JSON Schema",
                value=False,
                info="Return structured output for video production"
            )
        
        with gr.Row():
            sensory_rotation = gr.Checkbox(
                label="Sensory Rotation",
                value=True,
                info="Cycle through different senses systematically"
            )
            
            sleep_taper = gr.Checkbox(
                label="Sleep Taper",
                value=True,
                info="Gradually reduce stimulation toward the end"
            )
    
    return tts_markers, strict_schema, sensory_rotation, sleep_taper

def create_advanced_settings() -> Tuple:
    """Create advanced configuration settings."""
    with gr.Accordion("🔧 Advanced Settings", open=False):
        gr.Markdown("### Temperature & Generation")
        
        with gr.Row():
            model_temperature = gr.Slider(
                minimum=0.1,
                maximum=2.0,
                value=0.7,
                step=0.05,
                label="Model Temperature",
                info="Higher = more creative, Lower = more consistent"
            )
            
            coach_enabled = gr.Checkbox(
                label="Spatial Coach (DeepSeek)",
                value=False,
                info="Enhanced spatial reasoning and progression"
            )
        
        gr.Markdown("### Embodied Journey Parameters")
        
        with gr.Row():
            movement_verbs = gr.Slider(
                minimum=0,
                maximum=3,
                value=1,
                step=1,
                label="Movement Verbs/Beat",
                info="Physical action words per story segment"
            )
            
            transition_tokens = gr.Slider(
                minimum=0,
                maximum=3,
                value=1,
                step=1,
                label="Transition Tokens/Beat",
                info="Connecting words between segments"
            )
        
        with gr.Row():
            sensory_coupling = gr.Slider(
                minimum=0,
                maximum=4,
                value=2,
                step=1,
                label="Sensory Coupling",
                info="Body-environment sensory connections"
            )
            
            pov_second_person = gr.Checkbox(
                label="Enforce 2nd Person",
                value=True,
                info="Maintain 'you' perspective throughout"
            )
        
        gr.Markdown("### Destination Architecture")
        
        with gr.Row():
            destination_arc = gr.Checkbox(
                label="Destination Arc",
                value=True,
                info="Structure story as journey to peaceful destination"
            )
            
            arrival_start = gr.Slider(
                minimum=0.5,
                maximum=0.95,
                value=0.7,
                step=0.05,
                label="Arrival Signals Start",
                info="When to begin approaching destination (% through story)"
            )
        
        with gr.Row():
            settlement_beats = gr.Slider(
                minimum=1,
                maximum=5,
                value=2,
                step=1,
                label="Settlement Beats",
                info="Number of final peaceful segments"
            )
            
            archetype = gr.Dropdown(
                choices=[
                    "safe_shelter",
                    "peaceful_vista", 
                    "restorative_water",
                    "sacred_space"
                ],
                value="safe_shelter",
                label="Destination Archetype",
                info="Type of peaceful endpoint"
            )
    
    return (
        model_temperature, coach_enabled, movement_verbs, transition_tokens,
        sensory_coupling, pov_second_person, destination_arc, arrival_start,
        settlement_beats, archetype
    )

def create_generation_controls() -> Tuple:
    """Create main generation control buttons."""
    with gr.Row():
        generate_btn = gr.Button(
            "🚀 Generate Story",
            variant="primary",
            size="lg",
            scale=3
        )
        
        clear_btn = gr.Button(
            "🗑️ Clear All",
            variant="secondary",
            size="lg",
            scale=1
        )
    
    return generate_btn, clear_btn

def build_generation_payload(
    theme: str,
    description: str,
    duration: int,
    preset: str,
    use_custom_models: bool,
    generator_model: str,
    reasoner_model: str,
    polisher_model: str,
    use_reasoner: bool,
    use_polisher: bool,
    tts_markers: bool,
    strict_schema: bool,
    sensory_rotation: bool,
    sleep_taper: bool,
    model_temperature: float,
    coach_enabled: bool,
    movement_verbs: int,
    transition_tokens: int,
    sensory_coupling: int,
    pov_second_person: bool,
    destination_arc: bool,
    arrival_start: float,
    settlement_beats: int,
    archetype: str
) -> Dict[str, Any]:
    """Build generation payload from UI inputs."""
    payload = {
        "theme": theme,
        "duration": int(duration),
        "use_reasoner": bool(use_reasoner),
        "use_polish": bool(use_polisher),
        "tts_markers": bool(tts_markers),
        "strict_schema": bool(strict_schema),
        "sensory_rotation": bool(sensory_rotation),
        "sleep_taper": bool(sleep_taper)
    }
    
    # Add description if provided
    if description and description.strip():
        payload["description"] = description.strip()
    
    # Add custom models if specified
    if use_custom_models:
        models = {}
        if generator_model and generator_model.strip(): 
            models["generator"] = generator_model.strip()
        if reasoner_model and reasoner_model.strip(): 
            models["reasoner"] = reasoner_model.strip()
        if polisher_model and polisher_model.strip(): 
            models["polisher"] = polisher_model.strip()
        
        if models:
            payload["models"] = models
    
    # Add advanced parameters
    payload["advanced"] = {
        "model_temperature": float(model_temperature),
        "spatial_coach": bool(coach_enabled),
        "embodied": {
            "movement_verbs_required": int(movement_verbs),
            "transition_tokens_required": int(transition_tokens),
            "sensory_coupling": int(sensory_coupling),
            "pov_second_person": bool(pov_second_person)
        },
        "destination": {
            "enabled": bool(destination_arc),
            "arrival_signals_start": float(arrival_start),
            "settlement_beats": int(settlement_beats),
            "archetype": archetype
        }
    }
    
    return payload
