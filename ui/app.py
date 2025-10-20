import gradio as gr
import requests
import json
import time
import os
from typing import Optional
from datetime import timedelta

API_URL = os.getenv("API_URL", "http://backend:8000/api")

# --- Existing helper functions (SSEClient etc) omitted for brevity ---

# Simplified generator wrapper fix for Gradio

def generate_enhanced_story_with_sse_wrapper(*args, **kwargs):
    """Wrapper that ensures Gradio gets full 5-value output from the generator."""
    try:
        gen = generate_enhanced_story_with_sse(*args, **kwargs)
        latest = ("", "", "", "", "")
        for update in gen:
            if isinstance(update, tuple) and len(update) == 5:
                latest = update
        # Return final stable 5-tuple output
        return latest
    except Exception as e:
        return (f"❌ Error during enhanced generation: {str(e)}", "", "", "", "")

# Event handler fix
def handle_generate(theme, duration, description, model_preset,
                   custom_generator, custom_reasoner, custom_polisher,
                   use_reasoner, use_polisher, tts_markers, strict_schema):
    use_custom_models = (model_preset == "custom")
    return generate_enhanced_story_with_sse_wrapper(
        theme=theme,
        duration=duration,
        description=description,
        model_preset=model_preset,
        use_custom_models=use_custom_models,
        custom_generator=custom_generator,
        custom_reasoner=custom_reasoner,
        custom_polisher=custom_polisher,
        use_reasoner=use_reasoner,
        use_polisher=use_polisher,
        tts_markers=tts_markers,
        strict_schema=strict_schema
    )

# Integrate into UI Buttons (simplified for clarity)
with gr.Blocks(title="Sleep Stories AI - Enhanced v2.1") as demo:
    theme = gr.Textbox(label="Theme")
    duration = gr.Slider(20, 90, label="Duration")
    description = gr.Textbox(label="Description")
    generate_btn = gr.Button("Generate Enhanced Story")

    status = gr.Textbox(label="Status")
    story_output = gr.Textbox(label="Story")
    metrics_output = gr.Textbox(label="Metrics")
    outline_output = gr.Textbox(label="Outline")
    schema_output = gr.Textbox(label="Schema")

    generate_btn.click(
        fn=handle_generate,
        inputs=[theme, duration, description, gr.State(), gr.State(), gr.State(), gr.State(), gr.State(), gr.State(), gr.State(), gr.State()],
        outputs=[status, story_output, metrics_output, outline_output, schema_output]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)