# Epub AI Reader (Ralph)

## Embeddings (TEI)

This project uses Hugging Face Text Embeddings Inference (TEI) for embeddings.

- Docker image tag (CPU): `ghcr.io/huggingface/text-embeddings-inference:cpu-1.8.1`
- To switch to GPU, change the image tag in `docker-compose.yml` (e.g. to `:cuda-1.8.1`).

Required environment variables for embeddings:

- `TEI_MODEL` (default: `BAAI/bge-base-en-v1.5`)
- `TEI_BASE_URL` (default: `http://localhost:8080`)
- `TEI_BATCH_SIZE` (default: `32`)

The TEI container caches the model in a Docker volume (`tei_data`) so it is reused across restarts.

## Docker Compose Usage

- Prod app: `docker compose up --build`
- Dev app (fast reload): `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build`
- Dev app + codex: `docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.codex.yml up --build`

## Vector Storage

Chunk embeddings and payloads are stored in Qdrant. ChromaDB is no longer used for ingestion or sync.
