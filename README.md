# Sleep Stories AI - Enhanced v2.0 🌙

> **Next-Generation AI-Powered Sleep Story Generator with Multi-Model Architecture**

[![Version](https://img.shields.io/badge/version-2.0.0--enhanced-blue)](https://github.com/HubbleBana/content-generation)
[![RTX 3070Ti Optimized](https://img.shields.io/badge/RTX%203070Ti-Optimized-green)](https://github.com/HubbleBana/content-generation)
[![Multi-Model](https://img.shields.io/badge/Multi--Model-Pipeline-purple)](https://github.com/HubbleBana/content-generation)

A comprehensive AI system for generating high-quality sleep stories with advanced features including multi-model orchestration, sensory rotation, TTS integration, and structured output for YouTube content creation.

## 🎆 Enhanced Features v2.0

### 🤖 Multi-Model Architecture
- **Sequential Model Loading**: Optimized for RTX 3070Ti (8GB VRAM)
- **Generator**: qwen2.5:7b (Primary story creation)
- **Reasoner**: deepseek-r1:8b (Logic and coherence)
- **Polisher**: mistral:7b (Style refinement)
- **Retry & Fallback**: Automatic error handling with model fallbacks

### 🎯 Quality Enhancements
- **Sensory Rotation**: Automatic cycling (sight → sound → touch → smell → proprioception)
- **Dynamic Waypoints**: Spatial/temporal progression based on story setting
- **Mixed-Reward Proxy**: Real-time quality analysis with penalties for:
  - Repeated openers
  - Missing transitions
  - Sensory redundancy
- **Recursive Planning**: state → micro-goal → gentle change → settling
- **Dynamic Opener Blacklist**: Auto-expansion based on usage detection
- **Sleep-Taper**: Progressive density reduction in final 20%

### 🎤 TTS Integration
- **TTS Markers**: Optional `[PAUSE:x.x]` and `[BREATHE]` insertion
- **Natural Pacing**: Calculated positioning for optimal speech rhythm
- **XTTS-v2 Compatible**: Ready for voice synthesis pipeline

### 📋 Structured Output
- **Strict JSON Schema**: Beats with timing estimates and media cues
- **Video Production Ready**: Structured data for YouTube automation
- **Length Control**: ±10% precision for exact timing requirements

## 🛠️ Quick Start

### Prerequisites
- **GPU**: RTX 3070Ti (8GB VRAM) or equivalent
- **Docker & Docker Compose**
- **Ollama**: For local LLM hosting

### Installation

1. **Clone the repository**:
```bash
git clone https://github.com/HubbleBana/content-generation.git
cd content-generation
```

2. **Install required models** (via Ollama):
```bash
# Core models for RTX 3070Ti
ollama pull qwen2.5:7b      # Generator (primary)
ollama pull deepseek-r1:8b  # Reasoner (optional)
ollama pull mistral:7b      # Polisher (optional)
```

3. **Start the enhanced system**:
```bash
docker-compose up -d
```

4. **Access the Enhanced UI**:
- **Gradio Interface**: http://localhost:7860
- **API Documentation**: http://localhost:8000/docs
- **Enhanced Health Check**: http://localhost:8000/api/health/enhanced

## 📋 API Reference

### Enhanced Story Generation

```http
POST /api/generate/story
Content-Type: application/json

{
  "theme": "A peaceful mountain meadow at dawn",
  "duration": 45,
  "description": "Focus on gentle morning sounds and soft light",
  "models": {
    "generator": "qwen2.5:7b",
    "reasoner": "deepseek-r1:8b",
    "polisher": "mistral:7b"
  },
  "use_reasoner": true,
  "use_polish": true,
  "tts_markers": true,
  "strict_schema": true
}
```

### Model Presets

```http
GET /api/models/presets
```

Response:
```json
{
  "presets": {
    "quality_high": {
      "generator": "qwen2.5:7b",
      "reasoner": "deepseek-r1:8b", 
      "polisher": "mistral:7b"
    },
    "fast": {
      "generator": "qwen2.5:7b"
    }
  }
}
```

### Enhanced Response Format

```json
{
  "job_id": "uuid",
  "story_text": "Generated story with optional TTS markers...",
  "outline": "Structured story outline...",
  "metrics": {
    "generator_words": 1200,
    "reasoner_words": 1180,
    "polisher_words": 1195,
    "corrections_count": 5,
    "coherence_improvements": 3,
    "enhanced_features_used": {
      "sensory_rotation": true,
      "sleep_taper": true,
      "tts_markers": true
    }
  },
  "coherence_stats": {
    "sensory_transitions": 5,
    "avg_density_factor": 0.85
  },
  "beats_schema": {  // If strict_schema=true
    "beats": [
      {
        "beat_index": 0,
        "text": "Story content...",
        "sensory_mode": "sight",
        "timing_estimate": 45.2,
        "media_cues": {
          "visual_focus": true,
          "ambient_suggestion": "mountain meadow"
        }
      }
    ],
    "total_estimated_duration": 2700
  }
}
```

## 🎬 YouTube Integration Guide

### TTS Pipeline Integration

1. **Generate story with TTS markers**:
```python
response = requests.post('/api/generate/story', json={
    "theme": "Your theme",
    "tts_markers": True,
    "strict_schema": True
})
```

2. **Extract TTS-ready text**:
```python
story_text = response.json()['story_text']
# Contains: "Welcome to this peaceful place. [PAUSE:2.0] As you settle in... [BREATHE]"
```

3. **Process with XTTS-v2**:
```python
# Your XTTS-v2 integration code here
# Parse [PAUSE:x.x] and [BREATHE] markers for natural speech
```

### Video Production Integration

1. **Use strict schema for timing**:
```python
beats_schema = response.json()['beats_schema']
for beat in beats_schema['beats']:
    print(f"Beat {beat['beat_index']}: {beat['timing_estimate']}s")
    print(f"Visual focus: {beat['media_cues']['visual_focus']}")
    print(f"Ambient: {beat['media_cues']['ambient_suggestion']}")
```

2. **Generate images per beat**:
```python
# Use sensory_mode and ambient_suggestion for image prompts
# Use timing_estimate for video segment duration
```

## 📊 Performance Optimization

### RTX 3070Ti Configuration

The system is optimized for RTX 3070Ti (8GB VRAM):

- **Sequential Loading**: Only one model in VRAM at a time
- **Model Sizes**: 
  - qwen2.5:7b: ~4.1GB VRAM
  - deepseek-r1:8b: ~4.7GB VRAM 
  - mistral:7b: ~4.1GB VRAM
- **Automatic Unloading**: Models unloaded between stages

### Performance Metrics

| Configuration | Generation Time | Quality Score | VRAM Usage |
|---------------|----------------|---------------|------------|
| Quality High | 15-25 minutes | 95%+ | 4.7GB peak |
| Fast | 8-12 minutes | 85%+ | 4.1GB peak |

### Scaling Recommendations

- **RTX 4070+**: Can run multiple models simultaneously
- **RTX 3060**: Use "Fast" preset only
- **CPU Only**: Fallback mode available (very slow)

## 📝 Configuration Options

### Environment Variables

```bash
# Core settings
OLLAMA_URL=http://ollama:11434
DATA_PATH=/app/data

# Enhanced settings (optional)
SENSORY_ROTATION_ENABLED=true
SLEEP_TAPER_ENABLED=true
BEAT_PLANNING_ENABLED=true
MAX_CONCURRENT_MODELS=1
MAX_RETRIES=3
FALLBACK_MODEL=qwen2.5:7b
```

### Docker Compose Override

```yaml
# docker-compose.override.yml
version: '3.8'
services:
  backend:
    environment:
      - SENSORY_ROTATION_ENABLED=true
      - SLEEP_TAPER_ENABLED=true
      - TTS_MARKERS_ENABLED=false
      - MAX_CONCURRENT_MODELS=1
```

## 🤖 Advanced Usage

### Custom Model Configuration

```python
# Use different models for different stages
response = requests.post('/api/generate/story', json={
    "theme": "Your theme",
    "models": {
        "generator": "llama3.1:8b",    # Alternative generator
        "reasoner": "deepseek-r1:8b",  # Keep reasoner
        "polisher": "qwen2.5:7b"       # Alternative polisher
    },
    "use_reasoner": True,
    "use_polish": True
})
```

### Batch Processing

```python
# Generate multiple stories with different configurations
themes = [
    "Forest clearing at twilight",
    "Ocean waves on sandy beach", 
    "Mountain cabin in winter"
]

for theme in themes:
    job = requests.post('/api/generate/story', json={
        "theme": theme,
        "tts_markers": True,
        "strict_schema": True
    })
    # Monitor job progress via /api/generate/{job_id}/stream
```

## 🗺️ Roadmap

### Version 2.1 (Planned)
- [ ] **Multi-Language Support**: Direct generation in Italian, French, Spanish
- [ ] **Voice Cloning Integration**: XTTS-v2 voice selection
- [ ] **Advanced Video Generation**: Automated image generation per beat
- [ ] **Real-time Streaming**: Live story generation for interactive sessions

### Version 2.2 (Future)
- [ ] **Emotion Tracking**: Mood progression analysis and optimization
- [ ] **Biometric Integration**: Heart rate and sleep stage adaptation
- [ ] **Custom Voice Training**: Personal voice model support
- [ ] **Interactive Narratives**: Branching story paths

## 🐛 Troubleshooting

### Common Issues

**Q: Models not loading on RTX 3070Ti**
```bash
# Check VRAM usage
nvidia-smi

# Ensure sequential loading
echo "MAX_CONCURRENT_MODELS=1" >> .env
```

**Q: Generation fails with "CUDA out of memory"**
```bash
# Use fast preset
echo "DEFAULT_PRESET=fast" >> .env

# Or reduce model sizes
ollama pull qwen2:7b  # Smaller alternative
```

**Q: TTS markers not appearing**
```json
{
  "tts_markers": true,  // Must be explicitly enabled
  "strict_schema": true  // Recommended for TTS integration
}
```

### Debug Mode

```bash
# Enable debug logging
echo "LOG_LEVEL=DEBUG" >> .env
docker-compose restart backend

# Check logs
docker-compose logs -f backend
```

## 🎆 Contributing

We welcome contributions to the Enhanced Sleep Stories AI project!

### Development Setup

```bash
# Clone repository
git clone https://github.com/HubbleBana/content-generation.git
cd content-generation

# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Run linting
flake8 backend/
black backend/
```

### Enhancement Areas

- **Model Optimization**: New model configurations for different hardware
- **Quality Features**: Additional sensory and narrative enhancements
- **TTS Integration**: Advanced speech synthesis features
- **Video Generation**: Automated visual content creation
- **Performance**: Speed and memory optimizations

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 📧 Support

- **Issues**: [GitHub Issues](https://github.com/HubbleBana/content-generation/issues)
- **Discussions**: [GitHub Discussions](https://github.com/HubbleBana/content-generation/discussions)
- **Documentation**: [Wiki](https://github.com/HubbleBana/content-generation/wiki)

---

**🌙 Sleep Stories AI v2.0 - Where Technology Meets Tranquility**

*Optimized for RTX 3070Ti • Production-Ready • YouTube Integration • Multi-Model Excellence*