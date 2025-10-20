import os
import json
import time
import requests
import gradio as gr
from typing import Optional, Dict, Any, List

API_URL = os.getenv("API_URL", "http://backend:8000/api")

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

def load_ollama_models() -> List[str]:
    data = get_json("/models/ollama", timeout=6) or []
    return sorted([m.get("name") for m in data if isinstance(m, dict) and m.get("name")])

def load_presets() -> Dict[str, Dict[str, Any]]:
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

def build_payload(theme, description, duration,
                  use_reasoner, use_polish,
                  tts_markers, strict_schema,
                  sensory_rotation, sleep_taper, rotation,
                  generator_model, reasoner_model, polisher_model,
                  temp_gen, temp_rsn, temp_pol,
                  beats, words_per_beat, tolerance,
                  taper_start_pct, taper_reduction,
                  custom_waypoints_text,
                  tts_pause_min, tts_pause_max, tts_breathe_frequency,
                  movement_verbs_required, transition_tokens_required,
                  sensory_coupling, downshift_required, pov_enforce_second_person,
                  destination_promise_beat, arrival_signals_start, settlement_beats,
                  closure_required, destination_archetype,
                  enable_spatial_coach, spatial_coach_model, spatial_coach_temperature, spatial_coach_max_tokens,
                  opener_penalty_threshold, transition_penalty_weight, redundancy_penalty_weight,
                  beat_planning_enabled, beat_length_tolerance,
                  max_concurrent_models, model_unload_delay, max_retries,
                  retry_delay, fallback_model
                  ) -> Dict[str, Any]:
    models = {}
    if generator_model: models["generator"] = generator_model
    if reasoner_model:  models["reasoner"]  = reasoner_model
    if polisher_model:  models["polisher"]  = polisher_model
    custom_waypoints = None
    if custom_waypoints_text and custom_waypoints_text.strip():
        custom_waypoints = [w.strip() for w in custom_waypoints_text.splitlines() if w.strip()]
    payload: Dict[str, Any] = {
        "theme": theme,
        "duration": int(duration),
        "description": description or None,
        "models": models or None,
        "use_reasoner": bool(use_reasoner),
        "use_polish": bool(use_polish),
        "tts_markers": bool(tts_markers),
        "strict_schema": bool(strict_schema),
        "rotation": bool(rotation) if rotation is not None else None,
        "taper": {
            "start_pct": float(taper_start_pct),
            "reduction": float(taper_reduction),
        },
        "temps": {
            "generator": float(temp_gen),
            "reasoner": float(temp_rsn),
            "polisher": float(temp_pol),
        },
        "beats": int(beats) if beats else None,
        "words_per_beat": int(words_per_beat) if words_per_beat else None,
        "tolerance": float(tolerance) if tolerance else None,
        "custom_waypoints": custom_waypoints,
        "movement_verbs_required": int(movement_verbs_required),
        "transition_tokens_required": int(transition_tokens_required),
        "sensory_coupling": int(sensory_coupling),
        "downshift_required": bool(downshift_required),
        "pov_enforce_second_person": bool(pov_enforce_second_person),
        "closure_required": bool(closure_required),
        "tts_optimized": bool(tts_markers),
    }
    clean_payload = {k: v for k, v in payload.items() if v is not None}
    return clean_payload

def progress_bar(pct, color="#3b82f6"):
    pct = max(0, min(100, float(pct)))
    return f"<div style='background:#f1f5f9;border-radius:8px;overflow:hidden;height:14px;width:100%;border:1px solid #e2e8f0'><div style='height:14px;width:{pct}%;background:{color};transition:width 0.25s ease'></div></div>"

def render_params_html(params: Dict[str, Any]) -> str:
    if not params: return ""
    keys = [
        ("POV 2nd person", 'pov_enforce_second_person'),
        ("Movement verbs", 'movement_verbs_required'),
        ("Transitions", 'transition_tokens_required'),
        ("Sensory coupling", 'sensory_coupling'),
        ("Downshift req.", 'downshift_required'),
        ("Beats", 'beats_target'),
        ("Words/beat", 'words_per_beat'),
        ("Taper start", 'taper_start_pct'),
        ("Taper reduction", 'taper_reduction'),
        ("Rotation", 'sensory_rotation_enabled'),
        ("Temp gen", ('temps','generator')),
        ("Temp rsn", ('temps','reasoner')),
        ("Temp pol", ('temps','polisher')),
    ]
    rows = []
    for label, key in keys:
        val = None
        if isinstance(key, tuple):
            top, sub = key
            if isinstance(params.get(top), dict):
                val = params.get(top).get(sub)
        else:
            val = params.get(key)
        if val is not None:
            rows.append(f"<div style='display:flex;justify-content:space-between'><span>{label}</span><b>{val}</b></div>")
    if not rows: return ""
    return "<div style=\"background:white;border:1px solid #e5e7eb;border-radius:12px;padding:12px;margin-top:12px\"><div style=\"font-weight:700;margin-bottom:6px;color:#374151;border-bottom:2px solid #f3f4f6;padding-bottom:4px\">⚙️ Parameters</div>" + "\n".join(rows) + "</div>"

def render_status_html(ev: Dict[str, Any]) -> str:
    status = ev.get("status", "processing")
    status_upper = status.upper()
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
    timing = ev.get("timing", {}) or {}
    params = ev.get("generation_params", {}) or {}
    if status == "completed": color = "#16a34a"; icon = "✅"; pb_main_html = progress_bar(100, "#16a34a")
    elif status == "failed": color = "#dc2626"; icon = "❌"; pb_main_html = progress_bar(progress, "#dc2626")
    else: color = "#0ea5e9"; icon = "🚀"; pb_main_html = progress_bar(progress, color)
    gen = models.get("generator", "") or "—"
    rsn = models.get("reasoner", "") or "—"
    pol = models.get("polisher", "") or "—"
    tgen = temps.get("generator"); trsn = temps.get("reasoner"); tpol = temps.get("polisher")
    gen_temp_html = f"<span style='color:#3b82f6'>({tgen})</span>" if tgen is not None else ""
    rsn_temp_html = f"<span style='color:#3b82f6'>({trsn})</span>" if trsn is not None else ""
    pol_temp_html = f"<span style='color:#3b82f6'>({tpol})</span>" if tpol is not None else ""
    elapsed = int((timing or {}).get("elapsed_sec") or 0)
    eta = (timing or {}).get("eta_sec")
    elapsed_str = f"{elapsed//60}m {elapsed%60}s" if elapsed else "0s"
    eta_str = f"{int(eta)//60}m {int(eta)%60}s" if eta else "—"
    beat_section = "<div style='color:#6b7280;text-align:center;font-style:italic'>Beat info not available yet</div>"
    if bt > 0:
        beat_pct = (bi/max(bt,1))*100
        beat_section = f"<div style='margin-bottom:12px'><div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:6px'><span style='font-weight:700;color:#374151'>Overall Beat Progress</span><span style='background:#22c55e;color:white;padding:4px 8px;border-radius:12px;font-weight:700'>{bi}/{bt}</span></div>{progress_bar(beat_pct, '#22c55e')}<div style='text-align:right;color:#22c55e;font-weight:600;margin-top:4px'>{beat_pct:.1f}%</div></div>"
        if bstage:
            beat_section += f"<div><div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:6px'><span style='font-weight:700;color:#374151'>Current Stage: {bstage.upper()}</span><span style='background:#3b82f6;color:white;padding:4px 8px;border-radius:12px;font-weight:700'>{bstage_prog}%</span></div>{progress_bar(bstage_prog, '#3b82f6')}</div>"
    html = f"""
    <div style=\"border:2px solid {color};border-radius:16px;padding:20px;margin:8px 0;background:linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)\">
        <div style=\"background:white;border:2px solid {color};border-radius:12px;padding:16px;margin-bottom:16px\">
            <div style=\"display:flex;justify-content:space-between;align-items:center;margin-bottom:12px\">
                <div style=\"font-size:20px;font-weight:800;color:{color}\">{icon} {status_upper}</div>
                <div style=\"background:{color};color:white;padding:6px 12px;border-radius:20px;font-weight:700\">STEP {step_num}/{total_steps}</div>
            </div>
            <div style=\"font-size:16px;margin-bottom:10px;color:#111827;font-weight:600\">{step}</div>
            {pb_main}
            <div style=\"text-align:right;color:{color};font-weight:700;margin-top:6px\">{progress:.1f}%</div>
        </div>
        <div style=\"background:white;border:2px solid #22c55e;border-radius:12px;padding:16px;margin-bottom:16px\">
            <div style=\"font-size:16px;font-weight:800;color:#22c55e;margin-bottom:10px;text-align:center\">📊 BEAT TRACKER</div>
            {beat_section}
        </div>
        <div style=\"display:grid;grid-template-columns:1fr 1fr;gap:12px\">
            <div style=\"background:white;border:1px solid #e5e7eb;border-radius:12px;padding:12px\">
                <div style=\"font-weight:700;margin-bottom:8px;color:#374151;border-bottom:2px solid #f3f4f6;padding-bottom:4px\">🤖 Models & Temps</div>
                <div style=\"font-size:13px;line-height:1.5\">
                    <div>Gen: <span style=\"color:#111827;font-weight:600\">{gen}</span> {gen_temp}</div>
                    <div>Rsn: <span style=\"color:#111827;font-weight:600\">{rsn}</span> {rsn_temp}</div>
                    <div>Pol: <span style=\"color:#111827;font-weight:600\">{pol}</span> {pol_temp}</div>
                </div>
            </div>
            <div style=\"background:white;border:1px solid #e5e7eb;border-radius:12px;padding:12px\">
                <div style=\"font-weight:700;margin-bottom:8px;color:#374151;border-bottom:2px solid #f3f4f6;padding-bottom:4px\">⏱️ Timing</div>
                <div style=\"font-size:13px;line-height:1.5\">
                    <div>Elapsed: <span style=\"color:#111827;font-weight:600\">{elapsed_str}</span></div>
                    <div>ETA: <span style=\"color:#111827;font-weight:600\">{eta_str}</span></div>
                </div>
            </div>
        </div>
        {params_box}
    </div>
    """
    html = html.replace("{pb_main}", pb_main_html)
    html = html.replace("{beat_section}", beat_section)
    html = html.replace("{gen_temp}", gen_temp_html)
    html = html.replace("{rsn_temp}", rsn_temp_html)
    html = html.replace("{pol_temp}", pol_temp_html)
    html = html.replace("{params_box}", render_params_html(params))
    return html
# (rest unchanged)
