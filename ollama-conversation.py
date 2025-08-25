#!/usr/bin/env python3
"""
LLaMA Conversation CLI - Ollama Edition (Improved)
Modified to work with Ollama server using native API with better error handling
"""

import argparse
import sys
import os
import time
import re
import json
from datetime import datetime

try:
    import requests
except ImportError:
    print("Error: requests library is not installed.")
    print("Install it with: pip install requests")
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
        'server_url': 'http://localhost:11434',
        'model_name': 'llama3.1:8b',  # Changed to smaller default model
        'timeout': 180  # Added configurable timeout (3 minutes default)
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
            if key in ['max_tokens', 'timeout']:
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


def build_ollama_messages(sections):
    """Build Ollama chat messages format from parsed sections"""
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
                # Skip timestamp comment lines (they may now include token info)
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


def append_response_to_file(filepath, response_text, generation_time, token_info=None):
    """Append the AI response to the prompt file with clear separation"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build stats line with generation time and token info
    stats_line = f"# Generated: {timestamp} ({generation_time:.1f}s"
    if token_info:
        stats_line += f", {token_info['prompt_tokens']} prompt + {token_info['completion_tokens']} completion = {token_info['total_tokens']} tokens"
    stats_line += ")\n"

    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(f"\n\n---AI---\n")
        f.write(stats_line)
        f.write(response_text.strip())
        f.write(f"\n\n---HUMAN---\n")


def test_server_connection(server_url, verbose=False):
    """Test if the Ollama server is reachable and list available models"""
    try:
        if verbose:
            print("Testing Ollama server connection...")

        # Check if Ollama is running with a shorter timeout
        response = requests.get(f"{server_url}/api/tags", timeout=5)
        response.raise_for_status()

        models_data = response.json()
        available_models = [model['name'] for model in models_data.get('models', [])]

        if verbose:
            print(f"✓ Connected to Ollama server. Available models:")
            for model in available_models:
                print(f"  - {model}")

        return True, available_models
    except requests.exceptions.Timeout:
        print(f"Error: Connection to Ollama server timed out")
        print("Check if Ollama is running: ollama serve")
        return False, []
    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to Ollama server at {server_url}")
        print("Make sure Ollama is running: ollama serve")
        return False, []
    except requests.exceptions.RequestException as e:
        print(f"Error: Cannot connect to Ollama server: {e}")
        return False, []
    except Exception as e:
        print(f"Error: Unexpected error connecting to Ollama: {e}")
        return False, []


def check_model_status(server_url, model_name, verbose=False):
    """Check if a model is loaded and ready to use"""
    try:
        # Try to get model info
        response = requests.post(
            f"{server_url}/api/show",
            json={"name": model_name},
            timeout=10
        )

        if response.status_code == 200:
            model_info = response.json()
            if verbose:
                print(f"✓ Model {model_name} is available")
                # Print model size if available
                if 'details' in model_info:
                    details = model_info['details']
                    if 'parameter_size' in details:
                        print(f"  Parameter size: {details['parameter_size']}")
                    if 'quantization_level' in details:
                        print(f"  Quantization: {details['quantization_level']}")
            return True
        else:
            if verbose:
                print(f"⚠ Model {model_name} may not be fully loaded")
            return False
    except Exception as e:
        if verbose:
            print(f"⚠ Could not check model status: {e}")
        return True  # Assume it's okay and let the chat request handle it


def validate_model_name(server_url, model_name, verbose=False):
    """Validate that the specified model is available on Ollama"""
    success, available_models = test_server_connection(server_url, verbose=False)

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
            print("Pull a model with: ollama pull llama3.1:8b")
            return False

    # Check if model is loaded and ready
    check_model_status(server_url, model_name, verbose)

    return model_name


def generate_ollama_response(server_url, model_name, messages, config, stream=False, verbose=False):
    """Generate response using Ollama's native API with better error handling"""

    # Build the request payload
    payload = {
        "model": model_name,
        "messages": messages,
        "stream": stream,
        "options": {
            "temperature": config['temperature'],
            "top_p": config['top_p']
        }
    }

    # Add max_tokens if specified (Ollama calls it num_predict)
    if config['max_tokens'] is not None:
        payload["options"]["num_predict"] = config['max_tokens']

    if verbose:
        print(f"Sending request to: {server_url}/api/chat")
        print(f"Using timeout: {config.get('timeout', 180)}s")
        print(f"Model: {model_name}")

    try:
        timeout = config.get('timeout', 180)  # Use configurable timeout

        response = requests.post(
            f"{server_url}/api/chat",
            json=payload,
            stream=stream,
            timeout=timeout
        )
        response.raise_for_status()

        if stream:
            return response
        else:
            return response.json()

    except requests.exceptions.Timeout:
        raise Exception(f"Request timed out after {timeout} seconds. Try using a smaller model or increasing the timeout in your config.")
    except requests.exceptions.ConnectionError:
        raise Exception("Connection lost to Ollama server. Check if it's still running.")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Request failed: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Conversational LLaMA with Ollama server (Improved)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
.prompt file format:
  server_url: http://localhost:11434        # Ollama server URL
  model_name: llama3.1:8b                   # Ollama model name (8b recommended)
  max_tokens: 256                           # or 'none' for unlimited
  temperature: 0.7
  timeout: 180                              # Request timeout in seconds

  ---
  ---HUMAN---
  Your first question here

  ---AI---
  # Generated: timestamp (duration)
  AI's response (automatically added)

  ---HUMAN---
  Your next question here

Requires Ollama to be running:
  ollama serve

And a model to be pulled:
  ollama pull llama3.1:8b

Example:
  python llama-conversation-ollama.py conversation.prompt
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

    parser.add_argument(
        "--timeout",
        type=int,
        help="Override request timeout in seconds"
    )

    args = parser.parse_args()

    # Parse the prompt file
    config, conversation_text = parse_prompt_file(args.prompt_file)

    # Override timeout if provided via command line
    if args.timeout:
        config['timeout'] = args.timeout

    # Parse into sections
    sections = parse_conversation_sections(conversation_text)

    if not sections:
        print("Error: No conversation sections found")
        sys.exit(1)

    # Check if the last section is a human prompt
    if sections[-1]['type'] != 'human':
        print("Error: Last section must be a human prompt to generate a response")
        sys.exit(1)

    # Build messages for Ollama API
    messages = build_ollama_messages(sections)

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
        # Test server connection and validate model
        validated_model = validate_model_name(config['server_url'], config['model_name'], args.verbose)
        if not validated_model:
            sys.exit(1)

        # Update model name if it was changed during validation
        if validated_model != config['model_name']:
            config['model_name'] = validated_model

        if args.verbose:
            print(f"Server URL: {config['server_url']}")
            print(f"Model: {config['model_name']}")
            print(f"Timeout: {config.get('timeout', 180)}s")
            print(f"Found {len(sections)} conversation sections")
            print(f"Prepared {len(messages)} messages for API")

        # Track generation time
        start_time = time.time()

        if args.verbose:
            print("\nGenerating response...")

        # Generate response
        token_info = None

        if args.stream:
            # Streaming response
            print("\n=== STREAMING RESPONSE ===")
            response_text = ""

            try:
                stream_response = generate_ollama_response(
                    config['server_url'],
                    config['model_name'],
                    messages,
                    config,
                    stream=True,
                    verbose=args.verbose
                )

                final_chunk = None
                for line in stream_response.iter_lines():
                    if line:
                        try:
                            chunk_data = json.loads(line.decode('utf-8'))
                            if 'message' in chunk_data and 'content' in chunk_data['message']:
                                content = chunk_data['message']['content']
                                print(content, end="", flush=True)
                                response_text += content

                            # Check if this is the final chunk and save token info
                            if chunk_data.get('done', False):
                                final_chunk = chunk_data
                                break
                        except json.JSONDecodeError:
                            continue

                print()  # New line after streaming

                # Extract token info from final chunk
                if final_chunk:
                    token_info = {
                        'prompt_tokens': final_chunk.get('prompt_eval_count', 0),
                        'completion_tokens': final_chunk.get('eval_count', 0),
                        'total_tokens': final_chunk.get('prompt_eval_count', 0) + final_chunk.get('eval_count', 0)
                    }

            except Exception as e:
                print(f"\nStreaming failed: {e}")
                print("Falling back to non-streaming mode...")
                # Fall back to non-streaming
                response_data = generate_ollama_response(
                    config['server_url'],
                    config['model_name'],
                    messages,
                    config,
                    stream=False,
                    verbose=args.verbose
                )
                response_text = response_data['message']['content']

                # Extract token info from fallback response
                token_info = {
                    'prompt_tokens': response_data.get('prompt_eval_count', 0),
                    'completion_tokens': response_data.get('eval_count', 0),
                    'total_tokens': response_data.get('prompt_eval_count', 0) + response_data.get('eval_count', 0)
                }

        else:
            # Non-streaming response
            response_data = generate_ollama_response(
                config['server_url'],
                config['model_name'],
                messages,
                config,
                stream=False,
                verbose=args.verbose
            )
            response_text = response_data['message']['content']

            # Extract token info from response
            token_info = {
                'prompt_tokens': response_data.get('prompt_eval_count', 0),
                'completion_tokens': response_data.get('eval_count', 0),
                'total_tokens': response_data.get('prompt_eval_count', 0) + response_data.get('eval_count', 0)
            }

        # Calculate generation time
        generation_time = time.time() - start_time

        # Clean the generated text
        generated_text = response_text.strip()

        # Remove any timestamp comment lines that might have been generated
        cleaned_lines = []
        for line in generated_text.split('\n'):
            if line.strip().startswith('# Generated:'):
                continue
            cleaned_lines.append(line)

        generated_text = '\n'.join(cleaned_lines).strip()

        if args.verbose and not args.stream:
            print(f"\n=== GENERATED RESPONSE ===")
            print(generated_text)

        # Append response to the prompt file
        append_response_to_file(args.prompt_file, generated_text, generation_time, token_info)

        print(f"\nResponse appended to: {args.prompt_file}")
        if args.verbose:
            stats = f"Generated {len(generated_text)} characters in {generation_time:.1f}s"
            if token_info and token_info['total_tokens'] > 0:
                tokens_per_sec = token_info['completion_tokens'] / generation_time if generation_time > 0 else 0
                stats += f" ({token_info['total_tokens']} tokens total, {tokens_per_sec:.1f} tokens/sec)"
            print(stats)

    except Exception as e:
        print(f"Error: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
