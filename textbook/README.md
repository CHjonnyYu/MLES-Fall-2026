# Machine Learning in Engineering Science: Fall 2026 Course Reader

This is a rewritten, course-aligned LaTeX reader. `main.tex` is the entry point.

- The reader follows the Fall 2026 schedule, not a model-by-model survey.
- Core chapters cover ML foundations through the midterm, then LLM/RAG/agent workflows through the final project.
- `chapters/05b-sequences-attention-transformers.tex` is the core Week 07 unit, aligned with three 60-minute HTML decks and independent CPU notebooks.
- `chapters/B-extension-studios.tex` retains further architecture extensions; its brief sequence summary is supplemented by the core Week 07 chapter.
- `legacy-2025-main.tex` and `figures/` preserve the original source material for traceability. They are reference material, not the Fall 2026 canonical reader.
- Colab links use the public repository `CHjonnyYu/MLES-Fall-2026` and its root-level `notebooks/` directory.

Compile with `latexmk -pdf main.tex` when a LaTeX environment is available.
