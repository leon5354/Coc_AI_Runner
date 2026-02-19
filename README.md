# CoC AI Runner: Miskatonic Engine v2.3

A Call of Cthulhu (7th Edition) Campaign Runner powered by LLMs (Google Gemini, OpenRouter, or Ollama).

## Overview

This project is the core engine for running AI-driven tabletop RPG sessions. It features a **"Dual Logic"** system that adapts complexity based on your chosen model provider:

*   **API Mode (Google/OpenRouter):** Uses complex system prompts for deep roleplay, tactical thinking, and rich atmospheric descriptions.
*   **Local Mode (Ollama):** Uses simplified prompts optimized for smaller local models (e.g., Mistral, Llama 3) to ensure stability.

### Key Features
*   **Turn Queue System:** Deterministic turn-based gameplay preventing AI "dogpiling".
*   **Language Support:** Native support for **English**, **Traditional Chinese (Written)**, and **Cantonese (Spoken)**.
*   **Isolated Scripter:** Run the Scenario Generator on a high-IQ model (API) while playing the game on a local model.
*   **Protagonist Focus:** Enhanced narrative that centers on YOU (the Protagonist).

---

## 🚀 Quick Start

### 1. Prerequisites
*   Python 3.10+
*   API Key (Google Gemini OR OpenRouter) - *Optional if using Ollama exclusively.*

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/your-username/Coc_AI_Runner.git
cd Coc_AI_Runner

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration (.env)

Rename `.env.example` to `.env` and configure your provider:

```ini
# --- CORE GAME ENGINE (Keeper & NPCs) ---
# Options: google, openrouter, ollama
LLM_PROVIDER=google
LLM_MODEL=gemini-2.0-flash

# --- SCENARIO ARCHITECT (Scripter) ---
# Recommended: Keep this on a high-intelligence model (Google/OpenRouter)
SCRIPTER_PROVIDER=google
SCRIPTER_MODEL=gemini-2.0-flash

# --- API KEYS ---
GOOGLE_API_KEY=your_google_key_here
OPENROUTER_API_KEY=your_openrouter_key_here
```

### 4. Running the Game

```bash
# Start the Streamlit Interface
python -m streamlit run interface/app.py
```

---

## 🎮 How to Play

1.  **Select a Campaign:** Choose a YAML scenario from the sidebar in the Streamlit interface.
2.  **Configure your Party:** (If the scenario includes AI companions, they will load automatically).
3.  **Game Flow:**
    *   **Action Phase:** Describe your actions to the Keeper. Be clear about your intentions.
    *   **NPC Phase:** The AI companions will react to your actions.
    *   **React and Explore:** Listen carefully to the Keeper's descriptions and plan your next move!


## 🧠 Model Setup Guide

### Option A: Google Gemini (Recommended for Best Experience)
1.  Get a key from [Google AI Studio](https://aistudio.google.com/).
2.  Set `LLM_PROVIDER=google` and `LLM_MODEL=gemini-2.0-flash`.

### Option B: OpenRouter (Access Claude, GPT-4, Mistral Large)
1.  Get a key from [OpenRouter](https://openrouter.ai/).
2.  Set `LLM_PROVIDER=openrouter`.
3.  Set `LLM_MODEL=provider/model-name` (e.g., `mistralai/mistral-large`).

### Option C: Ollama (Local & Private)
1.  Install [Ollama](https://ollama.com/).
2.  Pull a model: `ollama pull mistral`
3.  Set `LLM_PROVIDER=ollama` and `LLM_MODEL=mistral`.
4.  *Note: The engine automatically switches to "Simple Mode" prompts for better stability.*

### Troubleshooting
*   **Connection Errors:**
    *   Verify your API keys are correct in `.env`.
    *   Check your network connection and firewall settings.
    *   Ensure your OpenRouter account has sufficient credits.
*   **Ollama:**
    *   Make sure Ollama is running (`ollama serve`).
    *   Confirm you have pulled the model (`ollama pull mistral`).

---

## 📂 Project Structure

*   `core/`: Core game logic (Keeper, Rules, Dice).
*   `agents/`: AI Personalities (PlayerAgent, Scripter).
*   `interface/`: Streamlit UI code.
*   `data/`: Campaign YAML files and Save slots.

## License
MIT License.
