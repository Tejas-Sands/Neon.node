---
title: AI Video Generator
emoji: 🎥
colorFrom: indigo
colorTo: pink
sdk: docker
app_port: 7860
pinned: false
---

# Remotion Video Generator Space

This is a self-contained video generation hub using Remotion, Python FastAPI, Llama 3.1, and SDXL.

## Running Locally

To run this space locally, install the Python and Node dependencies and launch the server:

```bash
# Install Python deps
pip install -r requirements.txt

# Install Node deps
npm install

# Run FastAPI
uvicorn main:app --host 0.0.0.0 --port 7860
```
# Neon.node
