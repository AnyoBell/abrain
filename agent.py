"""
agent.py — retrieval-augmented chat loop, fully local.

Flow: your question -> embed locally -> retrieve top-k chunks from Chroma
-> build a grounded prompt -> generate with a local Ollama model.

Every retrieval + generation is logged to ./logs/ for your own audit trail.
No data leaves this machine at any point in this loop.

Prereqs:
    ollama pull llama3.1:8b   (or whatever you set in config.yaml)
    ollama serve              (usually already running as a service)
    python ingest.py          (must be run at least once first)

Usage:
    python agent.py
"""
import datetime
import json
import sys
from pathlib import Path

import chromadb
import ollama
import yaml
from sentence_transformers import SentenceTransformer


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


class PersonalAgent:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.logs_dir = Path(cfg["logs_dir"])
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        print(f"Loading local embedding model: {cfg['embedding_model']}")
        self.embed_model = SentenceTransformer(cfg["embedding_model"])

        chroma_dir = Path(cfg["chroma_dir"])
        if not chroma_dir.exists():
            print("No vector store found. Run `python ingest.py` first.")
            sys.exit(1)

        client = chromadb.PersistentClient(path=str(chroma_dir))
        try:
            self.collection = client.get_collection(cfg["collection_name"])
        except Exception:
            print("Collection not found. Run `python ingest.py` first.")
            sys.exit(1)

        self.ollama_client = ollama.Client(host=cfg["ollama_host"])

    def retrieve(self, query: str) -> list[dict]:
        q_embedding = self.embed_model.encode([query]).tolist()
        results = self.collection.query(
            query_embeddings=q_embedding,
            n_results=self.cfg["top_k"],
        )
        hits = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]
        for doc, meta, dist in zip(docs, metas, dists):
            hits.append({"text": doc, "source": meta.get("source"),
                         "distance": dist})
        return hits

    def build_prompt(self, query: str, hits: list[dict]) -> str:
        context = "\n\n".join(
            f"[Source: {h['source']}]\n{h['text']}" for h in hits
        )
        return (
            f"Context from your notes:\n\n{context}\n\n"
            f"---\n\nQuestion: {query}\n\n"
            f"Answer using the context above where relevant. Cite which "
            f"source file(s) you drew from."
        )

    def ask(self, query: str) -> str:
        hits = self.retrieve(query)
        prompt = self.build_prompt(query, hits)

        response = self.ollama_client.chat(
            model=self.cfg["ollama_model"],
            messages=[
                {"role": "system", "content": self.cfg["system_prompt"]},
                {"role": "user", "content": prompt},
            ],
        )
        answer = response["message"]["content"]

        self._log(query, hits, answer)
        return answer

    def _log(self, query: str, hits: list[dict], answer: str):
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "query": query,
            "retrieved_sources": [h["source"] for h in hits],
            "answer": answer,
        }
        log_file = self.logs_dir / f"{datetime.date.today().isoformat()}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")


def main():
    cfg = load_config()
    agent = PersonalAgent(cfg)

    print("\nPersonal AGI — local agent ready. Type 'exit' to quit.\n")
    while True:
        try:
            query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        if query.lower() in ("exit", "quit"):
            break
        if not query:
            continue

        answer = agent.ask(query)
        print(f"\nAgent: {answer}\n")


if __name__ == "__main__":
    main()
