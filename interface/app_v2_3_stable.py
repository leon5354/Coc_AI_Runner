import os
import sys
import streamlit as st
import yaml
import json
from dotenv import load_dotenv

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# --- ENVIRONMENT VARIABLES ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    st.error("GOOGLE_API_KEY not found. Please set it in your .env file.")
    st.stop()
else:
    os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# --- IMPORTS ---
try:
    from core.rules import d100_roll, check_success, sanity_check
    from agents.player_agent import PlayerAgent
    from agents.scripter import Scripter
    from core.keeper import Keeper
    from core.state_manager import load_game_state, save_game_state
except ImportError as e:
    st.error(f"Import Error: {e}")
    st.stop()

# ====================
# STREAMLIT CONFIG
# ====================
st.set_page_config(page_title='Miskatonic-AI V2.3', page_icon='👻', layout="wide")

# ====================
# HELPER FUNCTIONS
# ====================
def get_campaign_files():
    campaign_dir = os.path.join(parent_dir, 'data', 'campaigns')
    os.makedirs(campaign_dir, exist_ok=True)
    return [f for f in os.listdir(campaign_dir) if f.endswith('.yaml')]

def load_campaign_yaml(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def get_save_filename(campaign_filename):
    base_name = os.path.splitext(campaign_filename)[0]
    return os.path.join(parent_dir, 'data', 'saves', f"{base_name}_save.json")

def save_current_state(current_file):
    """Helper to save game state consistency."""
    if 'game_state' not in st.session_state:
        st.session_state.game_state = {}
        
    # Update History
    st.session_state.game_state['history'] = st.session_state.messages

    # Save Agent States
    agents_data = {}
    if 'keeper' in st.session_state and st.session_state.keeper:
        for agent in st.session_state.keeper.ai_party:
            agents_data[agent.name] = {
                'inventory': getattr(agent, 'inventory', []),
                'sanity': agent.stats.get('Sanity', 50)
            }
    st.session_state.game_state['agents'] = agents_data

    save_path = get_save_filename(current_file)
    save_game_state(st.session_state.game_state, save_path)

# ====================
# MAIN UI
# ====================
tab1, tab2 = st.tabs(["Play Scenario", "Scenario Architect"])

# --------------------
# TAB 1: PLAY SCENARIO
# --------------------
with tab1:
    # Sidebar Controls
    with st.sidebar:
        st.header('Settings')
        campaign_files = get_campaign_files()

        if not campaign_files:
            st.warning("No campaigns found. Generate one first!")
            selected_file_index = 0
        else:
            if 'selected_campaign_index' not in st.session_state:
                st.session_state.selected_campaign_index = 0

            selected_file = st.selectbox(
                'Select Campaign',
                campaign_files,
                index=st.session_state.selected_campaign_index
            )

        model_name = st.selectbox('Select Model', ['gemini-2.0-flash', 'gemini-1.5-pro'])
        ENABLE_RESEARCHER = st.checkbox('Enable Researcher (Multimedia)', value=False)
        PROTAGONIST_MODE = st.checkbox('Solo Adventure Mode (Protagonist)', value=True, help="Turn the game into a single-player experience with interactive NPCs.")

        # --- V3: Select Party (Persistent Agents) ---
        st.subheader("Select Party (V3)")
        # FIX: Ensure directory exists to prevent crash
        agent_dir = os.path.join(parent_dir, 'data', 'agents')
        os.makedirs(agent_dir, exist_ok=True)
        
        agent_files = [f for f in os.listdir(agent_dir) if f.endswith(".yaml")]
        selected_agents = st.multiselect(
            "Choose your AI companions",
            agent_files, 
            default=agent_files[:2] if len(agent_files) >= 2 else agent_files  # Select first 2 by default
        )

        # APPLY BUTTON (Restored from V2_copy)
        if st.button("Apply / Restart Scenario"):
            if 'current_campaign_file' in st.session_state and 'game_state' in st.session_state:
                save_current_state(st.session_state.current_campaign_file)
                st.toast(f"Saved progress for {st.session_state.current_campaign_file}")

            st.session_state.current_campaign_file = selected_file
            st.session_state.messages = []
            st.session_state.keeper = None
            st.session_state.ai_turn_index = 0 # Reset turn index

            new_save_path = get_save_filename(selected_file)
            if os.path.exists(new_save_path):
                st.session_state.game_state = load_game_state(new_save_path)
                st.session_state.messages = st.session_state.game_state.get('history', [])
                st.toast(f"Loaded save for {selected_file}")
            else:
                st.session_state.game_state = {}
                st.toast(f"Started new game: {selected_file}")

            st.rerun()

        # --- CHARACTER CARDS (New Feature) ---
        if 'keeper' in st.session_state and st.session_state.keeper:
            st.divider()
            st.subheader("Party Members")
            for agent in st.session_state.keeper.ai_party:
                with st.expander(f"{agent.name} (SAN: {agent.stats.get('Sanity', 50)})"):
                    st.write(f"**Personality:** {agent.personality}")

                    # Inventory Section
                    if hasattr(agent, 'inventory') and agent.inventory:
                        st.write("**Inventory:**")
                        for item in agent.inventory:
                            st.write(f"- 📦 {item}")
                    else:
                        st.caption("No items carried.")

                    st.write("**Skills:**")
                    skills = agent.stats.get('Skills', {})
                    for s, v in skills.items():
                        st.write(f"- {s}: {v}%")

    # Main Game Area
    if 'current_campaign_file' in st.session_state:
        current_file = st.session_state.current_campaign_file
        st.title(f"Playing: {current_file.replace('.yaml', '').replace('_', ' ')}")

        try:
            campaign_path = os.path.join(parent_dir, 'data', 'campaigns', current_file)
            campaign_data = load_campaign_yaml(campaign_path)

            # Init Keeper if needed
            if 'keeper' not in st.session_state or st.session_state.keeper is None:
                st.session_state.keeper = Keeper(campaign_path, model_name, ENABLE_RESEARCHER)

                # Restore narrative & inventory from save
                if 'game_state' in st.session_state:
                    # Restore Chat
                    st.session_state.messages = st.session_state.game_state.get('history', [])

                    # Restore Keeper Narrative Memory
                    st.session_state.keeper.narrative_state = [
                         {'description': m['content']} for m in st.session_state.messages if m['role'] == 'assistant'
                    ]

                    # Restore Agent Inventories (if saved)
                    saved_agents = st.session_state.game_state.get('agents', {})
                    for agent in st.session_state.keeper.ai_party:
                        if agent.name in saved_agents:
                            agent.inventory = saved_agents[agent.name].get('inventory', [])
                            # Restore Sanity if tracked
                            if 'sanity' in saved_agents[agent.name]:
                                agent.stats['Sanity'] = saved_agents[agent.name]['sanity']

            else:
                st.session_state.keeper.enable_researcher = ENABLE_RESEARCHER
                if st.session_state.keeper.model_name != model_name:
                    st.session_state.keeper.model_name = model_name

            # Display History
            for message in st.session_state.messages:
                with st.chat_message(message['role'], avatar=message.get('avatar')):
                    st.markdown(message['content'])

            # Input
            if prompt := st.chat_input('What do you do?'):
                # 1. Player Turn
                st.session_state.messages.append({'role': 'user', 'content': prompt})
                with st.chat_message('user'):
                    st.markdown(prompt)

                # 2. Keeper Resolution (Dice Logic happens inside generate_narrative)
                with st.spinner("The Keeper is judging..."):
                    # Get user sanity and name for immersive monologue
                    user_stats = st.session_state.character.get('stats', {}) if 'character' in st.session_state else {}
                    user_sanity = user_stats.get('Sanity', 50)
                    user_name = st.session_state.character.get('name', 'Protagonist') if 'character' in st.session_state else "Protagonist"

                    # CALL V2.2 KEEPER LOGIC
                    keeper_response = st.session_state.keeper.generate_narrative(
                        prompt, 
                        user_sanity=user_sanity, 
                        character_name=user_name
                    )

                st.session_state.messages.append({'role': 'assistant', 'content': keeper_response})
                with st.chat_message('assistant'):
                    st.markdown(keeper_response)

                # 3. AI Party Turn (MANUAL ADVANCE: Click to Proceed)
                # This replaces the auto-loop from V2_copy
                if hasattr(st.session_state.keeper, 'ai_party') and st.session_state.keeper.ai_party:
                    # Initialize turn tracker
                    if 'ai_turn_index' not in st.session_state:
                        st.session_state.ai_turn_index = 0
                    
                    party = st.session_state.keeper.ai_party
                    # Identify who is next
                    agent = party[st.session_state.ai_turn_index % len(party)]
                    
                    st.divider()
                    # Unique key ensures button state persists correctly across interactions
                    if st.button(f"▶ Continue: {agent.name}'s Turn", key=f"next_turn_{len(st.session_state.messages)}"):
                        st.session_state.ai_turn_index += 1
                        
                        with st.spinner(f"{agent.name} is reacting..."):
                            # Agent intent (Now with Memory Injection)
                            action_intent = agent.generate_action(
                                st.session_state.keeper.narrative_state,
                                memory_system=st.session_state.keeper.memory
                            )

                            # Display intent
                            st.session_state.messages.append({'role': 'agent', 'content': action_intent, 'avatar': '🕵️'})

                            # Keeper Resolution for this agent
                            agent_sanity = agent.stats.get('Sanity', 50)
                            agent_resolution = st.session_state.keeper.generate_narrative(
                                f"Resolution for {agent.name}'s action: {action_intent}",
                                user_sanity=agent_sanity,
                                character_name=agent.name
                            )

                            st.session_state.messages.append({'role': 'assistant', 'content': agent_resolution})
                            
                            # CRITICAL FIX: Save State BEFORE Rerun
                            save_current_state(current_file)
                            st.rerun() # Refresh to show new messages

                # Auto-Save (Update state with new inventory/stats)
                # This handles normal inputs that don't trigger reruns immediately
                save_current_state(current_file)

        except Exception as e:
            st.error(f"Error: {e}")
    else:
        st.info("👈 Please select a campaign from the sidebar and click 'Apply / Restart Scenario'.")

# --------------------
# TAB 2: SCENARIO ARCHITECT
# --------------------
with tab2:
    st.header("Scenario Architect")
    st.write("Discuss your idea with the AI, then generate the full script.")

    if "scripter_messages" not in st.session_state:
        st.session_state.scripter_messages = [{
            "role": "assistant",
            "content": "I am the Scripter. Tell me a theme, setting, or idea, and we can refine it before generating the final scenario."
        }]

    if "scripter" not in st.session_state:
        st.session_state.scripter = Scripter(model_name=model_name)

    # Chat Interface
    for msg in st.session_state.scripter_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if prompt := st.chat_input("Describe your scenario idea..."):
        st.session_state.scripter_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        # Use the new chat method with research capability
        response = st.session_state.scripter.chat(st.session_state.scripter_messages)

        st.session_state.scripter_messages.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.write(response)

    # Generation
    st.divider()
    if st.button("Finalize & Generate Scenario"):
        full_context = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.scripter_messages])

        with st.spinner("Researching & Writing the tome... (This takes ~1-2 minutes)"):
            try:
                # Uses new generate_campaign with auto-research & JSON safety
                yaml_content = st.session_state.scripter.generate_campaign(full_context)

                if yaml_content.startswith("Error"):
                    st.error(yaml_content)
                else:
                    try:
                        parsed = yaml.safe_load(yaml_content)
                        import time
                        default_title = f"Scenario_{int(time.time())}"
                        title = parsed.get('title', default_title).replace(" ", "_")

                        save_dir = os.path.join(parent_dir, 'data', 'campaigns')
                        os.makedirs(save_dir, exist_ok=True)
                        filename = os.path.join(save_dir, f"{title}.yaml")

                        with open(filename, 'w', encoding='utf-8') as f:
                            f.write(yaml_content)

                        st.success(f"Scenario saved to `{filename}`!")
                        with st.expander("View YAML Code"):
                            st.code(yaml_content, language='yaml')
                    except Exception as e:
                        st.error(f"Failed to parse generated YAML: {e}")
                        st.text(yaml_content)

            except Exception as e:
                st.error(f"Generation Error: {e}")
