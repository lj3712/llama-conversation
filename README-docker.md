# LLaMA Conversation Docker Setup

This is a modified version of the original llama-conversation script that works with a Dockerized llama-cpp-python server with support for multiple models.

## Quick Start

### 1. Install Dependencies in your ai-research venv

```bash
# Activate your virtual environment
source ai-research/bin/activate  # or whatever your venv is called

# Install the OpenAI client library
pip install openai
```

### 2. Start the Docker Container

You have several options for model management:

#### Option A: Multiple Models with Config File (Recommended)

Create a `models-config.json` file (see example) and start the container:

```bash
# Create directory for config
mkdir config

# Foreground with logs visible
docker run --rm -p 8000:8000 \
  -v /path/to/your/models:/models \
  -v ./config:/config \
  -e CONFIG_FILE=/config/models-config.json \
  ghcr.io/abetlen/llama-cpp-python:latest

# OR run as background daemon
docker run -d --name llama-server -p 8000:8000 \
  -v /path/to/your/models:/models \
  -v ./config:/config \
  -e CONFIG_FILE=/config/models-config.json \
  --restart unless-stopped \
  ghcr.io/abetlen/llama-cpp-python:latest
```

#### Option B: Start Without Pre-loading Any Model

```bash
# Foreground with logs
docker run --rm -p 8000:8000 \
  -v /path/to/your/models:/models \
  ghcr.io/abetlen/llama-cpp-python:latest \
  python3 -m llama_cpp.server --host 0.0.0.0

# OR as background daemon
docker run -d --name llama-server -p 8000:8000 \
  -v /path/to/your/models:/models \
  --restart unless-stopped \
  ghcr.io/abetlen/llama-cpp-python:latest \
  python3 -m llama_cpp.server --host 0.0.0.0
```

#### Option C: Single Model (Original Approach)

```bash
# Foreground - good for testing
docker run --rm -p 8000:8000 \
  -v /path/to/your/models:/models \
  -e MODEL=/models/your-model.gguf \
  ghcr.io/abetlen/llama-cpp-python:latest

# Background daemon - good for production
docker run -d --name llama-server -p 8000:8000 \
  -v /path/to/your/models:/models \
  -e MODEL=/models/your-model.gguf \
  --restart unless-stopped \
  ghcr.io/abetlen/llama-cpp-python:latest

```bash
# Foreground - good for testing
docker run --rm -p 8000:8000 \
  -v /path/to/your/models:/models \
  -e MODEL=/models/your-model.gguf \
  ghcr.io/abetlen/llama-cpp-python:latest

# Background daemon - good for production
docker run -d --name llama-server -p 8000:8000 \
  -v /path/to/your/models:/models \
  -e MODEL=/models/your-model.gguf \
  --restart unless-stopped \
  ghcr.io/abetlen/llama-cpp-python:latest
```

#### GPU Support Note
Add `--gpus all` to any of the above Docker commands if you want GPU acceleration:
```bash
# Example with GPU support
docker run -d --name llama-server -p 8000:8000 --gpus all \
  -v /path/to/your/models:/models \
  -v ./config:/config \
  -e CONFIG_FILE=/config/models-config.json \
  --restart unless-stopped \
  ghcr.io/abetlen/llama-cpp-python:latest
```

### Server Management Commands

```bash
# View logs from background container
docker logs llama-server

# Follow logs in real-time
docker logs -f llama-server

# Stop the background server
docker stop llama-server

# Restart the server
docker restart llama-server

# Check if server is running
docker ps | grep llama-server
```

### When to Use Each Approach

**Foreground (`--rm`)**:
- ✅ Good for development and testing
- ✅ See logs immediately
- ✅ Easy to stop with Ctrl+C
- ✅ Container auto-removes when stopped

**Background daemon (`-d`)**:
- ✅ Good for production/long-running server
- ✅ Survives terminal disconnection
- ✅ `--restart unless-stopped` auto-restarts on system reboot
- ✅ Run multiple containers simultaneously

### 4. Create a .prompt File

Use the example-conversation.prompt file as a template. The key difference is specifying the `model_name` that corresponds to your model alias:

```
server_url: http://localhost:8000/v1
model_name: llama-3.1-8b  # This should match a model_alias from your config
max_tokens: 512
temperature: 0.7

---
---HUMAN---
Your question here
```

### 5. Run the Script

```bash
# Basic usage
python llama-conversation-docker.py example-conversation.prompt

# With verbose output
python llama-conversation-docker.py --verbose example-conversation.prompt

# With streaming (see responses as they're generated)
python llama-conversation-docker.py --stream example-conversation.prompt

# Dry run to see what would be sent without generating
python llama-conversation-docker.py --dry-run example-conversation.prompt
```

## Key Changes from Original

1. **Uses OpenAI client** instead of direct llama_cpp library
2. **Connects to Docker server** instead of loading model locally
3. **Server URL configuration** instead of model path
4. **Connection testing** to verify server is reachable
5. **Streaming support** for real-time response viewing
6. **OpenAI message format** for chat completions API

## Benefits of Multi-Model Approach

**Option A (Config File) is recommended because:**

- ✅ **Multiple models available**: Switch between models without restarting container
- ✅ **Automatic loading**: The server will automatically load and unload models as needed
- ✅ **Per-model settings**: Different context sizes, GPU layers, chat formats per model
- ✅ **Model aliases**: Use friendly names instead of full file paths
- ✅ **Dynamic switching**: Different job files can use different models seamlessly

**How it works:**
- The server supports routing requests to multiple models based on the model parameter in the request which matches against the model_alias in the config file
- Only one model is loaded in memory at a time, but switching is automatic
- Your prompt files can specify different `model_name` values to use different models

## Configuration Options

- `server_url`: URL of your llama-cpp-python Docker server (default: http://localhost:8000/v1)
- `model_name`: Model identifier for API calls (can be anything for local server)
- `max_tokens`: Maximum tokens to generate (or 'none' for unlimited)
- `temperature`: Creativity level (0.0 = deterministic, higher = more creative)
- `top_p`: Nucleus sampling parameter

## Troubleshooting

1. **Connection refused**: Make sure Docker container is running on port 8000
2. **Model not found**: Check that your model path in Docker command is correct
3. **Import error**: Make sure `openai` library is installed in your venv

## Benefits of This Approach

- ✅ **Isolation**: Model runs in Docker container, separate from your development environment
- ✅ **Resource management**: Easy to start/stop model server as needed
- ✅ **API compatibility**: Uses standard OpenAI-compatible API
- ✅ **Flexibility**: Can easily switch between different models by restarting container
- ✅ **Scalability**: Can deploy the same setup on different machines/cloud instances
- ✅ **Production ready**: Background daemon mode with auto-restart capabilities
- ✅ **Development friendly**: Foreground mode for testing with immediate log visibility