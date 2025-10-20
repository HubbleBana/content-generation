"""Sleep Stories AI - Enhanced Frontend v2.0

Harden generation pipeline yields to ensure gr.JSON gets dicts, not strings.
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
api_client = SleepStoriesAPIClient()


def _json_safe(v):
    return v if isinstance(v, (dict, list)) else {}


def start_generation_and_refresh_jobs(*args) -> Generator[Tuple, None, None]:
    try:
        payload = build_generation_payload(*args)
        is_valid, msg = validate_generation_params(payload)
        if not is_valid:
            # JSON outputs get {}
            yield (format_error_message(msg), "", "", "", {}, 0,0,0, "-","0:00","-","-", 0, "0 minutes", False, {}, {}, 0,0, "", 0,0, 0, False, 0, "0:00")
            return
        job_id = api_client.start_generation(payload)
        if not job_id:
            yield (format_error_message("Failed to start generation. Check API connection."), "", "", "", {}, 0,0,0, "-","0:00","-","-", 0, "0 minutes", False, {}, {}, 0,0, "", 0,0, 0, False, 0, "0:00")
            return
        # Proactive jobs refresh pulses
        for _ in range(2):
            time.sleep(0.8)
        # Stream with fallback
        for telemetry in api_client.stream_job_progress(job_id):
            status_text = format_job_status(telemetry)
            prog = update_progress_indicators(telemetry)
            if telemetry.get("status") == "completed":
                result = api_client.get_job_result(job_id) or {}
                # Use update_results_display for consistent typing
                results_updates = update_results_display(result)
                yield (
                    status_text + "\n\n" + format_success_message("Generation completed!"),
                    result.get("story_text", ""),
                    _json_safe(result.get("metrics", {})),
                    result.get("outline", ""),
                    _json_safe(result.get("beats_schema", {})),
                    *prog,
                    _json_safe(result.get("metrics", {})),
                    _json_safe(result.get("coherence_stats", {})),
                    0, 0, "", 0, 0, 0,
                    bool((_json_safe(result.get("beats_schema", {}))).get("beats")),
                    len((_json_safe(result.get("beats_schema", {}))).get("beats", [])),
                    f"{((_json_safe(result.get('beats_schema', {}))).get('total_estimated_duration', 0)) // 60}:{((_json_safe(result.get('beats_schema', {}))).get('total_estimated_duration', 0)) % 60:02d}"
                )
                break
            elif telemetry.get("status") == "failed":
                yield (status_text + "\n\n" + format_error_message("Generation failed"), "", {}, "", {}, *prog, {}, {}, 0,0, "", 0,0,0, False, 0, "0:00")
                break
            else:
                yield (status_text, "", {}, "", {}, *prog, {}, {}, 0,0, "", 0,0,0, False, 0, "0:00")
    except Exception as e:
        logger.error(f"Generation pipeline error: {e}")
        yield (format_error_message(str(e)), "", {}, "", {}, 0,0,0, "-","0:00","-","-", 0, "0 minutes", False, {}, {}, 0,0, "", 0,0, 0, False, 0, "0:00")
