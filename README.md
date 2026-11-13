# Personal AGI — Local, Private, Open Source

Self-hosted research agent that delivers a morning brief: the latest cybersecurity news, then a deep dive into one random research topic.

## Architecture

```
notes/*.md  --ingest.py-->  Chroma vector store (local, encrypted at rest)
                                     |
                              agent.py (retrieval loop)
                                     |
                          Ollama (local LLM, e.g. llama3.1)
```

- **LLM**: served by [Ollama](https://ollama.com) — fully open weights, runs offline.
- **Embeddings**: [sentence-transformers](https://www.sbert.net/) `bge-base-en-v1.5` — local, no API calls.
- **Vector store**: [Chroma](https://www.trychroma.com/) — self-hosted, persists to disk.
- **No cloud calls, ever**, once models are pulled. You can firewall this box
  to zero outbound egress after setup and it still works.

## Setup (run on your homelab, not in this sandbox)

### 1. Install Ollama and pull a model
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1:8b        # or mistral, qwen2.5, etc.
```

### 2. Set up a Python venv
```bash
cd personal-agi
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Add your data
Drop markdown files (notes, writing, research) into `notes/`. Subfolders are fine.

### 4. Ingest into the vector store
```bash
python ingest.py
```
This chunks your markdown, embeds it locally, and writes to `./chroma_db/`
(gitignored — this is your private index, encrypt the disk it lives on).

### 5. Run the agent
```bash
python agent.py
```
Ask it questions. It retrieves relevant chunks from your own notes and asks
your local Ollama model to answer grounded in them.

## Security notes (read this)

- **Encrypt the volume** holding `chroma_db/` and `notes/` — LUKS on Linux,
  FileVault on Mac. This is your most sensitive asset.
- **Isolate the host.** Run this in a VM or container separate from your
  daily-driver machine. Don't expose any port publicly — use Tailscale/WireGuard
  if you need remote access.
- **Verify model weights.** Check published checksums for anything you pull
  with `ollama pull` or `huggingface-cli download`.
- **Firewall egress.** Once models are downloaded, this stack needs zero
  internet access to function. Lock it down with `ufw`/`iptables` and confirm
  nothing calls out.
- **Git the notes repo, encrypt the remote.** If you push `notes/` anywhere,
  use `git-crypt` or keep it local-only.
- **Audit log.** `agent.py` logs every retrieval + generation to `logs/`
  (gitignored) so you have a local record of what the agent saw and said.

## Extending it

- Swap `llama3.1:8b` for any Ollama-supported model.
- Add tool-calling in `agent.py` (function schemas + a dispatch loop) once
  the retrieval baseline works.
- Fine-tuning (optional, later): use QLoRA via `unsloth` on a rented GPU if
  you want stylistic adaptation beyond retrieval. Treat fine-tuned weights as
  sensitive — encrypt, don't share.
