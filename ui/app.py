import gradio as gr
import requests
import json
import time
import os
from typing import Optional, Generator, Dict, Any
from datetime import timedelta

API_URL = os.getenv("API_URL", "http://backend:8000/api")

# Helpers
def fetch_json(url, timeout=8):
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None

def post_json(url, payload, timeout=30):
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        return r
    except Exception as e:
        return None

# UI Generators

def start_and_stream(payload: Dict[str, Any]) -> Generator[tuple, None, None]:
    start_time = time.time()
    # start job
    r = post_json(f"{API_URL}/generate/story", payload, timeout=30)
    if not r or r.status_code != 200:
        msg = f"❌ Start error: {(r.status_code if r else 'no response')}\n{(r.text[:200] if r else '')}"
        yield (msg, "", "", "", "")
        return
    job = r.json(); job_id = job.get("job_id")
    last_status = ""
    while True:
        st = fetch_json(f"{API_URL}/generate/{job_id}/status", timeout=10)
        if not st:
            yield (last_status + "\n⚠️ status unavailable", "", "", "", job_id)
            time.sleep(2)
            continue
        progress = st.get("progress", 0)
        step = st.get("current_step", "Processing...")
        step_num = st.get("current_step_number", 0)
        total_steps = st.get("total_steps", 8)
        elapsed = str(timedelta(seconds=int(time.time()-start_time)))[2:7]
        bar = f"[{'🟩'*int(progress/2.5)}{'⬜'*(40-int(progress/2.5))}] {progress:.1f}%"
        features = st.get("enhanced_features", {})
        status_text = f"""🚀 Sleep Stories AI — v3.0
Job: {job_id}\nElapsed: {elapsed}

Features:
- Multi-Model: {features.get('models',{})}
- Reasoner: {features.get('use_reasoner', True)} | Polisher: {features.get('use_polish', True)}
- TTS: {features.get('tts_markers', False)} | Schema: {features.get('strict_schema', False)}

Step {step_num}/{total_steps}: {step}
{bar}
"""
        if status_text != last_status:
            yield (status_text, "", "", "", job_id)
            last_status = status_text
        if st.get("status") == "completed":
            break
        if st.get("status") == "failed":
            yield (status_text+"\n❌ FAILED", "", "", "", job_id)
            return
        time.sleep(2)
    # result
    res = fetch_json(f"{API_URL}/generate/{job_id}/result", timeout=30)
    if not res:
        yield (last_status+"\n❌ result unavailable", "", "", "", job_id)
        return
    story = res.get('story_text','')
    metrics = res.get('metrics',{})
    coherence = res.get('coherence_stats',{})
    schema = res.get('beats_schema',{})
    # Build texts
    metrics_text = json.dumps(metrics, indent=2)
    coherence_text = json.dumps(coherence, indent=2)
    schema_text = json.dumps(schema, indent=2) if schema else "(no schema)"
    yield (last_status+"\n✅ COMPLETED", story, metrics_text+"\n\n---\nCoherence:\n"+coherence_text, "", schema_text)

with gr.Blocks(title="Sleep Stories AI — v3.0", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🌙 Sleep Stories AI — v3.0")
    gr.Markdown("""
Questa UI espone tutti i parametri principali. Suggerimenti:
- Usa 2a persona e presente, verbi di moto e transizioni per storie più immersive.
- Abilita Destination Arc per avere promessa, avanzamento, arrivo e closure.
""")

    # Connection & jobs
    with gr.Row():
        connection = gr.Markdown("Testing backend...")

    # Basic
    with gr.Row():
        with gr.Column():
            gr.Markdown("### 🎨 Base")
            theme = gr.Textbox(label="Theme / Setting", value="Bosco al chiaro di luna")
            description = gr.Textbox(label="Extra details", lines=3)
            duration = gr.Slider(10, 120, value=45, step=5, label="Duration (minutes)")
            gr.Markdown("### 🤖 Models")
            use_custom = gr.Checkbox(label="Use custom models", value=False)
            gen = gr.Textbox(label="Generator (default: qwen3:8b)")
            rsn = gr.Textbox(label="Reasoner (default: deepseek-r1:8b)")
            pol = gr.Textbox(label="Polisher (default: mistral:7b)")
            use_reasoner = gr.Checkbox(label="Enable Reasoner", value=True)
            use_polisher = gr.Checkbox(label="Enable Polisher", value=True)

        with gr.Column():
            gr.Markdown("### 🎯 Quality & Structure")
            tts = gr.Checkbox(label="Insert TTS markers", value=False)
            strict_schema = gr.Checkbox(label="Return strict JSON schema", value=False)
            sensory_rotation = gr.Checkbox(label="Sensory rotation", value=True)
            sleep_taper = gr.Checkbox(label="Sleep taper", value=True)
            gr.Markdown("#### Embodied Journey (utente-centrico)")
            movement_req = gr.Slider(0, 2, value=1, step=1, label="Movement verbs required per beat")
            transition_req = gr.Slider(0, 2, value=1, step=1, label="Transition tokens required per beat")
            sensory_coupling = gr.Slider(0, 3, value=2, step=1, label="Sensory coupling (corp+env) per beat")
            downshift_required = gr.Checkbox(label="Downshift required (breath/relax)", value=True)
            pov_second_person = gr.Checkbox(label="Enforce 2nd person present", value=True)
            gr.Markdown("#### Destination Architecture")
            destination_arc = gr.Checkbox(label="Enable Destination Arc", value=True)
            arrival_start = gr.Slider(0.5, 0.95, value=0.7, step=0.05, label="Approach signals start (story %)" )
            settlement_beats = gr.Slider(1, 4, value=2, step=1, label="Settlement beats (final)")
            closure_required = gr.Checkbox(label="Closure required", value=True)
            archetype = gr.Dropdown(label="Destination archetype", choices=["safe_shelter","peaceful_vista","restorative_water","sacred_space"], value="safe_shelter")

    with gr.Accordion("🔧 Advanced (examples included)", open=False):
        gr.Markdown("""
- Movement verbs example: "ti incammini", "attraversi", "raggiungi" — forza il senso di viaggio.
- Transition tokens example: "più avanti", "oltre il", "raggiungi" — guida l’avvicinamento.
- Sensory coupling: 1 corporeo (piedi/respiro/spalle) + 1 ambientale (luce/suoni/odori) per beat.
- Destination arc: promessa iniziale (Beat 1-2) → progress markers (centro) → approach (70%+) → arrivo e settlement (ultimi beat).
- Spatial Coach: genera un micro-brief per ogni beat per stabilizzare il viaggio nelle storie lunghe.
""")
        temp = gr.Slider(0.1, 1.5, value=0.7, step=0.05, label="Model temperature")
        coach_on = gr.Checkbox(label="Enable Spatial Coach (DeepSeek)", value=False)

    # Action
    run = gr.Button("Generate", variant="primary")

    # Outputs
    status = gr.Textbox(label="Status", lines=12)
    story_out = gr.Textbox(label="Story", lines=24, show_copy_button=True)
    metrics_out = gr.Textbox(label="Metrics & Coherence", lines=24, show_copy_button=True)
    outline_out = gr.Textbox(label="Outline", lines=8)
    schema_out = gr.Textbox(label="Schema", lines=12)

    def on_load():
        health = fetch_json(f"{API_URL}/health/enhanced", timeout=5)
        if health:
            return f"✅ Backend OK — Models: {health.get('models',{})}"
        return "❌ Backend not reachable"

    demo.load(on_load, inputs=None, outputs=[connection])

    def pack_payload(theme, description, duration,
                     use_custom, gen, rsn, pol, use_reasoner, use_polisher,
                     tts, strict_schema, sensory_rotation, sleep_taper,
                     movement_req, transition_req, sensory_coupling, downshift_required, pov_second_person,
                     destination_arc, arrival_start, settlement_beats, closure_required, archetype,
                     temp, coach_on):
        payload = {
            "theme": theme,
            "description": description or None,
            "duration": int(duration),
            "use_reasoner": bool(use_reasoner),
            "use_polish": bool(use_polisher),
            "tts_markers": bool(tts),
            "strict_schema": bool(strict_schema),
            "sensory_rotation": bool(sensory_rotation),
            "sleep_taper": bool(sleep_taper),
            # Advanced knobs (backend will read from settings or override internally)
            "advanced": {
                "model_temperature": float(temp),
                "embodied": {
                    "movement_verbs_required": int(movement_req),
                    "transition_tokens_required": int(transition_req),
                    "sensory_coupling": int(sensory_coupling),
                    "downshift_required": bool(downshift_required),
                    "pov_second_person": bool(pov_second_person)
                },
                "destination": {
                    "enabled": bool(destination_arc),
                    "arrival_signals_start": float(arrival_start),
                    "settlement_beats": int(settlement_beats),
                    "closure_required": bool(closure_required),
                    "archetype": archetype
                },
                "spatial_coach": bool(coach_on)
            }
        }
        if use_custom:
            payload["models"] = {
                "generator": gen or None,
                "reasoner": rsn or None,
                "polisher": pol or None
            }
        return payload

    def run_generate(*args):
        payload = pack_payload(*args)
        for update in start_and_stream(payload):
            yield update

    run.click(
        fn=run_generate,
        inputs=[theme, description, duration,
                use_custom, gen, rsn, pol, use_reasoner, use_polisher,
                tts, strict_schema, sensory_rotation, sleep_taper,
                movement_req, transition_req, sensory_coupling, downshift_required, pov_second_person,
                destination_arc, arrival_start, settlement_beats, closure_required, archetype,
                temp, coach_on],
        outputs=[status, story_out, metrics_out, outline_out, schema_out],
        concurrency_limit=1
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, show_error=True, debug=True, max_threads=40)
