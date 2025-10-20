import os
import json
import time
import asyncio
import aiohttp
import requests
import gradio as gr
from typing import Optional, Dict, Any, AsyncGenerator, List

API_URL = os.getenv("API_URL", "http://backend:8000/api")

# ----------------------
# HTTP helpers
# ----------------------
def get_json(path: str, timeout: int = 5) -> Optional[Dict[str, Any]]:
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
    try:
        data = get_json("/models/ollama", timeout=3) or []
        names = [m.get("name") for m in data if isinstance(m, dict) and m.get("name")]
        return sorted(names)
    except:
        return ["qwen2.5:7b", "deepseek-r1:8b", "mistral:7b"]

def load_presets() -> Dict[str, Dict[str, str]]:
    try:
        data = get_json("/models/presets", timeout=3) or {}
        return data.get("presets", {})
    except:
        return {"quality_high": {"generator": "qwen2.5:7b", "reasoner": "deepseek-r1:8b", "polisher": "mistral:7b"}}

def load_jobs_labels() -> List[str]:
    try:
        data = get_json("/jobs", timeout=2)
        if not data:
            return []
        labels = []
        for j in data.get("jobs", []):
            jid = j.get("job_id", "")
            status = j.get("status", "")
            prog = j.get("progress", 0)
            theme = j.get("theme", "unknown")[:40]
            labels.append(f"{jid}|{status}|{int(prog)}%|{theme}")
        return labels
    except:
        return ["No jobs available - API busy generating"]

def parse_job_id(label: str) -> str:
    if not label or "No jobs available" in label:
        return ""
    return (label or "").split("|", 1)[0]

# ----------------------
# Payload builder (come prima)
# ----------------------
def build_payload(theme, description, duration,
                  use_reasoner, use_polish,
                  tts_markers, strict_schema,
                  sensory_rotation, sleep_taper,
                  generator_model, reasoner_model, polisher_model,
                  temp_gen, temp_rsn, temp_pol,
                  beats, words_per_beat, tolerance,
                  taper_start_pct, taper_reduction,
                  movement_req, transition_req, sensory_coupling, downshift_required, pov_second_person,
                  destination_arc, arrival_start, settlement_beats, closure_required, archetype,
                  coach_on) -> Dict[str, Any]:
    
    models = {}
    if generator_model: models["generator"] = generator_model
    if reasoner_model:  models["reasoner"]  = reasoner_model
    if polisher_model:  models["polisher"]  = polisher_model
    
    return {
        "theme": theme,
        "duration": int(duration),
        "description": description or None,
        "models": models or None,
        "use_reasoner": bool(use_reasoner),
        "use_polish": bool(use_polish),
        "tts_markers": bool(tts_markers),
        "strict_schema": bool(strict_schema),
        "sensory_rotation": bool(sensory_rotation) if sensory_rotation is not None else None,
        "sleep_taper": bool(sleep_taper) if sleep_taper is not None else None,
        "temps": {
            "generator": float(temp_gen),
            "reasoner": float(temp_rsn),
            "polisher": float(temp_pol)
        },
        "beats": int(beats) if beats else None,
        "words_per_beat": int(words_per_beat) if words_per_beat else None,
        "tolerance": float(tolerance) if tolerance else None,
        "taper": {
            "start_pct": float(taper_start_pct),
            "reduction": float(taper_reduction)
        },
        "advanced": {
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

# ----------------------
# Status renderer (con beat/steps prominenti)
# ----------------------
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

    def progress_bar(pct, color="#3b82f6"):
        pct = max(0, min(100, float(pct)))
        return f"""
        <div style='background:#f1f5f9;border-radius:8px;overflow:hidden;height:14px;width:100%;border:1px solid #e2e8f0'>
            <div style='height:14px;width:{pct}%;background:{color};transition:width 0.3s ease'></div>
        </div>
        """

    if status == "completed":
        color = "#16a34a"; icon = "✅"
    elif status == "failed":
        color = "#dc2626"; icon = "❌"
    else:
        color = "#0ea5e9"; icon = "🚀"

    gen = models.get("generator", "")[:25] + ("..." if len(models.get("generator", "")) > 25 else "")
    rsn = models.get("reasoner", "")[:25] + ("..." if len(models.get("reasoner", "")) > 25 else "")
    pol = models.get("polisher", "")[:25] + ("..." if len(models.get("polisher", "")) > 25 else "")
    tgen = temps.get("generator"); trsn = temps.get("reasoner"); tpol = temps.get("polisher")

    sens_rot = quality.get("sensory_rotation")
    taper = quality.get("sleep_taper", {}) or {}
    taper_start = taper.get("start_pct"); taper_red = taper.get("reduction")

    elapsed = int(timing.get("elapsed_sec") or 0)
    eta = timing.get("eta_sec")
    elapsed_str = f"{elapsed//60}m {elapsed%60}s" if elapsed > 0 else "0s"
    eta_str = f"{int(eta)//60}m {int(eta)%60}s" if eta and eta > 0 else "—"

    f_tts = enh.get("tts_markers", False)
    f_schema = enh.get("strict_schema", False)
    f_reasoner = enh.get("use_reasoner", False)
    f_polish = enh.get("use_polish", False)

    html = f"""
    <div style="border:2px solid {color};border-radius:16px;padding:20px;margin:8px 0;background:linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)">
        
        <!-- STATUS HEADER -->
        <div style="background:white;border:2px solid {color};border-radius:12px;padding:16px;margin-bottom:16px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                <div style="font-size:22px;font-weight:800;color:{color}">{icon} {status.upper()}</div>
                <div style="background:{color};color:white;padding:6px 12px;border-radius:20px;font-weight:700">
                    STEP {step_num}/{total_steps}
                </div>
            </div>
            <div style="font-size:16px;margin-bottom:12px;color:#111827;font-weight:600">{step}</div>
            {progress_bar(progress, color)}
            <div style="text-align:right;color:{color};font-weight:700;font-size:16px;margin-top:6px">{progress:.1f}%</div>
        </div>

        <!-- BEAT TRACKER -->
        <div style="background:white;border:2px solid #22c55e;border-radius:12px;padding:16px;margin-bottom:16px">
            <div style="font-size:18px;font-weight:800;color:#22c55e;margin-bottom:12px;text-align:center">
                📊 BEAT TRACKER
            </div>
            {f'''
            <div style="margin-bottom:12px">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                    <span style="font-weight:700;color:#374151">Overall Beat Progress</span>
                    <span style="background:#22c55e;color:white;padding:4px 8px;border-radius:12px;font-weight:700">{bi}/{bt}</span>
                </div>
                {progress_bar((bi/max(bt,1))*100, "#22c55e")}
                <div style="text-align:right;color:#22c55e;font-weight:600;margin-top:4px">{(bi/max(bt,1))*100:.1f}%</div>
            </div>
            ''' if bt > 0 else '<div style="color:#6b7280;text-align:center;font-style:italic">Beat info not available yet</div>'}
            
            {f'''
            <div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                    <span style="font-weight:700;color:#374151">Current Stage: {bstage.upper()}</span>
                    <span style="background:#3b82f6;color:white;padding:4px 8px;border-radius:12px;font-weight:700">{bstage_prog}%</span>
                </div>
                {progress_bar(bstage_prog, "#3b82f6")}
            </div>
            ''' if bstage else ''}
        </div>
        
        <!-- DETTAGLI GRID -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <div style="background:white;border:1px solid #e5e7eb;border-radius:12px;padding:14px">
                <div style="font-weight:700;margin-bottom:10px;color:#374151;border-bottom:2px solid #f3f4f6;padding-bottom:6px">🤖 Models</div>
                <div style="font-size:13px;line-height:1.6">
                    <div><span style="color:#6b7280">Gen:</span> <span style="color:#111827;font-weight:600">{gen or '—'}</span> {f'<span style="color:#3b82f6">({tgen})</span>' if tgen else ''}</div>
                    <div><span style="color:#6b7280">Rsn:</span> <span style="color:#111827;font-weight:600">{rsn or '—'}</span> {f'<span style="color:#3b82f6">({trsn})</span>' if trsn else ''}</div>
                    <div><span style="color:#6b7280">Pol:</span> <span style="color:#111827;font-weight:600">{pol or '—'}</span> {f'<span style="color:#3b82f6">({tpol})</span>' if tpol else ''}</div>
                </div>
            </div>
            <div style="background:white;border:1px solid #e5e7eb;border-radius:12px;padding:14px">
                <div style="font-weight:700;margin-bottom:10px;color:#374151;border-bottom:2px solid #f3f4f6;padding-bottom:6px">⏱️ Timing</div>
                <div style="font-size:14px;line-height:1.6">
                    <div><span style="color:#6b7280">Elapsed:</span> <span style="color:#111827;font-weight:700">{elapsed_str}</span></div>
                    <div><span style="color:#6b7280">ETA:</span> <span style="color:#111827;font-weight:700">{eta_str}</span></div>
                </div>
            </div>
        </div>
    </div>
    """
    gen_history = ev.get("generation_history", [])
    current_gen = ev.get("current_generation", {})
    
    # History panel
    history_section = ""
    if gen_history:
        history_items = []
        for entry in gen_history[-3:]:  # Ultime 3 entries
            step_name = entry.get("step", "").replace("_", " ").title()
            preview = entry.get("content_preview", "")[:80] + "..."
            word_count = entry.get("word_count", 0)
            
            history_items.append(f"""
            <div style="border-left:3px solid #3b82f6;padding-left:8px;margin-bottom:6px;font-size:12px">
                <div style="font-weight:600;color:#3b82f6">{step_name}</div>
                <div style="color:#6b7280;font-style:italic">"{preview}"</div>
                <div style="color:#9ca3af">{word_count} words</div>
            </div>
            """)
        
        history_section = f"""
        <div style="background:white;border:1px solid #e5e7eb;border-radius:12px;padding:14px;margin-top:12px">
            <div style="font-weight:700;margin-bottom:10px;color:#374151;border-bottom:2px solid #f3f4f6;padding-bottom:6px">📜 Generation History</div>
            {"".join(history_items)}
        </div>
        """
    
    # Current generation preview
    current_gen_section = ""
    if current_gen:
        step_name = current_gen.get("step", "").replace("_", " ").title()
        preview = current_gen.get("preview", "")
        
        current_gen_section = f"""
        <div style="background:linear-gradient(135deg,#eff6ff,#dbeafe);border:1px solid #3b82f6;border-radius:12px;padding:14px;margin-top:12px">
            <div style="font-weight:700;margin-bottom:8px;color:#3b82f6;border-bottom:2px solid #bfdbfe;padding-bottom:4px">🔄 Currently Generating</div>
            <div style="font-weight:600;color:#1e40af;margin-bottom:4px">{step_name}</div>
            <div style="color:#374151;font-style:italic;font-size:13px">"{preview}"</div>
        </div>
        """
    
    # Aggiungi le nuove sezioni all'HTML esistente
    html += history_section + current_gen_section
    
    return html

# ----------------------
# 🔥 FIX STREAM SSE - Gestione corretta GeneratorExit
# ----------------------
def stream_sse_simple(job_id: str):
    """Stream SSE semplificato che evita GeneratorExit"""
    max_retries = 3
    retry_count = 0
    last_progress = -1
    
    while retry_count <= max_retries:
        try:
            # Simple requests SSE (no aiohttp async complexity)
            import requests
            
            url = f"{API_URL}/generate/{job_id}/stream"
            response = requests.get(url, 
                                  headers={"Accept": "text/event-stream"},
                                  stream=True,
                                  timeout=(10, 60))  # 10s connect, 60s read
            
            if response.status_code != 200:
                error_html = f"""
                <div style="border:2px solid #dc2626;border-radius:16px;padding:20px;margin:8px 0;background:#fef2f2">
                    <div style="font-size:18px;font-weight:700;color:#dc2626">❌ STREAM ERROR</div>
                    <div>HTTP {response.status_code}</div>
                </div>
                """
                yield (error_html, "", "", "")
                return
            
            # Reset retry count on successful connection
            retry_count = 0
            
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                    
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        status = data.get("status", "processing")
                        progress = data.get("progress", 0)
                        
                        # Update on significant change
                        if abs(progress - last_progress) >= 0.5 or status in ("completed", "failed"):
                            status_html = render_status_html(data)
                            yield (status_html, "", "", "")
                            last_progress = progress
                        
                        # Handle completion
                        if status == "completed":
                            res = get_json(f"/generate/{job_id}/result")
                            if res:
                                story = res.get("story_text", "")
                                metrics = json.dumps(res.get("metrics", {}), indent=2)
                                schema = json.dumps(res.get("beats_schema", {}), indent=2) if res.get("beats_schema") else "(no schema)"
                                final_html = render_status_html(data)
                                yield (final_html, story, metrics, schema)
                            return
                            
                        elif status == "failed":
                            failed_html = render_status_html(data)
                            yield (failed_html, "", "", "")
                            return
                            
                    except json.JSONDecodeError:
                        continue
                        
                elif line.startswith("event: heartbeat"):
                    # Just continue on heartbeat
                    continue
            
            # If we reach here, connection ended unexpectedly
            break
            
        except requests.exceptions.RequestException as e:
            retry_count += 1
            if retry_count > max_retries:
                error_html = f"""
                <div style="border:2px solid #dc2626;border-radius:16px;padding:20px;margin:8px 0;background:#fef2f2">
                    <div style="font-size:18px;font-weight:700;color:#dc2626">❌ CONNECTION FAILED</div>
                    <div>Max retries exceeded: {str(e)}</div>
                </div>
                """
                yield (error_html, "", "", "")
                return
            
            # Retry with backoff
            retry_html = f"""
            <div style="border:2px solid #f59e0b;border-radius:16px;padding:20px;margin:8px 0;background:#fef3c7">
                <div style="font-size:18px;font-weight:700;color:#f59e0b">⚠️ CONNECTION LOST</div>
                <div>Retrying... ({retry_count}/{max_retries})</div>
            </div>
            """
            yield (retry_html, "", "", "")
            time.sleep(min(2 ** retry_count, 8))

def start_and_stream(*args):
    payload = build_payload(*args)
    started = post_json("/generate/story", payload)
    if not started or "job_id" not in started:
        error_html = """
        <div style="border:2px solid #dc2626;border-radius:16px;padding:20px;margin:8px 0;background:#fef2f2">
            <div style="font-size:18px;font-weight:700;color:#dc2626">❌ GENERATION FAILED TO START</div>
        </div>
        """
        yield (error_html, "", "", "")
        return
    
    jid = started["job_id"]
    init_html = f"""
    <div style="border:2px solid #0ea5e9;border-radius:16px;padding:20px;margin:8px 0;background:linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%)">
        <div style="font-size:18px;font-weight:700;color:#0ea5e9">🚀 GENERATION STARTED</div>
        <div style="margin-top:8px">Job ID: <code>{jid}</code></div>
    </div>
    """
    yield (init_html, "", "", "")
    
    for update in stream_sse_simple(jid):
        yield update

def attach_and_stream(job_label: str):
    jid = parse_job_id(job_label)
    if not jid:
        error_html = """<div style="padding:20px;color:#dc2626">❌ No job selected</div>"""
        yield (error_html, "", "", "")
        return
    
    # Quick telemetry check
    tel = get_json(f"/generate/{jid}/telemetry", timeout=3)
    if tel:
        attach_html = render_status_html(tel)
        yield (attach_html, "", "", "")
    
    for update in stream_sse_simple(jid):
        yield update

def attach_manual_job(manual_job_id: str):
    if not manual_job_id.strip():
        error_html = """<div style="padding:20px;color:#dc2626">❌ No job ID provided</div>"""
        yield (error_html, "", "", "")
        return
    
    jid = manual_job_id.strip()
    tel = get_json(f"/generate/{jid}/telemetry", timeout=3)
    if tel:
        attach_html = render_status_html(tel)
        yield (attach_html, "", "", "")
    
    for update in stream_sse_simple(jid):
        yield update

# ----------------------
# Gradio UI (resto uguale)
# ----------------------
with gr.Blocks(title="Sleep Stories — Complete UI", theme=gr.themes.Soft()) as demo:
    gr.Markdown("## 🌙 Sleep Stories — UI SEMPLIFICATA e ROBUSTA")

    models_state = gr.State([])
    presets_state = gr.State({})

    with gr.Row():
        with gr.Column(scale=1, min_width=480):
            # Tutti i controlli come prima...
            gr.Markdown("### 🎨 Base")
            theme = gr.Textbox(label="Theme", value="Moonlit forest path")
            description = gr.Textbox(label="Description", lines=3)
            duration = gr.Slider(10, 120, value=45, step=5, label="Duration (minutes)")

            gr.Markdown("### 🤖 Models")
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

            # Tutti gli altri controlli...
            gr.Markdown("### ⚙️ Settings")
            use_reasoner = gr.Checkbox(label="Enable Reasoner", value=True)
            use_polish = gr.Checkbox(label="Enable Polisher", value=True)
            tts_markers = gr.Checkbox(label="TTS markers", value=False)
            strict_schema = gr.Checkbox(label="Strict schema", value=False)
            sensory_rotation = gr.Checkbox(label="Sensory rotation", value=True)
            sleep_taper = gr.Checkbox(label="Sleep taper", value=True)

            gr.Markdown("### 🎯 Temperatures")
            temp_gen = gr.Slider(0.1, 1.5, value=0.7, step=0.05, label="Generator")
            temp_rsn = gr.Slider(0.1, 1.5, value=0.3, step=0.05, label="Reasoner")
            temp_pol = gr.Slider(0.1, 1.5, value=0.4, step=0.05, label="Polisher")

            gr.Markdown("### 📊 Structure")
            beats = gr.Slider(6, 24, value=12, step=1, label="Beats")
            words_per_beat = gr.Slider(200, 800, value=500, step=50, label="Words per beat")
            tolerance = gr.Slider(0.05, 0.5, value=0.2, step=0.05, label="Tolerance")
            taper_start_pct = gr.Slider(0.5, 0.95, value=0.8, step=0.05, label="Taper start")
            taper_reduction = gr.Slider(0.3, 0.9, value=0.7, step=0.05, label="Taper reduction")

            gr.Markdown("### 🚶 Embodied Journey")
            movement_req = gr.Slider(0, 2, value=1, step=1, label="Movement verbs")
            transition_req = gr.Slider(0, 2, value=1, step=1, label="Transition tokens")
            sensory_coupling = gr.Slider(0, 3, value=2, step=1, label="Sensory coupling")
            downshift_required = gr.Checkbox(label="Downshift required", value=True)
            pov_second_person = gr.Checkbox(label="2nd person POV", value=True)

            gr.Markdown("### 🏛️ Destination")
            destination_arc = gr.Checkbox(label="Enable Destination Arc", value=True)
            arrival_start = gr.Slider(0.5, 0.95, value=0.7, step=0.05, label="Arrival start")
            settlement_beats = gr.Slider(1, 4, value=2, step=1, label="Settlement beats")
            closure_required = gr.Checkbox(label="Closure required", value=True)
            archetype = gr.Dropdown(
                choices=["safe_shelter", "peaceful_vista", "restorative_water", "sacred_space"],
                value="safe_shelter", label="Archetype"
            )

            gr.Markdown("### 🔧 Advanced")
            coach_on = gr.Checkbox(label="Spatial Coach", value=False)

            run_btn = gr.Button("🎬 Generate Story", variant="primary", size="lg")

        with gr.Column(scale=1, min_width=520):
            gr.Markdown("### 🔗 Jobs")
            with gr.Group():
                with gr.Row():
                    jobs_dd = gr.Dropdown(choices=[], label="Auto-detected", scale=3)
                    refresh_jobs = gr.Button("↻", size="sm", scale=1)
                    attach_btn = gr.Button("🔗", variant="secondary", scale=1)
                
                with gr.Row():
                    manual_job_id = gr.Textbox(label="Manual Job ID", placeholder="Enter job ID...", scale=3)
                    attach_manual_btn = gr.Button("🔗 Manual", variant="secondary", scale=1)

            gr.Markdown("### 📊 Status")
            status = gr.HTML(value="<div style='padding:20px;text-align:center;color:#6b7280'>Ready</div>")

            gr.Markdown("### 📤 Outputs")
            with gr.Tabs():
                with gr.Tab("Story"):
                    story = gr.Textbox(lines=18, show_copy_button=True, interactive=False)
                with gr.Tab("Metrics"):
                    metrics = gr.Textbox(lines=12, show_copy_button=True, interactive=False)
                with gr.Tab("Schema"):
                    schema = gr.Textbox(lines=12, show_copy_button=True, interactive=False)

    # Event handlers
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
            theme, description, duration, use_reasoner, use_polish, tts_markers, strict_schema,
            sensory_rotation, sleep_taper, gen_dd, rsn_dd, pol_dd, temp_gen, temp_rsn, temp_pol,
            beats, words_per_beat, tolerance, taper_start_pct, taper_reduction,
            movement_req, transition_req, sensory_coupling, downshift_required, pov_second_person,
            destination_arc, arrival_start, settlement_beats, closure_required, archetype, coach_on
        ],
        outputs=[status, story, metrics, schema],
        concurrency_id="generate", concurrency_limit=1
    )

    attach_btn.click(attach_and_stream, inputs=[jobs_dd], outputs=[status, story, metrics, schema])
    attach_manual_btn.click(attach_manual_job, inputs=[manual_job_id], outputs=[status, story, metrics, schema])

if __name__ == "__main__":
    demo.queue().launch(server_name="0.0.0.0", server_port=7860, show_error=True)
