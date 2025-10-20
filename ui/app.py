"""Sleep Stories AI - Enhanced Frontend v2.0

Restore run loop and auto-refresh worker; keep finalized fixes.
"""

import gradio as gr
import os
import sys
import threading
import time
import logging
from typing import Dict, Any, List, Tuple, Optional, Generator

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.api_client import SleepStoriesAPIClient
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
from utils.helpers import (
    format_job_status, validate_generation_params,
    create_job_choices_update, format_error_message, format_success_message
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
api_client = SleepStoriesAPIClient()

# Auto-refresh job list worker
_auto_refresh = True


def auto_refresh_jobs(active_jobs_dd, show_completed):
    while _auto_refresh:
        try:
            jobs = api_client.list_jobs() if show_completed.value else api_client.get_active_jobs()
            update = create_job_choices_update(jobs, api_client) if jobs else gr.update(choices=[], value=None)
            active_jobs_dd.update(**update)
        except Exception:
            pass
        time.sleep(10)


def create_interface():
    with gr.Blocks(title="🌙 Sleep Stories AI - Enhanced v2.0", theme=gr.themes.Soft()) as demo:
        with gr.Row(equal_height=False):
            with gr.Column(scale=1, min_width=500):
                theme, description, duration, preset = create_basic_settings()
                (use_custom, gen_dd, rsn_dd, pol_dd, use_rsn, use_pol, refresh_models_btn) = create_model_settings()
                tts, strict_schema, sensory_rotation, sleep_taper = create_quality_settings()
                (model_temp, coach_enabled, movement_verbs, transition_tokens, sensory_coupling, pov_2p, destination_arc, arrival_start, settlement_beats, archetype) = create_advanced_settings()
                generate_btn, clear_btn = create_generation_controls()
            with gr.Column(scale=2, min_width=700):
                active_jobs_dd, refresh_jobs_btn, attach_job_btn, auto_refresh_cb, show_completed = create_job_management()
                status_display = create_status_display()
                (overall_progress, current_beat, total_beats, beat_stage, elapsed_time, eta_time, current_model) = create_progress_indicators()
                system_status, refresh_system_btn, health_check_btn = create_system_info()
        (story_output, word_count, estimated_duration, tts_ready, export_txt_btn, export_tts_btn, generation_metrics, coherence_stats, memory_stats, sensory_score, coherence_score, flow_score, story_outline, beats_count, transitions_count, sensory_rotations, beats_schema, schema_valid, total_segments, total_duration, export_json_btn, export_video_ready_btn, sensory_breakdown, linguistic_stats, quality_report) = create_results_tabs()
        (download_story_file, download_metrics_file, download_schema_file, prepare_downloads_btn, download_all_btn) = create_download_section()
        (job_history, total_jobs, active_count, completed_count, failed_count, refresh_history_btn) = create_job_history()

        # Initial population handlers
        def populate_on_load():
            # Models
            model_list = [m.get("name") for m in (api_client.get_models() or []) if isinstance(m, dict) and m.get("name")]
            mu = gr.update(choices=model_list, value=None)
            # Jobs
            jobs = api_client.get_active_jobs()
            ju = create_job_choices_update(jobs, api_client) if jobs else gr.update(choices=[], value=None)
            # System
            sysinfo = api_client.get_generation_stats()
            # Presets & archetypes
            presets_data = api_client.get_model_presets() or {}
            preset_keys = list((presets_data.get("presets") or {}).keys()) or ["fast", "quality_high"]
            pu = gr.update(choices=preset_keys, value=preset_keys[0])
            arch = ["safe_shelter", "peaceful_vista", "restorative_water", "sacred_space", "mystical_grove", "cozy_hideaway"]
            au = gr.update(choices=arch, value=arch[0])
            return mu, mu, mu, ju, sysinfo, pu, au

        demo.load(fn=populate_on_load, inputs=None, outputs=[gen_dd, rsn_dd, pol_dd, active_jobs_dd, system_status, preset, archetype])

        # Start background auto-refresh thread on UI load
        def start_bg_refresh():
            t = threading.Thread(target=auto_refresh_jobs, args=(active_jobs_dd, show_completed), daemon=True)
            t.start()
        demo.load(fn=start_bg_refresh, inputs=None, outputs=None)

    return demo

if __name__ == "__main__":
    logger.info("Starting Sleep Stories AI - Enhanced Frontend v2.0 (Restored run)")
    demo = create_interface()
    demo.queue(default_concurrency_limit=1, max_size=20, status_update_rate="auto")
    demo.launch(server_name="0.0.0.0", server_port=7860, show_error=True, debug=False, max_threads=40, show_tips=False, quiet=False)
