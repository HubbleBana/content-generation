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
def get_json(path: str, timeout: int = 20) -> Optional[Dict[str, Any]]:
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
    data = get_json("/models/ollama") or []
    names = [m.get("name") for m in data if isinstance(m, dict) and m.get("name")]
    return sorted(names)

def load_presets() -> Dict[str, Dict[str, str]]:
    data = get_json("/models/presets") or {}
    return data.get("presets", {})

def load_jobs_labels() -> List[str]:
    data = get_json("/jobs") or {"jobs": []}
    labels = []
    for j in data.get("jobs", []):
        jid = j.get("job_id", "")
        status = j.get("status", "")
        prog = j.get("progress", 0)
        theme = j.get("theme", "unknown")[:40]
        labels.append(f"{jid}|{status}|{int(prog)}%|{theme}")
    return labels

def parse_job_id(label: str) -> str:
    return (label or "").split("|", 1)[0]

# ----------------------
# Payload builder COMPLETO
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
    
    payload = {
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
    return payload

# ----------------------
# SYNC streaming wrapper (FIX per Gradio)
# ----------------------
def stream_sse_sync(job_id: str):
    """Wrapper sincrono per SSE streaming - compatibile con Gradio"""
    
    def sync_sse_stream():
        import asyncio
        
        async def async_stream():
            url = f"{API_URL}/generate/{job_id}/stream"
            timeout = aiohttp.ClientTimeout(total=None, sock_read=60)
            retries = 0
            
            while retries <= 3:
                try:
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.get(url, headers={"Accept": "text/event-stream"}) as resp:
                            if resp.status != 200:
                                yield {"error": f"SSE HTTP {resp.status}"}
                                return
                            
                            async for chunk in resp.content:
                                line = chunk.decode("utf-8").strip()
                                if not line:
                                    continue
                                    
                                if line.startswith("data: "):
                                    try:
                                        yield json.loads(line[6:])
                                    except Exception:
                                        continue
                                elif line.startswith("event: heartbeat"):
                                    yield {"heartbeat": True}
                    return
                    
                except Exception as e:
                    retries += 1
                    yield {"error": f"stream error: {e}, retry {retries}/3"}
                    await asyncio.sleep(min(2**retries, 8))
        
        # Esegui l'async generator in modo sincrono
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async_gen = async_stream()
            while True:
                try:
                    event = loop.run_until_complete(async_gen.__anext__())
                    yield event
                except StopAsyncIteration:
                    break
        except Exception as e:
            yield {"error": f"sync wrapper error: {e}"}
        finally:
            loop.close()
    
    last_progress = -1
    for ev in sync_sse_stream():
        if "error" in ev:
            yield (f"❌ {ev['error']}", "", "", "")
            continue
        if "heartbeat" in ev:
            continue
            
        status = ev.get("status", "processing")
        progress = ev.get("progress", 0)
        step = ev.get("current_step", "processing...")
        beat = ev.get("beat", {})
        timing = ev.get("timing", {})
        
        # Progress bar
        bar = f"[{'█'*int(progress/2)}{'░'*(50-int(progress/2))}] {progress:.1f}%"
        
        # Beat info
        beat_txt = ""
        if beat:
            bi = beat.get("index", 0)
            bt = beat.get("total", 0) 
            stg = beat.get("stage", "")
            if bt:
                beat_txt = f"Beat {bi}/{bt} — {stg}"
        
        # Timing info
        elapsed = int((timing or {}).get("elapsed_sec") or 0)
        eta = (timing or {}).get("eta_sec")
        timing_txt = f"Elapsed: {elapsed}s" + (f" • ETA: {int(eta)}s" if eta is not None else "")

        status_text = f"{bar}\n{step}\n{beat_txt}\n{timing_txt}"
        
        # Update solo su cambi significativi
        if abs(progress - last_progress) >= 1 or status in ("completed","failed"):
            yield (status_text, "", "", "")
            last_progress = progress

        if status == "completed":
            res = get_json(f"/generate/{job_id}/result")
            if res:
                story = res.get("story_text","")
                metrics = json.dumps(res.get("metrics",{}), indent=2)
                schema = json.dumps(res.get("beats_schema",{}), indent=2) if res.get("beats_schema") else "(no schema)"
                yield (status_text+"\n✅ COMPLETED", story, metrics, schema)
            else:
                yield (status_text+"\n⚠️ result unavailable", "", "", "")
            return
        elif status == "failed":
            yield (status_text+"\n❌ FAILED", "", "", "")
            return

def start_and_stream(*args):
    """Start generation and stream updates"""
    payload = build_payload(*args)
    
    # Start generation
    started = post_json("/generate/story", payload)
    if not started or "job_id" not in started:
        yield ("❌ Failed to start generation", "", "", "")
        return
    
    jid = started["job_id"]
    yield (f"🚀 Generation started\nJob ID: {jid}", "", "", "")
    
    # Stream updates
    for update in stream_sse_sync(jid):
        yield update

def attach_and_stream(job_label: str):
    """Attach to existing job and stream updates"""
    jid = parse_job_id(job_label)
    if not jid:
        yield ("❌ Please select a job to attach to", "", "", "")
        return
    
    # Get current status first
    tel = get_json(f"/generate/{jid}/telemetry")
    if tel:
        progress = tel.get("progress", 0)
        step = tel.get("current_step", "processing...")
        bar = f"[{'█'*int(progress/2)}{'░'*(50-int(progress/2))}] {progress:.1f}%"
        yield (f"{bar}\n{step}\n🔗 Attached to {jid}", "", "", "")
    
    # Stream updates
    for update in stream_sse_sync(jid):
        yield update

# ----------------------
# Gradio 4.44.1 UI COMPLETA
# ----------------------
with gr.Blocks(title="Sleep Stories — Complete UI", theme=gr.themes.Soft()) as demo:
    gr.Markdown("## 🌙 Sleep Stories — UI Completa con tutti i parametri")

    models_state = gr.State([])
    presets_state = gr.State({})

    with gr.Row():
        with gr.Column(scale=1, min_width=480):
            gr.Markdown("### 🎨 Base")
            theme = gr.Textbox(label="Theme", value="Moonlit forest path")
            description = gr.Textbox(label="Description", lines=3, placeholder="Focus on gentle morning sounds and soft light...")
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

            preset_dd.change(
                on_preset_change,
                inputs=[preset_dd, presets_state],
                outputs=[gen_dd, rsn_dd, pol_dd]
            )

            gr.Markdown("### ⚙️ Quality & Structure")
            use_reasoner = gr.Checkbox(label="Enable Reasoner", value=True)
            use_polish = gr.Checkbox(label="Enable Polisher", value=True)
            tts_markers = gr.Checkbox(label="Insert TTS markers", value=False)
            strict_schema = gr.Checkbox(label="Return strict JSON schema", value=False)
            sensory_rotation = gr.Checkbox(label="Sensory rotation", value=True)
            sleep_taper = gr.Checkbox(label="Sleep taper", value=True)

            gr.Markdown("### 🎯 Model Temperatures")
            temp_gen = gr.Slider(0.1, 1.5, value=0.7, step=0.05, label="Temperature generator")
            temp_rsn = gr.Slider(0.1, 1.5, value=0.3, step=0.05, label="Temperature reasoner")
            temp_pol = gr.Slider(0.1, 1.5, value=0.4, step=0.05, label="Temperature polisher")

            gr.Markdown("### 📊 Story Structure")
            beats = gr.Slider(6, 24, value=12, step=1, label="Beats count")
            words_per_beat = gr.Slider(200, 800, value=500, step=50, label="Words per beat")
            tolerance = gr.Slider(0.05, 0.5, value=0.2, step=0.05, label="Word count tolerance (±)")
            taper_start_pct = gr.Slider(0.5, 0.95, value=0.8, step=0.05, label="Taper start percentage")
            taper_reduction = gr.Slider(0.3, 0.9, value=0.7, step=0.05, label="Taper reduction factor")

            gr.Markdown("### 🚶 Embodied Journey (User-Centric)")
            movement_req = gr.Slider(0, 2, value=1, step=1, label="Movement verbs per beat")
            transition_req = gr.Slider(0, 2, value=1, step=1, label="Transition tokens per beat")
            sensory_coupling = gr.Slider(0, 3, value=2, step=1, label="Sensory coupling (corp+env)")
            downshift_required = gr.Checkbox(label="Downshift required", value=True)
            pov_second_person = gr.Checkbox(label="Enforce 2nd person present", value=True)

            gr.Markdown("### 🏛️ Destination Architecture")
            destination_arc = gr.Checkbox(label="Enable Destination Arc", value=True)
            arrival_start = gr.Slider(0.5, 0.95, value=0.7, step=0.05, label="Approach signals start")
            settlement_beats = gr.Slider(1, 4, value=2, step=1, label="Settlement beats (final)")
            closure_required = gr.Checkbox(label="Closure required", value=True)
            archetype = gr.Dropdown(
                label="Destination archetype",
                choices=["safe_shelter", "peaceful_vista", "restorative_water", "sacred_space"],
                value="safe_shelter"
            )

            gr.Markdown("### 🔧 Advanced")
            coach_on = gr.Checkbox(label="Enable Spatial Coach (DeepSeek)", value=False)

            run_btn = gr.Button("🎬 Generate Story", variant="primary", size="lg")

        with gr.Column(scale=1, min_width=520):
            gr.Markdown("### 🔗 Sessions & Jobs")
            with gr.Row():
                jobs_dd = gr.Dropdown(choices=[], label="Active/Recent Jobs", allow_custom_value=False, scale=3)
                refresh_jobs = gr.Button("↻", size="sm", scale=1)
                attach_btn = gr.Button("🔗 Attach", variant="secondary", scale=1)

            gr.Markdown("### 📊 Real-time Status")
            status = gr.Textbox(label="Generation Status", lines=10, interactive=False)

            gr.Markdown("### 📤 Outputs")
            with gr.Tabs():
                with gr.Tab("📖 Story"):
                    story = gr.Textbox(lines=18, show_copy_button=True, interactive=False)
                with gr.Tab("📈 Metrics"):
                    metrics = gr.Textbox(lines=12, show_copy_button=True, interactive=False)
                with gr.Tab("🗂️ Schema"):
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

    demo.load(
        init_load,
        inputs=None,
        outputs=[models_state, presets_state, gen_dd, rsn_dd, pol_dd, preset_dd, jobs_dd]
    )

    def refresh_jobs_only():
        return gr.update(choices=load_jobs_labels(), value=None)

    refresh_jobs.click(refresh_jobs_only, None, [jobs_dd])

    # Generate with ALL parameters
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
            movement_req, transition_req, sensory_coupling, downshift_required, pov_second_person,
            destination_arc, arrival_start, settlement_beats, closure_required, archetype,
            coach_on
        ],
        outputs=[status, story, metrics, schema],
        concurrency_id="generate", concurrency_limit=1
    )

    attach_btn.click(
        attach_and_stream,
        inputs=[jobs_dd],
        outputs=[status, story, metrics, schema],
        concurrency_id="attach", concurrency_limit=2
    )

if __name__ == "__main__":
    demo.queue().launch(server_name="0.0.0.0", server_port=7860, show_error=True)
