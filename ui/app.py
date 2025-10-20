import os
import json
import time
import requests
import gradio as gr
from typing import Optional, Dict, Any, List

API_URL = os.getenv("API_URL", "http://backend:8000/api")

# ----------------------
# HTTP helpers
# ----------------------
def get_json(path: str, timeout: int = 6) -> Optional[Dict[str, Any]]:
    try:
        r = requests.get(f"{API_URL}{path}", timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None

def post_json(path: str, payload: Dict[str, Any], timeout: int = 30) -> Optional[Dict[str, Any]]:
    try:
        r = requests.post(f"{API_URL}{path}", json=payload, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None

# ----------------------
# Data loaders
# ----------------------
def load_ollama_models() -> List[str]:
    data = get_json("/models/ollama", timeout=6) or []
    return sorted([m.get("name") for m in data if isinstance(m, dict) and m.get("name")])

def load_presets() -> Dict[str, Dict[str, str]]:
    data = get_json("/models/presets", timeout=6) or {}
    return data.get("presets", {})

def load_jobs_labels() -> List[str]:
    data = get_json("/jobs", timeout=3) or {"jobs": []}
    labels = []
    for j in data.get("jobs", []):
        jid = j.get("job_id", "")
        status = j.get("status", "")
        prog = j.get("progress", 0)
        theme = j.get("theme", "unknown")[:48]
        labels.append(f"{jid}|{status}|{int(prog)}%|{theme}")
    return labels

def parse_job_id(label: str) -> str:
    return (label or "").split("|", 1)[0]

# ----------------------
# Payload builder — 1:1 con EnhancedStoryRequest
# ----------------------
def build_payload(theme, description, duration,
                  use_reasoner, use_polish,
                  tts_markers, strict_schema,
                  sensory_rotation, sleep_taper,
                  generator_model, reasoner_model, polisher_model,
                  temp_gen, temp_rsn, temp_pol,
                  beats, words_per_beat, tolerance,
                  taper_start_pct, taper_reduction,
                  custom_waypoints_text) -> Dict[str, Any]:

    models = {}
    if generator_model: models["generator"] = generator_model
    if reasoner_model:  models["reasoner"]  = reasoner_model
    if polisher_model:  models["polisher"]  = polisher_model

    # Parse custom waypoints (una per riga)
    custom_waypoints = None
    if custom_waypoints_text and custom_waypoints_text.strip():
        custom_waypoints = [w.strip() for w in custom_waypoints_text.splitlines() if w.strip()]

    payload = {
        "theme": theme,
        "duration": int(duration),
        "description": description or None,

        "models": models or None,
        "use_reasoner": bool(use_reasoner),
        "use_polish": bool(use_polish),

        "tts_markers": bool(tts_markers),
        "strict_schema": bool(strict_schema),

        # Questi due campi sono opzionali nel router: se None, usa i defaults del backend
        "sensory_rotation": bool(sensory_rotation) if sensory_rotation is not None else None,
        "sleep_taper": bool(sleep_taper) if sleep_taper is not None else None,

        # Advanced tweakables
        "temps": {
            "generator": float(temp_gen),
            "reasoner": float(temp_rsn),
            "polisher": float(temp_pol),
        },
        "beats": int(beats) if beats else None,
        "words_per_beat": int(words_per_beat) if words_per_beat else None,
        "tolerance": float(tolerance) if tolerance else None,
        "taper": {
            "start_pct": float(taper_start_pct),
            "reduction": float(taper_reduction),
        },

        # Waypoints opzionali
        "custom_waypoints": custom_waypoints
    }

    return payload

# ----------------------
# Status renderer
# ----------------------
def progress_bar(pct, color="#3b82f6"):
    pct = max(0, min(100, float(pct)))
    return f"""
    <div style='background:#f1f5f9;border-radius:8px;overflow:hidden;height:14px;width:100%;border:1px solid #e2e8f0'>
        <div style='height:14px;width:{pct}%;background:{color};transition:width 0.25s ease'></div>
    </div>
    """

def render_status_html(ev: Dict[str, Any]) -> str:
    status = ev.get("status", "processing")
    progress = float(ev.get("progress", 0))
    step = ev.get("current_step", "processing...")
    step_num = ev.get("current_step_number", 0)
    total_steps = ev.get("total_steps", 8)

    beat = ev.get("beat", {}) or {}
    bi = beat.get("index", 0)
    bt = beat.get("total", 0)
    bstage = beat.get("stage", "")
    bstage_prog = beat.get("stage_progress", 0)

    models = ev.get("models", {}) or {}
    temps = ev.get("temps", {}) or {}
    quality = ev.get("quality", {}) or {}
    timing = ev.get("timing", {}) or {}
    enh = ev.get("enhanced_features", {}) or {}

    if status == "completed":
        color = "#16a34a"; icon = "✅"
    elif status == "failed":
        color = "#dc2626"; icon = "❌"
    else:
        color = "#0ea5e9"; icon = "🚀"

    gen = models.get("generator", "") or "—"
    rsn = models.get("reasoner", "") or "—"
    pol = models.get("polisher", "") or "—"
    tgen = temps.get("generator"); trsn = temps.get("reasoner"); tpol = temps.get("polisher")

    sens_rot = quality.get("sensory_rotation")
    taper = quality.get("sleep_taper", {}) or {}
    elapsed = int((timing or {}).get("elapsed_sec") or 0)
    eta = (timing or {}).get("eta_sec")
    elapsed_str = f"{elapsed//60}m {elapsed%60}s" if elapsed else "0s"
    eta_str = f"{int(eta)//60}m {int(eta)%60}s" if eta else "—"

    beat_section = "<div style='color:#6b7280;text-align:center;font-style:italic'>Beat info not available yet</div>"
    if bt > 0:
        beat_pct = (bi/max(bt,1))*100
        beat_section = f"""
        <div style="margin-bottom:12px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                <span style="font-weight:700;color:#374151">Overall Beat Progress</span>
                <span style="background:#22c55e;color:white;padding:4px 8px;border-radius:12px;font-weight:700">{bi}/{bt}</span>
            </div>
            {progress_bar(beat_pct, "#22c55e")}
            <div style="text-align:right;color:#22c55e;font-weight:600;margin-top:4px">{beat_pct:.1f}%</div>
        </div>
        """
        if bstage:
            beat_section += f"""
            <div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                    <span style="font-weight:700;color:#374151">Current Stage: {bstage.upper()}</span>
                    <span style="background:#3b82f6;color:white;padding:4px 8px;border-radius:12px;font-weight:700">{bstage_prog}%</span>
                </div>
                {progress_bar(bstage_prog, "#3b82f6")}
            </div>
            """

    html = f"""
    <div style="border:2px solid {color};border-radius:16px;padding:20px;margin:8px 0;background:linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)">
        <div style="background:white;border:2px solid {color};border-radius:12px;padding:16px;margin-bottom:16px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                <div style="font-size:20px;font-weight:800;color:{color}">{icon} {status.upper()}</div>
                <div style="background:{color};color:white;padding:6px 12px;border-radius:20px;font-weight:700">STEP {step_num}/{total_steps}</div>
            </div>
            <div style="font-size:16px;margin-bottom:10px;color:#111827;font-weight:600">{step}</div>
            {progress_bar(progress, color)}
            <div style="text-align:right;color:{color};font-weight:700;margin-top:6px">{progress:.1f}%</div>
        </div>

        <div style="background:white;border:2px solid #22c55e;border-radius:12px;padding:16px;margin-bottom:16px">
            <div style="font-size:16px;font-weight:800;color:#22c55e;margin-bottom:10px;text-align:center">📊 BEAT TRACKER</div>
            {beat_section}
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <div style="background:white;border:1px solid #e5e7eb;border-radius:12px;padding:12px">
                <div style="font-weight:700;margin-bottom:8px;color:#374151;border-bottom:2px solid #f3f4f6;padding-bottom:4px">🤖 Models & Temps</div>
                <div style="font-size:13px;line-height:1.5">
                    <div>Gen: <span style="color:#111827;font-weight:600">{gen}</span> {f'<span style="color:#3b82f6">({tgen})</span>' if tgen is not None else ''}</div>
                    <div>Rsn: <span style="color:#111827;font-weight:600">{rsn}</span> {f'<span style="color:#3b82f6">({trsn})</span>' if trsn is not None else ''}</div>
                    <div>Pol: <span style="color:#111827;font-weight:600">{pol}</span> {f'<span style="color:#3b82f6">({tpol})</span>' if tpol is not None else ''}</div>
                </div>
            </div>
            <div style="background:white;border:1px solid #e5e7eb;border-radius:12px;padding:12px">
                <div style="font-weight:700;margin-bottom:8px;color:#374151;border-bottom:2px solid #f3f4f6;padding-bottom:4px">⏱️ Timing</div>
                <div style="font-size:13px;line-height:1.5">
                    <div>Elapsed: <span style="color:#111827;font-weight:600">{elapsed_str}</span></div>
                    <div>ETA: <span style="color:#111827;font-weight:600">{eta_str}</span></div>
                </div>
            </div>
        </div>
    </div>
    """
    return html

# ----------------------
# SSE streaming (requests.iter_lines)
# ----------------------
def stream_sse(job_id: str):
    url = f"{API_URL}/generate/{job_id}/stream"
    max_retries = 4
    retry = 0
    last_progress = -1.0

    while retry <= max_retries:
        try:
            with requests.get(url, headers={"Accept": "text/event-stream", "Cache-Control": "no-cache", "Connection": "keep-alive"}, stream=True, timeout=(10, 90)) as resp:
                if resp.status_code != 200:
                    yield (f"<div style='color:#dc2626'>❌ Stream HTTP {resp.status_code}</div>", "", "", "")
                    return
                retry = 0
                for line in resp.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                        except json.JSONDecodeError:
                            continue

                        status = data.get("status", "processing")
                        progress = float(data.get("progress", 0))

                        if abs(progress - last_progress) >= 0.5 or status in ("completed", "failed"):
                            yield (render_status_html(data), "", "", "")
                            last_progress = progress

                        if status == "completed":
                            res = get_json(f"/generate/{job_id}/result", timeout=10) or {}
                            story = res.get("story_text", "")
                            metrics = json.dumps(res.get("metrics", {}), indent=2)
                            schema = json.dumps(res.get("beats_schema", {}), indent=2) if res.get("beats_schema") else "(no schema)"
                            yield (render_status_html(data), story, metrics, schema)
                            return
                        if status == "failed":
                            yield (render_status_html(data), "", "", "")
                            return

                    elif line.startswith("event: heartbeat"):
                        # keep alive
                        continue

            break  # stream ended unexpectedly

        except requests.exceptions.RequestException as e:
            retry += 1
            if retry > max_retries:
                yield (f"<div style='color:#dc2626'>❌ Stream failed: {str(e)}</div>", "", "", "")
                return
            yield (f"<div style='color:#f59e0b'>⚠️ Stream lost, retrying ({retry}/{max_retries})...</div>", "", "", "")
            time.sleep(min(2 ** retry, 8))

# ----------------------
# Actions
# ----------------------
def start_and_stream(theme, description, duration,
                     use_reasoner, use_polish,
                     tts_markers, strict_schema,
                     sensory_rotation, sleep_taper,
                     generator_model, reasoner_model, polisher_model,
                     temp_gen, temp_rsn, temp_pol,
                     beats, words_per_beat, tolerance,
                     taper_start_pct, taper_reduction,
                     custom_waypoints_text):
    payload = build_payload(theme, description, duration,
                            use_reasoner, use_polish,
                            tts_markers, strict_schema,
                            sensory_rotation, sleep_taper,
                            generator_model, reasoner_model, polisher_model,
                            temp_gen, temp_rsn, temp_pol,
                            beats, words_per_beat, tolerance,
                            taper_start_pct, taper_reduction,
                            custom_waypoints_text)

    started = post_json("/generate/story", payload)
    if not started or "job_id" not in started:
        yield ("<div style='color:#dc2626'>❌ Failed to start generation</div>", "", "", "")
        return

    jid = started["job_id"]
    yield (f"<div style='color:#0ea5e9'>🚀 Generation started — Job ID: <code>{jid}</code></div>", "", "", "")

    for update in stream_sse(jid):
        yield update

def attach_and_stream(job_label: str):
    jid = parse_job_id(job_label)
    if not jid:
        yield ("<div style='color:#dc2626'>❌ Select a job</div>", "", "", "")
        return

    tel = get_json(f"/generate/{jid}/telemetry", timeout=4)
    if tel:
        yield (render_status_html(tel), "", "", "")

    for update in stream_sse(jid):
        yield update

def attach_manual(manual_id: str):
    jid = (manual_id or "").strip()
    if not jid:
        yield ("<div style='color:#dc2626'>❌ Enter a Job ID</div>", "", "", "")
        return
    tel = get_json(f"/generate/{jid}/telemetry", timeout=4)
    if tel:
        yield (render_status_html(tel), "", "", "")
    for update in stream_sse(jid):
        yield update

# ----------------------
# UI
# ----------------------
with gr.Blocks(title="Sleep Stories — UI", theme=gr.themes.Soft()) as demo:
    gr.Markdown("## 🌙 Sleep Stories — Complete UI")

    models_state = gr.State([])
    presets_state = gr.State({})

    with gr.Row():
        with gr.Column(scale=1, min_width=460):
            gr.Markdown("### Base")
            theme = gr.Textbox(label="Theme", value="A peaceful mountain meadow at dawn")
            description = gr.Textbox(label="Description", lines=3, placeholder="Optional")
            duration = gr.Slider(10, 120, value=45, step=5, label="Duration (minutes)")

            gr.Markdown("### Models")
            gen_dd = gr.Dropdown(choices=[], label="Generator", allow_custom_value=True)
            rsn_dd = gr.Dropdown(choices=[], label="Reasoner", allow_custom_value=True)
            pol_dd = gr.Dropdown(choices=[], label="Polisher", allow_custom_value=True)
            preset_dd = gr.Dropdown(choices=[], label="Model Preset", allow_custom_value=False)

            def on_preset_change(preset_key, presets):
                if not preset_key or not presets or preset_key not in presets:
                    return gr.update(), gr.update(), gr.update()
                p = presets[preset_key]
                return gr.update(value=p.get("generator")), gr.update(value=p.get("reasoner")), gr.update(value=p.get("polisher"))

            preset_dd.change(on_preset_change, inputs=[preset_dd, presets_state], outputs=[gen_dd, rsn_dd, pol_dd])

            gr.Markdown("### Quality & Output")
            use_reasoner = gr.Checkbox(label="Enable Reasoner", value=True)
            use_polish = gr.Checkbox(label="Enable Polisher", value=True)
            tts_markers = gr.Checkbox(label="Insert TTS markers", value=False)
            strict_schema = gr.Checkbox(label="Return strict JSON schema", value=False)
            sensory_rotation = gr.Checkbox(label="Sensory rotation", value=True)
            sleep_taper = gr.Checkbox(label="Sleep taper", value=True)

            gr.Markdown("### Temperatures")
            temp_gen = gr.Slider(0.1, 1.5, value=0.7, step=0.05, label="Generator")
            temp_rsn = gr.Slider(0.1, 1.5, value=0.3, step=0.05, label="Reasoner")
            temp_pol = gr.Slider(0.1, 1.5, value=0.4, step=0.05, label="Polisher")

            gr.Markdown("### Structure")
            beats = gr.Slider(0, 24, value=0, step=1, label="Beats (0 = backend default)")
            words_per_beat = gr.Slider(0, 800, value=0, step=50, label="Words per beat (0 = backend default)")
            tolerance = gr.Slider(0.0, 0.5, value=0.0, step=0.05, label="Tolerance (0 = backend default)")
            taper_start_pct = gr.Slider(0.5, 0.95, value=0.8, step=0.05, label="Taper start pct")
            taper_reduction = gr.Slider(0.3, 0.9, value=0.7, step=0.05, label="Taper reduction")

            gr.Markdown("### Waypoints")
            custom_waypoints_text = gr.Textbox(label="Custom waypoints (one per line)", lines=4, placeholder="e.g.\nentry path\ngentle bend\nsmall clearing")

            run_btn = gr.Button("🎬 Generate", variant="primary")

        with gr.Column(scale=1, min_width=520):
            gr.Markdown("### Sessions")
            with gr.Row():
                jobs_dd = gr.Dropdown(choices=[], label="Active/Recent Jobs", allow_custom_value=False)
                refresh_jobs = gr.Button("↻")
                attach_btn = gr.Button("🔗 Attach")
            with gr.Row():
                manual_id = gr.Textbox(label="Manual Job ID", placeholder="Enter job ID…")
                attach_manual_btn = gr.Button("🔗 Attach manual")

            gr.Markdown("### Status & Outputs")
            status = gr.HTML(value="<div style='padding:16px;color:#6b7280'>Ready.</div>")
            with gr.Tabs():
                with gr.Tab("Story"):
                    story = gr.Textbox(lines=18, show_copy_button=True)
                with gr.Tab("Metrics"):
                    metrics = gr.Textbox(lines=12, show_copy_button=True)
                with gr.Tab("Schema"):
                    schema = gr.Textbox(lines=12, show_copy_button=True)

    # Load presets/models/jobs on app load
    def init_load():
        models = load_ollama_models()
        presets = load_presets()
        jobs = load_jobs_labels()
        return (models, presets,
                gr.update(choices=models), gr.update(choices=models), gr.update(choices=models),
                gr.update(choices=list(presets.keys())),
                gr.update(choices=jobs, value=None))

    demo.load(init_load, inputs=None, outputs=[models_state, presets_state, gen_dd, rsn_dd, pol_dd, preset_dd, jobs_dd])

    def refresh_jobs_only():
        return gr.update(choices=load_jobs_labels(), value=None)

    refresh_jobs.click(refresh_jobs_only, None, [jobs_dd])

    run_btn.click(
        start_and_stream,
        inputs=[
            theme, description, duration,
            use_reasoner, use_polish,
            tts_markers, strict_schema,
            sensory_rotation, sleep_taper,
            gen_dd, rsn_dd, pol_dd,
            temp_gen, temp_rsn, temp_pol,
            beats, words_per_beat, tolerance,
            taper_start_pct, taper_reduction,
            custom_waypoints_text
        ],
        outputs=[status, story, metrics, schema],
        concurrency_id="generate", concurrency_limit=1
    )

    attach_btn.click(attach_and_stream, inputs=[jobs_dd], outputs=[status, story, metrics, schema])
    attach_manual_btn.click(attach_manual, inputs=[manual_id], outputs=[status, story, metrics, schema])

if __name__ == "__main__":
    demo.queue().launch(server_name="0.0.0.0", server_port=7860, show_error=True)
