# PRD: V2 Ingestion (Qdrant Chunk Indexing)

## Introduction/Overview

Implement V2 ingestion that indexes EPUB content as multi-sentence chunks in Qdrant to improve retrieval quality while preserving strict spoiler safety via sentence-level payloads.

## Goals

- Build a Qdrant index of chunked content with sentence-level payloads for truncation.
- Keep ingestion deterministic and repeatable for the same book content.
- Support re-ingestion to replace all chunks for a book.
- Fail fast with clear errors if Qdrant is unavailable.

## User Stories

### US-001: Uploading a book builds a spoiler-safe index

**Description:** As a reader, I want my uploaded book indexed into chunks so later answers can be high quality without spoilers.

**Acceptance Criteria:**

- [ ] When I upload an EPUB, the system parses it into a deterministic global sentence stream (S0..SN).
- [ ] Chunks are built with window=8 and overlap=2.
- [ ] Each chunk stores payload: `book_id`, `chapter_index`, `pos_start`, `pos_end`, `sentences`, `text`.
- [ ] `pos_start` and `pos_end` map correctly to the global sentence IDs.
- [ ] Each chunk covers the ordered sentence-id interval `[pos_start..pos_end]`.
- [ ] For each chunk, `sentences[k]` maps to `sid = pos_start + k`.
- [ ] Chunk embeddings are computed from the full chunk `text`.
- [ ] Typecheck/lint passes

### US-002: Re-upload replaces old indexing results

**Description:** As a reader, I want re-uploading a book to replace old indexes so answers stay consistent.

**Acceptance Criteria:**

- [ ] When I re-upload the same book, the system deletes or replaces all prior chunks for the same `book_id`.
- [ ] No duplicate chunks remain after re-ingest.
- [ ] Typecheck/lint passes

### US-003: Ingestion reports status and fails clearly

**Description:** As a reader, I want a clear failure if indexing cannot run so I can retry later.

**Acceptance Criteria:**

- [ ] If Qdrant cannot be reached, the upload is marked failed with an explicit error.
- [ ] Partial ingestion is not marked as successful.
- [ ] Progress is tracked as a best-effort percentage during ingestion.
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
