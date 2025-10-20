"""Results panel components for Sleep Stories AI.

Ensure gr.JSON components always receive dict/list, not empty strings.
Include create_download_section for UI imports.
"""

import gradio as gr
from typing import Dict, Any, List, Tuple


def create_results_tabs() -> Tuple:
    """Create comprehensive results display tabs."""
    with gr.Tabs() as results_tabs:
        # Story Tab
        with gr.Tab("📜 Story"):
            story_output = gr.Textbox(label="Generated Story", lines=25, interactive=False, show_copy_button=True, container=True, placeholder="Your generated story will appear here...")
            with gr.Row():
                word_count = gr.Number(label="Word Count", value=0, interactive=False)
                estimated_duration = gr.Textbox(label="Estimated Reading Time", value="0 minutes", interactive=False)
                tts_ready = gr.Checkbox(label="TTS Ready", value=False, interactive=False, info="Contains TTS markers")
            with gr.Row():
                export_txt_btn = gr.Button("📄 Export as TXT", size="sm", variant="secondary")
                export_tts_btn = gr.Button("🎙️ Export for TTS", size="sm", variant="secondary")
        
        # Metrics Tab
        with gr.Tab("📈 Metrics"):
            with gr.Row():
                with gr.Column():
                    generation_metrics = gr.JSON(label="Generation Metrics", value={}, container=True)
                with gr.Column():
                    coherence_stats = gr.JSON(label="Coherence Statistics", value={}, container=True)
            memory_stats = gr.JSON(label="Memory & Performance Statistics", value={}, container=True)
            with gr.Row():
                sensory_score = gr.Slider(minimum=0, maximum=100, value=0, label="Sensory Richness Score", interactive=False)
                coherence_score = gr.Slider(minimum=0, maximum=100, value=0, label="Coherence Score", interactive=False)
                flow_score = gr.Slider(minimum=0, maximum=100, value=0, label="Flow Score", interactive=False)
        
        # Outline Tab
        with gr.Tab("🗺️ Outline"):
            story_outline = gr.Textbox(label="Story Outline & Structure", lines=20, interactive=False, show_copy_button=True, container=True, placeholder="Story outline and structure analysis will appear here...")
            with gr.Row():
                beats_count = gr.Number(label="Total Beats", value=0, interactive=False)
                transitions_count = gr.Number(label="Transitions", value=0, interactive=False)
                sensory_rotations = gr.Number(label="Sensory Rotations", value=0, interactive=False)
        
        # Schema Tab
        with gr.Tab("📝 Schema"):
            beats_schema = gr.JSON(label="Beats Schema (Video Production)", value={}, container=True)
            with gr.Row():
                schema_valid = gr.Checkbox(label="Schema Valid", value=False, interactive=False, info="Ready for video production pipeline")
                total_segments = gr.Number(label="Video Segments", value=0, interactive=False)
                total_duration = gr.Textbox(label="Total Duration", value="0:00", interactive=False)
            with gr.Row():
                export_json_btn = gr.Button("📄 Export JSON", size="sm", variant="secondary")
                export_video_ready_btn = gr.Button("🎥 Export Video-Ready", size="sm", variant="secondary")
        
        # Analysis Tab
        with gr.Tab("🔍 Analysis"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Sensory Analysis")
                    sensory_breakdown = gr.JSON(label="Sensory Elements Breakdown", value={}, container=True)
                with gr.Column():
                    gr.Markdown("### Linguistic Analysis")
                    linguistic_stats = gr.JSON(label="Language & Style Statistics", value={}, container=True)
            gr.Markdown("### Quality Assessment")
            quality_report = gr.Textbox(label="Automated Quality Report", lines=15, interactive=False, show_copy_button=True, container=True, placeholder="Quality assessment report will appear here...")
    
    return (
        story_output, word_count, estimated_duration, tts_ready,
        export_txt_btn, export_tts_btn,
        generation_metrics, coherence_stats, memory_stats,
        sensory_score, coherence_score, flow_score,
        story_outline, beats_count, transitions_count, sensory_rotations,
        beats_schema, schema_valid, total_segments, total_duration,
        export_json_btn, export_video_ready_btn,
        sensory_breakdown, linguistic_stats, quality_report
    )


def create_download_section() -> Tuple:
    """Create file download section."""
    with gr.Group():
        gr.Markdown("### 📥 Download Results")
        with gr.Row():
            download_story_file = gr.File(label="Story File", visible=False)
            download_metrics_file = gr.File(label="Metrics File", visible=False)
            download_schema_file = gr.File(label="Schema File", visible=False)
        with gr.Row():
            prepare_downloads_btn = gr.Button("📎 Prepare Downloads", variant="secondary", size="sm")
            download_all_btn = gr.Button("📦 Download All", variant="primary", size="sm")
    return (download_story_file, download_metrics_file, download_schema_file, prepare_downloads_btn, download_all_btn)


def update_results_display(result: Dict[str, Any]) -> Tuple[gr.update, ...]:
    story_text = result.get("story_text", "")
    metrics = result.get("metrics", {}) or {}
    coherence_stats = result.get("coherence_stats", {}) or {}
    memory_stats = result.get("memory_stats", {}) or {}
    outline = result.get("outline", "")
    beats_schema = result.get("beats_schema", {}) or {}

    word_count_val = len(story_text.split()) if story_text else 0
    estimated_reading_time = f"{word_count_val // 200} minutes" if word_count_val > 0 else "0 minutes"
    tts_ready_val = ("[PAUSE:" in story_text) or ("[BREATHE]" in story_text)

    sensory_score_val = metrics.get("sensory_richness_score", 0) or 0
    coherence_score_val = coherence_stats.get("coherence_score", 0) or 0
    flow_score_val = metrics.get("flow_score", 0) or 0

    beats_count_val = metrics.get("beats_generated", 0) or 0
    transitions_count_val = coherence_stats.get("transitions", 0) or 0
    sensory_rotations_val = coherence_stats.get("sensory_rotations", 0) or 0

    schema_valid_val = bool(beats_schema.get("beats")) if isinstance(beats_schema, dict) else False
    total_segments_val = len(beats_schema.get("beats", [])) if isinstance(beats_schema, dict) else 0
    total_duration_seconds = beats_schema.get("total_estimated_duration", 0) if isinstance(beats_schema, dict) else 0
    total_duration_val = f"{total_duration_seconds // 60}:{total_duration_seconds % 60:02d}" if total_duration_seconds else "0:00"

    sensory_breakdown_val = metrics.get("sensory_analysis", {}) or {}
    linguistic_stats_val = metrics.get("linguistic_stats", {}) or {}

    quality_report_val = ""

    return (
        gr.update(value=story_text),
        gr.update(value=word_count_val),
        gr.update(value=estimated_reading_time),
        gr.update(value=tts_ready_val),
        gr.update(), gr.update(),
        gr.update(value=metrics),
        gr.update(value=coherence_stats),
        gr.update(value=memory_stats),
        gr.update(value=sensory_score_val),
        gr.update(value=coherence_score_val),
        gr.update(value=flow_score_val),
        gr.update(value=outline),
        gr.update(value=beats_count_val),
        gr.update(value=transitions_count_val),
        gr.update(value=sensory_rotations_val),
        gr.update(value=beats_schema),
        gr.update(value=schema_valid_val),
        gr.update(value=total_segments_val),
        gr.update(value=total_duration_val),
        gr.update(), gr.update(),
        gr.update(value=sensory_breakdown_val),
        gr.update(value=linguistic_stats_val),
        gr.update(value=quality_report_val)
    )
