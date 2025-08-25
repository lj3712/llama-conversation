# llama-conversation

> **Text‑file batch runner for local LLMs via Ollama**\
> Drive models from plain `.prompt` files; run one‑offs or watch a folder and process prompts as you save them.

---

## Why this exists

Working with local LLMs is fastest when your *prompts are files*. They’re easy to version, diff, grep, and script. This repo turns that idea into two simple CLIs:

- `` — run a single prompt file (append the response back into the same file).
- `` — watch a directory for `*.prompt` files and process them automatically (great for batch jobs).

It’s intentionally small and dependency‑light so you can drop it into any workflow.

---

## What it does

- Reads a **plain‑text **``** file** that contains your conversation.
- Sends the conversation to an **Ollama** server (default `http://localhost:11434`).
- **Appends** the model’s reply to the same `.prompt` file (keeping a linear, audit‑friendly log).
- Prints **timing and basic metadata** to stdout (you can redirect to a log).
- Optional wrapper script (`llama-monitor-wrapper.sh`) to keep the monitor alive.

> ℹ️ The repo started life as a simple CLI; it has grown into a **batch/text‑file processing system**. The name may change later — the interface below is the current truth.

---

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com/download) running locally or reachable over the network
- `pip install -r requirements.txt`

> Tip: verify Ollama is up with `curl http://localhost:11434/api/tags`.

---

## Install

```bash
git clone https://github.com/lj3712/llama-conversation
cd llama-conversation
python -m venv .venv && source .venv/bin/activate  # (Windows: .venv\\Scripts\\activate)
pip install -r requirements.txt
```

Pull at least one model with Ollama (examples use Llama 3–class models, but use anything you like):

```bash
ollama pull llama3:8b
```

---

## The `.prompt` file format (front matter + body)

A `.prompt` file has two parts:

1. **Front matter**: a simple key/value block delimited by `---` lines.
2. **Body**: the actual message, starting with a marker like `---HUMAN---` followed by your text.

**Supported front‑matter keys**

- `server_url` — Ollama endpoint (e.g. `http://localhost:11434`).
- `model_name` — model to use (must exist in Ollama, e.g. `llama3:8b`, `deepseek-r1:32b`).
- `max_tokens` — integer limit *or* `none` for unlimited.
- `temperature` — 0.0–2.0 (creativity).
- `top_p` — 0.0–1.0 (nucleus sampling).
- `timeout` — seconds to wait for a response.

> Lines beginning with `#` are comments and may appear anywhere in the front matter. Any CLI flags you pass take precedence over the front‑matter values.

**Minimal example**

```text
---
# Configuration for Ollama server
server_url: http://localhost:11434   # URL of Ollama server
model_name: deepseek-r1:32b          # Model name (as known to Ollama)
max_tokens: none                     # 'none' for unlimited, or an integer
temperature: 0.9
top_p: 0.9
timeout: 3600                        # seconds
---

---HUMAN---
Hello! I'm testing the Ollama server with multiple model support.
Can you explain what makes large language models useful for research?
```

**Notes**

- The body begins with a marker line such as `---HUMAN---` followed by your prompt text.
- You can run the tool, read the appended reply, edit the file (or add another `---HUMAN---` section), and run again.
- Unknown keys in the front matter are ignored.

---

## Quick start (single file)

```bash
# 1) create a prompt file
cat > examples/hello.prompt <<'EOF'
---
# minimal local run
server_url: http://localhost:11434
model_name: llama3:8b
max_tokens: 256
temperature: 0.2
top_p: 0.9
timeout: 120
---

---HUMAN---
Give me one fun fact about Jupiter in < 30 words.
EOF

# 2) run the conversation once
python ollama-conversation.py examples/hello.prompt

# 3) open the file to see the appended reply
sed -n '1,200p' examples/hello.prompt
```

**Common flags** (use `-h` for the authoritative list on your build):

- `--model llama3:8b` — override `model_name` in the file
- `--temperature 0.2` `--top-p 0.9` `--max-tokens 256`
- `--host http://localhost:11434` — point at a remote Ollama
- `--dry-run` — parse the file and print the payload; don’t call the model
- `--debug` — extra logs

---

## Batch mode: watch a folder

Have a directory of `.prompt` files you want processed automatically? Point the monitor at it:

```bash
# process any *.prompt created or modified under ./jobs
python llama-prompt-monitor.py ./jobs

# optional: keep it running under a simple shell wrapper
./llama-monitor-wrapper.sh ./jobs
```

**Behavior**

- Processes each file **once per change** (saves or appends trigger a run).
- Skips files that already contain a most‑recent `ASSISTANT` block for the trailing `USER` block (idempotent-ish).
- Logs a one‑line summary per completion (start/end/duration/model/tokens when available).

> Tip: pair this with your editor or another script that drops `.prompt` files into `./jobs` and you have a dead‑simple render farm for prompts.

---

## Environment variables

- `OLLAMA_HOST` — default is `http://localhost:11434` (CLI `--host` overrides)
- `LC_DEFAULT_MODEL` — optional default model if not provided elsewhere

---

## Examples

See the [`examples/`](./examples) folder for ready‑to‑run files. A few ideas:

- **Zero‑shot batch**: drop 100 small `.prompt` files in `jobs/`; the monitor will chew through them.
- **Prompt sweeps**: generate N files with slightly different `# options:` (temperature, max tokens) and compare.
- **Programmatic runs**: any tool that writes a `.prompt` file can “call” a model.

---

## Troubleshooting

- **Connection refused** — make sure Ollama is running and reachable; set `--host` if it’s remote.
- **Model not found** — pull it first: `ollama pull <model>`.
- **Nothing happens in batch mode** — confirm the file extension is `.prompt` and that you actually saved the file (touch/modify time must change).
- **Weird formatting in output** — remember the file is an append‑only log; keep your own separators consistent.

---

## Roadmap (nice‑to‑haves)

- Sidecar JSON (`.meta.json`) with per‑call timings and token counts
- Glob/regex filters in the monitor
- Simple retry policy and exponential backoff for flaky hosts
- Optional output directory (mirror the input filename but write responses elsewhere)

---

## License

MIT — see [LICENSE](./LICENSE).

---

## Acknowledgements

- [Ollama](https://ollama.com) for the local LLM runtime.
- Everyone building file‑first workflows.

---

## FAQ

**Why not store messages in JSON?**\
Text files are easier to compose by hand, diff nicely, and are editor‑agnostic. When/if you need structured metadata, that’s what sidecars are for.

**Does this support tools, images, or vision models?**\
The CLI sticks to basic chat. If your Ollama model accepts images or tools, you can extend the payload builder; the monitor will happily feed whatever `ollama-conversation.py` supports.

**Can I point this at a remote box?**\
Yes — pass `--host` or set `OLLAMA_HOST` and ensure firewalls permit access.

