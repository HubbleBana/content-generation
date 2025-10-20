import gradio as gr
import requests
import os
import json
import time
from datetime import timedelta

API_URL = os.getenv("API_URL", "http://backend:8000/api")

# Utility to fetch local Ollama models

def fetch_ollama_models():
    try:
        r = requests.get(f"{API_URL}/models/ollama", timeout=8)
        if r.status_code == 200:
            data = r.json()
            return [m.get("name") for m in data]
    except Exception:
        pass
    return []

# Dynamic dropdown choices functions

def refresh_generator_models():
    return gr.update(choices=fetch_ollama_models())

def refresh_reasoner_models():
    return gr.update(choices=fetch_ollama_models())

def refresh_polisher_models():
    return gr.update(choices=fetch_ollama_models())

# Existing generation function omitted for brevity.
# Assuming function generate_enhanced_story(theme, duration, description, ...)
# exists below in this file as implemented previously.

# Build UI
with gr.Blocks(title="Sleep Stories AI - Enhanced v2.1", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🌙 Sleep Stories AI - Enhanced v2.1")

    with gr.Row():
        with gr.Column(scale=1):
            theme = gr.Textbox(label="Theme / Setting")
            description = gr.Textbox(label="Additional Details", lines=3)
            duration = gr.Slider(20, 90, value=45, step=5, label="Duration (minutes)")

            gr.Markdown("### 🤖 Model Selection (Dynamic from Ollama)")
            with gr.Row():
                generator_dd = gr.Dropdown(choices=[], label="Generator Model", allow_custom_value=True)
                refresh_gen = gr.Button("↻", size="sm")
            with gr.Row():
                reasoner_dd = gr.Dropdown(choices=[], label="Reasoner Model", allow_custom_value=True)
                refresh_r = gr.Button("↻", size="sm")
            with gr.Row():
                polisher_dd = gr.Dropdown(choices=[], label="Polisher Model", allow_custom_value=True)
                refresh_p = gr.Button("↻", size="sm")

            use_reasoner = gr.Checkbox(label="Use Reasoner", value=True)
            use_polisher = gr.Checkbox(label="Use Polisher", value=True)
            tts_markers = gr.Checkbox(label="Insert TTS Markers", value=False)
            strict_schema = gr.Checkbox(label="Strict JSON Schema", value=False)

            generate_btn = gr.Button("Generate", variant="primary")
            clear_btn = gr.Button("Clear")

        with gr.Column(scale=2):
            status = gr.Textbox(label="Status", lines=15, interactive=False)
            with gr.Tabs():
                with gr.Tab("Story"):
                    story_output = gr.Textbox(lines=25, interactive=False, show_copy_button=True)
                with gr.Tab("Metrics"):
                    metrics_output = gr.Textbox(lines=25, interactive=False, show_copy_button=True)
                with gr.Tab("Outline"):
                    outline_output = gr.Textbox(lines=25, interactive=False, show_copy_button=True)
                with gr.Tab("Schema"):
                    schema_output = gr.Textbox(lines=25, interactive=False, show_copy_button=True)

    # Initial load of models into dropdowns
    def init_model_choices():
        models = fetch_ollama_models()
        return (gr.update(choices=models), gr.update(choices=models), gr.update(choices=models))

    demo.load(fn=init_model_choices, inputs=None, outputs=[generator_dd, reasoner_dd, polisher_dd])

    # Refresh buttons to update choices on demand
    refresh_gen.click(fn=refresh_generator_models, inputs=None, outputs=[generator_dd])
    refresh_r.click(fn=refresh_reasoner_models, inputs=None, outputs=[reasoner_dd])
    refresh_p.click(fn=refresh_polisher_models, inputs=None, outputs=[polisher_dd])

    # Generate handler (uses selected dropdown values if provided)
    def handle_generate(theme, duration, description, generator_model, reasoner_model, polisher_model,
                        use_reasoner, use_polisher, tts_markers, strict_schema):
        models = {}
        if generator_model: models["generator"] = generator_model
        if use_reasoner and reasoner_model: models["reasoner"] = reasoner_model
        if use_polisher and polisher_model: models["polisher"] = polisher_model
        return generate_enhanced_story(
            theme=theme,
            duration=duration,
            description=description,
            model_preset="custom" if models else "quality_high",
            use_custom_models=bool(models),
            custom_generator=models.get("generator", ""),
            custom_reasoner=models.get("reasoner", ""),
            custom_polisher=models.get("polisher", ""),
            use_reasoner=use_reasoner,
            use_polisher=use_polisher,
            tts_markers=tts_markers,
            strict_schema=strict_schema,
        )

    generate_btn.click(
        fn=handle_generate,
        inputs=[theme, duration, description, generator_dd, reasoner_dd, polisher_dd,
                use_reasoner, use_polisher, tts_markers, strict_schema],
        outputs=[status, story_output, metrics_output, outline_output, schema_output]
    )

    clear_btn.click(fn=lambda: ("", "", "", "", ""), inputs=None,
                    outputs=[status, story_output, metrics_output, outline_output, schema_output])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False, show_error=True)
