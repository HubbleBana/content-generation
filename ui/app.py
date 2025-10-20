import gradio as gr
import requests
import json
import time
import os
from typing import Optional, Generator, Dict, Any, List
from datetime import timedelta

API_URL = os.getenv("API_URL", "http://backend:8000/api")

# --- HTTP helpers ---

def fetch_json(url, timeout=15):
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None

# Build dropdown labels (include queued/created too)

def build_job_labels(jobs_payload: Dict[str, Any]) -> List[str]:
    jobs = (jobs_payload or {}).get('jobs', [])
    labels: List[str] = []
    for j in jobs:
        if j.get('status') in ['queued','created','started','processing']:
            jid = str(j.get('job_id',''))
            theme = str(j.get('theme','unknown'))
            prog = int(j.get('progress',0))
            labels.append(f"{jid}|{theme[:30]}|{prog}")
    return labels

# Parse label back to id

def parse_job_id(label: str) -> str:
    try:
        return label.split('|', 1)[0]
    except Exception:
        return label

# --- Streaming/polling generator ---

def start_and_stream(payload: Dict[str, Any]) -> Generator[tuple, None, None]:
    start_time = time.time()
    try:
        r = requests.post(f"{API_URL}/generate/story", json=payload, timeout=30)
    except Exception as e:
        yield (f"❌ Start error: {e}", "", "", "", "")
        return
    if r.status_code != 200:
        yield (f"❌ Start error: {r.status_code}\n{r.text[:200]}", "", "", "", "")
        return
    job_id = r.json().get("job_id")
    last_status = ""
    backoff = 2
    while True:
        st = fetch_json(f"{API_URL}/generate/{job_id}/status", timeout=15)
        if not st:
            yield (last_status + "\n⚠️ status unavailable", "", "", "", job_id)
            time.sleep(backoff)
            backoff = min(5, backoff + 1)
            continue
        progress = st.get("progress", 0)
        step = st.get("current_step", "Processing...")
        step_num = st.get("current_step_number", 0)
        total_steps = st.get("total_steps", 8)
        elapsed = str(timedelta(seconds=int(time.time()-start_time)))[2:7]
        bar = f"[{'🟩'*int(progress/2.5)}{'⬜'*(40-int(progress/2.5))}] {progress:.1f}%"
        status_text = f"""🚀 Sleep Stories AI — v3.5
Job: {job_id}\nElapsed: {elapsed}
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
        time.sleep(backoff)
        backoff = min(5, backoff + 1)
    res = fetch_json(f"{API_URL}/generate/{job_id}/result", timeout=30)
    if not res:
        yield (last_status+"\n❌ result unavailable", "", "", "", job_id)
        return
    story = res.get('story_text','')
    metrics_text = json.dumps(res.get('metrics',{}), indent=2)
    coherence_text = json.dumps(res.get('coherence_stats',{}), indent=2)
    schema_text = json.dumps(res.get('beats_schema',{}), indent=2) if res.get('beats_schema') else "(no schema)"
    yield (last_status+"\n✅ COMPLETED", story, metrics_text+"\n\n---\nCoherence:\n"+coherence_text, "", schema_text)

# --- Attach/resume generator ---

def attach_and_stream(label: str) -> Generator[tuple, None, None]:
    job_id = parse_job_id(label)
    if not job_id:
        yield ("❌ Select a job to attach", "", "", "", "")
        return
    start_time = time.time()
    last_status = ""
    backoff = 2
    while True:
        st = fetch_json(f"{API_URL}/generate/{job_id}/status", timeout=15)
        if not st:
            yield (last_status + "\n⚠️ status unavailable", "", "", "", job_id)
            time.sleep(backoff)
            backoff = min(5, backoff + 1)
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
        time.sleep(backoff)
        backoff = min(5, backoff + 1)
    res = fetch_json(f"{API_URL}/generate/{job_id}/result", timeout=30)
    if not res:
        yield (last_status+"\n❌ result unavailable", "", "", "", job_id)
        return
    story = res.get('story_text','')
    metrics = json.dumps(res.get('metrics',{}), indent=2)
    coherence = json.dumps(res.get('coherence_stats',{}), indent=2)
    yield (last_status+"\n✅ COMPLETED", story, metrics+"\n\n---\nCoherence:\n"+coherence, "", json.dumps(res.get('beats_schema',{}), indent=2) or "(no schema)"

# --- UI ---

with gr.Blocks(title="Sleep Stories AI — v3.5", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🌙 Sleep Stories AI — v3.5")

    with gr.Row():
        with gr.Column(scale=1, min_width=460):
            gr.Markdown("### 🎨 Base")
            theme = gr.Textbox(label="Theme / Setting", value="Moonlit forest path")
            description = gr.Textbox(label="Extra details (optional)", lines=3)
            duration = gr.Slider(10, 120, value=45, step=5, label="Duration (minutes)")

            gr.Markdown("### 🤖 Models")
            use_custom = gr.Checkbox(label="Override models manually", value=False)
            gen = gr.Dropdown(choices=[], value=None, label="Generator", allow_custom_value=True)
            rsn = gr.Dropdown(choices=[], value=None, label="Reasoner", allow_custom_value=True)
            pol = gr.Dropdown(choices=[], value=None, label="Polisher", allow_custom_value=True)
            refresh_models = gr.Button("↻ Refresh models", size="sm")
            use_reasoner = gr.Checkbox(label="Enable Reasoner", value=True)
            use_polisher = gr.Checkbox(label="Enable Polisher", value=True)

            gr.Markdown("### 🎯 Quality & Structure")
            tts = gr.Checkbox(label="Insert TTS markers", value=False)
            strict_schema = gr.Checkbox(label="Return strict JSON schema", value=False)
            sensory_rotation = gr.Checkbox(label="Sensory rotation", value=True)
            sleep_taper = gr.Checkbox(label="Sleep taper", value=True)

            gr.Markdown("#### Embodied Journey (user-centric)")
            movement_req = gr.Slider(0, 2, value=1, step=1, label="Movement verbs per beat")
            transition_req = gr.Slider(0, 2, value=1, step=1, label="Transition tokens per beat")
            sensory_coupling = gr.Slider(0, 3, value=2, step=1, label="Sensory coupling (corp+env)")
            downshift_required = gr.Checkbox(label="Downshift required", value=True)
            pov_second_person = gr.Checkbox(label="Enforce 2nd person present", value=True)

            gr.Markdown("#### Destination Architecture")
            destination_arc = gr.Checkbox(label="Enable Destination Arc", value=True)
            arrival_start = gr.Slider(0.5, 0.95, value=0.7, step=0.05, label="Approach signals start")
            settlement_beats = gr.Slider(1, 4, value=2, step=1, label="Settlement beats (final)")
            closure_required = gr.Checkbox(label="Closure required", value=True)
            archetype = gr.Dropdown(label="Destination archetype", choices=["safe_shelter","peaceful_vista","restorative_water","sacred_space"], value="safe_shelter")

            with gr.Accordion("🔧 Advanced (examples included)", open=False):
                temp = gr.Slider(0.1, 1.5, value=0.7, step=0.05, label="Model temperature")
                coach_on = gr.Checkbox(label="Enable Spatial Coach (DeepSeek)", value=False)

        with gr.Column(scale=2, min_width=640):
            gr.Markdown("### 🔗 Active Session")
            with gr.Row():
                active_jobs = gr.Dropdown(label="Active Jobs (Resume)", choices=[], value=None, allow_custom_value=False)
                refresh_jobs = gr.Button("↻", size="sm")
                attach_btn = gr.Button("🔗 Attach", variant="secondary")
            current_job = gr.Textbox(label="Current Job ID", interactive=False)
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

    # Loaders
    def on_load():
        jobs = fetch_json(f"{API_URL}/jobs", timeout=15) or {"jobs": []}
        job_labels = build_job_labels(jobs)
        models = fetch_json(f"{API_URL}/models/ollama", timeout=15) or []
        names = [m.get('name','') for m in models if isinstance(m, dict)]
        return [gr.update(choices=job_labels, value=None), gr.update(choices=names, value=None), gr.update(choices=names, value=None), gr.update(choices=names, value=None)]

    demo.load(on_load, inputs=None, outputs=[active_jobs, gen, rsn, pol])

    refresh_jobs.click(
        fn=lambda: [gr.update(choices=build_job_labels(fetch_json(f"{API_URL}/jobs", 15) or {"jobs": []}), value=None)],
        inputs=None,
        outputs=[active_jobs]
    )

    refresh_models.click(
        fn=lambda: [gr.update(choices=[m.get('name','') for m in (fetch_json(f"{API_URL}/models/ollama", 15) or []) if isinstance(m, dict)], value=None)],
        inputs=None,
        outputs=[gen]
    )

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
        gen_it = start_and_stream(payload)
        first = next(gen_it)
        status_txt, story, metrics, outline, schema = first
        job_id = ""
        if "Job: " in status_txt:
            try:
                job_id = status_txt.split("Job: ",1)[1].split("\n",1)[0].strip()
            except Exception:
                job_id = ""
        # update current job id
        current_job.update(job_id)
        yield (status_txt, story, metrics, outline, schema)
        for update in gen_it:
            yield update

    def run_attach(label):
        for update in attach_and_stream(label):
            yield update

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
