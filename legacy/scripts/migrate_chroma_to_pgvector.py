#!/usr/bin/env python3
"""
Migrate existing ChromaDB embeddings to pgvector.

Usage:
    python scripts/migrate_chroma_to_pgvector.py

Requirements:
    - DATABASE_URL env var pointing to the target Postgres instance
    - The old chroma_db/ directory must be present
    - Migrations 001 + 002 must already be applied
    - A placeholder user must exist in the users table (see --user-id flag)

Options:
    --chroma-dir PATH   Path to the old chroma_db directory (default: chroma_db)
    --user-id ID        Clerk user_id to assign migrated documents to (default: "migrated_user")
    --dry-run           Print what would be done without writing to Postgres
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--chroma-dir", default="chroma_db")
    p.add_argument("--user-id", default="migrated_user")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def migrate(chroma_dir: str, user_id: str, dry_run: bool) -> None:
    from dotenv import load_dotenv
    load_dotenv()

    db_url = os.getenv("DATABASE_URL", "postgresql://documind:documind@localhost:5432/documind")
    # psycopg2 needs plain postgresql:// not postgresql+asyncpg://
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    import psycopg2
    import psycopg2.extras
    from pgvector.psycopg2 import register_vector

    from chromadb import PersistentClient
    from chromadb.config import Settings

    print(f"Connecting to: {db_url}")
    if dry_run:
        print("[DRY RUN] No writes will be performed.")

    chroma_path = Path(chroma_dir)
    if not chroma_path.exists():
        print(f"ChromaDB directory not found: {chroma_path}")
        sys.exit(1)

    client = PersistentClient(
        path=str(chroma_path),
        settings=Settings(anonymized_telemetry=False),
    )
    collections = client.list_collections()
    print(f"Found {len(collections)} ChromaDB collection(s): {[c.name for c in collections]}")

    pg = psycopg2.connect(db_url)
    register_vector(pg)
    psycopg2.extras.register_uuid(pg)

    with pg.cursor() as cur:
        # Ensure placeholder user exists
        cur.execute(
            "INSERT INTO users (clerk_id, email) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (user_id, "migrated@local"),
        )
        pg.commit()

    total_chunks = 0
    total_docs = 0

    for collection in collections:
        col = client.get_collection(collection.name)
        result = col.get(include=["embeddings", "documents", "metadatas"])

        ids = result["ids"]
        embeddings = result["embeddings"]
        texts = result["documents"]
        metadatas = result["metadatas"]

        print(f"\nCollection '{collection.name}': {len(ids)} chunks")

        # Group chunks by doc_id
        by_doc: dict[str, list[tuple]] = {}
        for chunk_id, emb, text, meta in zip(ids, embeddings, texts, metadatas):
            doc_id = meta.get("doc_id", "unknown")
            by_doc.setdefault(doc_id, []).append((chunk_id, emb, text, meta))

        print(f"  → {len(by_doc)} unique document(s)")

        for doc_id, chunks in by_doc.items():
            filename = chunks[0][3].get("source", f"{doc_id}.pdf")
            print(f"  Migrating doc {doc_id} ({filename}) with {len(chunks)} chunks…")

            if dry_run:
                total_docs += 1
                total_chunks += len(chunks)
                continue

            with pg.cursor() as cur:
                # Create document record
                cur.execute(
                    """
                    INSERT INTO documents (id, user_id, filename, status)
                    VALUES (%s, %s, %s, 'indexed')
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (uuid.UUID(doc_id) if len(doc_id) == 32 else uuid.uuid5(uuid.NAMESPACE_DNS, doc_id),
                     user_id, filename),
                )

                # Insert chunks
                rows = []
                for chunk_ref, emb, text, meta in chunks:
                    rows.append((
                        uuid.uuid4(),
                        doc_id if len(doc_id) == 36 else str(uuid.uuid5(uuid.NAMESPACE_DNS, doc_id)),
                        chunk_ref,
                        text or "",
                        json.dumps(meta),
                        emb,
                    ))

                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO chunks (id, doc_id, ref, content, metadata, embedding)
                    VALUES %s
                    ON CONFLICT (ref) DO NOTHING
                    """,
                    rows,
                    template="(%s, %s::uuid, %s, %s, %s::jsonb, %s)",
                )

            pg.commit()
            total_docs += 1
            total_chunks += len(chunks)

    pg.close()

    print(f"\n{'[DRY RUN] Would migrate' if dry_run else 'Migrated'} {total_docs} document(s) "
          f"and {total_chunks} chunk(s) to pgvector.")

    if not dry_run:
        print("\nNext steps:")
        print("  1. Verify data in Postgres: SELECT COUNT(*) FROM chunks;")
        print("  2. Delete the old chroma_db/ directory once satisfied.")
        print("  3. Remove bm25_*.pkl files from the old chroma_db directory.")


if __name__ == "__main__":
    args = _parse_args()
    migrate(args.chroma_dir, args.user_id, args.dry_run)
