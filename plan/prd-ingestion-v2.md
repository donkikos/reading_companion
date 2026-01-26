# PRD: V2 Ingestion (Qdrant Chunk Indexing)

## Introduction/Overview

Implement V2 ingestion that indexes EPUB content as multi-sentence chunks in Qdrant to improve retrieval quality while preserving strict spoiler safety via sentence-level payloads.

## Goals

- Build a Qdrant index of chunked content with sentence-level payloads for truncation.
- Keep ingestion deterministic and repeatable for the same book content.
- Support re-ingestion to replace all chunks for a book.
- Fail fast with clear errors if Qdrant is unavailable.
- Use a TEI embedding service for ingestion (CPU on macOS; switch to GPU by changing the
  Docker Compose image tag; Ollama was the initial provider; see US-012/US-014 and US-017).
- Support reindexing when the embedding model changes.
- Run the embedding service in Docker Compose with persistent model storage.

## User Stories

### US-001: Build deterministic sentence stream

**Description:** As a reader, I want my uploaded book parsed into a stable sentence stream so indexing is consistent.

**Acceptance Criteria:**

- [x] Parse the EPUB into an ordered list of sentences S0..SN.
- [x] Sentence IDs are monotonic and contiguous for each book.
- [x] Run `ruff format` on changed Python files (line length 100)
- [x] Run `ruff check .` and ensure it passes
- [x] Add or update tests for this change
- [x] Tests pass
- [x] Run `pytest` and ensure it passes
- [x] Typecheck/lint passes

### US-002: Create fixed-window chunks

**Description:** As a reader, I want my book chunked consistently so retrieval quality is reliable.

**Acceptance Criteria:**

- [x] Create chunks using a fixed window of 8 sentences with overlap of 2.
- [x] Each chunk covers the ordered sentence-id interval `[pos_start..pos_end]`.
- [x] For each chunk, `sentences[k]` maps to `sid = pos_start + k`.
- [x] Run `ruff format` on changed Python files (line length 100)
- [x] Run `ruff check .` and ensure it passes
- [x] Add or update tests for this change
- [x] Tests pass
- [x] Run `pytest` and ensure it passes
- [x] Typecheck/lint passes

### US-003: Store chunk payloads in Qdrant

**Description:** As a reader, I want my uploaded book indexed in Qdrant so spoiler-safe retrieval can use it.

**Acceptance Criteria:**

- [x] Store payload fields: `book_id`, `chapter_index`, `pos_start`, `pos_end`, `sentences`, `text`.
- [x] Chunk embeddings are computed from the full chunk `text`.
- [x] Qdrant points are written for each chunk of the current book.
- [x] Run `ruff format` on changed Python files (line length 100)
- [x] Run `ruff check .` and ensure it passes
- [x] Add or update tests for this change
- [x] Tests pass
- [x] Run `pytest` and ensure it passes
- [x] Typecheck/lint passes

### US-004: Replace chunks on re-upload

**Description:** As a reader, I want re-uploading a book to replace old indexes so answers stay consistent.

**Acceptance Criteria:**

- [x] Re-ingestion deletes or replaces all prior chunks for the same `book_id`.
- [x] No duplicate chunks remain after re-ingest.
- [x] Run `ruff format` on changed Python files (line length 100)
- [x] Run `ruff check .` and ensure it passes
- [x] Add or update tests for this change
- [x] Tests pass
- [x] Run `pytest` and ensure it passes
- [x] Typecheck/lint passes

### US-005: Track ingestion progress

**Description:** As a reader, I want to see ingestion progress so I know when the book is ready.

**Acceptance Criteria:**

- [x] Progress is tracked as a best-effort percentage during ingestion.
- [x] Progress is based on sentences processed out of total.
- [x] Run `ruff format` on changed Python files (line length 100)
- [x] Run `ruff check .` and ensure it passes
- [x] Add or update tests for this change
- [x] Tests pass
- [x] Run `pytest` and ensure it passes
- [x] Typecheck/lint passes

### US-006: Fail clearly if Qdrant is unavailable

**Description:** As a reader, I want a clear failure when indexing cannot run so I can retry later.

**Acceptance Criteria:**

- [x] Ingestion fails with an explicit error when Qdrant cannot be reached.
- [x] Partial ingestion is not marked as successful.
- [x] Run `ruff format` on changed Python files (line length 100)
- [x] Run `ruff check .` and ensure it passes
- [x] Add or update tests for this change
- [x] Tests pass
- [x] Run `pytest` and ensure it passes
- [x] Typecheck/lint passes

### US-007: Verify ingestion via API

**Description:** As a developer, I want an API endpoint to verify Qdrant ingestion so I can confirm indexing without relying on retrieval.

**Acceptance Criteria:**

- [x] Provide an API endpoint that accepts `book_id` and verifies Qdrant ingestion for that book.
- [x] The endpoint recomputes expected chunk count from the sentence stream and chunking params.
- [x] The endpoint queries Qdrant by `book_id` and confirms the stored count matches expected.
- [x] The endpoint validates payload fields and `pos_start`/`pos_end` monotonicity on a sample of chunks.
- [x] The endpoint returns a clear pass/fail response with details on mismatches.
- [x] If Qdrant is unavailable, the endpoint returns an explicit error.
- [x] Restart the app server after implementing this story before verifying the endpoint.
- [x] Run `ruff format` on changed Python files (line length 100)
- [x] Run `ruff check .` and ensure it passes
- [x] Add or update tests for this change
- [x] Tests pass
- [x] Run `pytest` and ensure it passes
- [x] Typecheck/lint passes

### US-008: Single command to launch app + Qdrant

**Description:** As a developer, I want a single `docker compose` command to start the app and Qdrant so ingestion can run without manual service setup.

**Acceptance Criteria:**

- [x] Provide one `docker compose` command that starts the FastAPI app and Qdrant.
- [x] The command performs a health check that confirms the app responds and Qdrant is reachable.
- [x] The command exits cleanly and stops both services.
- [x] Restart the app server after implementing this story before running health checks.
- [x] Run `ruff format` on changed Python files (line length 100)
- [x] Run `ruff check .` and ensure it passes
- [x] Add or update tests for this change
- [x] Tests pass
- [x] Run `pytest` and ensure it passes
- [x] Typecheck/lint passes

### US-009: Add EPUB fixture for automated ingestion tests

**Description:** As a developer, I want a stable EPUB fixture so ingestion tests can run deterministically.

**Acceptance Criteria:**

- [x] Add a fixture EPUB at `tests/fixtures/minimal.epub` with multiple chapters and paragraphs.
- [x] Tests can ingest the fixture and verify Qdrant chunk counts using the verification API.
- [x] Restart the app server after implementing this story before running the ingestion tests.
- [x] The fixture stays ASCII-only and stable across runs.
- [x] Run `ruff format` on changed Python files (line length 100)
- [x] Run `ruff check .` and ensure it passes
- [x] Add or update tests for this change
- [x] Tests pass
- [x] Run `pytest` and ensure it passes
- [x] Typecheck/lint passes

### US-010: Delete a book with confirmation

**Description:** As a reader, I want to delete a book with confirmation so I can remove it safely.

**Acceptance Criteria:**

- [x] Provide a delete action in the library UI that opens a confirmation dialog.
- [x] Confirming delete removes the book file and all stored data (SQLite metadata, reading state, chapters, Chroma docs, Qdrant chunks).
- [x] Cancelling delete leaves the book untouched.
- [x] The library UI updates to remove the deleted book without a full reload.
- [x] Restart the app server after implementing this story before verifying the UI.
- [x] Run `ruff format` on changed Python files (line length 100)
- [x] Run `ruff check .` and ensure it passes
- [x] Add or update tests for this change
- [x] Tests pass
- [x] Run `pytest` and ensure it passes
- [x] Typecheck/lint passes
- [x] Verify in browser using MCP

### US-011: End-to-end ingestion progress in the UI

**Description:** As a reader, I want clear progress updates across all ingestion stages so I know what is happening.

**Acceptance Criteria:**

- [x] Uploading a book shows progress messages and percentage updates in the library UI.
- [x] The UI surfaces stage transitions (hashing, parsing, chunking, embedding, Qdrant upsert, metadata save).
- [x] The progress percentage reflects the full ingestion pipeline, not only sentence streaming.
- [x] Sentence-based progress may be tracked internally, but the UI must reflect the full pipeline only.
- [x] The UI shows top-level stage progress as `i/N` with an overall progress number.
- [x] Lower-level percent is optional (e.g., sentence parsing) when reasonable.
- [x] The task status reaches "completed" only after all storage steps finish.
- [x] Errors during ingestion surface a clear error message in the UI.
- [x] If any ingestion error occurs during verification, the story fails verification.
- [x] Restart the app server after implementing this story before verifying the UI.
- [x] Verify in browser using MCP.
- [x] Run `ruff format` on changed Python files (line length 100)
- [x] Run `ruff check .` and ensure it passes
- [x] Add or update tests for this change
- [x] Tests pass
- [x] Run `pytest` and ensure it passes
- [x] Typecheck/lint passes

### US-012: Configure embedding provider for ingestion

**Description:** As a developer, I want ingestion to use a configurable Ollama embedding service so we can improve retrieval quality without changing APIs.

**Acceptance Criteria:**

- [x] Embeddings are generated by calling Ollama `/api/embed` during ingestion.
- [x] The embedding model name and base URL are configurable (default model: `BAAI/bge-base-en-v1.5`).
- [x] Optional embedding dimensions are configurable (when supported by Ollama).
- [x] If the embedding service is unavailable, ingestion fails with a clear error.
- [x] Ollama runs as a docker compose service and uses a volume for model storage.
- [x] Add local Ollama model cache paths to `.gitignore`.
- [x] Run `ruff format` on changed Python files (line length 100)
- [x] Run `ruff check .` and ensure it passes
- [x] Add or update tests for this change
- [x] Tests pass
- [x] Run `pytest` and ensure it passes
- [x] Typecheck/lint passes

### US-013: Persist embedding metadata

**Description:** As a developer, I want ingestion to record embedding metadata so retrieval can detect mismatches.

**Acceptance Criteria:**

- [x] The ingestion pipeline records the embedding model name and dimensions used.
- [x] The ingestion pipeline documents that model changes require reindexing.
- [x] Run `ruff format` on changed Python files (line length 100)
- [x] Run `ruff check .` and ensure it passes
- [x] Add or update tests for this change
- [x] Tests pass
- [x] Run `pytest` and ensure it passes
- [x] Typecheck/lint passes

### US-014: Use Ollama embeddings for Qdrant vectors

**Description:** As a reader, I want Qdrant vectors to reflect semantic embeddings so retrieval quality is meaningful.

**Acceptance Criteria:**

- [x] Qdrant vectors are generated from Ollama embeddings of the full chunk text (not hash placeholders).
- [x] Run an end-to-end ingestion using a live Ollama model and confirm embeddings are stored in Qdrant.
- [x] Run `ruff format` on changed Python files (line length 100)
- [x] Run `ruff check .` and ensure it passes
- [x] Add or update tests for this change
- [x] Tests pass
- [x] Run `pytest` and ensure it passes
- [x] Typecheck/lint passes

### US-015: Remove Chroma ingestion

**Description:** As a developer, I want to remove Chroma writes so ingestion only targets Qdrant and SQLite.

**Acceptance Criteria:**

- [x] Ingestion no longer writes documents or metadata to Chroma.
- [x] All Chroma-related code paths are removed.
- [x] Delete flow does not attempt Chroma cleanup once Chroma is removed.
- [x] `/sync` uses Qdrant (not Chroma) for matching and position updates.
- [x] Removal is documented and tests are updated accordingly.
- [x] Run `ruff format` on changed Python files (line length 100)
- [x] Run `ruff check .` and ensure it passes
- [x] Add or update tests for this change
- [x] Tests pass
- [x] Run `pytest` and ensure it passes
- [x] Typecheck/lint passes

### US-016: Log ingestion timing metrics

**Description:** As a developer, I want ingestion timing metrics so we can validate performance on CPU-only Macs.

**Acceptance Criteria:**

- [x] Logs are structured JSON at debug level.
- [x] Logs include total ingestion time.
- [x] Logs include time spent generating embeddings.
- [x] Logs include time spent upserting to Qdrant.
- [x] Logs include chunks processed and chunks/sec.
- [x] Logs are emitted to stdout.
- [x] Run `ruff format` on changed Python files (line length 100)
- [x] Run `ruff check .` and ensure it passes
- [x] Add or update tests for this change
- [x] Tests pass
- [x] Run `pytest` and ensure it passes
- [x] Typecheck/lint passes

### US-017: Migrate embeddings away from Ollama to TEI (High Priority)

**Description:** As a developer, I want ingestion embeddings served by Hugging Face Text Embeddings Inference (TEI) so the configured model is actually served and reliable without Ollama.

**Acceptance Criteria:**

- [x] Replace the Ollama embedding dependency with a TEI service in Docker Compose.
- [x] Remove Ollama completely (compose service, env vars, code paths, docs/tests).
- [x] Use the CPU image `ghcr.io/huggingface/text-embeddings-inference:cpu-1.8.1` on macOS.
- [x] Switching to GPU is done by changing the Docker Compose image tag (no code changes).
- [x] TEI is configured to serve the target embedding model.
- [x] Ingestion embeddings are generated via TEI and succeed for a real EPUB upload.
- [x] TEI requests use the `/embed` endpoint and return an array of float arrays.
- [x] The embedding base URL and model name are configurable via environment variables (default model: `bge-base-en-v1.5`).
- [x] The model uses fixed dimensions; the configured Qdrant vector size matches the TEI embedding dimension.
- [x] The model is cached and reused across restarts (TEI model cache volume).
- [x] The app surfaces a clear error if the embedding service is unavailable.
- [x] Document in `README` the TEI image tag, how to switch to GPU via image tag, and required env vars (model name, base URL, batching).
- [x] Note that this story supersedes Ollama-specific stories (US-012/US-014) without changing their historical status in `prd.json`.
- [x] Run `ruff format` on changed Python files (line length 100)
- [x] Run `ruff check .` and ensure it passes
- [x] Add or update tests for this change
- [x] Tests pass
- [x] Run `pytest` and ensure it passes
- [x] Typecheck/lint passes

### US-018: Chunking within chapter boundaries

**Description:** As a reader, I want chunking to stay within chapter boundaries so context is consistent.

**Acceptance Criteria:**

- [x] Chunks are created per-chapter using the same window/overlap params.
- [x] Chunks do not cross chapter boundaries.
- [x] The last partial chunk in each chapter is kept.
- [x] `chapter_index` always matches the chunk's chapter.
- [x] Run `ruff format` on changed Python files (line length 100)
- [x] Run `ruff check .` and ensure it passes
- [x] Add or update tests for this change
- [x] Tests pass
- [x] Run `pytest` and ensure it passes
- [x] Typecheck/lint passes

### US-019: Data consistency check on server launch

**Description:** As a developer, I want server launch to clean up orphaned Qdrant data so storage stays consistent.

**Acceptance Criteria:**

- [x] On startup, scan local books in SQLite and remove Qdrant chunks for missing book IDs.
- [x] Cleanup runs before ingestion requests are accepted.
- [x] If Qdrant is unavailable, the server fails startup with a clear error.
- [x] Actions and errors are logged clearly.
- [x] Run `ruff format` on changed Python files (line length 100)
- [x] Run `ruff check .` and ensure it passes
- [x] Add or update tests for this change
- [x] Tests pass
- [x] Run `pytest` and ensure it passes
- [x] Typecheck/lint passes

### US-020: Purge old ingested Qdrant data after TEI migration

**Description:** As a developer, I want Qdrant data purged after TEI migration so all embeddings are consistent.

**Acceptance Criteria:**

- [x] At the start of implementing this story, purge all existing Qdrant chunks via API calls or CLI commands.
- [x] Cleanup is logged clearly and is idempotent.
- [x] Run `ruff format` on changed Python files (line length 100)
- [x] Run `ruff check .` and ensure it passes
- [x] Add or update tests for this change
- [x] Tests pass
- [x] Run `pytest` and ensure it passes
- [x] Typecheck/lint passes

## Functional Requirements

- FR-1: The system must parse EPUBs into a deterministic global sentence stream.
- FR-1a: Sentence IDs must be monotonic and contiguous for each book.
- FR-2: The system must build fixed-size chunks (window=8, overlap=2).
- FR-3: Each chunk must include payload fields `book_id`, `chapter_index`, `pos_start`, `pos_end`, `sentences`, `text`.
- FR-3a: Each chunk must cover `[pos_start..pos_end]` and map `sentences[k]` to `pos_start + k`.
- FR-4: The system must replace prior chunks for a book on re-ingest.
- FR-5: Ingestion must fail with a clear error when Qdrant is unavailable.
- FR-6: Chunk embeddings must be computed from the full chunk `text`.
- FR-7: The system must provide an API endpoint to verify Qdrant ingestion for a `book_id`.
- FR-8: The verification endpoint must recompute expected chunk counts and validate Qdrant payloads.
- FR-9: The system must provide a single command to launch the app and Qdrant with health checks.
- FR-10: The system must support an EPUB fixture for deterministic ingestion tests.
- FR-11: The system must allow deleting a book and all associated stored data.
- FR-12: Ingestion must generate embeddings via TEI (CPU on macOS; switch to GPU by changing the
  Docker Compose image tag).
- FR-13: Embedding model name and base URL must be configurable.
- FR-14: Ingestion must fail with a clear error if the embedding service is unavailable.
- FR-15: Changing the embedding model requires reindexing.
- FR-16: The embedding service runs as a docker compose service with persistent model storage.

## Non-Goals (Out of Scope)
- Reranking or hybrid retrieval.
- Alternative chunking strategies beyond fixed window.

## Design Considerations

- Keep chunking logic in a dedicated ingestion module (e.g., `ingest_v2.py`) for clarity.
- Use sentence-count-based chunking (window/overlap), not token-based splitting.
- Payload fields should be named consistently to support later retrieval filters.

## Technical Considerations

- Qdrant payload indexes should support filtering by `book_id` and `pos_start`.
- Use a `book_id` derived from the file hash to remain consistent with V1 identifiers.
- Ingestion is triggered by the existing upload flow and receives the `book_id`.
- Track ingestion progress as a best-effort full-pipeline percentage for the UI; internal
  sentence-based tracking is acceptable.
- Dependencies include `qdrant-client`.
- Qdrant must be available locally for ingestion runs.
- Add local embedding model cache paths to `.gitignore` to avoid committing downloads.
- TEI batching env vars: `MAX_CLIENT_BATCH_SIZE=64`, `MAX_BATCH_TOKENS=16384`.
- Use Docker Compose image tag changes to switch TEI CPU/GPU variants.
- Restart the app server after implementing new features so new routes and logic are loaded.
- Verification should recompute chunk counts from the sentence stream rather than relying on stored counts.
- Use `tests/fixtures/minimal.epub` as the deterministic ingestion fixture for tests.

## Success Metrics

- Re-ingesting the same EPUB yields identical chunk counts and positions.
- Verification endpoint passes for ingested books and fails clearly when counts or payloads mismatch.
- Single-command startup brings the app and Qdrant online with a passing health check.

## Open Questions

None.
