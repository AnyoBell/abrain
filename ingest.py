"""
ingest.py — chunk your markdown notes, embed them locally, store in Chroma.

Nothing here calls out to the internet. Embeddings run on-device via
sentence-transformers; the vector store is a local on-disk Chroma instance.

Usage:
    python ingest.py            # ingest everything in notes_dir
    python ingest.py --reset    # wipe and rebuild the collection from scratch
"""
import argparse
import hashlib
import os
import sys
from pathlib import Path

import chromadb
import yaml
from sentence_transformers import SentenceTransformer
from tqdm import tqdm


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Simple sliding-window chunker. Good enough for markdown notes;
    swap for a markdown-aware splitter (e.g. header-based) if your notes
    have heavy structure you want preserved."""
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true",
                         help="Wipe the collection and rebuild from scratch")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)

    notes_dir = Path(cfg["notes_dir"])
    chroma_dir = Path(cfg["chroma_dir"])
    chroma_dir.mkdir(parents=True, exist_ok=True)

    md_files = sorted(notes_dir.rglob("*.md"))
    if not md_files:
        print(f"No markdown files found in {notes_dir.resolve()}. "
              f"Add some notes and re-run.")
        sys.exit(0)

    print(f"Found {len(md_files)} markdown files.")
    print(f"Loading local embedding model: {cfg['embedding_model']} "
          f"(first run downloads it once, then it's cached locally)")
    model = SentenceTransformer(cfg["embedding_model"])

    client = chromadb.PersistentClient(path=str(chroma_dir))

    if args.reset:
        try:
            client.delete_collection(cfg["collection_name"])
            print("Existing collection wiped.")
        except Exception:
            pass

    collection = client.get_or_create_collection(cfg["collection_name"])

    all_chunks, all_ids, all_metas = [], [], []

    for fpath in tqdm(md_files, desc="Chunking"):
        text = fpath.read_text(encoding="utf-8", errors="ignore")
        if not text.strip():
            continue
        rel_path = str(fpath.relative_to(notes_dir))
        fhash = file_hash(fpath)
        chunks = chunk_text(text, cfg["chunk_size"], cfg["chunk_overlap"])
        for i, chunk in enumerate(chunks):
            chunk_id = f"{fhash}-{i}"
            all_chunks.append(chunk)
            all_ids.append(chunk_id)
            all_metas.append({"source": rel_path, "chunk_index": i})

    if not all_chunks:
        print("Nothing to embed (files were empty).")
        return

    print(f"Embedding {len(all_chunks)} chunks locally...")
    embeddings = model.encode(all_chunks, show_progress_bar=True,
                               convert_to_numpy=True).tolist()

    # Upsert in batches to keep memory reasonable on modest homelab hardware
    batch = 256
    for i in tqdm(range(0, len(all_chunks), batch), desc="Writing to Chroma"):
        collection.upsert(
            ids=all_ids[i:i + batch],
            documents=all_chunks[i:i + batch],
            embeddings=embeddings[i:i + batch],
            metadatas=all_metas[i:i + batch],
        )

    print(f"Done. {len(all_chunks)} chunks indexed from {len(md_files)} files.")
    print(f"Vector store lives at: {chroma_dir.resolve()} "
          f"— encrypt this volume at rest.")


if __name__ == "__main__":
    main()
