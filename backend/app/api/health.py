from fastapi import APIRouter
import ollama
import requests
import psutil
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/health/system")
async def system_health():
    """Comprehensive system health check for RTX 3070Ti optimization"""
    
    health_data = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "system": await _get_system_metrics(),
        "ollama": await _check_ollama_health(),
        "gpu": await _get_gpu_metrics(),
        "models": await _check_model_availability(),
        "memory": await _get_memory_metrics(),
        "optimization": await _get_optimization_status()
    }
    
    # Determine overall status
    critical_issues = []
    warnings = []
    
    # Check critical systems
    if not health_data["ollama"]["available"]:
        critical_issues.append("Ollama service unavailable")
    
    if health_data["memory"]["available_gb"] < 4.0:
        critical_issues.append("Insufficient system RAM (< 4GB available)")
    
    if health_data["gpu"]["vram_available_gb"] < 2.0:
        critical_issues.append("Insufficient VRAM (< 2GB available)")
    
    # Check warnings
    if health_data["gpu"]["vram_available_gb"] < 4.0:
        warnings.append("Low VRAM - consider using smaller models")
    
    if health_data["system"]["cpu_usage_percent"] > 80:
        warnings.append("High CPU usage - may affect performance")
    
    if len(health_data["models"]["available_models"]) < 3:
        warnings.append("Missing recommended models for multi-model pipeline")
    
    health_data["status"] = "critical" if critical_issues else ("warning" if warnings else "healthy")
    health_data["issues"] = critical_issues
    health_data["warnings"] = warnings
    
    return health_data

@router.get("/health/performance")
async def performance_metrics():
    """Real-time performance metrics for monitoring"""
    
    return {
        "timestamp": datetime.now().isoformat(),
        "gpu": {
            "utilization_percent": await _get_gpu_utilization(),
            "memory_usage_percent": await _get_gpu_memory_usage(),
            "temperature_celsius": await _get_gpu_temperature()
        },
        "system": {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "ram_usage_percent": psutil.virtual_memory().percent,
            "disk_usage_percent": psutil.disk_usage('/').percent
        },
        "ollama": {
            "response_time_ms": await _measure_ollama_response_time(),
            "active_models": await _get_active_models()
        }
    }

@router.get("/health/recommendations")
async def optimization_recommendations():
    """Get optimization recommendations based on current system state"""
    
    health = await system_health()
    recommendations = []
    
    # GPU optimizations
    if health["gpu"]["vram_available_gb"] < 6.0:
        recommendations.append({
            "category": "gpu",
            "priority": "high",
            "recommendation": "Use sequential model loading (MAX_CONCURRENT_MODELS=1)",
            "explanation": "Limited VRAM requires careful memory management"
        })
    
    if health["gpu"]["vram_available_gb"] < 4.0:
        recommendations.append({
            "category": "models",
            "priority": "high", 
            "recommendation": "Use 'fast' preset instead of 'quality_high'",
            "explanation": "Smaller models required for current VRAM capacity"
        })
    
    # System optimizations
    if health["system"]["cpu_usage_percent"] > 70:
        recommendations.append({
            "category": "system",
            "priority": "medium",
            "recommendation": "Reduce ThreadPoolExecutor max_workers to 1",
            "explanation": "High CPU usage detected - limit concurrent operations"
        })
    
    # Model recommendations
    available_models = health["models"]["available_models"]
    if "qwen2.5:7b" not in available_models:
        recommendations.append({
            "category": "models",
            "priority": "high",
            "recommendation": "Install qwen2.5:7b model: ollama pull qwen2.5:7b",
            "explanation": "Primary generator model missing"
        })
    
    if "deepseek-r1:8b" not in available_models:
        recommendations.append({
            "category": "models",
            "priority": "medium",
            "recommendation": "Install deepseek-r1:8b model: ollama pull deepseek-r1:8b",
            "explanation": "Reasoner model missing - quality will be reduced"
        })
    
    # Memory recommendations
    if health["memory"]["available_gb"] < 8.0:
        recommendations.append({
            "category": "memory",
            "priority": "medium",
            "recommendation": "Close unnecessary applications to free system RAM",
            "explanation": "More RAM will improve model loading and processing speed"
        })
    
    return {
        "timestamp": datetime.now().isoformat(),
        "system_status": health["status"],
        "recommendations": recommendations,
        "current_config": {
            "max_concurrent_models": settings.MAX_CONCURRENT_MODELS,
            "default_models": settings.DEFAULT_MODELS,
            "vram_optimization": health["gpu"]["vram_available_gb"] < 6.0
        }
    }

# Helper functions
async def _get_system_metrics() -> Dict[str, Any]:
    """Get basic system metrics"""
    try:
        return {
            "cpu_count": psutil.cpu_count(),
            "cpu_usage_percent": psutil.cpu_percent(interval=1),
            "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        return {"error": str(e)}

async def _check_ollama_health() -> Dict[str, Any]:
    """Check Ollama service health"""
    try:
        client = ollama.Client(host=settings.OLLAMA_URL)
        response = requests.get(f"{settings.OLLAMA_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            return {
                "available": True,
                "url": settings.OLLAMA_URL,
                "models_count": len(models),
                "response_time_ms": response.elapsed.total_seconds() * 1000
            }
        else:
            return {
                "available": False,
                "error": f"HTTP {response.status_code}"
            }
    except Exception as e:
        return {
            "available": False,
            "error": str(e)
        }

async def _get_gpu_metrics() -> Dict[str, Any]:
    """Get GPU metrics (NVIDIA specific)"""
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        
        # Memory info
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        vram_total_gb = mem_info.total / (1024**3)
        vram_used_gb = mem_info.used / (1024**3)
        vram_available_gb = vram_total_gb - vram_used_gb
        
        # GPU info
        gpu_name = pynvml.nvmlDeviceGetName(handle).decode('utf-8')
        
        return {
            "available": True,
            "name": gpu_name,
            "vram_total_gb": round(vram_total_gb, 2),
            "vram_used_gb": round(vram_used_gb, 2),
            "vram_available_gb": round(vram_available_gb, 2),
            "vram_usage_percent": round((vram_used_gb / vram_total_gb) * 100, 1),
            "rtx_3070ti_optimized": "RTX 3070" in gpu_name or "RTX 4070" in gpu_name
        }
    except ImportError:
        return {
            "available": False,
            "error": "pynvml not available - install nvidia-ml-py"
        }
    except Exception as e:
        return {
            "available": False,
            "error": str(e)
        }

async def _check_model_availability() -> Dict[str, Any]:
    """Check which models are available in Ollama"""
    try:
        response = requests.get(f"{settings.OLLAMA_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            models_data = response.json().get('models', [])
            available_models = [model['name'] for model in models_data]
            
            # Check for required models
            required_models = list(settings.DEFAULT_MODELS.values())
            missing_models = [model for model in required_models if model not in available_models]
            
            return {
                "available_models": available_models,
                "required_models": required_models,
                "missing_models": missing_models,
                "models_ready": len(missing_models) == 0
            }
        else:
            return {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

async def _get_memory_metrics() -> Dict[str, Any]:
    """Get system memory metrics"""
    try:
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        return {
            "total_gb": round(memory.total / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "used_gb": round(memory.used / (1024**3), 2),
            "usage_percent": memory.percent,
            "swap_total_gb": round(swap.total / (1024**3), 2),
            "swap_used_gb": round(swap.used / (1024**3), 2)
        }
    except Exception as e:
        return {"error": str(e)}

async def _get_optimization_status() -> Dict[str, Any]:
    """Get current optimization settings status"""
    return {
        "sequential_loading": settings.MAX_CONCURRENT_MODELS == 1,
        "sleep_taper_enabled": settings.SLEEP_TAPER_ENABLED,
        "sensory_rotation_enabled": settings.SENSORY_ROTATION_ENABLED,
        "max_retries": settings.MAX_RETRIES,
        "fallback_model": settings.FALLBACK_MODEL,
        "model_presets_available": list(settings.MODEL_PRESETS.keys())
    }

# Performance monitoring helpers
async def _get_gpu_utilization() -> Optional[float]:
    """Get current GPU utilization percentage"""
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        return float(util.gpu)
    except:
        return None

async def _get_gpu_memory_usage() -> Optional[float]:
    """Get current GPU memory usage percentage"""
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        return round((mem_info.used / mem_info.total) * 100, 1)
    except:
        return None

async def _get_gpu_temperature() -> Optional[float]:
    """Get current GPU temperature"""
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        return float(temp)
    except:
        return None

async def _measure_ollama_response_time() -> Optional[float]:
    """Measure Ollama API response time"""
    try:
        import time
        start = time.time()
        response = requests.get(f"{settings.OLLAMA_URL}/api/tags", timeout=5)
        end = time.time()
        if response.status_code == 200:
            return round((end - start) * 1000, 2)  # Convert to ms
        return None
    except:
        return None

async def _get_active_models() -> int:
    """Get number of currently loaded models"""
    try:
        response = requests.get(f"{settings.OLLAMA_URL}/api/ps", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            return len(models)
        return 0
    except:
        return 0