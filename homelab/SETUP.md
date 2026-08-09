# Homelab Setup — Isolated VM for Personal AGI

Simple, isolated VM setup on UTM (same tool as your existing homelab), kept
separate from your Kali/Metasploitable/ELK boxes.

## 1. Create the VM in UTM

1. UTM → New VM → Virtualize (not Emulate, for speed) → Linux.
2. Download **Ubuntu Server 24.04 LTS** ISO (minimal — you don't need a
   desktop environment for this).
3. Resource allocation — sizing for an 8B model:
   - **RAM: 12–16GB** (8B model needs ~8GB just to load; leave headroom for
     embeddings + OS)
   - **CPU: 4+ cores**
   - **Disk: 60GB+** (model weights alone run 5–15GB each; notes + vector
     store are small by comparison)
4. Name it something distinct from your other VMs, e.g. `personal-agi-vm`.
5. **Network mode: Shared Network / NAT** — not Bridged. This keeps it off
   your main LAN by default, one less thing to segment manually.

## 2. Base OS setup

Boot the VM, install Ubuntu Server minimal, then SSH in (or use the UTM
console directly) and run the provisioning script below.

## 3. Run the provisioning script

Copy `provision.sh` (in this folder) into the VM and run it:

```bash
chmod +x provision.sh
sudo ./provision.sh
```

This installs Ollama, Python, sets up a firewall that blocks everything
inbound except SSH, and disables unnecessary services. Read it before
running — nothing here is exotic, but you should know what's on the box.

## 4. Encrypt the data volume

If UTM's disk image isn't already encrypted, encrypt at least the
partition/folder holding your notes and vector store:

```bash
# Simplest option: encrypt a folder with gocryptfs (lightweight, no repartitioning)
sudo apt install gocryptfs
mkdir -p ~/agi-data-encrypted ~/agi-data
gocryptfs -init ~/agi-data-encrypted
gocryptfs ~/agi-data-encrypted ~/agi-data
# Put your personal-agi project's notes/ and chroma_db/ inside ~/agi-data,
# and symlink them from the project folder.
```

Unmount (`fusermount -u ~/agi-data`) when you're not actively using it.

## 5. Move the project in

```bash
git clone <wherever you're keeping personal-agi> ~/agi-data/personal-agi
cd ~/agi-data/personal-agi
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
ollama pull llama3.1:8b
python ingest.py
python agent.py
```

## 6. Remote access (optional, only if you need it)

Don't port-forward. Install Tailscale instead — gives you a private
mesh network to reach the VM without exposing anything publicly:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

## 7. Verify isolation

From the VM, confirm it's not reachable from outside your Tailscale/SSH
paths, and confirm outbound is locked down to what's actually needed:

```bash
sudo ufw status verbose
```

You should see deny-by-default with only SSH (and Tailscale, if used)
allowed in. Ollama and Chroma only need to talk to `localhost` — they
should have no inbound rule at all.

## Day-to-day

- Snapshot the VM in UTM before major changes (model updates, new tools) —
  cheap rollback if something breaks or you want to audit a change.
- Keep this VM's only job being the agent. Don't browse, don't install
  unrelated software on it — smaller attack surface, easier to reason about.
