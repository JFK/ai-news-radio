#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# AI News Radio - Interactive Setup Script
# ============================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

info()    { echo -e "${BLUE}ℹ${NC}  $*"; }
success() { echo -e "${GREEN}✔${NC}  $*"; }
warn()    { echo -e "${YELLOW}⚠${NC}  $*"; }
error()   { echo -e "${RED}✖${NC}  $*"; }
header()  { echo -e "\n${BOLD}${CYAN}$*${NC}\n"; }

# Error trap
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo ""
        error "Setup failed (exit code: $exit_code)"
        echo ""
        echo "  Troubleshooting:"
        echo "    - Check Docker is running:  docker info"
        echo "    - View logs:                docker compose logs"
        echo "    - Reset and retry:          docker compose down -v && ./setup.sh"
        echo ""
    fi
}
trap cleanup EXIT

# ============================================================
# Banner
# ============================================================

echo ""
echo -e "${BOLD}${CYAN}"
echo "    █████╗ ██╗    ███╗   ██╗███████╗██╗    ██╗███████╗"
echo "   ██╔══██╗██║    ████╗  ██║██╔════╝██║    ██║██╔════╝"
echo "   ███████║██║    ██╔██╗ ██║█████╗  ██║ █╗ ██║███████╗"
echo "   ██╔══██║██║    ██║╚██╗██║██╔══╝  ██║███╗██║╚════██║"
echo "   ██║  ██║██║    ██║ ╚████║███████╗╚███╔███╔╝███████║"
echo "   ╚═╝  ╚═╝╚═╝    ╚═╝  ╚═══╝╚══════╝ ╚══╝╚══╝ ╚══════╝"
echo -e "${NC}"
echo -e "   ${BOLD}AI News Radio${NC} — Not just reading the news."
echo -e "   A radio that thinks with you."
echo ""

# ============================================================
# Prerequisites
# ============================================================

header "Checking prerequisites..."

check_command() {
    if command -v "$1" &> /dev/null; then
        local version
        version=$($2 2>&1 | head -1)
        success "$1 found: $version"
        return 0
    else
        error "$1 is not installed."
        return 1
    fi
}

missing=0
check_command "docker" "docker --version" || missing=1
check_command "git" "git --version" || missing=1

# Check docker compose (plugin or standalone)
if docker compose version &> /dev/null; then
    success "docker compose found: $(docker compose version --short 2>/dev/null || docker compose version)"
elif command -v docker-compose &> /dev/null; then
    success "docker-compose found: $(docker-compose --version)"
    warn "Consider upgrading to the Docker Compose plugin (v2)"
else
    error "docker compose is not installed."
    missing=1
fi

if [ $missing -ne 0 ]; then
    echo ""
    error "Missing prerequisites. Please install them and retry."
    exit 1
fi

# Check Docker daemon
if ! docker info &> /dev/null; then
    error "Docker daemon is not running. Please start Docker and retry."
    exit 1
fi

# ============================================================
# AI Provider Selection
# ============================================================

header "AI Provider Configuration"

echo "  Select your default AI provider:"
echo ""
echo "    1) Anthropic (Claude)     — recommended"
echo "    2) OpenAI (GPT)"
echo "    3) Google (Gemini)"
echo ""
read -rp "  Choose [1-3] (default: 1): " ai_choice

case "${ai_choice:-1}" in
    1)
        AI_PROVIDER="anthropic"
        AI_MODEL="claude-sonnet-4-20250514"
        AI_KEY_VAR="ANTHROPIC_API_KEY"
        AI_KEY_URL="https://console.anthropic.com/settings/keys"
        ;;
    2)
        AI_PROVIDER="openai"
        AI_MODEL="gpt-4o"
        AI_KEY_VAR="OPENAI_API_KEY"
        AI_KEY_URL="https://platform.openai.com/api-keys"
        ;;
    3)
        AI_PROVIDER="google"
        AI_MODEL="gemini-2.5-pro"
        AI_KEY_VAR="GOOGLE_API_KEY"
        AI_KEY_URL="https://aistudio.google.com/apikey"
        ;;
    *)
        warn "Invalid choice, using Anthropic."
        AI_PROVIDER="anthropic"
        AI_MODEL="claude-sonnet-4-20250514"
        AI_KEY_VAR="ANTHROPIC_API_KEY"
        AI_KEY_URL="https://console.anthropic.com/settings/keys"
        ;;
esac

success "Provider: $AI_PROVIDER ($AI_MODEL)"

# ============================================================
# API Keys
# ============================================================

header "API Keys"

info "Get your $AI_PROVIDER key at: $AI_KEY_URL"
echo ""
read -rsp "  Enter your $AI_KEY_VAR: " AI_KEY
echo ""

if [ -z "$AI_KEY" ]; then
    warn "No API key entered. You'll need to add it to .env later."
fi

echo ""
info "Brave Search is used for news collection and fact-checking."
info "Get your key at: https://brave.com/search/api/"
echo ""
read -rsp "  Enter your BRAVE_SEARCH_API_KEY (press Enter to skip): " BRAVE_KEY
echo ""

# ============================================================
# TTS Provider Selection
# ============================================================

header "TTS (Text-to-Speech) Provider"

echo "  Select your TTS provider:"
echo ""
echo "    1) VOICEVOX (local, free, no API key needed) — default"
echo "    2) OpenAI TTS"
echo "    3) ElevenLabs"
echo "    4) Google Cloud TTS"
echo ""
read -rp "  Choose [1-4] (default: 1): " tts_choice

TTS_PROVIDER="voicevox"
ELEVENLABS_KEY=""

case "${tts_choice:-1}" in
    1) TTS_PROVIDER="voicevox" ;;
    2) TTS_PROVIDER="openai" ;;
    3)
        TTS_PROVIDER="elevenlabs"
        echo ""
        read -rsp "  Enter your ELEVENLABS_API_KEY: " ELEVENLABS_KEY
        echo ""
        ;;
    4) TTS_PROVIDER="google" ;;
    *) warn "Invalid choice, using VOICEVOX." ;;
esac

success "TTS Provider: $TTS_PROVIDER"

# ============================================================
# Generate .env
# ============================================================

header "Generating .env file..."

if [ -f .env ]; then
    warn ".env already exists. Backing up to .env.backup"
    cp .env .env.backup
fi

cp .env.example .env

# Update provider settings
sed -i "s|^DEFAULT_AI_PROVIDER=.*|DEFAULT_AI_PROVIDER=$AI_PROVIDER|" .env
sed -i "s|^DEFAULT_AI_MODEL=.*|DEFAULT_AI_MODEL=$AI_MODEL|" .env
sed -i "s|^PIPELINE_FACTCHECK_PROVIDER=.*|PIPELINE_FACTCHECK_PROVIDER=$AI_PROVIDER|" .env
sed -i "s|^PIPELINE_FACTCHECK_MODEL=.*|PIPELINE_FACTCHECK_MODEL=$AI_MODEL|" .env
sed -i "s|^PIPELINE_ANALYSIS_PROVIDER=.*|PIPELINE_ANALYSIS_PROVIDER=$AI_PROVIDER|" .env
sed -i "s|^PIPELINE_ANALYSIS_MODEL=.*|PIPELINE_ANALYSIS_MODEL=$AI_MODEL|" .env
sed -i "s|^PIPELINE_SCRIPT_PROVIDER=.*|PIPELINE_SCRIPT_PROVIDER=$AI_PROVIDER|" .env
sed -i "s|^PIPELINE_SCRIPT_MODEL=.*|PIPELINE_SCRIPT_MODEL=$AI_MODEL|" .env

# Set API keys
if [ -n "$AI_KEY" ]; then
    sed -i "s|^${AI_KEY_VAR}=.*|${AI_KEY_VAR}=${AI_KEY}|" .env
fi
if [ -n "${BRAVE_KEY:-}" ]; then
    sed -i "s|^BRAVE_SEARCH_API_KEY=.*|BRAVE_SEARCH_API_KEY=${BRAVE_KEY}|" .env
fi
if [ -n "${ELEVENLABS_KEY:-}" ]; then
    sed -i "s|^ELEVENLABS_API_KEY=.*|ELEVENLABS_API_KEY=${ELEVENLABS_KEY}|" .env
fi

# Set TTS provider
sed -i "s|^PIPELINE_VOICE_PROVIDER=.*|PIPELINE_VOICE_PROVIDER=$TTS_PROVIDER|" .env

success ".env generated"

# ============================================================
# Docker Compose
# ============================================================

header "Starting services with Docker Compose..."

docker compose up -d --build

success "All containers started"

# ============================================================
# Database Migration
# ============================================================

header "Running database migrations..."

# Wait for the backend to be ready
info "Waiting for backend to be ready..."
sleep 5

docker compose exec -T backend alembic upgrade head

success "Database migrations complete"

# ============================================================
# Health Check
# ============================================================

header "Running health check..."

MAX_RETRIES=10
RETRY_INTERVAL=3

for i in $(seq 1 $MAX_RETRIES); do
    if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
        success "Backend is healthy!"
        break
    fi
    if [ "$i" -eq "$MAX_RETRIES" ]; then
        warn "Health check timed out. The backend may still be starting."
        warn "Check with: curl http://localhost:8000/api/health"
    else
        info "Waiting for backend... ($i/$MAX_RETRIES)"
        sleep $RETRY_INTERVAL
    fi
done

# ============================================================
# Done!
# ============================================================

echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║              Setup Complete!                         ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Dashboard:     http://localhost:3000"
echo "  Backend API:   http://localhost:8000/api/health"
echo "  VOICEVOX:      http://localhost:50021/docs"
echo ""
echo "  Useful commands:"
echo "    docker compose logs -f          # View logs"
echo "    docker compose restart backend  # Restart backend"
echo "    docker compose down             # Stop all services"
echo ""
echo -e "  ${CYAN}Happy broadcasting!${NC}"
echo ""
