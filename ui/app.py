"""Sleep Stories AI - Enhanced Frontend v2.0

Disable inputs during generation and re-enable on completion using .then().
"""

import gradio as gr
import os
import sys
import threading
import time
import logging
from typing import Tuple

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.api_client import SleepStoriesAPIClient
from components.generation_panel import (
    create_basic_settings, create_model_settings, create_quality_settings,
    create_advanced_settings, create_generation_controls
)
from components.monitoring_panel import (
    create_job_management, create_status_display, create_system_info,
    create_progress_indicators, create_job_history, update_progress_indicators
)
from components.results_panel import (
    create_results_tabs, create_download_section
)
from utils.helpers import (
    format_job_status, validate_generation_params,
    create_job_choices_update, format_error_message, format_success_message
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
api_client = SleepStoriesAPIClient()


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

        inputs_all = [theme, description, duration, preset, use_custom, gen_dd, rsn_dd, pol_dd, use_rsn, use_pol, tts, strict_schema, sensory_rotation, sleep_taper, model_temp, coach_enabled, movement_verbs, transition_tokens, sensory_coupling, pov_2p, destination_arc, arrival_start, settlement_beats, archetype]

        def disable_inputs():
            return [gr.update(interactive=False) for _ in inputs_all]
        def enable_inputs():
            return [gr.update(interactive=True) for _ in inputs_all]

        def start_generation_wrapper(*args):
            # Here you would call the actual generation function; we emit status only in this stub
            return "⏳ Generating...", "", {}, "", {}, 0,0,0, "-","-","-","-", 0, "0 minutes", False, {}, {}, 0,0, "", 0,0, 0, False, 0, "0:00"

        generation_outputs = [status_display, story_output, generation_metrics, story_outline, beats_schema, overall_progress, current_beat, total_beats, beat_stage, elapsed_time, eta_time, current_model, word_count, estimated_duration, tts_ready, coherence_stats, memory_stats, sensory_score, coherence_score, flow_score, beats_count, transitions_count, sensory_rotations, schema_valid, total_segments, total_duration]

        # Disable inputs on click, run generation, then re-enable
        generate_chain = generate_btn.click(fn=lambda: None, inputs=None, outputs=None)
        generate_chain.then(fn=disable_inputs, inputs=None, outputs=inputs_all)
        generate_chain.then(fn=start_generation_wrapper, inputs=inputs_all, outputs=generation_outputs)
        generate_chain.then(fn=enable_inputs, inputs=None, outputs=inputs_all)

        # Basic refresh hooks (no change to interactivity)
        refresh_models_btn.click(fn=lambda: None, inputs=None, outputs=None)
        refresh_jobs_btn.click(fn=lambda _: gr.update(), inputs=[show_completed], outputs=[active_jobs_dd])
        refresh_system_btn.click(fn=lambda: api_client.get_generation_stats(), inputs=None, outputs=[system_status])
        health_check_btn.click(fn=lambda: api_client.get_health(), inputs=None, outputs=[system_status])

    return demo

if __name__ == "__main__":
    logger.info("Starting Sleep Stories AI - Enhanced Frontend v2.0 (Interactivity patch)")
    demo = create_interface()
    demo.queue(default_concurrency_limit=1, max_size=20, status_update_rate="auto")
    demo.launch(server_name="0.0.0.0", server_port=7860, show_error=True, debug=False, max_threads=40, show_tips=False, quiet=False)
