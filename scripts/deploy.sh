#!/bin/bash

# Deployment script for Reddit Shorts Video Maker
# Usage: ./scripts/deploy.sh [--build] [--test] [--docker]

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

LOG_FILE="${PROJECT_ROOT}/deploy.log"
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

log() {
    echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "Reddit Shorts Deployment Script"
log "=========================================="

# Parse arguments
BUILD_IMAGE=0
RUN_TESTS=1
BUILD_DOCKER=0

while [[ $# -gt 0 ]]; do
    case $1 in
        --build) BUILD_IMAGE=1; shift ;;
        --no-tests) RUN_TESTS=0; shift ;;
        --docker) BUILD_DOCKER=1; shift ;;
        *) log "Unknown option: $1"; exit 1 ;;
    esac
done

cd "$PROJECT_ROOT"

# 1. Check environment
log "Checking environment..."
if ! command -v python3 &> /dev/null; then
    log "ERROR: python3 not found"
    exit 1
fi

log "Python version: $(python3 --version)"

# 2. Install/update dependencies
log "Installing dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -q -r requirements.txt
else
    log "WARNING: requirements.txt not found"
fi

# 3. Run tests (optional)
if [ $RUN_TESTS -eq 1 ]; then
    log "Running test suite..."
    if python3 -m pytest tests/ -q; then
        log "✓ All tests passed"
    else
        log "✗ Tests failed"
        exit 1
    fi
fi

# 4. Run linter (optional, non-blocking)
log "Running linter..."
if command -v flake8 &> /dev/null; then
    if flake8 . --max-line-length=127 --exit-zero 2>/dev/null; then
        log "✓ Linter check passed"
    else
        log "⚠ Linter warnings (non-blocking)"
    fi
fi

# 5. Build Docker image (optional)
if [ $BUILD_DOCKER -eq 1 ]; then
    log "Building Docker image..."
    if command -v docker &> /dev/null; then
        if docker build -t reddit-shorts:latest .; then
            log "✓ Docker image built successfully"
            log "  To run: docker run -v \$(pwd)/output:/app/output reddit-shorts:latest --limit 1"
        else
            log "✗ Docker build failed"
            exit 1
        fi
    else
        log "WARNING: Docker not found, skipping image build"
    fi
fi

log "=========================================="
log "✓ Deployment preparation complete"
log "=========================================="

if [ $BUILD_DOCKER -eq 0 ]; then
    log "To start the application locally:"
    log "  python main.py --limit 1"
    log ""
    log "To build and test Docker:"
    log "  ./scripts/deploy.sh --docker"
fi
