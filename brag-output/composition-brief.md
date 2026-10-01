# Hyperframes Composition Brief: Your-Own-AI

## Objective

Create a 20-second cinematic launch video for Your-Own-AI, a C++ vector database with HNSW, KD-Tree, brute-force search, and local Ollama RAG.

## Output

- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: 1920x1080 landscape, 30fps
- Duration: 20 seconds

## Product truth

Show the actual user flow: paste a document, turn it into a 768D embedding, store it in HNSW, ask a question, retrieve context, and answer through a local LLM. Use fictional document content only.

## Storyboard

1. 0.0–3.0: semantic clusters assemble; headline `YOUR DOCS. YOUR AI. LOCAL.`
2. 3.0–7.0: Documents UI; `Graph Algorithms Notes` → `EMBED & INSERT` → `768D EMBEDDING` into a layered HNSW graph.
3. 7.0–12.0: Ask AI UI; type the HNSW question; reveal three context chips sequentially.
4. 12.0–16.5: streamed answer and `OLLAMA • LOCAL LLM` tag.
5. 16.5–20.0: `SEARCH. RETRIEVE. REASON.` and `YOUR-OWN-AI` lockup.

## Design direction

- Recreate the source interface in a dark terminal aesthetic, not generic SaaS.
- Palette: `#07070f` background, `#0c0c18` cards, `#cdd6f4` text, `#6c63ff` violet accent, plus cyan `#00d9ff`, green `#a6e3a1`, amber `#ffb74d`.
- Font: Fira Code or a close monospace fallback.
- Visual centerpiece: a responsive 2D semantic scatter plot and compact dark panels.
- Keep every sentence on screen long enough to read.

## Audio

Use a low-volume warm electronic bed if bundled assets are available. Add sparse UI click/type/card-placement accents; no aggressive glitch sounds. Let the strongest accent land on `768D` and the final wordmark.

## Required checks

Run `npx hyperframes check` with zero errors, render high quality, extract the strongest settled frame as `brag.jpg`, and bake it into frame 0 of the final MP4.
