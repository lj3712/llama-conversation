#!/bin/bash
# LLaMA Monitor Wrapper Script
# This script activates the virtual environment and runs the monitor
# Uses file locking to prevent multiple instances

# Configuration - UPDATE THESE PATHS
VENV_PATH="/home/lj/ai-research"
MONITOR_SCRIPT="$VENV_PATH/llama-conversation/llama-prompt-monitor.py"  # Use the no-lock version
PROMPT_DIR="$VENV_PATH/batchprompts"
LOG_FILE="/var/log/llama-monitor.log"
LOCK_FILE="/tmp/llama-monitor.lock"

# Function to log with timestamp
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to cleanup on exit
cleanup() {
    if [ -f "$LOCK_FILE" ]; then
        rm -f "$LOCK_FILE"
    fi
}

# Set trap to cleanup on exit
trap cleanup EXIT

# Check if another instance is running using flock
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    log_message "Another instance is already running. Exiting."
    exit 0
fi

# Write PID to lock file for debugging
echo $ > "$LOCK_FILE"

# Check if venv exists
if [ ! -d "$VENV_PATH" ]; then
    log_message "ERROR: Virtual environment not found at $VENV_PATH"
    exit 1
fi

# Check if monitor script exists
if [ ! -f "$MONITOR_SCRIPT" ]; then
    log_message "ERROR: Monitor script not found at $MONITOR_SCRIPT"
    exit 1
fi

# Check if prompt directory exists
if [ ! -d "$PROMPT_DIR" ]; then
    log_message "ERROR: Prompt directory not found at $PROMPT_DIR"
    exit 1
fi

# Activate virtual environment
source "$VENV_PATH/bin/activate"

# Check if activation worked
if [ "$VIRTUAL_ENV" != "$VENV_PATH" ]; then
    log_message "ERROR: Failed to activate virtual environment"
    exit 1
fi

# Run the monitor
log_message "Starting llama monitor (venv: $VIRTUAL_ENV)"
python "$MONITOR_SCRIPT" "$PROMPT_DIR" --llama-script $VENV_PATH/llama-conversation/ollama-conversation.py --log "$LOG_FILE" "$@"
#python "$MONITOR_SCRIPT" "$PROMPT_DIR" --llama-script $VENV_PATH/llama-conversation/llama-conversation-docker.py --log "$LOG_FILE" "$@"


# Capture exit code
EXIT_CODE=$?

# Deactivate venv
deactivate

# Log completion
if [ $EXIT_CODE -eq 0 ]; then
    log_message "Monitor completed successfully"
else
    log_message "Monitor exited with error code $EXIT_CODE"
fi

exit $EXIT_CODE
