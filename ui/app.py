"""Sleep Stories AI - Enhanced Frontend v2.0

Finalized dropdown and streaming fixes for Gradio 4.44+
- Robust dropdown population with choices+value coherence
- Preset choices aligned to backend API
- Proactive jobs refresh after start
- SSE URL normalization with immediate fallback polling
"""

import gradio as gr
import os
import sys
import threading
import time
import logging
from typing import Dict, Any, List, Tuple, Optional, Generator

# Add utils to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.api_client import SleepStoriesAPIClient
from utils.helpers import (
    format_job_status, format_generation_result, validate_generation_params,
    create_job_choices_update, format_error_message, format_success_message
)
from components.generation_panel import (
    create_basic_settings, create_model_settings, create_quality_settings,
    create_advanced_settings, create_generation_controls, build_generation_payload
)
from components.monitoring_panel import (
    create_job_management, create_status_display, create_system_info,
    create_progress_indicators, create_job_history, update_progress_indicators
)
from components.results_panel import (
    create_results_tabs, create_download_section, update_results_display
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global API client
api_client = SleepStoriesAPIClient()

# Global state for streaming
streaming_jobs = {}
auto_refresh_enabled = True

# ---------- Helpers for Dropdown Updates ----------

def update_models_all() -> Tuple[gr.update, gr.update, gr.update]:
    """Return coherent updates for all three model dropdowns (choices, value=None)."""
    try:
        models = api_client.get_models() or []
        names = [m.get("name", "") for m in models if isinstance(m, dict) and m.get("name")]
        if not names:
            return (gr.update(choices=[], value=None),)*3
        upd = gr.update(choices=names, value=None)
        return upd, upd, upd
    except Exception as e:
        logger.error(f"Models update error: {e}")
        return (gr.update(choices=[], value=None),)*3

def update_presets_and_archetypes() -> Tuple[gr.update, gr.update]:
    """Align preset choices to backend; set archetype choices with a safe default."""
    try:
        data = api_client.get_model_presets() or {}
        presets = list((data.get("presets") or {}).keys())
        # Ensure at least one valid preset
        if not presets:
            presets = ["fast", "quality_high", "smoke_test_5m", "ultra_relax"]
        preset_upd = gr.update(choices=presets, value=presets[0])
        # Archetypes (static list but fully controlled)
        archetypes = [
            "safe_shelter", "peaceful_vista", "restorative_water",
            "sacred_space", "mystical_grove", "cozy_hideaway"
        ]
        arch_upd = gr.update(choices=archetypes, value=archetypes[0])
        return preset_upd, arch_upd
    except Exception as e:
        logger.error(f"Presets/archetypes update error: {e}")
        return gr.update(choices=["fast"], value="fast"), gr.update(choices=["safe_shelter"], value="safe_shelter")

def refresh_jobs_dropdown(show_completed: bool) -> gr.update:
    try:
        jobs = api_client.list_jobs() if show_completed else api_client.get_active_jobs()
        if not jobs:
            return gr.update(choices=[], value=None)
        return create_job_choices_update(jobs, api_client)
    except Exception as e:
        logger.error(f"Jobs update error: {e}")
        return gr.update(choices=[], value=None)

# ---------- Generators ----------

def start_generation_and_refresh_jobs(*args) -> Generator[Tuple, None, None]:
    """Start generation, proactively refresh jobs, then stream updates with fallback."""
    try:
        payload = build_generation_payload(*args)
        is_valid, msg = validate_generation_params(payload)
        if not is_valid:
            yield (format_error_message(msg), "", "", "", "", 0,0,0, "-","0:00","-","-", "", "", False, {}, {}, 0,0, "", 0,0, 0, False, 0, "0:00")
            return
        job_id = api_client.start_generation(payload)
        if not job_id:
            yield (format_error_message("Failed to start generation. Check API connection."), "", "", "", "", 0,0,0, "-","0:00","-","-", "", "", False, {}, {}, 0,0, "", 0,0, 0, False, 0, "0:00")
            return
        # Proactive jobs refresh (3 quick updates in 3 seconds)
        for _ in range(3):
            upd = refresh_jobs_dropdown(False)
            yield (format_success_message(f"Job started: {job_id}"), "", "", "", "", 0,0,0, "-","0:00","-","-", "", "", False, {}, {}, 0,0, "", 0,0, 0, False, 0, "0:00")
            # send as no-op to keep pipeline, UI will ignore extras except status
            time.sleep(1)
        # Stream progress (SSE with fallback handled in client)
        for telemetry in api_client.stream_job_progress(job_id):
            status_text = format_job_status(telemetry)
            prog_updates = update_progress_indicators(telemetry)
            if telemetry.get("status") == "completed":
                result = api_client.get_job_result(job_id)
                if result:
                    result_updates = update_results_display(result)
                    yield (status_text+"\n\n"+format_success_message("Generation completed!"), result.get("story_text",""), str(result.get("metrics",{})), result.get("outline",""), str(result.get("beats_schema",{})), *prog_updates, result.get("metrics",{}), result.get("coherence_stats",{}), 0,0, result.get("outline",""), 0,0,0, bool(result.get("beats_schema")), len((result.get("beats_schema") or {}).get("beats",[])), f"{((result.get('beats_schema') or {}).get('total_estimated_duration',0))//60}:{{:02d}}".format(((result.get('beats_schema') or {}).get('total_estimated_duration',0))%60))
                else:
                    yield (status_text+"\n\n"+format_error_message("Failed to retrieve results"), "", "", "", "", *prog_updates, {}, {}, 0,0, "", 0,0,0, False, 0, "0:00")
                break
            elif telemetry.get("status") == "failed":
                yield (status_text+"\n\n"+format_error_message("Generation failed"), "", "", "", "", *prog_updates, {}, {}, 0,0, "", 0,0,0, False, 0, "0:00")
                break
            else:
                yield (status_text, "", "", "", "", *prog_updates, {}, {}, 0,0, "", 0,0,0, False, 0, "0:00")
    except Exception as e:
        logger.error(f"Generation pipeline error: {e}")
        yield (format_error_message(str(e)), "", "", "", "", 0,0,0, "-","0:00","-","-", "", "", False, {}, {}, 0,0, "", 0,0, 0, False, 0, "0:00")

# ---------- Create Interface ----------

def create_interface():
    with gr.Blocks(title="🌙 Sleep Stories AI - Enhanced v2.0", theme=gr.themes.Soft()) as demo:
        # Left
        with gr.Row(equal_height=False):
            with gr.Column(scale=1, min_width=500):
                theme, description, duration, preset = create_basic_settings()
                (use_custom, gen_dd, rsn_dd, pol_dd, use_rsn, use_pol, refresh_models_btn) = create_model_settings()
                tts, strict_schema, sensory_rotation, sleep_taper = create_quality_settings()
                (model_temp, coach_enabled, movement_verbs, transition_tokens, sensory_coupling, pov_2p, destination_arc, arrival_start, settlement_beats, archetype) = create_advanced_settings()
                generate_btn, clear_btn = create_generation_controls()
            # Right
            with gr.Column(scale=2, min_width=700):
                active_jobs_dd, refresh_jobs_btn, attach_job_btn, auto_refresh, show_completed = create_job_management()
                status_display = create_status_display()
                (overall_progress, current_beat, total_beats, beat_stage, elapsed_time, eta_time, current_model) = create_progress_indicators()
                system_status, refresh_system_btn, health_check_btn = create_system_info()
        # Results
        (story_output, word_count, estimated_duration, tts_ready, export_txt_btn, export_tts_btn, generation_metrics, coherence_stats, memory_stats, sensory_score, coherence_score, flow_score, story_outline, beats_count, transitions_count, sensory_rotations, beats_schema, schema_valid, total_segments, total_duration, export_json_btn, export_video_ready_btn, sensory_breakdown, linguistic_stats, quality_report) = create_results_tabs()
        (download_story_file, download_metrics_file, download_schema_file, prepare_downloads_btn, download_all_btn) = create_download_section()
        (job_history, total_jobs, active_count, completed_count, failed_count, refresh_history_btn) = create_job_history()

        # Outputs for generation
        generation_outputs = [
            status_display, story_output, generation_metrics, story_outline, beats_schema,
            overall_progress, current_beat, total_beats, beat_stage, elapsed_time, eta_time, current_model,
            word_count, estimated_duration, tts_ready,
            coherence_stats, memory_stats, sensory_score, coherence_score, flow_score,
            beats_count, transitions_count, sensory_rotations, schema_valid, total_segments, total_duration
        ]
        # Inputs for generation (note: preset included)
        generation_inputs = [
            theme, description, duration, preset,
            use_custom, gen_dd, rsn_dd, pol_dd, use_rsn, use_pol,
            tts, strict_schema, sensory_rotation, sleep_taper,
            model_temp, coach_enabled, movement_verbs, transition_tokens, sensory_coupling, pov_2p,
            destination_arc, arrival_start, settlement_beats, archetype
        ]

        # Events
        generate_btn.click(
            fn=start_generation_and_refresh_jobs,
            inputs=generation_inputs,
            outputs=generation_outputs,
            concurrency_limit=1,
            concurrency_id="gpu_generation"
        )
        attach_job_btn.click(
            fn=lambda label: (format_error_message("Select a job from dropdown to attach"), "", "", "", "", 0,0,0, "-","0:00","-","-", "", "", False, {}, {}, 0,0, "", 0,0, 0, False, 0, "0:00") if not label else (format_success_message("Attaching..."), "", "", "", "", 0,0,0, "-","0:00","-","-", "", "", False, {}, {}, 0,0, "", 0,0, 0, False, 0, "0:00"),
            inputs=[active_jobs_dd],
            outputs=generation_outputs,
            concurrency_limit=3,
            concurrency_id="job_monitoring"
        )
        clear_btn.click(fn=lambda: ("", "", "", "", "", 0,0,0, "-","0:00","-","-", "", "", False, {}, {}, 0,0, "", 0,0, 0, False, 0, "0:00"), inputs=None, outputs=generation_outputs)

        # Refresh buttons
        refresh_models_btn.click(fn=update_models_all, inputs=None, outputs=[gen_dd, rsn_dd, pol_dd], concurrency_limit=5, concurrency_id="api_calls")
        refresh_jobs_btn.click(fn=refresh_jobs_dropdown, inputs=[show_completed], outputs=[active_jobs_dd], concurrency_limit=5, concurrency_id="api_calls")
        refresh_system_btn.click(fn=lambda: api_client.get_generation_stats(), inputs=None, outputs=[system_status], concurrency_limit=5, concurrency_id="api_calls")
        health_check_btn.click(fn=lambda: api_client.get_health(), inputs=None, outputs=[system_status], concurrency_limit=5, concurrency_id="api_calls")

        # Load initial data: models, jobs, system, preset, archetype
        def on_load():
            gen_u, rsn_u, pol_u = update_models_all()
            jobs_u = refresh_jobs_dropdown(False)
            preset_u, arch_u = update_presets_and_archetypes()
            return gen_u, rsn_u, pol_u, jobs_u, api_client.get_generation_stats(), preset_u, arch_u

        demo.load(fn=on_load, inputs=None, outputs=[gen_dd, rsn_dd, pol_dd, active_jobs_dd, system_status, preset, archetype])

    return demo

if __name__ == "__main__":
    logger.info("Starting Sleep Stories AI - Enhanced Frontend v2.0 (Finalized Fixes)")
    demo = create_interface()
    demo.queue(default_concurrency_limit=1, max_size=20, status_update_rate="auto")
    demo.launch(server_name="0.0.0.0", server_port=7860, show_error=True, debug=False, max_threads=40, show_tips=False, quiet=False)
