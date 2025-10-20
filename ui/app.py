import gradio as gr
import requests
import json
import time
import os
from typing import Optional
from datetime import datetime, timedelta

API_URL = os.getenv("API_URL", "http://backend:8000/api")

class SSEClient:
    def __init__(self, url: str):
        self.url = url
        self.response = None
    def __enter__(self):
        self.response = requests.get(self.url, stream=True, timeout=300, headers={'Accept': 'text/event-stream', 'Cache-Control': 'no-cache'})
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.response:
            self.response.close()
    def events(self):
        if not self.response:
            return
        for line in self.response.iter_lines(decode_unicode=True):
            if line.startswith('data: '):
                try:
                    data = json.loads(line[6:])
                    yield data
                except json.JSONDecodeError:
                    continue
            elif line.startswith('event: heartbeat'):
                continue

# --- Backend integrations ---

def fetch_ollama_models():
    try:
        r = requests.get(f"{API_URL}/models/ollama", timeout=8)
        if r.status_code == 200:
            return [m.get("name") for m in r.json()]
    except Exception:
        pass
    return []

# --- Core generator (complete) ---

def generate_enhanced_story(theme: str, duration: int, description: Optional[str] = None,
                            model_preset: str = "quality_high", use_custom_models: bool = False,
                            custom_generator: str = "", custom_reasoner: str = "", custom_polisher: str = "",
                            use_reasoner: bool = True, use_polisher: bool = True,
                            tts_markers: bool = False, strict_schema: bool = False,
                            sensory_rotation: Optional[bool] = None, sleep_taper: Optional[bool] = None,
                            custom_waypoints: Optional[list] = None):
    start_time = time.time()
    models_block = None
    if use_custom_models:
        models = {}
        if custom_generator: models["generator"] = custom_generator
        if custom_reasoner: models["reasoner"] = custom_reasoner
        if custom_polisher: models["polisher"] = custom_polisher
        if models:
            models_block = models
    payload = {
        "theme": theme,
        "duration": duration,
        "description": description or None,
        "use_reasoner": use_reasoner,
        "use_polish": use_polisher,
        "tts_markers": tts_markers,
        "strict_schema": strict_schema
    }
    if models_block:
        payload["models"] = models_block
    if sensory_rotation is not None:
        payload["sensory_rotation"] = sensory_rotation
    if sleep_taper is not None:
        payload["sleep_taper"] = sleep_taper
    if custom_waypoints:
        payload["custom_waypoints"] = custom_waypoints

    r = requests.post(f"{API_URL}/generate/story", json=payload, timeout=30)
    if r.status_code != 200:
        return f"❌ Error starting generation: {r.text}", "", "", "", ""
    job = r.json(); job_id = job.get("job_id")

    def build_status(progress, current_step, step_num, total_steps, elapsed, features):
        feats = job.get("features", {}) if features is None else features
        lines = [
            f"{'🔥' if feats.get('multi_model') else '📦'} Multi-Model: {'ENABLED' if feats.get('multi_model') else 'DISABLED'}",
            f"{'🎯' if feats.get('quality_enhancements') else '📦'} Quality Enhanced: {'YES' if feats.get('quality_enhancements') else 'NO'}",
            f"{'🎤' if feats.get('tts_markers') else '📦'} TTS Markers: {'YES' if feats.get('tts_markers') else 'NO'}",
            f"{'📋' if feats.get('strict_schema') else '📦'} Strict Schema: {'YES' if feats.get('strict_schema') else 'NO'}",
        ]
        bar = f"[{'🟩'*int(progress/2.5)}{'⬜'*(40-int(progress/2.5))}] {progress:.1f}%"
        return f"""🚀 Enhanced Sleep Stories AI Generator

Job: {job_id}
Preset: {model_preset if not use_custom_models else 'CUSTOM'}
Elapsed: {elapsed}

Features:\n- " + "\n- ".join(lines) + f"\n\nStatus: PROCESSING\nStep: {step_num}/{total_steps} - {current_step}\n{bar}"""

    # stream
    features = None
    status_text = build_status(0, "Initializing...", 0, 8, "00:00", features)

    try:
        with SSEClient(f"{API_URL}/generate/{job_id}/stream") as sse:
            for ev in sse.events():
                elapsed = str(timedelta(seconds=int(time.time()-start_time)))[2:7]
                features = ev.get("enhanced_features", features)
                status_text = build_status(ev.get("progress",0), ev.get("current_step","Processing..."), ev.get("current_step_number",0), ev.get("total_steps",8), elapsed, features)
                if ev.get('status') == 'completed':
                    break
                if ev.get('status') == 'failed':
                    return status_text+"\n❌ FAILED", "", "", "", ""
    except Exception:
        pass

    res = requests.get(f"{API_URL}/generate/{job_id}/result", timeout=30)
    if res.status_code != 200:
        elapsed = str(timedelta(seconds=int(time.time()-start_time)))[2:7]
        return status_text+f"\n❌ Error getting results after {elapsed}", "", "", "", ""
    data = res.json()

    story_text = data.get('story_text','')
    metrics = data.get('metrics',{})
    coherence = data.get('coherence_stats',{})
    memory = data.get('memory_stats',{})
    info = data.get('generation_info',{})
    beats_schema = data.get('beats_schema',{})

    total_elapsed = str(timedelta(seconds=int(time.time()-start_time)))[2:7]
    metrics_text = (
        "📊 ENHANCED METRICS\n\n"
        f"Total Time: {total_elapsed}\n"
        f"Target Duration: {duration} min\n"
        f"Final Words: {metrics.get('english_word_count',0):,}\n"
        f"Target Words: {metrics.get('target_words',0):,}\n"
        f"Accuracy: {metrics.get('accuracy_percent',0):.1f}% deviation\n\n"
        f"Generator Words: {metrics.get('generator_words',0):,}\n"
        f"Reasoner Words: {metrics.get('reasoner_words',0):,}\n"
        f"Polisher Words: {metrics.get('polisher_words',0):,}\n\n"
        f"Sensory Transitions: {coherence.get('sensory_transitions',0)}\n"
        f"Avg Density: {coherence.get('avg_density_factor',1.0)}\n"
    )

    if isinstance(data.get('outline',''), dict):
        outline_text = json.dumps(data['outline'], indent=2)
    else:
        outline_text = str(data.get('outline',''))

    if beats_schema and strict_schema:
        schema_text = json.dumps(beats_schema, indent=2)
    else:
        schema_text = "Strict schema not enabled."

    final_status = status_text + f"\n\n✅ COMPLETED in {total_elapsed}"
    return final_status, story_text, metrics_text, outline_text, schema_text

# --- UI ---
with gr.Blocks(title="Sleep Stories AI - Enhanced v2.2", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🌙 Sleep Stories AI - Enhanced v2.2")

    with gr.Row():
        with gr.Column(scale=1):
            theme = gr.Textbox(label="Theme / Setting", value="A tranquil mountain meadow with gentle morning mist")
            description = gr.Textbox(label="Additional Details (optional)", lines=3)
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

            use_reasoner = gr.Checkbox(label="Use Reasoner (DeepSeek-R1)", value=True)
            use_polisher = gr.Checkbox(label="Use Polisher (Mistral-7B)", value=True)
            tts_markers = gr.Checkbox(label="Insert TTS Markers", value=False)
            strict_schema = gr.Checkbox(label="Strict JSON Schema", value=False)

            gr.Markdown("### 🔧 Advanced Settings (optional)")
            sensory_rotation = gr.Checkbox(label="Override Sensory Rotation")
            sleep_taper = gr.Checkbox(label="Override Sleep Taper")
            custom_waypoints = gr.Textbox(label="Custom Waypoints (comma separated)")

            generate_btn = gr.Button("Generate", variant="primary")
            clear_btn = gr.Button("Clear")

        with gr.Column(scale=2):
            status = gr.Textbox(label="Status", lines=16, interactive=False)
            with gr.Tabs():
                with gr.Tab("Story"):
                    story_output = gr.Textbox(lines=26, interactive=False, show_copy_button=True)
                with gr.Tab("Metrics"):
                    metrics_output = gr.Textbox(lines=26, interactive=False, show_copy_button=True)
                with gr.Tab("Outline"):
                    outline_output = gr.Textbox(lines=26, interactive=False, show_copy_button=True)
                with gr.Tab("Schema"):
                    schema_output = gr.Textbox(lines=26, interactive=False, show_copy_button=True)

    # init choices on load
    def init_model_choices():
        models = fetch_ollama_models()
        return (gr.update(choices=models), gr.update(choices=models), gr.update(choices=models))
    demo.load(fn=init_model_choices, inputs=None, outputs=[generator_dd, reasoner_dd, polisher_dd])

    # refresh on click
    refresh_gen.click(fn=lambda: gr.update(choices=fetch_ollama_models()), inputs=None, outputs=[generator_dd])
    refresh_r.click(fn=lambda: gr.update(choices=fetch_ollama_models()), inputs=None, outputs=[reasoner_dd])
    refresh_p.click(fn=lambda: gr.update(choices=fetch_ollama_models()), inputs=None, outputs=[polisher_dd])

    def handle_generate(theme, duration, description, generator_model, reasoner_model, polisher_model,
                        use_reasoner, use_polisher, tts_markers, strict_schema,
                        sensory_rotation, sleep_taper, custom_waypoints):
        models = {}
        if generator_model: models["generator"] = generator_model
        if use_reasoner and reasoner_model: models["reasoner"] = reasoner_model
        if use_polisher and polisher_model: models["polisher"] = polisher_model
        waypoints = [w.strip() for w in custom_waypoints.split(',')] if custom_waypoints else None
        return generate_enhanced_story(
            theme=theme,
            duration=duration,
            description=description,
            model_preset="custom" if models else "quality_high",
            use_custom_models=bool(models),
            custom_generator=models.get("generator",""),
            custom_reasoner=models.get("reasoner",""),
            custom_polisher=models.get("polisher",""),
            use_reasoner=use_reasoner,
            use_polisher=use_polisher,
            tts_markers=tts_markers,
            strict_schema=strict_schema,
            sensory_rotation=True if sensory_rotation else None,
            sleep_taper=True if sleep_taper else None,
            custom_waypoints=waypoints
        )

    generate_btn.click(
        fn=handle_generate,
        inputs=[theme, duration, description, generator_dd, reasoner_dd, polisher_dd,
                use_reasoner, use_polisher, tts_markers, strict_schema,
                sensory_rotation, sleep_taper, custom_waypoints],
        outputs=[status, story_output, metrics_output, outline_output, schema_output]
    )

    clear_btn.click(fn=lambda: ("", "", "", "", ""), inputs=None,
                    outputs=[status, story_output, metrics_output, outline_output, schema_output])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False, show_error=True)
