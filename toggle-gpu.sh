#!/bin/bash

# Script to toggle GPU mode on/off

# Function to display usage
show_usage() {
    echo "Usage: ./toggle-gpu.sh [on|off]"
    echo "  on  - Enable GPU mode"
    echo "  off - Disable GPU mode (use CPU)"
    echo "  If no argument is provided, the script will show the current setting."
}

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cp .env.example .env || touch .env
fi

# Function to get current GPU setting
get_gpu_status() {
    USE_GPU=$(grep "USE_GPU" .env | cut -d= -f2)
    PLATFORM=$(grep "PLATFORM" .env | cut -d= -f2)
    GPU_DRIVER=$(grep "GPU_DRIVER" .env | cut -d= -f2)
    
    if [ "$USE_GPU" = "true" ]; then
        echo "GPU mode is currently ENABLED"
        echo "Platform: $PLATFORM"
        echo "GPU driver: $GPU_DRIVER"
    else
        echo "GPU mode is currently DISABLED (using CPU)"
    fi
}

# Create GPU-specific docker-compose override
create_gpu_override() {
    cat > docker-compose.gpu.yml << EOF
# GPU configuration override for docker-compose
version: '3'

services:
  worker:
    platform: ''
    deploy:
      resources:
        reservations:
          devices:
            - driver: "nvidia"
              count: 1
              capabilities: ["gpu"]

  trainer:
    platform: ''
    deploy:
      resources:
        reservations:
          devices:
            - driver: "nvidia"
              count: 1
              capabilities: ["gpu"]
EOF
    echo "Created GPU configuration override file: docker-compose.gpu.yml"
}

# Handle command line arguments
if [ $# -eq 0 ]; then
    get_gpu_status
    exit 0
fi

case "$1" in
    on)
        echo "Enabling GPU mode..."
        # Set GPU-related environment variables
        sed -i.bak 's/USE_GPU=.*/USE_GPU=true/' .env 2>/dev/null || echo "USE_GPU=true" >> .env
        sed -i.bak 's/PLATFORM=.*/PLATFORM=/' .env 2>/dev/null || echo "PLATFORM=" >> .env
        sed -i.bak 's/USE_MOCK_DOCKER=.*/USE_MOCK_DOCKER=false/' .env 2>/dev/null || echo "USE_MOCK_DOCKER=false" >> .env
        
        # Create GPU override file
        create_gpu_override
        
        echo "GPU mode enabled. Run 'docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d' to apply changes."
        ;;
    off)
        echo "Disabling GPU mode (using CPU)..."
        # Set CPU-related environment variables
        sed -i.bak 's/USE_GPU=.*/USE_GPU=false/' .env 2>/dev/null || echo "USE_GPU=false" >> .env
        sed -i.bak 's/PLATFORM=.*/PLATFORM=linux\/arm64/' .env 2>/dev/null || echo "PLATFORM=linux/arm64" >> .env
        sed -i.bak 's/USE_MOCK_DOCKER=.*/USE_MOCK_DOCKER=true/' .env 2>/dev/null || echo "USE_MOCK_DOCKER=true" >> .env
        
        # Remove GPU override file if it exists
        if [ -f docker-compose.gpu.yml ]; then
            rm docker-compose.gpu.yml
            echo "Removed GPU configuration override file"
        fi
        
        echo "GPU mode disabled. Run 'docker compose up -d' to apply changes."
        ;;
    *)
        show_usage
        exit 1
        ;;
esac

# Remove backup files
rm -f .env.bak

# Display current status
get_gpu_status 