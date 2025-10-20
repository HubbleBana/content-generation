"""Sleep Stories AI - Enhanced Frontend v2.0

Completely rewritten frontend with real-time streaming, enhanced UI,
and comprehensive parameter control for the Sleep Stories AI system.

By Jimmy - Frontend Expert
Updated for Gradio 4.44+ compatibility and fixed dropdown population
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
    create_model_choices_update, create_job_choices_update, create_status_update,
    create_result_updates, format_error_message, format_success_message
)
from components.generation_panel import (
    create_basic_settings, create_model_settings, create_quality_settings,
    create_advanced_settings, create_generation_controls, build_generation_payload
)
from components.monitoring_panel import (
    create_job_management, create_status_display, create_system_info,
    create_progress_indicators, create_job_history, update_progress_indicators,
    format_job_history_data, update_job_statistics
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

def load_custom_css() -> str:
    """Load custom CSS styling."""
    css_path = os.path.join(os.path.dirname(__file__), "static", "custom.css")
    if os.path.exists(css_path):
        with open(css_path, "r") as f:
            return f.read()
    return ""

def refresh_all_models() -> Tuple[gr.update, gr.update, gr.update]:
    """Refresh ALL model dropdowns (generator, reasoner, polisher)."""
    try:
        models = api_client.get_models()
        choices = [model.get("name", "") for model in models if isinstance(model, dict)]
        
        if not choices:
            # If no models found, add a message
            choices = ["⚠️ No models found - check Ollama connection"]
            logger.warning("No models found from Ollama API")
        else:
            logger.info(f"Found {len(choices)} models: {choices[:3]}{'...' if len(choices) > 3 else ''}")
        
        # Return updates for all three dropdowns
        update = gr.update(choices=choices, value=choices[0] if choices and not choices[0].startswith("⚠️") else None)
        return update, update, update
        
    except Exception as e:
        logger.error(f"Failed to refresh models: {e}")
        error_choice = [f"❌ API Error: {str(e)[:50]}..."]
        error_update = gr.update(choices=error_choice, value=None)
        return error_update, error_update, error_update

def refresh_jobs(show_completed: bool = False) -> gr.update:
    """Refresh active jobs from API."""
    try:
        if show_completed:
            jobs = api_client.list_jobs()
        else:
            jobs = api_client.get_active_jobs()
        
        if not jobs:
            return gr.update(choices=["📭 No active jobs found"], value=None)
        
        choices = [api_client.format_job_label(job) for job in jobs]
        logger.info(f"Found {len(jobs)} jobs")
        return gr.update(choices=choices, value=None)
        
    except Exception as e:
        logger.error(f"Failed to refresh jobs: {e}")
        return gr.update(choices=[f"❌ API Error: {str(e)[:50]}..."], value=None)

def get_model_presets_and_defaults() -> Tuple[gr.update, List[str]]:
    """Get model presets and return archetype choices."""
    try:
        presets = api_client.get_model_presets()
        logger.info(f"Retrieved model presets: {list(presets.get('presets', {}).keys())}")
        
        # Standard archetype choices (these are hardcoded in the backend)
        archetype_choices = [
            "safe_shelter",
            "peaceful_vista", 
            "restorative_water",
            "sacred_space",
            "mystical_grove",
            "cozy_hideaway"
        ]
        
        # Update preset dropdown
        preset_choices = ["quality_high", "balanced", "fast", "custom"]
        if presets.get("presets"):
            preset_choices = list(presets["presets"].keys()) + ["custom"]
        
        return gr.update(choices=preset_choices, value="balanced"), archetype_choices
        
    except Exception as e:
        logger.error(f"Failed to get presets: {e}")
        # Return defaults if API fails
        return gr.update(choices=["balanced", "fast", "custom"], value="balanced"), [
            "safe_shelter", "peaceful_vista", "restorative_water", "sacred_space"
        ]

def get_system_info() -> Dict[str, Any]:
    """Get system information and statistics."""
    try:
        stats = api_client.get_generation_stats()
        logger.info("Retrieved system statistics")
        return stats
    except Exception as e:
        logger.error(f"Failed to get system info: {e}")
        return {"error": str(e), "status": "API connection failed"}

def start_generation(*args) -> Generator[Tuple, None, None]:
    """Start story generation with real-time streaming."""
    try:
        # Build payload from UI inputs
        payload = build_generation_payload(*args)
        
        # Validate parameters
        is_valid, validation_message = validate_generation_params(payload)
        if not is_valid:
            yield (
                format_error_message(validation_message),
                "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""
            )
            return
        
        # Start generation
        job_id = api_client.start_generation(payload)
        if not job_id:
            yield (
                format_error_message("Failed to start generation. Check API connection."),
                "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""
            )
            return
        
        # Store job for potential cleanup
        streaming_jobs[job_id] = True
        
        # Stream progress
        for telemetry in api_client.stream_job_progress(job_id):
            if job_id not in streaming_jobs:
                break  # Job was cancelled
            
            # Format status display
            status_text = format_job_status(telemetry)
            
            # Update progress indicators
            progress_updates = update_progress_indicators(telemetry)
            
            # Check if completed
            if telemetry.get("status") == "completed":
                try:
                    result = api_client.get_job_result(job_id)
                    if result:
                        story_text, metrics_text, outline, schema_text = format_generation_result(result)
                        result_updates = update_results_display(result)
                        
                        success_status = status_text + "\n\n" + format_success_message("Generation completed successfully!")
                        
                        yield (
                            success_status,
                            story_text,
                            metrics_text,
                            outline,
                            schema_text,
                            *progress_updates,
                            *result_updates[4:],  # Skip first 4 which are story, metrics, outline, schema
                        )
                    else:
                        yield (
                            status_text + "\n\n" + format_error_message("Failed to retrieve results"),
                            "", "", "", "", *progress_updates, "", "", "", "", "", "", "", "", "", "", "", "", "", ""
                        )
                except Exception as e:
                    logger.error(f"Failed to get results: {e}")
                    yield (
                        status_text + "\n\n" + format_error_message(f"Results error: {e}"),
                        "", "", "", "", *progress_updates, "", "", "", "", "", "", "", "", "", "", "", "", "", ""
                    )
                break
                
            elif telemetry.get("status") == "failed":
                error_msg = telemetry.get("error", "Unknown error")
                yield (
                    status_text + "\n\n" + format_error_message(f"Generation failed: {error_msg}"),
                    "", "", "", "", *progress_updates, "", "", "", "", "", "", "", "", "", "", "", "", "", ""
                )
                break
            else:
                # In progress
                yield (
                    status_text,
                    "", "", "", "", *progress_updates, "", "", "", "", "", "", "", "", "", "", "", "", "", ""
                )
        
        # Cleanup
        if job_id in streaming_jobs:
            del streaming_jobs[job_id]
            
    except Exception as e:
        logger.error(f"Generation error: {e}")
        yield (
            format_error_message(f"Generation error: {e}"),
            "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""
        )

def attach_to_job(job_label: str) -> Generator[Tuple, None, None]:
    """Attach to existing job for monitoring."""
    try:
        if not job_label or job_label.startswith(("📭", "❌")):
            yield (
                format_error_message("Please select a valid job to attach to"),
                "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""
            )
            return
        
        job_id = api_client.parse_job_id_from_label(job_label)
        if not job_id:
            yield (
                format_error_message("Unable to parse job ID from selection"),
                "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""
            )
            return
        
        # Store job for potential cleanup
        streaming_jobs[job_id] = True
        
        # Stream progress
        for telemetry in api_client.stream_job_progress(job_id):
            if job_id not in streaming_jobs:
                break  # Job was cancelled
            
            # Format status display
            status_text = f"🔗 ATTACHED TO JOB: {job_id}\n\n" + format_job_status(telemetry)
            
            # Update progress indicators
            progress_updates = update_progress_indicators(telemetry)
            
            # Check if completed
            if telemetry.get("status") == "completed":
                try:
                    result = api_client.get_job_result(job_id)
                    if result:
                        story_text, metrics_text, outline, schema_text = format_generation_result(result)
                        result_updates = update_results_display(result)
                        
                        success_status = status_text + "\n\n" + format_success_message("Job completed successfully!")
                        
                        yield (
                            success_status,
                            story_text,
                            metrics_text,
                            outline,
                            schema_text,
                            *progress_updates,
                            *result_updates[4:],
                        )
                    else:
                        yield (
                            status_text + "\n\n" + format_error_message("Failed to retrieve results"),
                            "", "", "", "", *progress_updates, "", "", "", "", "", "", "", "", "", "", "", "", "", ""
                        )
                except Exception as e:
                    yield (
                        status_text + "\n\n" + format_error_message(f"Results error: {e}"),
                        "", "", "", "", *progress_updates, "", "", "", "", "", "", "", "", "", "", "", "", "", ""
                    )
                break
                
            elif telemetry.get("status") == "failed":
                error_msg = telemetry.get("error", "Unknown error")
                yield (
                    status_text + "\n\n" + format_error_message(f"Job failed: {error_msg}"),
                    "", "", "", "", *progress_updates, "", "", "", "", "", "", "", "", "", "", "", "", "", ""
                )
                break
            else:
                # In progress
                yield (
                    status_text,
                    "", "", "", "", *progress_updates, "", "", "", "", "", "", "", "", "", "", "", "", "", ""
                )
        
        # Cleanup
        if job_id in streaming_jobs:
            del streaming_jobs[job_id]
            
    except Exception as e:
        logger.error(f"Attach error: {e}")
        yield (
            format_error_message(f"Attach error: {e}"),
            "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""
        )

def clear_all_outputs() -> Tuple:
    """Clear all output displays."""
    return (
        "🌙 Sleep Stories AI - Ready\n\nSelect generation parameters and click 'Generate Story' to begin.",
        "", "", "", "", 0, 0, 0, "-", "0:00", "-", "-", "", "", "", "", "", "", "", "", 0, 0, 0, ""
    )

def auto_refresh_jobs_worker():
    """Background worker for auto-refreshing jobs."""
    while auto_refresh_enabled:
        try:
            time.sleep(10)  # Refresh every 10 seconds
            # This would need to be connected to the actual dropdown update
            # in a real implementation, this is just the structure
        except Exception as e:
            logger.error(f"Auto-refresh error: {e}")
        time.sleep(1)

# Create the Gradio interface
def create_interface():
    """Create the main Gradio interface."""
    
    custom_css = load_custom_css()
    
    with gr.Blocks(
        title="🌙 Sleep Stories AI - Enhanced v2.0",
        theme=gr.themes.Soft(),
        css=custom_css
    ) as demo:
        
        # Header
        gr.Markdown(
            """
            # 🌙 Sleep Stories AI - Enhanced v2.0
            ### Next-Generation AI-Powered Sleep Story Generator
            *Optimized for RTX 3070Ti • Real-time Streaming • Complete Parameter Control*
            """
        )
        
        with gr.Row(equal_height=False):
            # Left Column - Generation Settings
            with gr.Column(scale=1, min_width=500):
                # Basic Settings
                theme, description, duration, preset = create_basic_settings()
                
                # Model Settings
                (
                    use_custom_models, generator_model, reasoner_model, polisher_model,
                    use_reasoner, use_polisher, refresh_models_btn
                ) = create_model_settings()
                
                # Quality Settings
                tts_markers, strict_schema, sensory_rotation, sleep_taper = create_quality_settings()
                
                # Advanced Settings
                (
                    model_temperature, coach_enabled, movement_verbs, transition_tokens,
                    sensory_coupling, pov_second_person, destination_arc, arrival_start,
                    settlement_beats, archetype
                ) = create_advanced_settings()
                
                # Generation Controls
                generate_btn, clear_btn = create_generation_controls()
            
            # Right Column - Monitoring and Results
            with gr.Column(scale=2, min_width=700):
                # Job Management
                (
                    active_jobs_dropdown, refresh_jobs_btn, attach_job_btn,
                    auto_refresh, show_completed
                ) = create_job_management()
                
                # Status Display
                status_display = create_status_display()
                
                # Progress Indicators
                (
                    overall_progress, current_beat, total_beats, beat_stage,
                    elapsed_time, eta_time, current_model
                ) = create_progress_indicators()
                
                # System Information
                system_status, refresh_system_btn, health_check_btn = create_system_info()
                
        # Results Section
        with gr.Row():
            with gr.Column():
                (
                    story_output, word_count, estimated_duration, tts_ready,
                    export_txt_btn, export_tts_btn,
                    generation_metrics, coherence_stats, memory_stats,
                    sensory_score, coherence_score, flow_score,
                    story_outline, beats_count, transitions_count, sensory_rotations,
                    beats_schema, schema_valid, total_segments, total_duration,
                    export_json_btn, export_video_ready_btn,
                    sensory_breakdown, linguistic_stats, quality_report
                ) = create_results_tabs()
                
                # Download Section
                (
                    download_story_file, download_metrics_file, download_schema_file,
                    prepare_downloads_btn, download_all_btn
                ) = create_download_section()
        
        # Job History (in accordion)
        (
            job_history, total_jobs, active_count, completed_count, failed_count,
            refresh_history_btn
        ) = create_job_history()
        
        # Define all outputs for generation streaming
        generation_outputs = [
            status_display,
            story_output, generation_metrics, story_outline, beats_schema,
            overall_progress, current_beat, total_beats, beat_stage,
            elapsed_time, eta_time, current_model,
            word_count, estimated_duration, tts_ready,
            coherence_stats, memory_stats, sensory_score, coherence_score, flow_score,
            beats_count, transitions_count, sensory_rotations,
            schema_valid, total_segments, total_duration
        ]
        
        # Define all inputs for generation (includes preset now)
        generation_inputs = [
            theme, description, duration, preset,
            use_custom_models, generator_model, reasoner_model, polisher_model,
            use_reasoner, use_polisher,
            tts_markers, strict_schema, sensory_rotation, sleep_taper,
            model_temperature, coach_enabled, movement_verbs, transition_tokens,
            sensory_coupling, pov_second_person, destination_arc, arrival_start,
            settlement_beats, archetype
        ]
        
        # Event handlers with Gradio 4.44+ compatible parameters
        
        # Generation - GPU intensive, limit to 1 concurrent
        generate_btn.click(
            fn=start_generation,
            inputs=generation_inputs,
            outputs=generation_outputs,
            concurrency_limit=1,
            concurrency_id="gpu_generation"  # Share queue with other GPU operations
        )
        
        # Attach to job - Monitoring only, can have more concurrent
        attach_job_btn.click(
            fn=attach_to_job,
            inputs=[active_jobs_dropdown],
            outputs=generation_outputs,
            concurrency_limit=3,
            concurrency_id="job_monitoring"  # Separate queue for monitoring
        )
        
        # Clear outputs - No concurrency limit needed
        clear_btn.click(
            fn=clear_all_outputs,
            inputs=None,
            outputs=generation_outputs
        )
        
        # Refresh ALL models - Update all three model dropdowns
        refresh_models_btn.click(
            fn=refresh_all_models,
            inputs=None,
            outputs=[generator_model, reasoner_model, polisher_model],
            concurrency_limit=5,
            concurrency_id="api_calls"
        )
        
        refresh_jobs_btn.click(
            fn=refresh_jobs,
            inputs=[show_completed],
            outputs=[active_jobs_dropdown],
            concurrency_limit=5,
            concurrency_id="api_calls"
        )
        
        refresh_system_btn.click(
            fn=get_system_info,
            inputs=None,
            outputs=[system_status],
            concurrency_limit=5,
            concurrency_id="api_calls"
        )
        
        health_check_btn.click(
            fn=lambda: api_client.get_health(),
            inputs=None,
            outputs=[system_status],
            concurrency_limit=5,
            concurrency_id="api_calls"
        )
        
        # Auto-refresh jobs when checkbox changes
        show_completed.change(
            fn=refresh_jobs,
            inputs=[show_completed],
            outputs=[active_jobs_dropdown],
            concurrency_limit=5,
            concurrency_id="api_calls"
        )
        
        # Load initial data - FIXED to populate ALL components
        def load_initial_data():
            """Load all initial data on startup."""
            try:
                # Get models for all three dropdowns
                gen_update, reas_update, pol_update = refresh_all_models()
                
                # Get jobs
                jobs_update = refresh_jobs(False)
                
                # Get system info
                system_info = get_system_info()
                
                # Get presets and archetype choices
                preset_update, archetype_choices = get_model_presets_and_defaults()
                
                return (
                    gen_update,      # generator_model
                    reas_update,     # reasoner_model  
                    pol_update,      # polisher_model
                    jobs_update,     # active_jobs_dropdown
                    system_info,     # system_status
                    preset_update,   # preset dropdown
                    gr.update(choices=archetype_choices, value=archetype_choices[0])  # archetype
                )
            except Exception as e:
                logger.error(f"Failed to load initial data: {e}")
                error_update = gr.update(choices=[f"❌ Load Error: {e}"], value=None)
                return error_update, error_update, error_update, error_update, {"error": str(e)}, error_update, error_update
        
        demo.load(
            fn=load_initial_data,
            inputs=None,
            outputs=[
                generator_model, reasoner_model, polisher_model, 
                active_jobs_dropdown, system_status, preset, archetype
            ]
        )
    
    return demo

if __name__ == "__main__":
    logger.info("Starting Sleep Stories AI - Enhanced Frontend v2.0 (Dropdown Fix Applied)")
    
    # Start auto-refresh worker
    refresh_thread = threading.Thread(target=auto_refresh_jobs_worker, daemon=True)
    refresh_thread.start()
    
    # Create and launch interface
    demo = create_interface()
    
    # Gradio 4.44+ compatible queue configuration
    # Reference: https://www.gradio.app/4.44.1/guides/queuing
    # Reference: https://www.gradio.app/4.44.1/guides/setting-up-a-demo-for-maximum-performance
    demo.queue(
        default_concurrency_limit=1,  # Default limit for events without explicit concurrency_limit
        max_size=20,                  # Maximum queue size
        status_update_rate="auto"     # Auto-update rate for queue status
    )
    
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True,
        debug=False,
        max_threads=40,               # Total worker threads
        show_tips=False,
        quiet=False
    )
