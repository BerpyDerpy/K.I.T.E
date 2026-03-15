"""
core/retriever.py — Skill Retriever for K.I.T.E.

Loads skills from registry/skills.json, embeds their descriptions
with sentence-transformers, stores them in ChromaDB, and exposes
a retrieve_skill() function for semantic search.
"""

import json
import os

import chromadb
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# ──────────────────────────────────────────────
#  Config
# ──────────────────────────────────────────────
load_dotenv()
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
REGISTRY_PATH = os.getenv("REGISTRY_PATH", "./registry/skills.json")

# The embedding model (small + fast, runs locally)
EMBED_MODEL = "all-MiniLM-L6-v2"

# ChromaDB collection name for skills
COLLECTION_NAME = "kite_skills"


# ──────────────────────────────────────────────
#  Step 1: Load skills from JSON
# ──────────────────────────────────────────────
def load_skills(path: str = REGISTRY_PATH) -> list[dict]:
    """Read the skills registry JSON file and return a list of skill dicts."""
    with open(path, "r") as f:
        skills = json.load(f)
    print(f"[retriever] Loaded {len(skills)} skills from {path}")
    return skills


# ──────────────────────────────────────────────
#  Step 2: Build the ChromaDB index
# ──────────────────────────────────────────────
def build_index(skills: list[dict]) -> chromadb.Collection:
    """
    Embed every skill description with sentence-transformers and
    store (or update) them in a persistent ChromaDB collection.

    Returns the ChromaDB collection for querying.
    """
    # Load the sentence-transformer model
    print(f"[retriever] Loading embedding model: {EMBED_MODEL} ...")
    model = SentenceTransformer(EMBED_MODEL)

    # Create / open a persistent ChromaDB client
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    # Delete old collection if it exists, so we always start fresh
    existing = [c.name for c in client.list_collections()]
    if COLLECTION_NAME in existing:
        client.delete_collection(COLLECTION_NAME)

    collection = client.create_collection(name=COLLECTION_NAME)

    # Prepare data for batch insert
    ids = [skill["id"] for skill in skills]
    descriptions = [skill["description"] for skill in skills]
    metadatas = [
        {
            "name": skill["name"],
            "description": skill["description"],
            "mcp_server_url": skill.get("mcp_server_url") or "",
            "tools": json.dumps(skill.get("tools", [])),
        }
        for skill in skills
    ]

    # Compute embeddings
    print(f"[retriever] Embedding {len(descriptions)} skill descriptions ...")
    embeddings = model.encode(descriptions).tolist()

    # Upsert into ChromaDB
    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=descriptions,
        metadatas=metadatas,
    )
    print(f"[retriever] Stored {len(ids)} skills in ChromaDB at '{CHROMA_PATH}'")

    return collection


# ──────────────────────────────────────────────
#  Step 3: Retrieve matching skills
# ──────────────────────────────────────────────

# Module-level cache so we only load the model once
_model = None
_collection = None


def _get_model() -> SentenceTransformer:
    """Lazy-load the sentence-transformer model."""
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def _get_collection() -> chromadb.Collection:
    """Lazy-load the ChromaDB collection."""
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = client.get_collection(name=COLLECTION_NAME)
    return _collection


def retrieve_skill(query: str, top_k: int = 5) -> list[dict]:
    """
    Retrieve the top-k most relevant skills for a user query.

    Parameters
    ----------
    query : str
        The natural-language query to match against skill descriptions.
    top_k : int
        How many results to return (default 5).

    Returns
    -------
    list[dict]
        A list of skill dicts, each containing:
        id, name, description, mcp_server_url, tools, and distance.
    """
    model = _get_model()
    collection = _get_collection()

    # Embed the query
    query_embedding = model.encode([query]).tolist()

    # Search ChromaDB
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
    )

    # Unpack ChromaDB results into clean dicts
    skills = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        skills.append({
            "id": results["ids"][0][i],
            "name": meta["name"],
            "description": meta["description"],
            "mcp_server_url": meta["mcp_server_url"] or None,
            "tools": json.loads(meta["tools"]),
            "distance": results["distances"][0][i],
        })

    return skills


# ──────────────────────────────────────────────
#  __main__ test block
# ──────────────────────────────────────────────
if __name__ == "__main__":
    # --- 1. Load skills and build the index ---
    skills = load_skills()
    build_index(skills)

    # --- 2. Test queries ---
    test_queries = [
        "List all files in my home directory",
        "What time is it in Tokyo right now?",
        "Send a POST request to an API with JSON data",
    ]

    print("\n" + "=" * 60)
    print("  K.I.T.E. Retriever — Test Run")
    print("=" * 60)

    for query in test_queries:
        print(f"\n{'─' * 60}")
        print(f"  Query: \"{query}\"")
        print(f"{'─' * 60}")

        matched_skills = retrieve_skill(query, top_k=5)

        for rank, skill in enumerate(matched_skills, 1):
            print(f"  {rank}. {skill['name']}  (id: {skill['id']})")
            print(f"     {skill['description']}")
            print(f"     distance: {skill['distance']:.4f}")

    print("\n" + "=" * 60)
    print("  Tests complete.")
    print("=" * 60)
