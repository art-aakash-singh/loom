---
version: 1
slug: "src-app-app-tsx"
primary_target: "src/app/App.tsx"
related_targets: ["src/features/chat/ChatPage.tsx","src/features/conversations/components/Conversations.tsx"]
---

# Chat workspace (conversations + chat)

Scope: the single app screen in `src/app/App.tsx` composing `features/conversations` and `features/chat`. Mode: Operate.

Audience and task: the builder, chatting with Loom daily; switch conversations, send, stop, edit a prompt, regenerate a reply, move between versions. Constraints: generated API client only, feature boundaries enforced by lint, every existing behavior and test intent preserved.

Confirmed answers: per-reply metadata line (model, tokens in/out, stop reason) from data the API already returns; Markdown rendering for replies (react-markdown + remark-gfm); structure "Versions as tabs" chosen from the second hand.

## Direction contract

THESIS: A chat screen where the message tree is legible in place: every turn with sibling versions carries a tab strip directly above it, so branch points read as tabs, not hidden 1/3 arrows. Refuses the category default of tiny ‹ 2/3 › arrows tucked under a bubble.

OWN-WORLD: Loom's logo palette as working colour. Indigo (#2F4A6B) owns the whole sidebar as the warp; linen-tinted paper ground for reading; Ink text; Madder (#B04A2E) is the weft: active-tab underline, selected-conversation tick, the Send button, and nothing decorative. Work Sans for all UI and prose, JetBrains Mono only for code. The woven mark (SVG) and the extracted serif wordmark head the sidebar. Dark theme from the dark app icon: ink ground, linen text, lighter madder.

STORY: The user sees their conversations, opens one, reads replies as formatted Markdown, sees exactly which version of a prompt or reply they are on and what each reply cost in tokens, and acts (send, stop, edit, regenerate, switch) without hunting.

FIRST VIEWPORT: Indigo sidebar 264px left (mark + wordmark, New conversation, conversation list, API health in footer). Main: 56px title bar with conversation title; centered 720px column; user prompts as linen-2 blocks offset right; replies full-width prose with a quiet metadata line + Regenerate; version tab strip above any turn with siblings; composer docked at bottom, autosizing textarea with madder Send / Stop.

FORM: Versions as tabs, position 4 on the re-rolled ranked list (dealt as card 3 of hand 2). seed:4c308412e0eeec75

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
