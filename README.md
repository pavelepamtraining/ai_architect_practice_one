# AI Architect Practice One

## Description

This repository contains a Jupyter Notebook demonstrating **ReAct-based prompt engineering**, tool-augmented reasoning, and self-reflection techniques using a local LLM.  
The goal of this practice is **educational**: to explore agent loops, prompt debugging, and meta-prompting in a controlled experiment.

---

## Requirements

- Python 3.10+
- pip
- Jupyter Notebook
- Ollama local LLM runtime

---

## Setup Instructions

1. **Verify Python and pip are installed**

```bash
python --version
pip --version
```

2. **Install Ollama (local LLM runtime)**

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama --version
```

3. **Download and start a model**

```bash
ollama pull llama3
ollama serve
```

4. **Create a virtual environment**

```bash
python -m venv venv
source venv/bin/activate
```

5. **Start Jupyter Notebook**
```bash
jupyter notebook ReAct.ipynb
```