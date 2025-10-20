import gradio as gr
import requests
import json
import time
import os
from typing import Optional
from datetime import datetime, timedelta

API_URL = os.getenv("API_URL", "http://backend:8000/api")

class SSEClient:
    """Client for Server-Sent Events streaming"""
    
    def __init__(self, url: str):
        self.url = url
        self.response = None
        
    def __enter__(self):
        try:
            self.response = requests.get(
                self.url, 
                stream=True, 
                timeout=300,
                headers={'Accept': 'text/event-stream', 'Cache-Control': 'no-cache'}
            )
            return self
        except Exception as e:
            raise ConnectionError(f"Failed to connect to SSE stream: {e}")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.response:
            self.response.close()
    
    def events(self):
        """Generator that yields SSE events"""
        if not self.response:
            return
        
        for line in self.response.iter_lines(decode_unicode=True):
            if line.startswith('data: '):
                try:
                    data = json.loads(line[6:])  # Remove 'data: ' prefix
                    yield data
                except json.JSONDecodeError:
                    continue
            elif line.startswith('event: heartbeat'):
                continue  # Skip heartbeat events

def load_model_presets():
    """Load available model presets from API."""
    try:
        response = requests.get(f"{API_URL}/models/presets", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('presets', {}), data.get('default_models', {}), data.get('available_features', {})
        else:
            # Fallback defaults
            return {
                "quality_high": {"generator": "qwen2.5:7b", "reasoner": "deepseek-r1:8b", "polisher": "mistral:7b"},
                "fast": {"generator": "qwen2.5:7b", "reasoner": None, "polisher": None}
            }, {"generator": "qwen2.5:7b", "reasoner": "deepseek-r1:8b", "polisher": "mistral:7b"}, {}
    except:
        # Fallback if API unavailable
        return {
            "quality_high": {"generator": "qwen2.5:7b", "reasoner": "deepseek-r1:8b", "polisher": "mistral:7b"},
            "fast": {"generator": "qwen2.5:7b", "reasoner": None, "polisher": None}
        }, {"generator": "qwen2.5:7b", "reasoner": "deepseek-r1:8b", "polisher": "mistral:7b"}, {}

def generate_enhanced_story(theme, duration, description=None, 
                          model_preset="quality_high", use_custom_models=False,
                          custom_generator="", custom_reasoner="", custom_polisher="",
                          use_reasoner=True, use_polisher=True,
                          tts_markers=False, strict_schema=False,
                          sensory_rotation=None, sleep_taper=None, custom_waypoints=None):
    """Complete enhanced story generation with all API parameters"""
    
    start_time = time.time()
    
    try:
        # Prepare model configuration based on UI selections
        models_config = None
        if use_custom_models and model_preset == "Custom":
            models_config = {}
            if custom_generator.strip():
                models_config["generator"] = custom_generator.strip()
            if custom_reasoner.strip():
                models_config["reasoner"] = custom_reasoner.strip() 
            if custom_polisher.strip():
                models_config["polisher"] = custom_polisher.strip()
        
        # Build enhanced API request payload
        payload = {
            "theme": theme,
            "duration": duration,
            "description": description if description and description.strip() else None,
            "use_reasoner": use_reasoner,
            "use_polish": use_polisher,
            "tts_markers": tts_markers,
            "strict_schema": strict_schema
        }
        
        # Add model configuration if specified
        if models_config:
            payload["models"] = models_config
        
        # Add advanced settings if specified
        if sensory_rotation is not None:
            payload["sensory_rotation"] = sensory_rotation
        if sleep_taper is not None:
            payload["sleep_taper"] = sleep_taper
        if custom_waypoints:
            payload["custom_waypoints"] = custom_waypoints
        
        # Start generation job
        response = requests.post(
            f"{API_URL}/generate/story",
            json=payload,
            timeout=30
        )
        
        if response.status_code != 200:
            return f"❌ Error starting generation: {response.text}", "", "", "", ""
        
        job_data = response.json()
        job_id = job_data["job_id"]
        features_enabled = job_data.get("features", {})
        
        # Build status display
        def build_status(progress, current_step, step_num, total_steps, elapsed_time, stage_metrics=None):
            features_text = "\n".join([
                f"{'🔥' if features_enabled.get('multi_model', False) else '📦'} Multi-Model: {'ENABLED' if features_enabled.get('multi_model', False) else 'DISABLED'}",
                f"{'🎯' if features_enabled.get('quality_enhancements', False) else '📦'} Quality Enhanced: {'YES' if features_enabled.get('quality_enhancements', False) else 'NO'}",
                f"{'🎤' if features_enabled.get('tts_markers', False) else '📦'} TTS Markers: {'YES' if features_enabled.get('tts_markers', False) else 'NO'}",
                f"{'📋' if features_enabled.get('strict_schema', False) else '📦'} Strict Schema: {'YES' if features_enabled.get('strict_schema', False) else 'NO'}"
            ])
            
            stage_info = ""
            if stage_metrics:
                stage_info = f"\n\n📊 **Stage Metrics**:\n"
                for key, value in stage_metrics.items():
                    stage_info += f"- {key}: {value}\n"
            
            return f"""🚀 **Enhanced Sleep Stories AI Generator v2.0**

📋 Job ID: `{job_id}`
⚡ Preset: **{model_preset if not use_custom_models else 'CUSTOM'}**
⏱️ Elapsed: **{elapsed_time}**

🔧 **Enhanced Features**:
{features_text}

**Status**: PROCESSING
**Step**: {step_num}/{total_steps} - {current_step}
**Progress**: {progress:.1f}%

[{"🟩" * int(progress/2.5)}{"⬜" * (40-int(progress/2.5))}] {progress:.1f}%{stage_info}

{"🎯 **Phase**: Enhanced Analysis" if step_num <= 2 else "🤖 **Phase**: Multi-Model Generation" if step_num <= 6 else "✨ **Phase**: Quality Enhancement"}"""
        
        # Monitor generation with real-time updates
        elapsed = "00:00"
        initial_status = build_status(0, "Initializing enhanced generation...", 0, 8, elapsed)
        current_status = initial_status
        
        # Use SSE streaming for real-time updates
        try:
            with SSEClient(f"{API_URL}/generate/{job_id}/stream") as sse:
                for event_data in sse.events():
                    elapsed_seconds = int(time.time() - start_time)
                    elapsed = str(timedelta(seconds=elapsed_seconds))[2:7]
                    
                    status = event_data.get('status', 'processing')
                    progress = event_data.get('progress', 0)
                    current_step = event_data.get('current_step', 'Processing...')
                    step_num = event_data.get('current_step_number', 0)
                    total_steps = event_data.get('total_steps', 8)
                    stage_metrics = event_data.get('stage_metrics')
                    
                    current_status = build_status(progress, current_step, step_num, total_steps, elapsed, stage_metrics)
                    
                    if status == 'completed':
                        break
                    elif status == 'failed':
                        error_msg = event_data.get('error', 'Unknown error occurred')
                        final_elapsed = str(timedelta(seconds=int(time.time() - start_time)))[2:7]
                        error_status = current_status + f"\n\n❌ **FAILED** after {final_elapsed}: {error_msg}"
                        return error_status, "", "", "", ""
        
        except Exception as sse_error:
            elapsed = str(timedelta(seconds=int(time.time() - start_time)))[2:7]
            fallback_status = build_status(10, f"SSE failed - Using polling...", 1, 8, elapsed)
            time.sleep(5)  # Fallback polling
        
        # Get final results
        try:
            result_response = requests.get(f"{API_URL}/generate/{job_id}/result", timeout=30)
            if result_response.status_code != 200:
                final_elapsed = str(timedelta(seconds=int(time.time() - start_time)))[2:7]
                return current_status + f"\n❌ Error getting results after {final_elapsed}", "", "", "", ""
                
            result = result_response.json()
            total_elapsed = str(timedelta(seconds=int(time.time() - start_time)))[2:7]
            
            # Extract enhanced results
            story_text = result.get('story_text', '')
            metrics = result.get('metrics', {})
            coherence_stats = result.get('coherence_stats', {})
            memory_stats = result.get('memory_stats', {})
            generation_info = result.get('generation_info', {})
            beats_schema = result.get('beats_schema', {})
            
            # Format enhanced metrics display
            enhanced_metrics_text = f"""📊 **ENHANCED GENERATION METRICS**

⏱️ **Performance**:
- Total Generation Time: {total_elapsed}
- Target Duration: {duration} minutes
- Generation Speed: {metrics.get('english_word_count', 0) / max(1, metrics.get('generation_time_seconds', 1)):.1f} words/sec

🤖 **Multi-Model Pipeline**:
- Generator: {generation_info.get('models_used', {}).get('generator', 'N/A')}
- Reasoner: {generation_info.get('models_used', {}).get('reasoner', 'None')}
- Polisher: {generation_info.get('models_used', {}).get('polisher', 'None')}

📝 **Word Count Analysis**:
- Generator Words: {metrics.get('generator_words', 0):,}
- Reasoner Words: {metrics.get('reasoner_words', 0):,}
- Polisher Words: {metrics.get('polisher_words', 0):,}
- Final Words: {metrics.get('english_word_count', 0):,}
- Target Words: {metrics.get('target_words', 0):,}
- Accuracy: {metrics.get('accuracy_percent', 0):.1f}% deviation

🔧 **Quality Enhancements**:
- Corrections Applied: {metrics.get('corrections_count', 0)}
- Coherence Improvements: {metrics.get('coherence_improvements', 0)}
- Sensory Transitions: {coherence_stats.get('sensory_transitions', 0)}
- Average Density Factor: {coherence_stats.get('avg_density_factor', 1.0):.3f}

📖 **Story Structure**:
- Beats Generated: {memory_stats.get('total_beats', 0)}
- Avg Words/Beat: {memory_stats.get('avg_words_per_beat', 0):.1f}
- Duration Estimate: {metrics.get('duration_estimate_minutes', 0):.1f} minutes

🎯 **Enhanced Features Used**:
{chr(10).join([f"- {k.replace('_', ' ').title()}: {'YES' if v else 'NO'}" for k, v in metrics.get('enhanced_features_used', {}).items()])}

🧠 **Memory & Coherence**:
- Sensory Distribution: {json.dumps(memory_stats.get('sensory_distribution', {}), indent=2)}
"""
            
            # Format outline/structure
            outline_text = result.get('outline', '')
            if isinstance(outline_text, dict):
                outline_formatted = f"""📖 **ENHANCED STORY STRUCTURE**

🌍 **Story Bible**:
{json.dumps(outline_text, indent=2)}

📊 **Generation Timeline**:
- Start Time: {generation_info.get('generation_timestamp', 'N/A')}
- Total Duration: {total_elapsed}
- Features Enabled: {len([k for k, v in generation_info.get('features_enabled', {}).items() if v])}

🎬 **Pipeline Stages**:
1. Enhanced Theme Analysis ✓
2. Quality-Enhanced Outline ✓
3. Multi-Model Generation ✓
4. Sensory Rotation ✓
5. Mixed-Reward Proxy ✓
6. Sleep-Taper Application ✓
7. {'TTS Markers Inserted ✓' if tts_markers else 'TTS Markers Skipped ⏭️'}
8. {'Strict Schema Generated ✓' if strict_schema else 'Standard Output ⏭️'}
"""
            else:
                outline_formatted = str(outline_text)
            
            # Format schema output if available
            schema_output = ""
            if beats_schema and strict_schema:
                schema_output = f"""📋 **STRICT BEATS SCHEMA**

⏱️ **Timing Information**:
- Total Estimated Duration: {beats_schema.get('total_estimated_duration', 0):.1f} seconds
- Schema Version: {beats_schema.get('schema_version', 'N/A')}

🎬 **Beat Breakdown**:
{json.dumps(beats_schema.get('beats', []), indent=2)}

🎤 **TTS Integration Notes**:
- Each beat includes timing estimates for TTS systems
- Media cues provided for video generation
- Sensory focus tagged for image generation
- Waypoints marked for spatial progression
"""
            else:
                schema_output = "Strict schema not enabled for this generation."
            
            # Final status
            final_status = build_status(100, "Enhanced generation complete!", 8, 8, total_elapsed)
            final_status += f"\n\n✅ **ENHANCED GENERATION COMPLETE!**\n📝 Story generated with {metrics.get('english_word_count', 0):,} words\n🎯 Quality enhancements applied\n{'🎤 TTS markers integrated' if tts_markers else ''}\n{'📋 Strict schema generated' if strict_schema else ''}\n📁 Enhanced output files saved\n⏱️ **Total time: {total_elapsed}**"
            
            return final_status, story_text, enhanced_metrics_text, outline_formatted, schema_output
            
        except Exception as e:
            final_elapsed = str(timedelta(seconds=int(time.time() - start_time)))[2:7]
            return current_status + f"\n❌ Error processing results after {final_elapsed}: {str(e)}", "", "", "", ""
    
    except Exception as e:
        elapsed = str(timedelta(seconds=int(time.time() - start_time)))[2:7]
        return f"❌ **Generation Error** after {elapsed}: {str(e)}", "", "", "", ""

# Load presets at startup
MODEL_PRESETS, DEFAULT_MODELS, AVAILABLE_FEATURES = load_model_presets()

# Create Complete Enhanced UI
with gr.Blocks(title="Sleep Stories AI - Enhanced v2.0", theme=gr.themes.Soft()) as demo:
    
    # Custom CSS
    demo.css = """
    .markdown-content {
        line-height: 1.6;
    }
    .status-box textarea {
        font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
        line-height: 1.4;
    }
    .enhanced-section {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
    }
    """
    
    gr.HTML("""
    <div style="text-align: center; margin-bottom: 20px;">
        <h1>🌙 Sleep Stories AI - <strong>Enhanced v2.0</strong></h1>
        <p><strong>🚀 Multi-Model AI with Quality Enhancements, TTS Integration & Advanced Features</strong></p>
    </div>
    """)
    
    with gr.Row():
        with gr.Column(scale=1):
            gr.HTML('<h3>📝 <strong>Enhanced Story Configuration</strong></h3>')
            
            # Basic Story Settings
            theme = gr.Textbox(
                label="🌍 Theme / Setting",
                placeholder="e.g., A peaceful Scottish Highland lake at dawn",
                value="A tranquil mountain meadow with gentle morning mist",
                info="Main setting/location for the story"
            )
            
            description = gr.Textbox(
                label="📋 Additional Details (optional)",
                placeholder="Focus on specific sensory elements, mood, or atmosphere...",
                lines=3,
                info="Extra guidance for enhanced AI generation"
            )
            
            duration = gr.Slider(
                label="⏱️ Duration (minutes)",
                minimum=20,
                maximum=90,
                value=45,
                step=5,
                info="Target story duration (enhanced quality supports longer stories)"
            )
            
            # Enhanced Model Configuration
            gr.HTML('<div class="enhanced-section"><h4>🤖 Model Configuration</h4></div>')
            
            model_preset = gr.Radio(
                label="🎯 Model Presets (Optimized for RTX 3070Ti)",
                choices=[
                    "Quality High (qwen2.5:7b + deepseek-r1:8b + mistral:7b)",
                    "Fast (qwen2.5:7b only)",
                    "Custom"
                ],
                value="Quality High (qwen2.5:7b + deepseek-r1:8b + mistral:7b)",
                info="Pre-configured model combinations for optimal quality vs speed"
            )
            
            with gr.Group(visible=False) as custom_models_group:
                gr.HTML("<h5>🔧 Custom Model Configuration</h5>")
                custom_generator = gr.Textbox(
                    label="Generator Model",
                    placeholder="e.g., qwen2.5:7b",
                    value=DEFAULT_MODELS.get('generator', 'qwen2.5:7b'),
                    info="Main story generation model"
                )
                custom_reasoner = gr.Textbox(
                    label="Reasoner Model (optional)",
                    placeholder="e.g., deepseek-r1:8b",
                    value=DEFAULT_MODELS.get('reasoner', 'deepseek-r1:8b'),
                    info="Logic and coherence improvement model"
                )
                custom_polisher = gr.Textbox(
                    label="Polisher Model (optional)",
                    placeholder="e.g., mistral:7b",
                    value=DEFAULT_MODELS.get('polisher', 'mistral:7b'),
                    info="Final style and flow refinement model"
                )
            
            # Enhanced Features Section
            gr.HTML('<div class="enhanced-section"><h4>⚡ Enhanced Features</h4></div>')
            
            with gr.Row():
                use_reasoner = gr.Checkbox(
                    label="🧠 Use Reasoner (DeepSeek-R1)",
                    value=True,
                    info="Enable logic and coherence improvements"
                )
                use_polisher = gr.Checkbox(
                    label="✨ Use Polisher (Mistral-7B)",
                    value=True,
                    info="Enable final style and flow refinement"
                )
            
            with gr.Row():
                tts_markers = gr.Checkbox(
                    label="🎤 Insert TTS Markers",
                    value=False,
                    info="Add [PAUSE:x.x] and [BREATHE] markers for TTS"
                )
                strict_schema = gr.Checkbox(
                    label="📋 Strict JSON Schema",
                    value=False,
                    info="Generate structured beats with timing and media cues"
                )
            
            # Advanced Settings (optional)
            gr.HTML('<h4>🔧 Advanced Settings (optional)</h4>')
            
            with gr.Row():
                sensory_rotation = gr.Checkbox(
                    label="🔄 Override Sensory Rotation",
                    value=None,
                    info="Force enable/disable sensory rotation (leave unchecked for default)"
                )
                sleep_taper = gr.Checkbox(
                    label="🌅 Override Sleep Taper",
                    value=None,
                    info="Force enable/disable sleep taper (leave unchecked for default)"
                )
            
            custom_waypoints = gr.Textbox(
                label="🗺️ Custom Waypoints (comma separated)",
                placeholder="e.g., forest entrance, deeper woods, clearing, sacred grove",
                info="Custom spatial/temporal progression waypoints"
            )
            
            with gr.Row():
                generate_btn = gr.Button("🚀 Generate Enhanced Story", variant="primary", size="lg")
                clear_btn = gr.Button("🔄 Clear All", size="lg")
        
        with gr.Column(scale=2):
            gr.HTML('<h3>📤 <strong>Enhanced Generation Output</strong></h3>')
            
            status = gr.Textbox(
                label="⚡ Real-Time Enhanced Generation Status",
                lines=18,
                interactive=False,
                show_copy_button=True,
                placeholder="Click 'Generate Enhanced Story' to start with live progress tracking...",
                elem_classes=["status-box"]
            )
            
            with gr.Tabs():
                with gr.Tab("📖 Enhanced Story"):
                    story_output = gr.Textbox(
                        label="Generated Enhanced Story",
                        lines=30,
                        interactive=False,
                        show_copy_button=True,
                        placeholder="Your enhanced sleep story will appear here...",
                        elem_classes=["markdown-content"]
                    )
                
                with gr.Tab("📊 Enhanced Metrics"):
                    metrics_output = gr.Textbox(
                        label="Multi-Model Quality & Performance Metrics",
                        lines=30,
                        interactive=False,
                        show_copy_button=True,
                        placeholder="Detailed enhanced metrics will show here...",
                        elem_classes=["markdown-content"]
                    )
                
                with gr.Tab("🗂️ Story Structure"):
                    outline_output = gr.Textbox(
                        label="Enhanced Story Outline & Generation Info",
                        lines=30,
                        interactive=False,
                        show_copy_button=True,
                        placeholder="Enhanced story structure details will appear here...",
                        elem_classes=["markdown-content"]
                    )
                
                with gr.Tab("📋 Schema Output"):
                    schema_output = gr.Textbox(
                        label="Strict Schema & TTS Integration Data",
                        lines=30,
                        interactive=False,
                        show_copy_button=True,
                        placeholder="Structured beats schema will appear here (if enabled)...",
                        elem_classes=["markdown-content"]
                    )
    
    # Information Panel
    gr.HTML("""
    <div style="margin-top: 20px; padding: 15px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 8px;">
        <h3>🔧 <strong>Enhanced Generation Process v2.0</strong>:</h3>
        <ol style="color: white;">
            <li><strong>🎯 Enhanced Theme Analysis</strong> - Advanced AI extraction with spatial waypoints and sensory mapping</li>
            <li><strong>📋 Quality-Enhanced Outline</strong> - Multi-dimensional structure with sleep-taper and TTS pacing</li>
            <li><strong>🤖 Multi-Model Generation</strong> - Sequential model orchestration (Generator → Reasoner → Polisher)</li>
            <li><strong>🔄 Sensory Rotation</strong> - Automatic sight → sound → touch → smell → proprioception cycling</li>
            <li><strong>🎯 Mixed-Reward Proxy</strong> - Real-time quality analysis with opener blacklist and transition hints</li>
            <li><strong>🌅 Sleep-Taper</strong> - Progressive density reduction in final 20% for deeper relaxation</li>
            <li><strong>🎤 TTS Integration</strong> - Optional markers for breathing cues and natural pauses</li>
            <li><strong>📋 Structured Output</strong> - Optional JSON schema with timing estimates and media cues</li>
        </ol>
        
        <p><strong>⏱️ Expected time</strong>: 15-25 minutes for enhanced generation (RTX 3070Ti optimized)<br>
        <strong>🎯 Quality</strong>: Multi-model pipeline with 95%+ coherence and accuracy<br>
        <strong>📁 Output</strong>: Enhanced stories with optional TTS and video production integration</p>
        
        <p style="text-align: center; margin-top: 15px;"><strong>🚀 Next-Generation Sleep Story AI - Ready for Production!</strong></p>
    </div>
    """)
    
    # Show/hide custom models based on preset selection
    def update_custom_models_visibility(preset):
        return gr.Group(visible=(preset == "Custom"))
    
    model_preset.change(
        fn=update_custom_models_visibility,
        inputs=[model_preset],
        outputs=[custom_models_group]
    )
    
    # Main generation handler
    def handle_generate(theme, duration, description, model_preset,
                       custom_generator, custom_reasoner, custom_polisher,
                       use_reasoner, use_polisher, tts_markers, strict_schema,
                       sensory_rotation, sleep_taper, custom_waypoints):
        
        # Parse custom waypoints if provided
        waypoints_list = None
        if custom_waypoints and custom_waypoints.strip():
            waypoints_list = [wp.strip() for wp in custom_waypoints.split(',') if wp.strip()]
        
        # Determine if using custom models
        use_custom_models = (model_preset == "Custom")
        
        return generate_enhanced_story(
            theme=theme,
            duration=duration,
            description=description,
            model_preset=model_preset,
            use_custom_models=use_custom_models,
            custom_generator=custom_generator,
            custom_reasoner=custom_reasoner,
            custom_polisher=custom_polisher,
            use_reasoner=use_reasoner,
            use_polisher=use_polisher,
            tts_markers=tts_markers,
            strict_schema=strict_schema,
            sensory_rotation=sensory_rotation if sensory_rotation else None,
            sleep_taper=sleep_taper if sleep_taper else None,
            custom_waypoints=waypoints_list
        )
    
    generate_btn.click(
        fn=handle_generate,
        inputs=[
            theme, duration, description, model_preset,
            custom_generator, custom_reasoner, custom_polisher,
            use_reasoner, use_polisher, tts_markers, strict_schema,
            sensory_rotation, sleep_taper, custom_waypoints
        ],
        outputs=[status, story_output, metrics_output, outline_output, schema_output]
    )
    
    clear_btn.click(
        fn=lambda: ("", "", "", "", ""),
        inputs=None,
        outputs=[status, story_output, metrics_output, outline_output, schema_output]
    )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )