"""Monitoring panel components for Sleep Stories AI."""

import gradio as gr
from typing import Dict, Any, List, Tuple, Optional

def create_job_management() -> Tuple:
    """Create job management and monitoring components."""
    with gr.Group():
        gr.Markdown("### 🔗 Job Management")
        
        with gr.Row():
            active_jobs_dropdown = gr.Dropdown(
                label="Active Jobs",
                choices=[],
                value=None,
                allow_custom_value=False,
                info="Select a job to monitor or resume",
                scale=3
            )
            
            refresh_jobs_btn = gr.Button(
                "🔄",
                size="sm",
                variant="secondary",
                scale=0
            )
            
            attach_job_btn = gr.Button(
                "🔗 Attach",
                variant="secondary",
                scale=1
            )
        
        with gr.Row():
            auto_refresh = gr.Checkbox(
                label="Auto-refresh jobs",
                value=True,
                info="Automatically refresh job list every 10 seconds"
            )
            
            show_completed = gr.Checkbox(
                label="Show completed jobs",
                value=False,
                info="Include finished jobs in the list"
            )
    
    return (
        active_jobs_dropdown, refresh_jobs_btn, attach_job_btn,
        auto_refresh, show_completed
    )

def create_status_display() -> gr.Textbox:
    """Create main status display component."""
    return gr.Textbox(
        label="Generation Status",
        lines=15,
        interactive=False,
        show_copy_button=True,
        container=True,
        value="🌙 Sleep Stories AI - Ready\n\nSelect generation parameters and click 'Generate Story' to begin."
    )

def create_system_info() -> Tuple:
    """Create system information display."""
    with gr.Accordion("📊 System Information", open=False):
        system_status = gr.JSON(
            label="System Status",
            value={},
            container=True
        )
        
        with gr.Row():
            refresh_system_btn = gr.Button(
                "🔄 Refresh System Info",
                size="sm",
                variant="secondary"
            )
            
            health_check_btn = gr.Button(
                "❤️ Health Check",
                size="sm",
                variant="secondary"
            )
    
    return system_status, refresh_system_btn, health_check_btn

def create_progress_indicators() -> Tuple:
    """Create detailed progress indicator components."""
    with gr.Group():
        gr.Markdown("### 📈 Detailed Progress")
        
        with gr.Row():
            overall_progress = gr.Slider(
                minimum=0,
                maximum=100,
                value=0,
                label="Overall Progress (%)",
                interactive=False,
                info="Total generation progress"
            )
        
        with gr.Row():
            current_beat = gr.Number(
                label="Current Beat",
                value=0,
                interactive=False,
                precision=0
            )
            
            total_beats = gr.Number(
                label="Total Beats",
                value=0,
                interactive=False,
                precision=0
            )
            
            beat_stage = gr.Textbox(
                label="Beat Stage",
                value="-",
                interactive=False
            )
        
        with gr.Row():
            elapsed_time = gr.Textbox(
                label="Elapsed Time",
                value="0:00",
                interactive=False
            )
            
            eta_time = gr.Textbox(
                label="Estimated Remaining",
                value="-",
                interactive=False
            )
            
            current_model = gr.Textbox(
                label="Current Model",
                value="-",
                interactive=False
            )
    
    return (
        overall_progress, current_beat, total_beats, beat_stage,
        elapsed_time, eta_time, current_model
    )

def create_job_history() -> Tuple:
    """Create job history and statistics components."""
    with gr.Accordion("📁 Job History & Statistics", open=False):
        job_history = gr.Dataframe(
            headers=["Job ID", "Theme", "Status", "Duration", "Created", "Progress"],
            datatype=["str", "str", "str", "str", "str", "number"],
            interactive=False,
            value=[],
            label="Recent Jobs"
        )
        
        with gr.Row():
            total_jobs = gr.Number(
                label="Total Jobs",
                value=0,
                interactive=False
            )
            
            active_count = gr.Number(
                label="Active",
                value=0,
                interactive=False
            )
            
            completed_count = gr.Number(
                label="Completed",
                value=0,
                interactive=False
            )
            
            failed_count = gr.Number(
                label="Failed",
                value=0,
                interactive=False
            )
        
        refresh_history_btn = gr.Button(
            "🔄 Refresh History",
            size="sm",
            variant="secondary"
        )
    
    return (
        job_history, total_jobs, active_count, completed_count, failed_count,
        refresh_history_btn
    )

def update_progress_indicators(
    telemetry: Dict[str, Any]
) -> Tuple[gr.update, ...]:
    """Update all progress indicators with telemetry data."""
    # Extract telemetry data
    progress = telemetry.get("progress", 0)
    
    beat_info = telemetry.get("beat", {})
    current_beat_val = beat_info.get("index", 0)
    total_beats_val = beat_info.get("total", 0)
    beat_stage_val = beat_info.get("stage", "-")
    
    timing = telemetry.get("timing", {})
    elapsed_sec = timing.get("elapsed_sec", 0)
    eta_sec = timing.get("eta_sec")
    
    models = telemetry.get("models", {})
    current_model_val = models.get("generator", "-")
    
    # Format time displays
    elapsed_str = f"{int(elapsed_sec // 60)}:{int(elapsed_sec % 60):02d}"
    eta_str = f"{int(eta_sec // 60)}:{int(eta_sec % 60):02d}" if eta_sec else "-"
    
    return (
        gr.update(value=progress),
        gr.update(value=current_beat_val),
        gr.update(value=total_beats_val),
        gr.update(value=beat_stage_val),
        gr.update(value=elapsed_str),
        gr.update(value=eta_str),
        gr.update(value=current_model_val)
    )

def format_job_history_data(jobs: List[Dict[str, Any]]) -> List[List[str]]:
    """Format jobs data for history dataframe."""
    formatted_jobs = []
    
    for job in jobs:
        job_id = job.get("job_id", "")[:12] + "..."
        theme = job.get("theme", "")[:30] + "..." if len(job.get("theme", "")) > 30 else job.get("theme", "")
        status = job.get("status", "").upper()
        duration = f"{job.get('duration', 0)}min"
        created = job.get("created_at", "")[:16] if job.get("created_at") else "-"
        progress = job.get("progress", 0)
        
        formatted_jobs.append([job_id, theme, status, duration, created, progress])
    
    return formatted_jobs

def update_job_statistics(jobs: List[Dict[str, Any]]) -> Tuple[gr.update, ...]:
    """Update job statistics counters."""
    total = len(jobs)
    active = len([j for j in jobs if j.get("status") in ["started", "processing", "queued"]])
    completed = len([j for j in jobs if j.get("status") == "completed"])
    failed = len([j for j in jobs if j.get("status") == "failed"])
    
    return (
        gr.update(value=total),
        gr.update(value=active),
        gr.update(value=completed),
        gr.update(value=failed)
    )

def create_real_time_logs() -> gr.Textbox:
    """Create real-time logs display."""
    return gr.Textbox(
        label="Real-time Logs",
        lines=8,
        interactive=False,
        show_copy_button=True,
        container=True,
        value="Logs will appear here during generation...",
        visible=False  # Hidden by default, can be shown via accordion
    )
