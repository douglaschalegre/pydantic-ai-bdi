# BDI Agent Frontend (Single-Screen MVP)

This prototype provides a single page to:
1. Enter a natural language brief to create an agent.
2. View evolving desires & intentions.
3. Observe cycle events and basic chat messages.

## Current State
- Mock backend in-browser (`src/mockBackend.ts`) simulates cycles, desire progression, and intention switching.
- No real backend or WebSocket yet.
- Styling kept intentionally minimal/dark for focus.

## Run (after installing deps)
```
npm install
npm run dev
```
Open the printed local URL in your browser.

## Key Files
- `types.ts` – shared TypeScript interfaces for agent, messages, events.
- `src/mockBackend.ts` – simulated runtime & event emission.
- `src/App.tsx` – single-screen UI.
- `src/style.css` – basic styling.

## Next Steps (Not Implemented Yet)
- Real backend integration & WebSocket events.
- Chat command interpretation (currently just appends user messages).
- Pause/Stop controls.
- Accessibility audit (baseline semantics present; needs ARIA refinement).

## Contributing
For now keep changes small & focused; larger structural changes will wait until multi-screen expansion.
