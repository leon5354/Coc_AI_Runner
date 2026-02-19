Project Proposal: "Miskatonic-AI" (GitHub-Ready CoC Engine)
1. Project Overview

A local, web-based AI application designed to generate and play Call of Cthulhu (7th Edition) tabletop RPG adventures. The system utilizes a modular multi-agent architecture to handle everything from pre-game plot creation to real-time game mastering.
2. Technical Stack & Repository Standards

    Framework: Streamlit (for the local browser-based UI).

    Language: Python 3.10+.

    LLM Backend: Google GenAI SDK (Gemini 2.0 Flash / 1.5 Pro).

    GitHub Readiness & Safety:

        Credential Security: Use of .env for API keys, with a strict .gitignore to prevent leaks.

        Documentation: A professional README.md for setup and usage.

        Environment: requirements.txt for one-command dependency installation.

3. Modular Architecture & Agent Logic
A. The Scripter Agent (agents/scripter.py)

    Role: The Pre-Game Architect.

    Function: Generates a complete, branching campaign.yaml before play begins.

    Output: Includes the mystery plot, branching paths (success/failure/insanity), scenes with clues/skill checks, and a party of AI investigators.

B. The Core (Keeper & Rules)

    The Keeper (core/keeper.py): The Game Master. Navigates the YAML script and orchestrates the live session.

    Rule Engine (core/rules.py): Pure Python logic for D100 rolls and Sanity mechanics.

    State Manager (core/state_manager.py): Manages game_state.json for persistence.

C. AI Player Agents (agents/player_agent.py)

    Logic: Reactive agents roleplaying the investigators defined in the YAML. They interact with the Keeper and wait for Rule Engine validation.

D. The Researcher Agent (agents/researcher.py)

    Toggle: Optional multimedia support (images/audio) via a sidebar checkbox.

4. Folder Structure (GitHub Ready)
Plaintext

/Miskatonic-AI
¢x
¢u¢w¢w .env                 # (PRIVATE) Contains GOOGLE_API_KEY
¢u¢w¢w .env.example         # Template for others to fill in their keys
¢u¢w¢w .gitignore           # EXCLUDES: .env, __pycache__/, data/saves/, .venv/
¢u¢w¢w README.md            # Installation and "How to Play" guide
¢u¢w¢w requirements.txt     # streamlit, google-generativeai, pyyaml, python-dotenv
¢u¢w¢w main.py              # Entry point (streamlit run interface/app.py)
¢x
¢u¢w¢w /core
¢x   ¢u¢w¢w keeper.py        # GM logic
¢x   ¢u¢w¢w rules.py         # D100 & Sanity math
¢x   ¢u¢w¢w scenario_loader.py
¢x   ¢|¢w¢w state_manager.py # Save/Load persistence
¢x
¢u¢w¢w /agents
¢x   ¢u¢w¢w scripter.py      # Pre-game plot generator
¢x   ¢u¢w¢w player_agent.py  # AI investigator logic
¢x   ¢|¢w¢w researcher.py    # Multimedia handler
¢x
¢u¢w¢w /interface
¢x   ¢u¢w¢w app.py           # Main Streamlit UI
¢x   ¢|¢w¢w components.py    # Sidebar widgets & character cards
¢x
¢|¢w¢w /data
    ¢u¢w¢w /campaigns       # Storage for generated YAML scripts
    ¢|¢w¢w /saves           # Session save data

5. Security & Safety Implementation

To ensure this is safe for GitHub, the developer must:

    Prevent API Leaks: The .gitignore must explicitly include .env.

    User Instructions: The README.md must explain how to obtain a Gemini API key and place it in a local .env file.

    Data Isolation: User save files and local logs must be ignored by Git to keep the repository clean.

6. Success Criteria for the Coder

    Clean Launch: The app runs via streamlit run main.py immediately after pip install -r requirements.txt.

    Valid Generation: The Scripter creates a YAML file that the Keeper can immediately load and play.

    State Persistence: Closing the browser does not lose character health or sanity progress.

Instructions for the Coder Agent

    "I need you to act as the Lead Developer for 'Miskatonic-AI'.

    Priority 1: Safety & Structure. Generate the .gitignore, .env.example, and a professional README.md first.
    Priority 2: The Scripter. Create agents/scripter.py and the YAML schema it uses to build branching plots.
    Priority 3: The Engine. Implement the Keeper, PlayerAgent, and rules.py.
    Priority 4: The UI. Build the Streamlit interface with a 'Generator' tab and a 'Play' tab.

    Proceed step-by-step. Start by providing the content for the .gitignore and README.md to establish the GitHub-ready foundation."