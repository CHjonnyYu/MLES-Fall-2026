# Machine Learning in Engineering Science — Fall 2026

National Cheng Kung University · LAiMM Laboratory · Prof. Chi-Hua Jonny Yu  
Monday 14:00–17:00 · English-medium instruction

## Course website

https://mles-course-vgqg4abvka-de.a.run.app/

The full-semester portal is `index.html`. For an offline copy, download the repository ZIP, extract it, and open `index.html` in a browser. Slides use embedded CSS, JavaScript, and explanatory SVGs. Logos are local assets.

## 19 October 2026 — Week 07

| Hour | Time | Slides | Notebook |
|---|---|---|---|
| H1: Sequential Data and LSTM | 14:00–15:00 | [30 slides](lectures/week-07-hour-1/index.html) | [Colab](https://colab.research.google.com/github/CHjonnyYu/MLES-Fall-2026/blob/main/notebooks/week-07-h1-sequences-lstm.ipynb) |
| H2: Why Attention, and How It Works | 15:00–16:00 | [30 slides](lectures/week-07-hour-2/index.html) | [Colab](https://colab.research.google.com/github/CHjonnyYu/MLES-Fall-2026/blob/main/notebooks/week-07-h2-attention.ipynb) |
| H3: From Attention to a Transformer | 16:00–17:00 | [30 slides](lectures/week-07-hour-3/index.html) | [Colab](https://colab.research.google.com/github/CHjonnyYu/MLES-Fall-2026/blob/main/notebooks/week-07-h3-transformer.ipynb) |

Every deck contains a complete 60-minute facilitation plan: 30 slides with 2-minute cues. Explanation, hand calculation, classroom interaction, and notebook practice share those 60 minutes. The deck is not intended to have a separate additional hour of practice appended to it.

Slide keys: arrows navigate, N opens speaker notes, R reveals an answer, O toggles overview, F requests fullscreen. Print from the browser for a 16:9 PDF.

## Teaching-team administration

The GCP administration panel is https://mles-course-vgqg4abvka-de.a.run.app/admin/ .
The instructor can sign in with the provisioned administrator account and add
individual teaching-assistant accounts. Passwords and session secrets are not
included in this repository.

Choose a week to edit its title, Monday date, learning focus, and course phase.
Add a file or HTTPS resource link, choose Draft or Published, and save. Drafts
are visible only to the signed-in teaching team. Published additions appear
below the week's prepared materials on the student site. A stale editing form
returns a conflict instead of replacing a newer edit.

Administrators can create, disable, or reset teaching-team accounts. Assistants
can manage course content but cannot manage accounts. Recent actions are logged.
Cloud Run hosts the service; a private versioned Cloud Storage bucket preserves
edits and uploads across deployments. Secret Manager supplies startup secrets.
See [deployment instructions](deployment/README.md) for operation and recovery.

## Notebooks

Use Colab CPU or install the packages in `requirements.txt` and open a notebook in Jupyter. Run cells in order. Each notebook is independently runnable; complete worked code is followed by a checkpoint and controlled modifications. No paid model API, GPU, API key, or separately downloaded dataset is required. The first setup may install missing packages over the network.

Weekly notebooks are in-class practice and optional extensions, not new graded weekly assignments. Weeks 04 and 08 are calendar holidays. Weeks 11 and 18 include optional written/oral exam-readiness notebooks.

## Evidence and interpretation

Synthetic data and illustrative diagrams are explicitly labeled. Loss curves and trained attention plots are created by executing the notebooks. Actual results must be reported even if a simple baseline wins. Attention weights are routing coefficients, not proof of causal importance.

The notebooks save runtime versions, seeds, configuration, data identity where applicable, and measured results under `artifacts/`. Download runtime files before ending a Colab session. Reproduction across environments is not guaranteed bit-for-bit; inspect numerical tolerances and versions.

## Reader and sources

`textbook/` contains the modular Fall 2026 LaTeX source plus a detailed Week 07 chapter. Deck speaker notes and `source-notes.json` files identify primary sources. External video links point to their creators; videos are not redistributed.

NCKU and LAiMM logos remain their respective owners’ marks. No license for third-party trademarks or referenced works is granted by this repository. No student submissions or private data are included.
