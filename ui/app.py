import gradio as gr
import requests
import json
import time
import os
from typing import Optional, Generator
import threading
from queue import Queue, Empty
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

def generate_story_with_sse(theme: str, duration: int, description: Optional[str] = None, include_italian: bool = True, translation_quality: str = "high"):
    """Generate story with Server-Sent Events for real-time updates"""
    
    start_time = time.time()
    
    try:
        # Start generation - sempre inglese come base
        response = requests.post(
            f"{API_URL}/generate/story",
            json={
                "theme": theme,
                "duration": duration, 
                "description": description or None,
                "language": "it" if include_italian else "en",
                "translation_quality": translation_quality
            },
            timeout=30
        )
        
        if response.status_code != 200:
            yield f"❌ Error starting generation: {response.text}", "", "", "", ""
            return
        
        job_data = response.json()
        job_id = job_data["job_id"]
        
        # Initialize status
        def build_status(progress, current_step, step_num, total_steps, elapsed_time):
            return f"""🚀 **Sleep Stories AI Generator**

📋 Job ID: `{job_id}`
🇬🇧 Base: **ENGLISH** | 🇮🇹 Italian: **{"YES" if include_italian else "NO"}** | ⚡ Quality: **{translation_quality}**
⏱️ Elapsed: **{elapsed_time}**

**Status**: PROCESSING
**Step**: {step_num}/{total_steps} - {current_step}
**Progress**: {progress:.1f}%

[{"🟩" * int(progress/2.5)}{"⬜" * (40-int(progress/2.5))}] {progress:.1f}%

{"🔤 **Phase**: English Generation" if step_num <= 4 else "🇮🇹 **Phase**: Italian Translation" if step_num <= 6 else "✨ **Phase**: Final Processing"}"""
        
        # Initial status
        elapsed = "00:00"
        initial_status = build_status(0, "Connecting to real-time stream...", 0, 8, elapsed)
        yield initial_status, "", "", "", ""
        
        # Connect to SSE stream
        current_status = initial_status
        
        try:
            with SSEClient(f"{API_URL}/generate/{job_id}/stream") as sse:
                for event_data in sse.events():
                    # Calculate elapsed time
                    elapsed_seconds = int(time.time() - start_time)
                    elapsed = str(timedelta(seconds=elapsed_seconds))[2:7]
                    
                    status = event_data.get('status', 'processing')
                    progress = event_data.get('progress', 0)
                    current_step = event_data.get('current_step', 'Processing...')
                    step_num = event_data.get('current_step_number', 0) 
                    total_steps = event_data.get('total_steps', 8)
                    
                    current_status = build_status(progress, current_step, step_num, total_steps, elapsed)
                    yield current_status, "", "", "", ""
                    
                    # Check for completion
                    if status == 'completed':
                        break
                    elif status == 'failed':
                        error_msg = event_data.get('error', 'Unknown error occurred')
                        final_elapsed = str(timedelta(seconds=int(time.time() - start_time)))[2:7]
                        error_status = current_status + f"\n\n❌ **FAILED** after {final_elapsed}: {error_msg}"
                        yield error_status, "", "", "", ""
                        return
        
        except Exception as sse_error:
            elapsed = str(timedelta(seconds=int(time.time() - start_time)))[2:7]
            fallback_status = build_status(10, f"SSE failed - Using polling...", 1, 8, elapsed)
            yield fallback_status, "", "", "", ""
            
            # Fallback to polling (simplified)
            time.sleep(5)
        
        # Get final results
        try:
            result_response = requests.get(f"{API_URL}/generate/{job_id}/result", timeout=30)
            if result_response.status_code != 200:
                final_elapsed = str(timedelta(seconds=int(time.time() - start_time)))[2:7]
                yield current_status + f"\n❌ Error getting results after {final_elapsed}", "", "", "", ""
                return
                
            result = result_response.json()
            
            # Calculate final elapsed time
            total_elapsed = str(timedelta(seconds=int(time.time() - start_time)))[2:7]
            
            # Extract results
            story_english = result.get('story_text_english', result.get('story_text', ''))
            story_italian = result.get('story_text', '') if include_italian else ""
            metrics = result.get('metrics', {})
            translation_metrics = result.get('translation_metrics', {})
            coherence_stats = result.get('coherence_stats', {})
            outline = result.get('outline', {})
            
            # Format comprehensive metrics
            metrics_text = f"""📊 **GENERATION METRICS**

⏱️ **Performance**:
- Total Generation Time: {total_elapsed}
- Target Duration: {duration} minutes
- Translation: {"ENABLED" if include_italian else "DISABLED"}

📝 **Word Counts**:
- English Words: {metrics.get('english_word_count', 0):,}
{"- Italian Words: " + str(metrics.get('final_word_count', 0)) + "," if include_italian else ""}
- Target Words: {metrics.get('target_words', 0):,}
- Accuracy: {metrics.get('accuracy_percent', 0):.1f}% deviation

📖 **Story Structure**:
- Duration Estimate: {metrics.get('duration_estimate_minutes', 0):.1f} minutes
- Beats Generated: {metrics.get('beats_generated', 0)}

{"🇮🇹 **Translation Quality**:" if include_italian else ""}
{f"- Pace Ratio: {translation_metrics.get('pace_ratio', 1.0):.3f}" if include_italian else ""}
{f"- Chunks Processed: {translation_metrics.get('chunks_processed', 0)}" if include_italian else ""}

🧠 **Coherence System**:
- Characters Tracked: {coherence_stats.get('tracked_characters', 0)}
- Locations Tracked: {coherence_stats.get('tracked_locations', 0)}
- Objects Tracked: {coherence_stats.get('tracked_objects', 0)}
- Repetitions Avoided: {coherence_stats.get('forbidden_repetitions', 0)}"""
            
            # Format outline
            outline_text = f"""📖 **STORY STRUCTURE**

🌍 **Setting**:
- Location: {outline.get('story_bible', {}).get('setting', 'N/A')}
- Time: {outline.get('story_bible', {}).get('time_of_day', 'N/A')}
- Mood Baseline: {outline.get('story_bible', {}).get('mood_baseline', 'N/A')}/10

🎭 **Structure**:
- Acts: {len(outline.get('acts', []))}
- Total Beats: {sum(len(act.get('beats', [])) for act in outline.get('acts', []))}

📚 **Story Bible Objects**:
{', '.join(outline.get('story_bible', {}).get('key_objects', ['None']))}

⏱️ **Generation Timeline**:
- Total Time: {total_elapsed}
- Average per Beat: {int(time.time() - start_time) // max(metrics.get('beats_generated', 1), 1)}s per beat"""
            
            # Final status
            final_status = build_status(100, "Generation complete!", 8, 8, total_elapsed)
            final_status += f"\n\n✅ **GENERATION COMPLETE!**\n🇬🇧 English story ready\n{'🇮🇹 Italian translation ready' if include_italian else ''}\n📁 Files saved to volume\n⏱️ **Total time: {total_elapsed}**"
            
            yield final_status, story_english, metrics_text, outline_text, story_italian
            
        except Exception as e:
            final_elapsed = str(timedelta(seconds=int(time.time() - start_time)))[2:7]
            yield current_status + f"\n❌ Error processing results after {final_elapsed}: {str(e)}", "", "", "", ""
            
    except Exception as e:
        elapsed = str(timedelta(seconds=int(time.time() - start_time)))[2:7] 
        yield f"❌ **Generation Error** after {elapsed}: {str(e)}", "", "", "", ""

# Create Enhanced Gradio Interface
with gr.Blocks(title="Sleep Stories AI - Dual Output", theme=gr.themes.Soft()) as demo:
    
    # Custom CSS for proper markdown rendering
    demo.css = """
    .markdown-content {
        line-height: 1.6;
    }
    .status-box textarea {
        font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
        line-height: 1.4;
    }
    """
    
    gr.HTML("""
    <div style="text-align: center; margin-bottom: 20px;">
        <h1>🌙 Sleep Stories AI - <strong>Dual Language Generator</strong></h1>
        <p><strong>🇬🇧 AI-powered English story generation with optional 🇮🇹 Italian translation</strong></p>
    </div>
    """)
    
    with gr.Row():
        with gr.Column(scale=1):
            gr.HTML("<h3>📝 <strong>Story Configuration</strong></h3>")
            
            theme = gr.Textbox(
                label="🌍 Theme / Setting",
                placeholder="e.g., A peaceful Scottish Highland lake at dawn",
                value="A tranquil Italian countryside vineyard at sunset",
                info="Main setting/location for the story (describe in English)"
            )
            
            description = gr.Textbox(
                label="📋 Additional Details (optional)",
                placeholder="Focus on water sounds and gentle breeze...",
                lines=3,
                info="Extra guidance for the AI"
            )
            
            with gr.Row():
                duration = gr.Slider(
                    label="⏱️ Duration (minutes)",
                    minimum=20,
                    maximum=60,
                    value=45,
                    step=5,
                    info="Target story duration"
                )
                
                include_italian = gr.Checkbox(
                    label="🇮🇹 Include Italian Translation",
                    value=True,
                    info="Generate Italian version alongside English"
                )
            
            translation_quality = gr.Radio(
                label="⚡ Translation Quality (if Italian enabled)",
                choices=[("🚀 High Quality", "high"), ("⚡ Fast", "fast")],
                value="high",
                info="Quality vs speed for translation"
            )
            
            with gr.Row():
                generate_btn = gr.Button("🎬 Generate Story", variant="primary", size="lg")
                clear_btn = gr.Button("🔄 Clear All", size="lg")
        
        with gr.Column(scale=2):
            gr.HTML("<h3>📤 <strong>Generation Output</strong></h3>")
            
            status = gr.Textbox(
                label="⚡ Real-Time Generation Status",
                lines=12,
                interactive=False,
                show_copy_button=True,
                placeholder="Click 'Generate Story' to start with live progress...",
                elem_classes=["status-box"]
            )
            
            with gr.Tabs():
                with gr.Tab("📖 English Story"):
                    story_english_output = gr.Textbox(
                        label="Generated English Story",
                        lines=25,
                        interactive=False,
                        show_copy_button=True,
                        placeholder="Your English sleep story will appear here...",
                        elem_classes=["markdown-content"]
                    )
                
                with gr.Tab("🇮🇹 Italian Version"):
                    story_italian_output = gr.Textbox(
                        label="Translated Italian Story",
                        lines=25,
                        interactive=False,
                        show_copy_button=True,
                        placeholder="Italian translation will appear here (if enabled)...",
                        elem_classes=["markdown-content"]
                    )
                
                with gr.Tab("📊 Advanced Metrics"):
                    metrics_output = gr.Textbox(
                        label="Quality & Translation Metrics",
                        lines=20,
                        interactive=False,
                        placeholder="Detailed metrics will show here...",
                        elem_classes=["markdown-content"]
                    )
                
                with gr.Tab("🗂️ Story Structure"):
                    outline_output = gr.Textbox(
                        label="Story Outline & Bible",
                        lines=20,
                        interactive=False,
                        placeholder="Story structure details will appear here...",
                        elem_classes=["markdown-content"]
                    )
    
    gr.HTML("""
    <div style="margin-top: 20px; padding: 15px; background-color: #f0f0f0; border-radius: 8px;">
        <h3>🔧 <strong>Enhanced Generation Process</strong>:</h3>
        <ol>
            <li><strong>🧩 Theme Analysis</strong> - AI extracts sensory and cultural elements</li>
            <li><strong>📋 Outline Generation</strong> - Creates detailed 3-act structure optimized for sleep</li>
            <li><strong>🇬🇧 English Generation</strong> - Writes story in English for optimal LLM quality</li>
            <li><strong>🧠 Coherence Validation</strong> - Tracks entities, avoids repetition, maintains consistency</li>
            <li><strong>🇮🇹 Italian Translation</strong> - High-quality translation preserving pace and rhythm (optional)</li>
            <li><strong>✨ Final Polish</strong> - Quality assurance and TTS timing optimization</li>
        </ol>
        
        <p><strong>⏱️ Expected time</strong>: 25-35 minutes for English only, 35-45 minutes with Italian translation<br>
        <strong>🎯 Accuracy</strong>: ~95% word count precision for TTS timing<br>
        <strong>📁 Output</strong>: Dual language versions saved to Docker volume</p>
        
        <p style="text-align: center; margin-top: 15px;"><strong>🚀 Ready to generate your dual-language sleep story!</strong></p>
    </div>
    """)
    
    # Event handlers
    generate_btn.click(
        fn=generate_story_with_sse,
        inputs=[theme, duration, description, include_italian, translation_quality],
        outputs=[status, story_english_output, metrics_output, outline_output, story_italian_output]
    )
    
    clear_btn.click(
        fn=lambda: ("", "", "", "", ""),
        inputs=None,
        outputs=[status, story_english_output, metrics_output, outline_output, story_italian_output]
    )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )
