import gradio as gr
import requests
import time
import os
from typing import Optional

API_URL = os.getenv("API_URL", "http://backend:8000/api")

def generate_story(theme: str, duration: int, description: Optional[str] = None):
    try:
        # Start generation
        response = requests.post(
            f"{API_URL}/generate/story",
            json={
                "theme": theme,
                "duration": duration,
                "description": description or None
            },
            timeout=300000
        )
        
        if response.status_code != 200:
            yield f"❌ Error: {response.text}", "", "", ""
            return
        
        job_id = response.json()["job_id"]
        
        # Poll for status
        status_text = f"🚀 Job ID: {job_id}\n\nInitializing...\n"
        
        while True:
            try:
                status_response = requests.get(
                    f"{API_URL}/generate/{job_id}/status",
                    timeout=3000
                )
                
                if status_response.status_code != 200:
                    yield status_text + "\n❌ Error checking status", "", "", ""
                    return
                
                status = status_response.json()
                
                # Build status display
                status_lines = [
                    f"📋 Job ID: {job_id}",
                    f"",
                    f"Status: {status['status'].upper()}",
                    f"Progress: {status['progress']:.1f}%",
                    f"Current: {status['current_step']}",
                    f"",
                ]
                
                # Progress bar
                progress = status['progress']
                bar_length = 30
                filled = int(bar_length * progress / 100)
                bar = '█' * filled + '░' * (bar_length - filled)
                status_lines.append(f"[{bar}] {progress:.1f}%")
                
                status_text = "\n".join(status_lines)
                
                yield status_text, "", "", ""
                
                # Check completion
                if status['status'] == 'completed':
                    # Get result
                    result_response = requests.get(
                        f"{API_URL}/generate/{job_id}/result",
                        timeout=30
                    )
                    result = result_response.json()
                    
                    story_text = result.get('story_text', '')
                    metrics = result.get('metrics', {})
                    outline = result.get('outline', {})
                    
                    # Format metrics
                    metrics_text = f'''
📊 GENERATION METRICS:

Word Count: {metrics.get('word_count', 0):,}
Target Words: {metrics.get('target_words', 0):,}
Accuracy: {metrics.get('accuracy_percent', 0):.1f}% deviation
Duration: {metrics.get('duration_estimate_minutes', 0):.1f} minutes
Beats: {metrics.get('beats_generated', 0)}

Memory Stats:
- Total beats tracked: {result.get('memory_stats', {}).get('total_beats', 0)}
- Entities tracked: {result.get('memory_stats', {}).get('entities_tracked', 0)}
'''
                    
                    # Format outline summary
                    outline_text = f'''
📖 STORY STRUCTURE:

Setting: {outline.get('story_bible', {}).get('setting', 'N/A')}
Time: {outline.get('story_bible', {}).get('time_of_day', 'N/A')}
Mood: {outline.get('story_bible', {}).get('mood_baseline', 'N/A')}/10

Acts: {len(outline.get('acts', []))}
Total Beats: {sum(len(act.get('beats', [])) for act in outline.get('acts', []))}
'''
                    
                    final_status = status_text + "\n\n✅ GENERATION COMPLETE!"
                    
                    yield final_status, story_text, metrics_text, outline_text
                    break
                
                elif status['status'] == 'failed':
                    error = status.get('error', 'Unknown error')
                    yield status_text + f"\n\n❌ FAILED: {error}", "", "", ""
                    break
                
                time.sleep(3)  # Poll every 3 seconds
                
            except requests.exceptions.RequestException as e:
                yield status_text + f"\n\n⚠️ Connection error: {str(e)}", "", "", ""
                time.sleep(5)
    
    except Exception as e:
        yield f"❌ Error: {str(e)}", "", "", ""

# Create Gradio Interface
with gr.Blocks(title="Sleep Stories AI", theme=gr.themes.Soft()) as demo:
    gr.Markdown('''
    # 🌙 Sleep Stories AI Generator
    
    **AI-powered story generation with self-tuning and output validation**
    
    Features:
    - 🧠 Multi-layer generation system (DOME + SCORE)
    - 🔄 Automatic self-correction and quality tuning
    - ✅ JSON output validation with retry logic
    - 📊 Word count enforcement
    - 💾 All data stored in Docker volume
    
    *Week 1 MVP - Text generation only. Audio/Images/Video coming soon!*
    ''')
    
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 📝 Input")
            
            theme = gr.Textbox(
                label="Theme",
                placeholder="e.g., Scottish Highland lake at dawn",
                value="Scottish Highland lake at dawn",
                info="Main setting/location for the story"
            )
            
            description = gr.Textbox(
                label="Additional Details (optional)",
                placeholder="Focus on mist and water sounds...",
                lines=3,
                info="Extra guidance for the AI"
            )
            
            duration = gr.Slider(
                label="Duration (minutes)",
                minimum=20,
                maximum=60,
                value=45,
                step=5,
                info="Target story duration"
            )
            
            with gr.Row():
                generate_btn = gr.Button("🎬 Generate Story", variant="primary", size="lg")
                clear_btn = gr.Button("🔄 Clear", size="lg")
        
        with gr.Column(scale=2):
            gr.Markdown("### 📤 Output")
            
            status = gr.Textbox(
                label="⚡ Generation Status",
                lines=12,
                interactive=False,
                show_copy_button=True
            )
            
            with gr.Tabs():
                with gr.Tab("📖 Story Text"):
                    story_output = gr.Textbox(
                        label="Generated Story",
                        lines=25,
                        interactive=False,
                        show_copy_button=True
                    )
                
                with gr.Tab("📊 Metrics"):
                    metrics_output = gr.Textbox(
                        label="Quality Metrics",
                        lines=15,
                        interactive=False
                    )
                
                with gr.Tab("🗂️ Outline"):
                    outline_output = gr.Textbox(
                        label="Story Structure",
                        lines=15,
                        interactive=False
                    )
    
    gr.Markdown('''
    ### 🔧 How It Works:
    
    1. **Theme Analysis** - AI extracts sensory elements
    2. **Outline Generation** - Creates 3-act structure with beats
    3. **Beat Generation** - Writes story incrementally with self-tuning
    4. **Quality Check** - Self-refines for calmness and coherence
    5. **Output Validation** - Ensures JSON validity and word count
    
    ⏱️ **Expected time**: 25-35 minutes for 45-minute story
    
    📁 **Output location**: /app/data/outputs/{job_id}/ in Docker volume
    ''')
    
    # Event handlers
    generate_btn.click(
        fn=generate_story,
        inputs=[theme, duration, description],
        outputs=[status, story_output, metrics_output, outline_output]
    )
    
    clear_btn.click(
        fn=lambda: ("", "", "", ""),
        inputs=None,
        outputs=[status, story_output, metrics_output, outline_output]
    )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )
