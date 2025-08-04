#!/usr/bin/env python3
"""
LLaMA Prompt Monitor - Batch processor for .prompt files (No built-in locking)
This version relies on external locking (e.g., wrapper script with flock)
"""

import os
import sys
import time
import glob
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

def find_prompt_files(directory):
    """Find all .prompt files that are not already completed"""
    prompt_pattern = os.path.join(directory, "*.prompt")
    all_prompts = glob.glob(prompt_pattern)

    # Filter out .prompt.complete files and get only base .prompt files
    ready_prompts = []
    for prompt_file in all_prompts:
        if not prompt_file.endswith('.prompt.complete'):
            ready_prompts.append(prompt_file)

    return ready_prompts

def is_file_ready(filepath, wait_time=2):
    """Check if file is stable (not being written to) by comparing size"""
    try:
        size1 = os.path.getsize(filepath)
        time.sleep(wait_time)
        size2 = os.path.getsize(filepath)
        return size1 == size2
    except (OSError, FileNotFoundError):
        return False

def process_prompt_file(prompt_file, llama_script_path, verbose=False, python_executable=None):
    """Process a single .prompt file using llama-conversation-docker.py"""
    if verbose:
        print(f"Processing: {prompt_file}")

    try:
        # Use specified python executable or current one
        python_exec = python_executable or sys.executable

        # Run llama-conversation-docker.py on the file
        cmd = [python_exec, llama_script_path, prompt_file]
        if verbose:
            cmd.append("--verbose")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=7200  # 30 minute timeout
        )

        if result.returncode == 0:
            if verbose:
                print(f"✓ Successfully processed: {prompt_file}")
                if result.stdout:
                    print(f"Output: {result.stdout}")
            return True
        else:
            print(f"✗ Error processing {prompt_file}:")
            print(f"Return code: {result.returncode}")
            if result.stderr:
                print(f"Error: {result.stderr}")
            if result.stdout:
                print(f"Output: {result.stdout}")
            return False

    except subprocess.TimeoutExpired:
        print(f"✗ Timeout processing {prompt_file} (exceeded 30 minutes)")
        return False
    except Exception as e:
        print(f"✗ Exception processing {prompt_file}: {e}")
        return False

def mark_as_complete(prompt_file, success=True):
    """Rename .prompt file to .prompt.complete or .prompt.error"""
    try:
        if success:
            new_name = prompt_file + ".complete"
        else:
            new_name = prompt_file + ".error"

        os.rename(prompt_file, new_name)
        return new_name
    except OSError as e:
        print(f"Warning: Could not rename {prompt_file}: {e}")
        return None

def log_activity(message, log_file=None):
    """Log activity with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {message}"

    print(log_message)

    if log_file:
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(log_message + "\n")
        except Exception as e:
            print(f"Warning: Could not write to log file {log_file}: {e}")

def find_llama_script():
    """Try to find llama-conversation-docker.py in common locations"""
    possible_locations = [
        "llama-conversation-docker.py",  # Current directory
        os.path.join(os.path.dirname(__file__), "llama-conversation-docker.py"),  # Same dir as monitor
        os.path.expanduser("~/llama-conversation-docker.py"),  # Home directory
        "/usr/local/bin/llama-conversation-docker.py",  # System location
    ]

    for location in possible_locations:
        if os.path.isfile(location) and os.access(location, os.X_OK):
            return location

    return None

def main():
    parser = argparse.ArgumentParser(
        description="Monitor directory for .prompt files and process them (no built-in locking)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This version relies on external locking (e.g., wrapper script with flock).
Use with llama-monitor-wrapper.sh for safe cron execution.

Examples:
  # Single run (use with wrapper script for cron safety)
  python llama-prompt-monitor-no-lock.py /path/to/prompts

  # Continuous monitoring (use systemd service instead of cron)
  python llama-prompt-monitor-no-lock.py /path/to/prompts --continuous --interval 30
        """
    )

    parser.add_argument(
        "directory",
        help="Directory to monitor for .prompt files"
    )

    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuously instead of single pass"
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Seconds between checks in continuous mode (default: 60)"
    )

    parser.add_argument(
        "--llama-script",
        help="Path to llama-conversation-docker.py script"
    )

    parser.add_argument(
        "--log",
        help="Log file path for activity logging"
    )

    parser.add_argument(
        "--python",
        help="Python executable to use (useful for venv)"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without actually processing"
    )

    args = parser.parse_args()

    # Validate directory
    if not os.path.isdir(args.directory):
        print(f"Error: Directory '{args.directory}' does not exist")
        sys.exit(1)

    # Find llama-conversation-docker.py script
    llama_script = args.llama_script or find_llama_script()
    if not llama_script:
        print("Error: Could not find llama-conversation-docker.py script")
        print("Please specify location with --llama-script option")
        sys.exit(1)

    if not os.path.isfile(llama_script):
        print(f"Error: llama-conversation-docker.py script not found at: {llama_script}")
        sys.exit(1)

    log_activity(f"Monitor started for directory: {args.directory}", args.log)
    log_activity(f"Using llama script: {llama_script}", args.log)

    def process_directory():
        """Process all ready prompt files in the directory"""
        prompt_files = find_prompt_files(args.directory)

        if not prompt_files:
            if args.verbose:
                log_activity("No .prompt files found to process", args.log)
            return 0

        processed_count = 0

        for prompt_file in prompt_files:
            # Check if file is stable (not being written to)
            if not is_file_ready(prompt_file):
                if args.verbose:
                    log_activity(f"Skipping {prompt_file} (still being written)", args.log)
                continue

            if args.dry_run:
                log_activity(f"Would process: {prompt_file}", args.log)
                processed_count += 1
                continue

            log_activity(f"Processing: {prompt_file}", args.log)

            # Process the file
            success = process_prompt_file(prompt_file, llama_script, args.verbose, args.python)

            # Mark as complete or error
            new_name = mark_as_complete(prompt_file, success)
            if new_name:
                status = "completed" if success else "failed"
                log_activity(f"File {status}: {prompt_file} -> {new_name}", args.log)
                processed_count += 1
            else:
                log_activity(f"Could not rename file: {prompt_file}", args.log)

        return processed_count

    # Main processing loop
    try:
        if args.continuous:
            log_activity(f"Starting continuous monitoring (interval: {args.interval}s)", args.log)
            while True:
                count = process_directory()
                if count > 0:
                    log_activity(f"Processed {count} files", args.log)

                time.sleep(args.interval)
        else:
            # Single run
            count = process_directory()
            log_activity(f"Single run completed. Processed {count} files", args.log)

    except KeyboardInterrupt:
        log_activity("Monitor stopped by user (Ctrl+C)", args.log)
    except Exception as e:
        log_activity(f"Monitor error: {e}", args.log)
        sys.exit(1)

if __name__ == "__main__":
    main()
