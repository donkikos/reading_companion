# PRD: V2 Ingestion (Qdrant Chunk Indexing)

## Introduction/Overview

Implement V2 ingestion that indexes EPUB content as multi-sentence chunks in Qdrant to improve retrieval quality while preserving strict spoiler safety via sentence-level payloads.

## Goals

- Build a Qdrant index of chunked content with sentence-level payloads for truncation.
- Keep ingestion deterministic and repeatable for the same book content.
- Support re-ingestion to replace all chunks for a book.
- Fail fast with clear errors if Qdrant is unavailable.

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

**Description:** As a developer, I want a single command to start the app and Qdrant so ingestion can run without manual service setup.

**Acceptance Criteria:**

- [ ] Provide one command that starts the FastAPI app and Qdrant.
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
- Restart the app server after implementing new features so new routes and logic are loaded.
- Verification should recompute chunk counts from the sentence stream rather than relying on stored counts.
- Use `tests/fixtures/minimal.epub` as the deterministic ingestion fixture for tests.

## Success Metrics

- Re-ingesting the same EPUB yields identical chunk counts and positions.
- Verification endpoint passes for ingested books and fails clearly when counts or payloads mismatch.
- Single-command startup brings the app and Qdrant online with a passing health check.

## Open Questions

None.
