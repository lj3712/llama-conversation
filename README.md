# LLaMA Conversation CLI

A simple, robust command-line interface for conversational AI using llama-cpp-python with persistent context in `.prompt` files.

## Features
- 🗣️ **Persistent conversations** with growing context
- 🔧 **Robust parsing** prevents model hallucination issues
- ⏱️ **Generation timing** and metadata tracking
- 🎛️ **Flexible configuration** per conversation
- 🔍 **Debug modes** for troubleshooting

## Quick Start
```bash
pip install llama-cpp-python
python llama_conversation.py example.prompt

## Docker start

Create a models-config.json file (see example) and start the container:

docker run -d --name llama-server -p 8000:8000 \
  -v /path/to/your/models:/models \
  -v ./config:/config \
  -e CONFIG_FILE=/config/models-config.json \
  --restart unless-stopped \
  ghcr.io/abetlen/llama-cpp-python:latest