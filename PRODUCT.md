# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary user today: the builder (Aakash), a backend engineer using Loom as a working AI chat assistant while building it to understand how products like ChatGPT and Claude work inside.

Later audience (confirmed intent, not yet served): other people such as friends, teammates, and portfolio viewers. Work done now should not assume a single user forever, but nothing multi-user (accounts, sharing, auth) exists yet.

## Product Purpose

A ChatGPT-style chat product that works as a real assistant and also shows the machinery behind it. Success has two parts: it is good enough to use for real conversations, and it makes the AI-engineering core (context assembly, token budgeting, message trees, streaming) understandable by showing that core working.

## Positioning

Mainstream chat products hide what the model actually received. Loom shows it. What sets Loom apart is that the internals are visible and first-class: what went into the context window, how the token budget was spent and what was truncated, and which branch of the message tree was sent. Seeing these is a core part of the product, not a debug mode.

## Operating Context

- Used in a desktop browser against a local stack (FastAPI API on :8000, Vite web on :5173, Postgres and Redis via docker-compose).
- Conversations are long-lived and branch: users edit earlier messages, regenerate replies, and move between sibling versions.
- Replies stream token by token over SSE, and a turn can be stopped partway.

## Capabilities and Constraints

Implemented:
- A conversation list: create, select, and reopen the last-open conversation.
- Streaming chat replies over SSE, with stop and server-reconciled history after each turn.
- A message tree: edit a user message, regenerate a reply, and step through sibling versions (VersionNav).
- Typed error handling, including a "generation in progress" conflict.
- Backend context building with token budgeting and estimation (`apps/api/src/loom_api/context/`).

Terminology: *conversation*, *message*, *turn* (one user message plus its streamed reply), *branch* / *version* (sibling messages in the tree), *leaf* (the end of the active path), *context* / *budget* (what gets sent to the model, and the token allowance it must fit).

Constraints:
- The web client calls the API only through the generated OpenAPI client, via each feature's `api/` layer.
- The web app's feature boundaries are enforced by lint (see CLAUDE.md).

Undecided:
- How and where the internals appear in the UI (an inline view, a side panel, or per message). Showing them requires the API to expose context-build results, which it does not do yet.
- Multi-user concerns: accounts, sharing, hosting.

## Brand Commitments

Name: **Loom**. The working identity in `docs/logo/` (a woven-grid mark, a serif lowercase wordmark, and a named palette of Linen #F1E9DC, Madder #B04A2E, Indigo #2F4A6B and Ink #2A2420) is **provisional**. The user has not made any of it binding, so future work may refine or replace it.

## Evidence on Hand

- Logo sheets as PNG only: `docs/logo/Primary lockup@2x.png` and `docs/logo/Icon at small sizes@2x.png` (light and dark app icons; 160/64/32/16 favicon sizes). There is no SVG source.
- No users, testimonials, metrics, or public deployment exist. Do not fabricate any.

## Product Principles

1. **Show the machinery.** If the model saw it, the user can see it. Context, budget, and branch path are product surfaces, not logs.
2. **A real assistant first.** Showing internals must never make everyday chatting worse. Chat stays the primary flow.
3. **The server's view wins.** The UI reflects the stored state (the active path and the persisted messages) rather than guessing locally.
4. **Built to grow past one user.** Personal today, but avoid choices that make it hard to open Loom to others later.
