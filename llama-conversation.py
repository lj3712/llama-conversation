#!/usr/bin/env python3
"""
LLaMA Conversation CLI
Copyright (c) 2025 L.J. Mattson
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
    from llama_cpp import Llama
except ImportError:
    print("Error: llama-cpp-python is not installed.")
    print("Install it with: pip install llama-cpp-python")
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
        'n_ctx': 2048,
        'n_threads': None
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
            if key in ['max_tokens', 'n_ctx', 'n_threads']:
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


def build_context_string(sections):
    """Build the context string for the model from parsed sections"""
    context_parts = []

    for section in sections:
        if section['type'] == 'human':
            context_parts.append(f"Human: {section['content']}")
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
                context_parts.append(f"Assistant: {clean_ai_content}")

    # Add the final "Assistant:" prompt for the model to continue
    context_parts.append("Assistant:")

    return '\n\n'.join(context_parts)


def append_response_to_file(filepath, response_text, generation_time):
    """Append the AI response to the prompt file with clear separation"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(f"\n\n---AI---\n")
        f.write(f"# Generated: {timestamp} ({generation_time:.1f}s)\n")
        f.write(response_text.strip())
        f.write(f"\n\n---HUMAN---\n")


def main():
    parser = argparse.ArgumentParser(
        description="Conversational LLaMA with robust section parsing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
.prompt file format:
  model: path/to/model.gguf
  max_tokens: 256  # or 'none' for unlimited
  temperature: 0.7

  ---
  ---HUMAN---
  Your first question here

  ---AI---
  # Generated: timestamp (duration)
  AI's response (automatically added)

  ---HUMAN---
  Your next question here

Uses robust ---HUMAN--- and ---AI--- markers that models
won't accidentally generate. Only the latest incomplete
human prompt triggers generation.

Example:
  python llama_oneshot.py conversation.prompt
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

    # Build context for the model
    context_string = build_context_string(sections)

    # Validate required fields
    if 'model' not in config:
        print("Error: 'model' must be specified in the prompt file")
        sys.exit(1)

    # Validate model file exists
    if not os.path.isfile(config['model']):
        print(f"Error: Model file '{config['model']}' not found.")
        sys.exit(1)

    if args.dry_run:
        print("=== PARSED SECTIONS ===")
        for i, section in enumerate(sections):
            print(f"{i+1}. {section['type'].upper()}: {section['content'][:100]}...")
        print("\n=== CONTEXT FOR MODEL ===")
        print(context_string)
        print("\n=== CONFIG ===")
        for key, value in config.items():
            print(f"{key}: {value}")
        print("\n(Dry run - no generation performed)")
        return

    try:
        if args.verbose:
            print(f"Loading model: {config['model']}")
            print(f"Found {len(sections)} conversation sections")
            print(f"Context length: {len(context_string)} characters")
            print("\n=== CONTEXT SENT TO MODEL ===")
            print(context_string)
            print("=" * 50)

        # Initialize the model
        llm = Llama(
            model_path=config['model'],
            n_ctx=config['n_ctx'],
            n_threads=config['n_threads'],
            verbose=args.verbose
        )

        if args.verbose:
            print("Generating response...")

        # Track generation time
        start_time = time.time()

        # Generate text using the context string
        generation_params = {
            'temperature': config['temperature'],
            'top_p': config['top_p'],
            'echo': False,
            'stop': ["Human:", "---HUMAN---", "---AI---", "# Generated:"]
        }

        # Handle unlimited tokens
        if config['max_tokens'] is not None:
            generation_params['max_tokens'] = config['max_tokens']
        else:
            generation_params['max_tokens'] = -1

        response = llm(context_string, **generation_params)

        # Calculate generation time
        generation_time = time.time() - start_time

        # Extract and clean the generated text
        generated_text = response['choices'][0]['text'].strip()

        # Remove any accidental "Assistant:" prefix
        if generated_text.startswith("Assistant:"):
            generated_text = generated_text[10:].strip()

        # Remove any timestamp comment lines that the model might have generated
        cleaned_lines = []
        for line in generated_text.split('\n'):
            # Skip any timestamp comment lines
            if line.strip().startswith('# Generated:'):
                continue
            cleaned_lines.append(line)

        generated_text = '\n'.join(cleaned_lines).strip()

        if args.verbose:
            print(f"\n=== GENERATED RESPONSE ===")
            print(generated_text)

        # Append response to the prompt file
        append_response_to_file(args.prompt_file, generated_text, generation_time)

        print(f"Response appended to: {args.prompt_file}")
        if args.verbose:
            print(f"Generated {len(generated_text)} characters in {generation_time:.1f}s")

    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
