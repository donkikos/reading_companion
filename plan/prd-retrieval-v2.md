# PRD: V2 Retrieval (Spoiler-Safe Qdrant Query)

## Introduction/Overview

Implement V2 retrieval that queries Qdrant for chunked content and enforces strict spoiler safety by truncating output at the user's reading position.

## Goals

- Retrieve relevant chunks using dense vector search with a spoiler-safe filter.
- Truncate returned content so no sentence past the user position is exposed.
- Keep retrieval deterministic and safe without reranking or hybrid search.

## User Stories

### US-001: Ask the assistant without spoilers

**Description:** As a reader, I want to ask the assistant questions about the book and get answers that never reveal content beyond my reading position.

**Acceptance Criteria:**

- [ ] When I ask a question, the MCP retrieves context from Qdrant for the current `book_id`.
- [ ] The MCP reads `user_pos` from the persisted reading state before querying Qdrant.
- [ ] Qdrant queries include a filter `pos_start <= user_pos`.
- [ ] Results are restricted to the current `book_id`.
- [ ] For each chunk, iterate `sentences` and compute `sid = pos_start + k`.
- [ ] Stop including sentences when `sid > user_pos`.
- [ ] Rejoin only safe sentences for final context.
- [ ] Verify that a partially read chunk only returns sentences at or before `user_pos`.
- [ ] Typecheck/lint passes

### US-002: Get clean, relevant context

**Description:** As a reader, I want retrieved context to be relevant and readable without repeated text.

**Acceptance Criteria:**

- [ ] Default retrieval returns top-k 20 chunks.
- [ ] Overlapping sentences across chunks are removed from the final context.
- [ ] The final context preserves original sentence order.
- [ ] Queries use dense vector search without reranking.
- [ ] Typecheck/lint passes

## Functional Requirements

- FR-1: Retrieval must filter Qdrant results with `pos_start <= user_pos`.
- FR-2: Retrieval must filter by `book_id`.
- FR-3: Returned context must be truncated at `user_pos` using sentence IDs.
- FR-4: Overlapping sentences across chunks must be deduplicated.
- FR-5: Default retrieval returns top-k 20 chunks.
- FR-6: Retrieval is exposed through the MCP server for LLM access.
- FR-7: The MCP must read `user_pos` from the persisted reading state before retrieval.

## Non-Goals (Out of Scope)

- Reranking or cross-encoder scoring.
- Sparse or hybrid retrieval.
- Query-less retrieval modes.

## Design Considerations

- Truncation must happen after retrieval and before the LLM receives any text.
- Deduplication should preserve sentence order from the global stream.

## Technical Considerations

- Qdrant filter should use payload indexes for `book_id` and `pos_start`.
- Retrieval should accept a query string; a query is required.
- MCP must obtain `user_pos` from the persisted reading state before querying Qdrant.

## Success Metrics

- Queries never return any sentence with `sid > user_pos`.
- Retrieval completes within an acceptable latency for local use.

## Open Questions

None.
