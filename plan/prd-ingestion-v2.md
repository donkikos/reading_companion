# PRD: V2 Ingestion (Qdrant Chunk Indexing)

## Introduction/Overview

Implement V2 ingestion that indexes EPUB content as multi-sentence chunks in Qdrant to improve retrieval quality while preserving strict spoiler safety via sentence-level payloads.

## Goals

- Build a Qdrant index of chunked content with sentence-level payloads for truncation.
- Keep ingestion deterministic and repeatable for the same book content.
- Support re-ingestion to replace all chunks for a book.
- Fail fast with clear errors if Qdrant is unavailable.
- Use a GPU-backed TEI embedding service for ingestion (Ollama was the initial provider; see US-012/US-014 and US-017).
- Support reindexing when the embedding model changes.
- Run the embedding service in Docker Compose with persistent model storage.

## User Stories

### US-001: Build deterministic sentence stream

**Description:** As a reader, I want my uploaded book parsed into a stable sentence stream so indexing is consistent.

**Acceptance Criteria:**

- [ ] Parse the EPUB into an ordered list of sentences S0..SN.
- [ ] Sentence IDs are monotonic and contiguous for each book.
- [ ] Run `ruff format` on changed Python files (line length 100)
- [ ] Run `ruff check .` and ensure it passes
- [ ] Add or update tests for this change
- [ ] Tests pass
- [ ] Run `pytest` and ensure it passes
- [ ] Typecheck/lint passes

### US-002: Create fixed-window chunks

**Description:** As a reader, I want my book chunked consistently so retrieval quality is reliable.

**Acceptance Criteria:**

- [ ] Create chunks using a fixed window of 8 sentences with overlap of 2.
- [ ] Each chunk covers the ordered sentence-id interval `[pos_start..pos_end]`.
- [ ] For each chunk, `sentences[k]` maps to `sid = pos_start + k`.
- [ ] Run `ruff format` on changed Python files (line length 100)
- [ ] Run `ruff check .` and ensure it passes
- [ ] Add or update tests for this change
- [ ] Tests pass
- [ ] Run `pytest` and ensure it passes
- [ ] Typecheck/lint passes

### US-003: Store chunk payloads in Qdrant

**Description:** As a reader, I want my uploaded book indexed in Qdrant so spoiler-safe retrieval can use it.

**Acceptance Criteria:**

- [ ] Store payload fields: `book_id`, `chapter_index`, `pos_start`, `pos_end`, `sentences`, `text`.
- [ ] Chunk embeddings are computed from the full chunk `text`.
- [ ] Qdrant points are written for each chunk of the current book.
- [ ] Run `ruff format` on changed Python files (line length 100)
- [ ] Run `ruff check .` and ensure it passes
- [ ] Add or update tests for this change
- [ ] Tests pass
- [ ] Run `pytest` and ensure it passes
- [ ] Typecheck/lint passes

### US-004: Replace chunks on re-upload

**Description:** As a reader, I want re-uploading a book to replace old indexes so answers stay consistent.

**Acceptance Criteria:**

- [ ] Re-ingestion deletes or replaces all prior chunks for the same `book_id`.
- [ ] No duplicate chunks remain after re-ingest.
- [ ] Run `ruff format` on changed Python files (line length 100)
- [ ] Run `ruff check .` and ensure it passes
- [ ] Add or update tests for this change
- [ ] Tests pass
- [ ] Run `pytest` and ensure it passes
- [ ] Typecheck/lint passes

### US-005: Track ingestion progress

**Description:** As a reader, I want to see ingestion progress so I know when the book is ready.

**Acceptance Criteria:**

- [ ] Progress is tracked as a best-effort percentage during ingestion.
- [ ] Progress is based on sentences processed out of total.
- [ ] Run `ruff format` on changed Python files (line length 100)
- [ ] Run `ruff check .` and ensure it passes
- [ ] Add or update tests for this change
- [ ] Tests pass
- [ ] Run `pytest` and ensure it passes
- [ ] Typecheck/lint passes

### US-006: Fail clearly if Qdrant is unavailable

**Description:** As a reader, I want a clear failure when indexing cannot run so I can retry later.

**Acceptance Criteria:**

- [ ] Ingestion fails with an explicit error when Qdrant cannot be reached.
- [ ] Partial ingestion is not marked as successful.
- [ ] Run `ruff format` on changed Python files (line length 100)
- [ ] Run `ruff check .` and ensure it passes
- [ ] Add or update tests for this change
- [ ] Tests pass
- [ ] Run `pytest` and ensure it passes
- [ ] Typecheck/lint passes

### US-007: Verify ingestion via API

**Description:** As a developer, I want an API endpoint to verify Qdrant ingestion so I can confirm indexing without relying on retrieval.

**Acceptance Criteria:**

- [ ] Provide an API endpoint that accepts `book_id` and verifies Qdrant ingestion for that book.
- [ ] The endpoint recomputes expected chunk count from the sentence stream and chunking params.
- [ ] The endpoint queries Qdrant by `book_id` and confirms the stored count matches expected.
- [ ] The endpoint validates payload fields and `pos_start`/`pos_end` monotonicity on a sample of chunks.
- [ ] The endpoint returns a clear pass/fail response with details on mismatches.
- [ ] If Qdrant is unavailable, the endpoint returns an explicit error.
- [ ] Restart the app server after implementing this story before verifying the endpoint.
- [ ] Run `ruff format` on changed Python files (line length 100)
- [ ] Run `ruff check .` and ensure it passes
- [ ] Add or update tests for this change
- [ ] Tests pass
- [ ] Run `pytest` and ensure it passes
- [ ] Typecheck/lint passes

### US-008: Single command to launch app + Qdrant

**Description:** As a developer, I want a single `docker compose` command to start the app and Qdrant so ingestion can run without manual service setup.

**Acceptance Criteria:**

- [ ] Provide one `docker compose` command that starts the FastAPI app and Qdrant.
- [ ] The command performs a health check that confirms the app responds and Qdrant is reachable.
- [ ] The command exits cleanly and stops both services.
- [ ] Restart the app server after implementing this story before running health checks.
- [ ] Run `ruff format` on changed Python files (line length 100)
- [ ] Run `ruff check .` and ensure it passes
- [ ] Add or update tests for this change
- [ ] Tests pass
- [ ] Run `pytest` and ensure it passes
- [ ] Typecheck/lint passes

### US-009: Add EPUB fixture for automated ingestion tests

**Description:** As a developer, I want a stable EPUB fixture so ingestion tests can run deterministically.

**Acceptance Criteria:**

- [ ] Add a fixture EPUB at `tests/fixtures/minimal.epub` with multiple chapters and paragraphs.
- [ ] Tests can ingest the fixture and verify Qdrant chunk counts using the verification API.
- [ ] Restart the app server after implementing this story before running the ingestion tests.
- [ ] The fixture stays ASCII-only and stable across runs.
- [ ] Run `ruff format` on changed Python files (line length 100)
- [ ] Run `ruff check .` and ensure it passes
- [ ] Add or update tests for this change
- [ ] Tests pass
- [ ] Run `pytest` and ensure it passes
- [ ] Typecheck/lint passes

### US-010: Delete a book with confirmation

**Description:** As a reader, I want to delete a book with confirmation so I can remove it safely.

**Acceptance Criteria:**

- [ ] Provide a delete action in the library UI that opens a confirmation dialog.
- [ ] Confirming delete removes the book file and all stored data (SQLite metadata, reading state, chapters, Chroma docs, Qdrant chunks).
- [ ] Cancelling delete leaves the book untouched.
- [ ] The library UI updates to remove the deleted book without a full reload.
- [ ] Restart the app server after implementing this story before verifying the UI.
- [ ] Run `ruff format` on changed Python files (line length 100)
- [ ] Run `ruff check .` and ensure it passes
- [ ] Add or update tests for this change
- [ ] Tests pass
- [ ] Run `pytest` and ensure it passes
- [ ] Typecheck/lint passes
- [ ] Verify in browser using MCP

### US-011: End-to-end ingestion progress in the UI

**Description:** As a reader, I want clear progress updates across all ingestion stages so I know what is happening.

**Acceptance Criteria:**

- [ ] Uploading a book shows progress messages and percentage updates in the library UI.
- [ ] The UI surfaces stage transitions (hashing, parsing, chunking, embedding, Qdrant upsert, metadata save).
- [ ] The progress percentage reflects the full ingestion pipeline, not only sentence streaming.
- [ ] The task status reaches "completed" only after all storage steps finish.
- [ ] Errors during ingestion surface a clear error message in the UI.
- [ ] If any ingestion error occurs during verification, the story fails verification.
- [ ] Restart the app server after implementing this story before verifying the UI.
- [ ] Verify in browser using MCP.
- [ ] Run `ruff format` on changed Python files (line length 100)
- [ ] Run `ruff check .` and ensure it passes
- [ ] Add or update tests for this change
- [ ] Tests pass
- [ ] Run `pytest` and ensure it passes
- [ ] Typecheck/lint passes

### US-012: Configure embedding provider for ingestion

**Description:** As a developer, I want ingestion to use a configurable Ollama embedding service so we can improve retrieval quality without changing APIs.

**Acceptance Criteria:**

- [ ] Embeddings are generated by calling Ollama `/api/embed` during ingestion.
- [ ] The embedding model name and base URL are configurable (default model: `BAAI/bge-base-en-v1.5`).
- [ ] Optional embedding dimensions are configurable (when supported by Ollama).
- [ ] If the embedding service is unavailable, ingestion fails with a clear error.
- [ ] Ollama runs as a docker compose service and uses a volume for model storage.
- [ ] Add local Ollama model cache paths to `.gitignore`.
- [ ] Run `ruff format` on changed Python files (line length 100)
- [ ] Run `ruff check .` and ensure it passes
- [ ] Add or update tests for this change
- [ ] Tests pass
- [ ] Run `pytest` and ensure it passes
- [ ] Typecheck/lint passes

### US-013: Persist embedding metadata

**Description:** As a developer, I want ingestion to record embedding metadata so retrieval can detect mismatches.

**Acceptance Criteria:**

- [ ] The ingestion pipeline records the embedding model name and dimensions used.
- [ ] The ingestion pipeline documents that model changes require reindexing.
- [ ] Run `ruff format` on changed Python files (line length 100)
- [ ] Run `ruff check .` and ensure it passes
- [ ] Add or update tests for this change
- [ ] Tests pass
- [ ] Run `pytest` and ensure it passes
- [ ] Typecheck/lint passes

### US-014: Use Ollama embeddings for Qdrant vectors

**Description:** As a reader, I want Qdrant vectors to reflect semantic embeddings so retrieval quality is meaningful.

**Acceptance Criteria:**

- [ ] Qdrant vectors are generated from Ollama embeddings of the full chunk text (not hash placeholders).
- [ ] Run an end-to-end ingestion using a live Ollama model and confirm embeddings are stored in Qdrant.
- [ ] Run `ruff format` on changed Python files (line length 100)
- [ ] Run `ruff check .` and ensure it passes
- [ ] Add or update tests for this change
- [ ] Tests pass
- [ ] Run `pytest` and ensure it passes
- [ ] Typecheck/lint passes

### US-015: Remove Chroma ingestion

**Description:** As a developer, I want to remove Chroma writes so ingestion only targets Qdrant and SQLite.

**Acceptance Criteria:**

- [ ] Ingestion no longer writes documents or metadata to Chroma.
- [ ] Removal is documented and tests are updated accordingly.
- [ ] Run `ruff format` on changed Python files (line length 100)
- [ ] Run `ruff check .` and ensure it passes
- [ ] Add or update tests for this change
- [ ] Tests pass
- [ ] Run `pytest` and ensure it passes
- [ ] Typecheck/lint passes

### US-016: Log ingestion timing metrics

**Description:** As a developer, I want ingestion timing metrics so we can validate performance on CPU-only Macs.

**Acceptance Criteria:**

- [ ] Logs include total ingestion time.
- [ ] Logs include time spent generating embeddings.
- [ ] Logs include time spent upserting to Qdrant.
- [ ] Logs include chunks processed and chunks/sec.
- [ ] Run `ruff format` on changed Python files (line length 100)
- [ ] Run `ruff check .` and ensure it passes
- [ ] Add or update tests for this change
- [ ] Tests pass
- [ ] Run `pytest` and ensure it passes
- [ ] Typecheck/lint passes

### US-017: Migrate embeddings away from Ollama to GPU-backed TEI (High Priority)

**Description:** As a developer, I want ingestion embeddings served by Hugging Face Text Embeddings Inference (TEI) on GPU so the configured model is actually served and reliable without Ollama.

**Acceptance Criteria:**

- [ ] Replace the Ollama embedding dependency with a TEI service in Docker Compose.
- [ ] TEI is configured to serve the target embedding model and runs on GPU.
- [ ] Ingestion embeddings are generated via TEI and succeed for a real EPUB upload.
- [ ] TEI requests use the `/embed` endpoint and return embeddings in the expected shape for Qdrant.
- [ ] The embedding base URL and model name are configurable via environment variables (default model: `bge-base-en-v1.5`).
- [ ] The model uses fixed dimensions; the configured Qdrant vector size matches the TEI embedding dimension.
- [ ] The model is cached and reused across restarts (TEI model cache volume).
- [ ] The app surfaces a clear error if the embedding service is unavailable.
- [ ] Document setup and GPU requirements in project docs.
- [ ] Note that this story supersedes Ollama-specific stories (US-012/US-014) without changing their historical status in `prd.json`.
- [ ] Run `ruff format` on changed Python files (line length 100)
- [ ] Run `ruff check .` and ensure it passes
- [ ] Add or update tests for this change
- [ ] Tests pass
- [ ] Run `pytest` and ensure it passes
- [ ] Typecheck/lint passes

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
- FR-12: Ingestion must generate embeddings via TEI (GPU-backed).
- FR-13: Embedding model name and base URL must be configurable.
- FR-14: Ingestion must fail with a clear error if the embedding service is unavailable.
- FR-15: Changing the embedding model requires reindexing.
- FR-16: The embedding service runs as a docker compose service with persistent model storage.

## Non-Goals (Out of Scope)

- UI changes for upload or progress display beyond delete confirmation.
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
- Track ingestion progress as a best-effort percentage (e.g., sentences processed / total).
- Dependencies include `qdrant-client`.
- Qdrant must be available locally for ingestion runs.
- Add local embedding model cache paths to `.gitignore` to avoid committing downloads.
- Restart the app server after implementing new features so new routes and logic are loaded.
- Verification should recompute chunk counts from the sentence stream rather than relying on stored counts.
- Use `tests/fixtures/minimal.epub` as the deterministic ingestion fixture for tests.

## Success Metrics

- Re-ingesting the same EPUB yields identical chunk counts and positions.
- Verification endpoint passes for ingested books and fails clearly when counts or payloads mismatch.
- Single-command startup brings the app and Qdrant online with a passing health check.

## Open Questions

None.
