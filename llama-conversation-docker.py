#!/usr/bin/env python3
"""
LLaMA Conversation CLI - Docker Edition
Modified to work with Dockerized llama-cpp-python server using OpenAI client
Original Copyright (c) 2025 L.J. Mattson
Licensed under the MIT License - see LICENSE file for details
Conversational LLaMA CLI interface using .prompt files
Uses robust section parsing to separate human prompts and AI responses
"""

import argparse
import sys
import os
import time
import re
from datetime import datetime

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai library is not installed.")
    print("Install it with: pip install openai")
    sys.exit(1)


def parse_prompt_file(filepath):
    """Parse a .prompt file into config and conversation sections"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: Prompt file '{filepath}' not found.")
        sys.exit(1)

    # Split on --- separator between config and conversation
    if '---' not in content:
        print("Error: Prompt file must contain '---' separator between config and conversation")
        sys.exit(1)

    config_part, conversation_part = content.split('---', 1)

    # Parse config (simple key: value format)
    config = {
        'max_tokens': 256,
        'temperature': 0.7,
        'top_p': 0.9,
        'server_url': 'http://localhost:2547/v1',  # Default Docker server URL
        'model_name': 'llama-13b'  # Default model alias (will use first available if not found)
    }

    for line in config_part.strip().split('\n'):
        line = line.strip()
        if line and ':' in line and not line.startswith('#'):
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()

            # Strip inline comments (anything after #)
            if '#' in value:
                value = value.split('#')[0].strip()

            # Convert types
            if key in ['max_tokens']:
                config[key] = int(value) if value.lower() != 'none' else None
            elif key in ['temperature', 'top_p']:
                config[key] = float(value)
            else:
                config[key] = value

    return config, conversation_part.strip()


def parse_conversation_sections(conversation_text):
    """Parse conversation into alternating human/AI sections"""
    # Split by our section markers
    sections = re.split(r'---(?:HUMAN|AI)---', conversation_text)

    # Remove empty sections
    sections = [s.strip() for s in sections if s.strip()]

    # Find section headers to determine type
    headers = re.findall(r'---(HUMAN|AI)---', conversation_text)

    if len(headers) != len(sections):
        print("Error: Mismatched section headers and content")
        sys.exit(1)

    parsed_sections = []
    for header, content in zip(headers, sections):
        parsed_sections.append({
            'type': header.lower(),
            'content': content.strip()
        })

    return parsed_sections


def build_openai_messages(sections):
    """Build OpenAI chat messages format from parsed sections"""
    messages = []

    for section in sections:
        if section['type'] == 'human':
            messages.append({
                "role": "user",
                "content": section['content']
            })
        elif section['type'] == 'ai':
            # Filter out timestamp comment lines from AI content
            ai_lines = []
            for line in section['content'].split('\n'):
                # Skip timestamp comment lines
                if line.strip().startswith('# Generated:'):
                    continue
                ai_lines.append(line)

            clean_ai_content = '\n'.join(ai_lines).strip()
            if clean_ai_content:  # Only add if there's actual content
                messages.append({
                    "role": "assistant",
                    "content": clean_ai_content
                })

    return messages


def append_response_to_file(filepath, response_text, generation_time):
    """Append the AI response to the prompt file with clear separation"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(f"\n\n---AI---\n")
        f.write(f"# Generated: {timestamp} ({generation_time:.1f}s)\n")
        f.write(response_text.strip())
        f.write(f"\n\n---HUMAN---\n")


def test_server_connection(client, verbose=False):
    """Test if the server is reachable and list available models"""
    try:
        if verbose:
            print("Testing server connection...")

        # Try to get models list
        models = client.models.list()
        available_models = [model.id for model in models.data]

        if verbose:
            print(f"✓ Connected to server. Available models:")
            for model in available_models:
                print(f"  - {model}")

        return True, available_models
    except Exception as e:
        print(f"Error: Cannot connect to llama-cpp-python server: {e}")
        print("Make sure the Docker container is running on the configured URL")
        return False, []


def validate_model_name(client, model_name, verbose=False):
    """Validate that the specified model is available on the server"""
    success, available_models = test_server_connection(client, verbose=False)

    if not success:
        return False

    if model_name not in available_models:
        print(f"Warning: Model '{model_name}' not found on server.")
        if available_models:
            print(f"Available models: {', '.join(available_models)}")
            print(f"Using first available model: {available_models[0]}")
            return available_models[0]
        else:
            print("No models available on server!")
            return False

    return model_name


def main():
    parser = argparse.ArgumentParser(
        description="Conversational LLaMA with Docker llama-cpp-python server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
.prompt file format:
  server_url: http://localhost:8000/v1  # llama-cpp-python server URL
  model_name: llama-model               # model identifier for API
  max_tokens: 256                       # or 'none' for unlimited
  temperature: 0.7

  ---
  ---HUMAN---
  Your first question here

  ---AI---
  # Generated: timestamp (duration)
  AI's response (automatically added)

  ---HUMAN---
  Your next question here

Requires a running llama-cpp-python Docker container:
  docker run --rm -it -p 8000:8000 \\
    -v /path/to/models:/models \\
    -e MODEL=/models/your-model.gguf \\
    ghcr.io/abetlen/llama-cpp-python:latest

Example:
  python llama-conversation-docker.py conversation.prompt
        """
    )

    parser.add_argument(
        "prompt_file",
        help="Path to the .prompt file"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be sent to the model without actually running it"
    )

    parser.add_argument(
        "--stream",
        action="store_true",
        help="Enable streaming responses (print as generated)"
    )

    args = parser.parse_args()

    # Parse the prompt file
    config, conversation_text = parse_prompt_file(args.prompt_file)

    # Parse into sections
    sections = parse_conversation_sections(conversation_text)

    if not sections:
        print("Error: No conversation sections found")
        sys.exit(1)

    # Check if the last section is a human prompt (indicating we need to generate a response)
    if sections[-1]['type'] != 'human':
        print("Error: Last section must be a human prompt to generate a response")
        sys.exit(1)

    # Build messages for OpenAI API
    messages = build_openai_messages(sections)

    if args.dry_run:
        print("=== PARSED SECTIONS ===")
        for i, section in enumerate(sections):
            print(f"{i+1}. {section['type'].upper()}: {section['content'][:100]}...")
        print("\n=== MESSAGES FOR API ===")
        for i, msg in enumerate(messages):
            print(f"{i+1}. {msg['role']}: {msg['content'][:100]}...")
        print("\n=== CONFIG ===")
        for key, value in config.items():
            print(f"{key}: {value}")
        print("\n(Dry run - no generation performed)")
        return

    try:
        # Initialize OpenAI client
        client = OpenAI(
            base_url=config['server_url'],
            api_key="sk-not-needed"  # API key not required for local server
        )

        # Test server connection and validate model
        validated_model = validate_model_name(client, config['model_name'], args.verbose)
        if not validated_model:
            sys.exit(1)

        # Update model name if it was changed during validation
        if validated_model != config['model_name']:
            config['model_name'] = validated_model

        if args.verbose:
            print(f"Server URL: {config['server_url']}")
            print(f"Found {len(sections)} conversation sections")
            print(f"Prepared {len(messages)} messages for API")
            print("\n=== MESSAGES SENT TO API ===")
            for msg in messages:
                print(f"{msg['role']}: {msg['content']}")
            print("=" * 50)

        # Track generation time
        start_time = time.time()

        # Prepare API parameters
        api_params = {
            'model': config['model_name'],
            'messages': messages,
            'temperature': config['temperature'],
            'top_p': config['top_p'],
            'stream': args.stream
        }

        # Handle max_tokens
        if config['max_tokens'] is not None:
            api_params['max_tokens'] = config['max_tokens']

        if args.verbose:
            print("Generating response...")

        # Generate response
        if args.stream:
            # Streaming response
            print("\n=== STREAMING RESPONSE ===")
            response_text = ""

            stream = client.chat.completions.create(**api_params)

            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    print(content, end="", flush=True)
                    response_text += content

            print()  # New line after streaming

        else:
            # Non-streaming response
            response = client.chat.completions.create(**api_params)
            response_text = response.choices[0].message.content

        # Calculate generation time
        generation_time = time.time() - start_time

        # Clean the generated text (remove any unwanted prefixes/suffixes)
        generated_text = response_text.strip()

        # Remove any timestamp comment lines that might have been generated
        cleaned_lines = []
        for line in generated_text.split('\n'):
            # Skip any timestamp comment lines
            if line.strip().startswith('# Generated:'):
                continue
            cleaned_lines.append(line)

        generated_text = '\n'.join(cleaned_lines).strip()

        if args.verbose and not args.stream:
            print(f"\n=== GENERATED RESPONSE ===")
            print(generated_text)

        # Append response to the prompt file
        append_response_to_file(args.prompt_file, generated_text, generation_time)

        print(f"\nResponse appended to: {args.prompt_file}")
        if args.verbose:
            print(f"Generated {len(generated_text)} characters in {generation_time:.1f}s")

    except Exception as e:
        print(f"Error: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
