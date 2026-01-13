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

## Functional Requirements

- FR-1: The system must parse EPUBs into a deterministic global sentence stream.
- FR-1a: Sentence IDs must be monotonic and contiguous for each book.
- FR-2: The system must build fixed-size chunks (window=8, overlap=2).
- FR-3: Each chunk must include payload fields `book_id`, `chapter_index`, `pos_start`, `pos_end`, `sentences`, `text`.
- FR-3a: Each chunk must cover `[pos_start..pos_end]` and map `sentences[k]` to `pos_start + k`.
- FR-4: The system must replace prior chunks for a book on re-ingest.
- FR-5: Ingestion must fail with a clear error when Qdrant is unavailable.
- FR-6: Chunk embeddings must be computed from the full chunk `text`.

## Non-Goals (Out of Scope)

- UI changes for upload or progress display.
- Reranking or hybrid retrieval.
- Alternative chunking strategies beyond fixed window.

## Design Considerations

- Keep chunking logic in a dedicated ingestion module (e.g., `ingest_v2.py`) for clarity.
- Use sentence-count-based chunking (window/overlap), not token-based splitting.
- Payload fields should be named consistently to support later retrieval filters.

## Technical Considerations

- Qdrant payload indexes should support filtering by `book_id` and `pos_start`.
- Use the book hash as `book_id` to remain consistent with V1 identifiers.
- Ingestion is triggered by the existing upload flow and receives the book hash.
- Track ingestion progress as a best-effort percentage (e.g., sentences processed / total).
- Dependencies include `llama-index`, `llama-index-vector-stores-qdrant`, and `qdrant-client`.
- Qdrant must be available locally for ingestion runs.

## Success Metrics

- Re-ingesting the same EPUB yields identical chunk counts and positions.
- Retrieval can truncate context by sentence ID without errors.

## Open Questions

None.
