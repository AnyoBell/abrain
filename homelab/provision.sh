#!/usr/bin/env bash
#
# provision.sh — sets up an isolated Ubuntu VM for running the personal-agi
# stack. Installs Ollama + Python, locks down the firewall to deny-by-default,
# disables services this box doesn't need.
#
# Run with: sudo ./provision.sh
# Read it before running it.

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run this with sudo."
  exit 1
fi

echo "== Updating system =="
apt update && apt upgrade -y

echo "== Installing base packages =="
apt install -y python3 python3-venv python3-pip git curl ufw gocryptfs

echo "== Installing Ollama (local LLM runtime) =="
curl -fsSL https://ollama.com/install.sh | sh

echo "== Configuring firewall: deny-by-default, allow SSH only =="
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
# Ollama (11434) and Chroma stay local-only — no ufw rule needed since
# they're not exposed beyond localhost by default. If you ever bind them
# to 0.0.0.0, add explicit rules scoped to your Tailscale subnet only.
ufw --force enable

echo "== Disabling unnecessary services =="
systemctl disable --now avahi-daemon 2>/dev/null || true
systemctl disable --now cups 2>/dev/null || true

echo "== Done =="
echo "Firewall status:"
ufw status verbose
echo ""
echo "Next steps:"
echo "  1. Pull a model:      ollama pull llama3.1:8b"
echo "  2. Set up the venv and install requirements.txt for personal-agi"
echo "  3. (Optional) Install Tailscale for remote access instead of port-forwarding:"
echo "       curl -fsSL https://tailscale.com/install.sh | sh && tailscale up"
