#!/bin/bash

# Fix Ollama Container Issues
# For Sleep Stories AI - Frontend Rewrite v2.0

echo "🔧 Ollama Container Troubleshooting Script"
echo "========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check NVIDIA Docker runtime
check_nvidia_runtime() {
    print_status "Checking NVIDIA Docker runtime..."
    
    if command -v nvidia-docker &> /dev/null; then
        print_success "NVIDIA Docker found"
    else
        print_error "NVIDIA Docker not found. Installing..."
        # Add installation commands if needed
    fi
    
    # Check if nvidia runtime is available
    if docker info | grep -q nvidia; then
        print_success "NVIDIA runtime available in Docker"
    else
        print_warning "NVIDIA runtime not configured in Docker"
    fi
}

# Check GPU availability
check_gpu() {
    print_status "Checking GPU availability..."
    
    if command -v nvidia-smi &> /dev/null; then
        echo "GPU Status:"
        nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader,nounits
        print_success "GPU detected and accessible"
    else
        print_error "nvidia-smi not found. NVIDIA drivers may not be installed"
    fi
}

# Stop and cleanup existing containers
cleanup_containers() {
    print_status "Stopping and cleaning up existing containers..."
    
    # Stop containers
    docker-compose down
    
    # Remove orphaned containers
    docker container prune -f
    
    # Remove dangling images
    docker image prune -f
    
    print_success "Cleanup completed"
}

# Fix Ollama specific issues
fix_ollama() {
    print_status "Applying Ollama fixes..."
    
    # Create volume if it doesn't exist
    if ! docker volume ls | grep -q sleepai_volume; then
        print_status "Creating sleepai_volume..."
        docker volume create sleepai_volume
        print_success "Volume created"
    fi
    
    # Start only Ollama first
    print_status "Starting Ollama container individually..."
    docker-compose up -d ollama
    
    # Wait and monitor
    print_status "Waiting for Ollama to initialize (this may take 2-3 minutes)..."
    
    max_attempts=60
    attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if docker exec sleep-stories-ollama curl -f http://localhost:11434/api/tags &>/dev/null; then
            print_success "Ollama is responding!"
            break
        fi
        
        echo -n "."
        sleep 5
        ((attempt++))
    done
    
    if [ $attempt -eq $max_attempts ]; then
        print_error "Ollama failed to start after 5 minutes"
        print_status "Checking Ollama logs:"
        docker logs sleep-stories-ollama --tail 20
        return 1
    fi
    
    # List available models
    print_status "Checking available models:"
    docker exec sleep-stories-ollama curl -s http://localhost:11434/api/tags | jq '.models[].name' 2>/dev/null || echo "No models found or jq not available"
    
    return 0
}

# Start remaining services
start_remaining_services() {
    print_status "Starting remaining services..."
    
    docker-compose up -d
    
    print_status "Waiting for all services to be healthy..."
    sleep 30
    
    # Check service status
    print_status "Service status:"
    docker-compose ps
    
    # Test endpoints
    print_status "Testing endpoints:"
    
    if curl -f http://localhost:11434/api/tags &>/dev/null; then
        print_success "✅ Ollama API accessible"
    else
        print_error "❌ Ollama API not accessible"
    fi
    
    if curl -f http://localhost:8000/health &>/dev/null; then
        print_success "✅ Backend API accessible"
    else
        print_error "❌ Backend API not accessible"
    fi
    
    if curl -f http://localhost:7860 &>/dev/null; then
        print_success "✅ Frontend UI accessible"
    else
        print_error "❌ Frontend UI not accessible"
    fi
}

# Main execution
main() {
    echo
    print_status "Starting Ollama troubleshooting process..."
    echo
    
    check_nvidia_runtime
    echo
    
    check_gpu
    echo
    
    cleanup_containers
    echo
    
    if fix_ollama; then
        echo
        start_remaining_services
        echo
        
        print_success "🎉 All services should now be running!"
        print_status "Access the application at: http://localhost:7860"
    else
        print_error "Failed to start Ollama. Check the logs above for details."
        echo
        print_status "Manual troubleshooting steps:"
        echo "1. Check NVIDIA drivers: nvidia-smi"
        echo "2. Check Docker NVIDIA runtime: docker info | grep nvidia"
        echo "3. Check Ollama logs: docker logs sleep-stories-ollama"
        echo "4. Try pulling Ollama image manually: docker pull ollama/ollama:latest"
    fi
}

# Run main function
main
