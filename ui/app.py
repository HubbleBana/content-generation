import gradio as gr
import requests
import json
import time
import os
from typing import Optional
from datetime import timedelta

API_URL = os.getenv("API_URL", "http://backend:8000/api")

class SSEClient:
    """Client for Server-Sent Events streaming"""
    
    def __init__(self, url: str):
        self.url = url
        self.response = None
        
    def __enter__(self):
        try:
            self.response = requests.get(
                self.url, 
                stream=True, 
                timeout=300,
                headers={'Accept': 'text/event-stream', 'Cache-Control': 'no-cache'}
            )
            return self
        except Exception as e:
            raise ConnectionError(f"Failed to connect to SSE stream: {e}")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.response:
            self.response.close()
    
    def events(self) -> iter:
        """Generator that yields SSE events"""
        if not self.response:
            return
        
        for line in self.response.iter_lines(decode_unicode=True):
            if line.startswith('data: '):
                try:
                    data = json.loads(line[6:])  # Remove 'data: ' prefix
                    yield data
                except json.JSONDecodeError:
                    continue
            elif line.startswith('event: heartbeat'):
                continue  # Skip heartbeat events

# Load model presets from API

def load_model_presets():
    """Load available model presets from API."""
    try:
        response = requests.get(f"{API_URL}/models/presets", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('presets', {}), data.get('default_models', {}), data.get('available_features', {})
        else:
            # Fallback defaults
            return {
                "quality_high": {"generator": "qwen2.5:7b", "reasoner": "deepseek-r1:8b", "polisher": "mistral:7b"},
                "fast": {"generator": "qwen2.5:7b", "reasoner": None, "polisher": None}
            }, {"generator": "qwen2.5:7b", "reasoner": "deepseek-r1:8b", "polisher": "mistral:7b"}, {}
    except:
        # Fallback if API unavailable
        return {
            "quality_high": {"generator": "qwen2.5:7b", "reasoner": "deepseek-r1:8b", "polisher": "mistral:7b"},
            "fast": {"generator": "qwen2.5:7b", "reasoner": None, "polisher": None}
        }, {"generator": "qwen2.5:7b", "reasoner": "deepseek-r1:8b", "polisher": "mistral:7b"}, {}


# Wrapper per gestire generatore e restituire 5 valori

def generate_enhanced_story_with_sse_wrapper(*args, **kwargs):
    try:
        gen = generate_enhanced_story_with_sse(*args, **kwargs)
        latest = ("", "", "", "", "")
        for update in gen:
            if isinstance(update, tuple) and len(update) == 5:
                latest = update
        return latest
    except Exception as e:
        return (f"❌ Error during enhanced generation: {str(e)}", "", "", "", "")

# Event handler gestito

def handle_generate(theme, duration, description, model_preset,
                    custom_generator, custom_reasoner, custom_polisher,
                    use_reasoner, use_polisher, tts_markers, strict_schema):
    use_custom_models = (model_preset == "Custom")
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


MODEL_PRESETS, DEFAULT_MODELS, AVAILABLE_FEATURES = load_model_presets()

with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.HTML("""
    <div style="text-align:center; margin-bottom:15px;">
        <h1>🌙 Sleep Stories AI - Enhanced v2.0</h1>
        <p>A comprehensive AI story generation system with multi-model backend support and TTS integration</p>
    </div>
    """)

    with gr.Row():
        with gr.Column(scale=1):
            gr.HTML("<h3>📝 Story Configuration</h3>")
            theme = gr.Textbox(label="Theme / Setting", placeholder="e.g., A peaceful Scottish Highland lake at dawn", value="A tranquil mountain meadow with gentle morning mist")
            description = gr.Textbox(label="Additional Details (optional)", placeholder="E.g., Focus on sounds and mood", lines=3)
            duration = gr.Slider(label="Duration (minutes)", minimum=20, maximum=90, value=45, step=5)
            gr.HTML("<h4>Model Presets</h4>")
            model_preset = gr.Radio(label="Model Presets (optimized for RTX 3070Ti)", choices=["Quality High", "Fast", "Custom"], value="Quality High")
            with gr.Group(visible=False) as custom_models_group:
                gr.HTML("<h5>Custom Model Configuration</h5>")
                custom_generator = gr.Textbox(label="Generator Model", placeholder="e.g., qwen2.5:7b", value=DEFAULT_MODELS.get("generator", "qwen2.5:7b"))
                custom_reasoner = gr.Textbox(label="Reasoner Model (optional)", placeholder="e.g., deepseek-r1:8b", value=DEFAULT_MODELS.get("reasoner", "deepseek-r1:8b"))
                custom_polisher = gr.Textbox(label="Polisher Model (optional)", placeholder="e.g., mistral:7b", value=DEFAULT_MODELS.get("polisher", "mistral:7b"))
            gr.HTML("<h4>Feature Toggles</h4>")
            use_reasoner = gr.Checkbox(label="Use Reasoner (DeepSeek-R1)", value=True)
            use_polisher = gr.Checkbox(label="Use Polisher (Mistral-7B)", value=True)
            tts_markers = gr.Checkbox(label="Insert TTS Markers", value=False)
            strict_schema = gr.Checkbox(label="Strict JSON Schema", value=False)
            generate_btn = gr.Button("Generate Enhanced Story", variant="primary", size="lg")
            clear_btn = gr.Button("Clear All", size="lg")
        with gr.Column(scale=2):
            gr.HTML("<h3>Generation Output</h3>")
            status = gr.Textbox(label="Status", lines=15, interactive=False, show_copy_button=True, placeholder="Generation progress will appear here.")
            with gr.Tabs():
                with gr.Tab("Enhanced Story"):
                    story_output = gr.Textbox(lines=25, interactive=False, show_copy_button=True)
                with gr.Tab("Enhanced Metrics"):
                    metrics_output = gr.Textbox(lines=25, interactive=False, show_copy_button=True)
                with gr.Tab("Story Structure"):
                    outline_output = gr.Textbox(lines=25, interactive=False, show_copy_button=True)
                with gr.Tab("Schema Output"):
                    schema_output = gr.Textbox(lines=25, interactive=False, show_copy_button=True)

    def update_custom_models_visibility(preset):
        return gr.Group(visible=(preset == "Custom"))

    model_preset.change(
        fn=update_custom_models_visibility,
        inputs=[model_preset],
        outputs=[custom_models_group]
    )

    generate_btn.click(
        fn=handle_generate,
        inputs=[
            theme, duration, description, model_preset,
            custom_generator, custom_reasoner, custom_polisher,
            use_reasoner, use_polisher, tts_markers, strict_schema
        ],
        outputs=[status, story_output, metrics_output, outline_output, schema_output]
    )

    clear_btn.click(
        fn=lambda: ("", "", "", "", ""),
        inputs=None,
        outputs=[status, story_output, metrics_output, outline_output, schema_output]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)