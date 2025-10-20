import gradio as gr
import requests
import json
import time
import os
from typing import Optional, Generator, Dict, Any
from datetime import timedelta

API_URL = os.getenv("API_URL", "http://backend:8000/api")

# --- HTTP helpers ---

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
    except Exception:
        return None

# --- Streaming/polling generator ---

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
        status_text = f"""🚀 Sleep Stories AI — v3.1
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

# --- Attach/resume generator ---

def attach_and_stream(job_id: str) -> Generator[tuple, None, None]:
    if not job_id:
        yield ("❌ Please select a job to attach to", "", "", "", "")
        return
    start_time = time.time()
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
        status_text = f"""🔗 ATTACHED TO JOB
Job: {job_id}\nAttached for: {elapsed}
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
    res = fetch_json(f"{API_URL}/generate/{job_id}/result", timeout=30)
    if not res:
        yield (last_status+"\n❌ result unavailable", "", "", "", job_id)
        return
    story = res.get('story_text','')
    metrics = json.dumps(res.get('metrics',{}), indent=2)
    coherence = json.dumps(res.get('coherence_stats',{}), indent=2)
    yield (last_status+"\n✅ COMPLETED", story, metrics+"\n\n---\nCoherence:\n"+coherence, "", json.dumps(res.get('beats_schema',{}), indent=2) or "(no schema)")

# --- UI ---

with gr.Blocks(title="Sleep Stories AI — v3.1", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🌙 Sleep Stories AI — v3.1")

    with gr.Row():
        # LEFT: all parameters
        with gr.Column(scale=1, min_width=460):
            gr.Markdown("### 🎨 Base")
            theme = gr.Textbox(label="Theme / Setting", value="Moonlit forest path")
            description = gr.Textbox(label="Extra details (optional)", lines=3)
            duration = gr.Slider(10, 120, value=45, step=5, label="Duration (minutes)")
            gr.Markdown("### 🤖 Models")
            use_custom = gr.Checkbox(label="Use custom models", value=False)
            gen = gr.Textbox(label="Generator (default: qwen3:8b)")
            rsn = gr.Textbox(label="Reasoner (default: deepseek-r1:8b)")
            pol = gr.Textbox(label="Polisher (default: mistral:7b)")
            use_reasoner = gr.Checkbox(label="Enable Reasoner", value=True)
            use_polisher = gr.Checkbox(label="Enable Polisher", value=True)

            gr.Markdown("### 🎯 Quality & Structure")
            tts = gr.Checkbox(label="Insert TTS markers", value=False)
            strict_schema = gr.Checkbox(label="Return strict JSON schema", value=False)
            sensory_rotation = gr.Checkbox(label="Sensory rotation", value=True)
            sleep_taper = gr.Checkbox(label="Sleep taper", value=True)

            gr.Markdown("#### Embodied Journey (user-centric)")
            movement_req = gr.Slider(0, 2, value=1, step=1, label="Movement verbs required per beat (e.g., 'you walk', 'you cross')")
            transition_req = gr.Slider(0, 2, value=1, step=1, label="Transition tokens required per beat (e.g., 'ahead', 'beyond', 'you reach')")
            sensory_coupling = gr.Slider(0, 3, value=2, step=1, label="Sensory coupling per beat (1 corporeal + 1 environmental)")
            downshift_required = gr.Checkbox(label="Downshift required (breath/relax cue)", value=True)
            pov_second_person = gr.Checkbox(label="Enforce 2nd person present", value=True)

            gr.Markdown("#### Destination Architecture")
            destination_arc = gr.Checkbox(label="Enable Destination Arc", value=True)
            arrival_start = gr.Slider(0.5, 0.95, value=0.7, step=0.05, label="Approach signals start (fraction of story)")
            settlement_beats = gr.Slider(1, 4, value=2, step=1, label="Settlement beats (final)")
            closure_required = gr.Checkbox(label="Closure required (arrival + permission to rest)", value=True)
            archetype = gr.Dropdown(label="Destination archetype", choices=["safe_shelter","peaceful_vista","restorative_water","sacred_space"], value="safe_shelter")

            with gr.Accordion("🔧 Advanced (examples included)", open=False):
                gr.Markdown("""
Examples & Tips:
- Movement verbs: "you walk", "you cross", "you reach" → increases travel sense.
- Transition tokens: "ahead", "beyond", "you reach" → guides approach.
- Sensory coupling: 1 corporeal (feet/breath/shoulders) + 1 environmental (light/sound/scent).
- Destination arc: promise (Beat 1-2) → progress markers → approach (70%+) → arrival & settlement → closure.
- Spatial Coach: per-beat micro-brief to stabilize journeys in long stories.
""")
                temp = gr.Slider(0.1, 1.5, value=0.7, step=0.05, label="Model temperature")
                coach_on = gr.Checkbox(label="Enable Spatial Coach (DeepSeek)", value=False)

        # RIGHT: session controls on top, outputs below
        with gr.Column(scale=2, min_width=640):
            gr.Markdown("### 🔗 Active Session")
            with gr.Row():
                active_jobs = gr.Dropdown(label="Active Jobs (Resume)", choices=[], allow_custom_value=True)
                refresh_jobs = gr.Button("↻ Refresh", size="sm")
                attach_btn = gr.Button("🔗 Attach", variant="secondary")
            status = gr.Textbox(label="Status", lines=10, interactive=False)

            gr.Markdown("### 📤 Outputs")
            with gr.Tabs():
                with gr.Tab("Story"):
                    story_out = gr.Textbox(lines=24, interactive=False, show_copy_button=True)
                with gr.Tab("Metrics & Coherence"):
                    metrics_out = gr.Textbox(lines=24, interactive=False, show_copy_button=True)
                with gr.Tab("Outline"):
                    outline_out = gr.Textbox(lines=12, interactive=False, show_copy_button=True)
                with gr.Tab("Schema"):
                    schema_out = gr.Textbox(lines=12, interactive=False, show_copy_button=True)

            with gr.Row():
                run = gr.Button("Generate", variant="primary")
                clear_btn = gr.Button("Clear")

    # Data loaders
    def on_load():
        health = fetch_json(f"{API_URL}/health/enhanced", timeout=5)
        jobs = fetch_json(f"{API_URL}/jobs", timeout=5) or {"jobs": []}
        job_choices = [(f"{j['job_id'][:8]} - {j['theme'][:30]}...", j['job_id']) for j in jobs.get('jobs', []) if j.get('status') in ['started','processing']]
        return [
            gr.update(choices=job_choices)
        ]

    demo.load(on_load, inputs=None, outputs=[active_jobs])

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
            payload["models"] = {"generator": gen or None, "reasoner": rsn or None, "polisher": pol or None}
        return payload

    def run_generate(*args):
        payload = pack_payload(*args)
        for update in start_and_stream(payload):
            yield update

    def run_attach(job_choice):
        job_id = job_choice[1] if isinstance(job_choice, (list, tuple)) else job_choice
        for update in attach_and_stream(job_id):
            yield update

    refresh_jobs.click(
        fn=lambda: [gr.update(choices=[(f"{j['job_id'][:8]} - {j['theme'][:30]}...", j['job_id']) for j in (fetch_json(f"{API_URL}/jobs", 5) or {"jobs": []}).get('jobs', []) if j.get('status') in ['started','processing']])],
        inputs=None,
        outputs=[active_jobs]
    )

    attach_btn.click(
        fn=run_attach,
        inputs=[active_jobs],
        outputs=[status, story_out, metrics_out, outline_out, schema_out],
        concurrency_limit=2
    )

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

    clear_btn.click(
        fn=lambda: ("", "", "", "", ""),
        inputs=None,
        outputs=[status, story_out, metrics_out, outline_out, schema_out]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, show_error=True, debug=True, max_threads=40)
