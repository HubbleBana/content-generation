# 🌙 Sleep Stories AI - Enhanced v2.0

**Next-Generation AI-Powered Sleep Story Generator with Multi-Model Architecture**

🎆 **COMPLETELY REWRITTEN FRONTEND** - Now with real-time streaming, enhanced UI, and full Gradio 4.44+ compatibility!

---

## 🚀 **New in v2.0**

### ✅ **Frontend Completely Rewritten**
- **Real-time streaming** with Server-Sent Events
- **Working job management** with functional dropdowns
- **All parameters exposed** - complete backend control
- **Modern responsive UI** with glassmorphism design
- **Gradio 4.44+ compatible** - no more compatibility errors

### ✅ **Technical Improvements**
- **Modular architecture** with separated components
- **Enhanced API client** with SSE and fallback polling  
- **Optimized for RTX 3070Ti** with proper resource management
- **Docker improvements** with health checks and troubleshooting

### ✅ **Issues Resolved**
- **✅ Stream updates working** - real-time progress tracking
- **✅ Dropdown menus fixed** - job selection now functional
- **✅ Parameter exposure complete** - all backend options available
- **✅ Gradio compatibility** - updated for 4.44+ versions

---

## 🏗️ **System Requirements**

### **Hardware**
- **GPU**: RTX 3070Ti (8GB VRAM) or equivalent NVIDIA GPU
- **RAM**: 16GB+ recommended
- **Storage**: 20GB+ free space for models and data

### **Software**
- **Docker** with NVIDIA runtime support
- **Docker Compose** v2.0+
- **NVIDIA Drivers** 470.x+ with CUDA support

---

## 🚀 **Quick Start**

### **1. Clone Repository**
```bash
git clone https://github.com/HubbleBana/content-generation.git
cd content-generation
```

### **2. Switch to Enhanced Branch**
```bash
git checkout frontend-rewrite-v2
```

### **3. Create Docker Volume**
```bash
docker volume create sleepai_volume
```

### **4. Start Services**
```bash
# Standard startup
docker-compose up --build

# Or use troubleshooting script if Ollama has issues
chmod +x scripts/fix-ollama.sh
./scripts/fix-ollama.sh
```

### **5. Access Application**
- **Frontend UI**: http://localhost:7860
- **Backend API**: http://localhost:8000/docs
- **Ollama API**: http://localhost:11434

---

## 🎯 **Features Overview**

### 🎨 **Story Generation**
- **Multi-model orchestration** (Generator + Reasoner + Polisher)
- **Sensory rotation** with systematic sensory cycling
- **Sleep taper** with progressive relaxation
- **TTS markers** for speech synthesis integration
- **JSON schema output** for video production

### 🔍 **Real-time Monitoring**
- **Live progress tracking** with beat-by-beat updates
- **Job management** with attachment and resuming
- **System telemetry** with resource monitoring
- **Quality metrics** with automated assessment

### 🎥 **YouTube Integration Ready**
- **Structured output** with timing and media cues
- **TTS-ready text** with pause and breath markers
- **Video segments** with visual focus suggestions
- **Export functionality** for production workflows

---

## 📊 **Architecture**

### **Frontend (Enhanced v2.0)**
```
ui/
├── app.py                    # Main Gradio application
├── components/
│   ├── generation_panel.py   # Generation controls
│   ├── monitoring_panel.py   # Real-time monitoring
│   └── results_panel.py      # Results and analysis
├── utils/
│   ├── api_client.py         # Enhanced API client with SSE
│   └── helpers.py            # Utility functions
└── static/
    └── custom.css            # Modern UI styling
```

### **Backend (Multi-Model)**
- **FastAPI** with streaming endpoints
- **Multi-model orchestration** for quality enhancement
- **Real-time telemetry** with detailed progress tracking
- **Structured output** for video production pipelines

### **Infrastructure**
- **Docker Compose** with health checks
- **Ollama** for local LLM hosting
- **NVIDIA GPU** optimization for RTX 3070Ti
- **Volume management** for persistent data

---

## 🔧 **Configuration**

### **Environment Variables**
```bash
# Core Configuration
OLLAMA_URL=http://ollama:11434
DATA_PATH=/app/data
LOG_LEVEL=INFO

# GPU Optimization
MAX_CONCURRENT_MODELS=1
OLLAMA_MAX_LOADED_MODELS=1
OLLAMA_KEEP_ALIVE=5m

# Enhanced Features
SENSORY_ROTATION_ENABLED=true
SLEEP_TAPER_ENABLED=true
BEAT_PLANNING_ENABLED=true

# UI Configuration
UI_AUTO_REFRESH=true
UI_STREAMING_ENABLED=true
GRADIO_ANALYTICS_ENABLED=false
```

### **Model Presets**
- **Quality High**: All models enabled (15-25 min generation)
- **Balanced**: Generator + Reasoner (10-15 min generation)
- **Fast**: Generator only (5-10 min generation)
- **Custom**: User-defined model configuration

---

## 🐛 **Troubleshooting**

### **Ollama Container Issues**
```bash
# Use the automated fix script
./scripts/fix-ollama.sh

# Or debug manually
docker-compose -f docker-compose.debug.yml up ollama
```

### **Gradio Compatibility Issues**
The system is now **fully compatible with Gradio 4.44+**. All compatibility issues have been resolved:
- ✅ Queue configuration updated
- ✅ Event handlers modernized
- ✅ Component parameters cleaned

See `GRADIO_4_44_COMPATIBILITY.md` for full details.

### **Common Issues**

**Q: Stream updates not appearing**
- ✅ Fixed in v2.0 with proper SSE implementation

**Q: Job dropdown not working**
- ✅ Fixed in v2.0 with enhanced job management

**Q: Missing parameters in UI**
- ✅ Fixed in v2.0 - all backend parameters now exposed

**Q: Container hanging on startup**
- Use `./scripts/fix-ollama.sh` for automated diagnosis and fix

---

## 📈 **Performance**

### **RTX 3070Ti Optimized**
- **Sequential model loading** to stay within 8GB VRAM
- **Memory management** with automatic cleanup
- **Queue optimization** for GPU resource allocation

### **Generation Times**
|Configuration|Duration|Quality Score|VRAM Usage|
|-------------|--------|-------------|----------|
|Quality High|15-25 min|95%+|4.7GB peak|
|Balanced|10-15 min|90%+|4.1GB peak|
|Fast|5-10 min|85%+|4.1GB peak|

---

## 📁 **Documentation**

- **Frontend Rewrite**: `FRONTEND_REWRITE_V2.md`
- **Gradio Compatibility**: `GRADIO_4_44_COMPATIBILITY.md`  
- **API Documentation**: http://localhost:8000/docs
- **Troubleshooting**: `scripts/fix-ollama.sh`

---

## 🤝 **Contributing**

### **Development Setup**
```bash
# Clone and setup
git clone https://github.com/HubbleBana/content-generation.git
cd content-generation
git checkout frontend-rewrite-v2

# Install development dependencies
pip install -r ui/requirements.txt
pip install -r backend/requirements.txt

# Run in development mode
cd ui && python app.py
```

### **Pull Request Guidelines**
- **Frontend changes**: Update components in `ui/components/`
- **API changes**: Update backend in `backend/app/api/`
- **Documentation**: Update relevant `.md` files
- **Testing**: Ensure compatibility with Gradio 4.44+

---

## 📝 **License**

MIT License - see `LICENSE` for details.

---

## 👥 **Team**

- **John**: AI Specialist & System Architecture
- **Carl**: Social Media Manager & Content Strategy  
- **Jimmy**: Frontend Expert & UI/UX (v2.0 Rewrite)

---

## 🎆 **Status**

**✅ PRODUCTION READY** - Enhanced v2.0

- ✅ **Real-time streaming** working
- ✅ **Job management** functional
- ✅ **All parameters** exposed
- ✅ **Gradio 4.44+** compatible
- ✅ **Docker optimized** with troubleshooting
- ✅ **RTX 3070Ti** performance tuned
- ✅ **YouTube integration** ready

**Ready for YouTube content generation! 🚀🌙**

---

*Sleep Stories AI - Where Technology Meets Tranquility*
