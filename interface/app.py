import os
import sys
import streamlit as st
import yaml
import json
import time
import re
import random
from dotenv import load_dotenv

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# --- ENVIRONMENT VARIABLES ---
load_dotenv()

# --- IMPORTS ---
try:
    from core.rules import d100_roll, check_success, sanity_check
    from agents.player_agent import PlayerAgent
    from agents.scripter import Scripter
    from core.keeper import Keeper
except ImportError as e:
    st.error(f"Import Error: {e}")
    st.stop()

# ====================
# HELPER FUNCTIONS
# ====================
def save_json(data, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)

def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_yaml(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def get_campaign_files():
    campaign_dir = os.path.join(parent_dir, 'data', 'campaigns')
    os.makedirs(campaign_dir, exist_ok=True)
    return [f for f in os.listdir(campaign_dir) if f.endswith('.yaml')]

def get_save_filename(campaign_filename):
    base_name = os.path.splitext(campaign_filename)[0]
    save_dir = os.path.join(parent_dir, 'data', 'saves')
    os.makedirs(save_dir, exist_ok=True)
    return os.path.join(save_dir, f"{base_name}_save.json")

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(" ", "_")

def save_current_state(current_file):
    if 'game_state' not in st.session_state:
        st.session_state.game_state = {}
        
    st.session_state.game_state['history'] = st.session_state.messages
    
    # Save Agent States
    agents_data = {}
    if 'keeper' in st.session_state and st.session_state.keeper:
        for agent in st.session_state.keeper.ai_party:
            agents_data[agent.name] = {
                'inventory': getattr(agent, 'inventory', []),
                'stats': agent.stats, 
            }
    st.session_state.game_state['agents'] = agents_data
    
    # Save Turn Queue
    if 'turn_queue' in st.session_state:
        st.session_state.game_state['turn_queue'] = st.session_state.turn_queue

    save_path = get_save_filename(current_file)
    save_json(st.session_state.game_state, save_path)

# ====================
# MAIN UI
# ====================
st.set_page_config(page_title='Coc AI Runner', page_icon='🐙', layout="wide")

tab1, tab2 = st.tabs(["🕵️ Play Scenario", "📜 Scenario Architect"])

# --------------------
# TAB 1: PLAY SCENARIO
# --------------------
with tab1:
    with st.sidebar:
        st.title("🐙 Coc AI Runner")
        st.caption(f"Engine: {os.getenv('LLM_PROVIDER', 'Unknown').upper()}")
        
        # --- HERO CARD ---
        try:
            hero_path = os.path.join(parent_dir, 'data', 'agents', 'protagonist.yaml')
            if os.path.exists(hero_path):
                hero_data = load_yaml(hero_path)
                with st.expander(f"🦸 {hero_data.get('name', 'Protagonist')}", expanded=True):
                    st.caption(f"**Occupation:** {hero_data.get('occupation', 'Investigator')}")
                    st.caption(f"**Gender:** {hero_data.get('gender', 'Unknown')}")
                    
                    stats = hero_data.get('stats', {})
                    col1, col2 = st.columns(2)
                    with col1: st.metric("SAN", stats.get('Sanity', 50))
                    with col2: st.metric("HP", stats.get('HP', 10))
                    
                    st.markdown("**Skills:**")
                    st.text(", ".join([f"{k} ({v}%)" for k,v in stats.get('Skills', {}).items()]))
                    
                    st.markdown("**Inventory:**")
                    for item in hero_data.get('inventory', []):
                        st.caption(f"- {item}")
        except Exception as e:
            st.error(f"Hero Load Error: {e}")

        st.divider()
        
        campaign_files = get_campaign_files()
        if not campaign_files:
            st.warning("No campaigns found.")
            selected_file = None
        else:
            selected_file = st.selectbox('Select Campaign', campaign_files)

        ENABLE_RESEARCHER = st.checkbox('Enable Researcher', value=False)
        PROTAGONIST_MODE = st.checkbox('Solo Mode', value=True, help="Focuses narrative on YOU.")

        if st.button("Apply / Restart Scenario", type="primary"):
            if 'current_campaign_file' in st.session_state and 'game_state' in st.session_state:
                save_current_state(st.session_state.current_campaign_file)
                st.toast("Saved previous game.")

            st.session_state.current_campaign_file = selected_file
            st.session_state.messages = []
            st.session_state.keeper = None
            st.session_state.turn_queue = []
            st.session_state.pending_roll = False  # Reset roll state

            new_save_path = get_save_filename(selected_file)
            if os.path.exists(new_save_path):
                try:
                    st.session_state.game_state = load_json(new_save_path)
                    st.session_state.messages = st.session_state.game_state.get('history', [])
                    st.session_state.turn_queue = st.session_state.game_state.get('turn_queue', [])
                    st.toast(f"Loaded save for {selected_file}")
                except Exception:
                    st.session_state.game_state = {}
            else:
                st.session_state.game_state = {}
                st.toast(f"Started new game: {selected_file}")

            st.rerun()
            
        # --- AI PARTY CARD ---
        if 'keeper' in st.session_state and st.session_state.keeper and st.session_state.keeper.ai_party:
            st.divider()
            st.subheader("👥 Party Members")
            for agent in st.session_state.keeper.ai_party:
                with st.expander(f"{agent.name} ({agent.gender})"):
                    st.caption(f"**Personality:** {agent.personality[:60]}...")
                    san = agent.stats.get('Sanity', 50)
                    st.progress(min(san, 100) / 100, text=f"Sanity: {san}")
                    skills = agent.stats.get('Skills', {})
                    if skills:
                        st.markdown("**Skills:** " + ", ".join([f"{k}" for k in skills]))
                    if hasattr(agent, 'inventory') and agent.inventory:
                        st.markdown("**Inventory:**")
                        for item in agent.inventory:
                            st.caption(f"- {item}")
                    else:
                        st.caption("*No items*")

    # Main Game Area
    if 'current_campaign_file' in st.session_state and st.session_state.current_campaign_file:
        current_file = st.session_state.current_campaign_file
        st.subheader(f"📖 {current_file.replace('.yaml', '').replace('_', ' ')}")

        try:
            campaign_path = os.path.join(parent_dir, 'data', 'campaigns', current_file)
            
            if 'keeper' not in st.session_state or st.session_state.keeper is None:
                st.session_state.keeper = Keeper(campaign_path, enable_researcher=ENABLE_RESEARCHER)
                if 'game_state' in st.session_state:
                    st.session_state.keeper.narrative_state = [
                         {'description': m['content']} for m in st.session_state.messages if m['role'] == 'assistant'
                    ]
                    saved_agents = st.session_state.game_state.get('agents', {})
                    for agent in st.session_state.keeper.ai_party:
                        if agent.name in saved_agents:
                            agent.inventory = saved_agents[agent.name].get('inventory', [])
                            if 'stats' in saved_agents[agent.name]:
                                agent.stats = saved_agents[agent.name]['stats']
            else:
                st.session_state.keeper.enable_researcher = ENABLE_RESEARCHER

            # Display Chat
            for message in st.session_state.messages:
                role = message['role']
                avatar = message.get('avatar', None)
                if role == 'agent': avatar = '🗣️'
                elif role == 'assistant': avatar = '🐙'
                with st.chat_message(role, avatar=avatar):
                    st.markdown(message['content'])

            if 'turn_queue' not in st.session_state:
                st.session_state.turn_queue = []
            if 'pending_roll' not in st.session_state:
                st.session_state.pending_roll = False

            # --- INTERRUPT LOGIC: PENDING ROLL & NEGOTIATION ---
            if st.session_state.pending_roll:
                st.divider()
                st.warning("🎲 THE KEEPER DEMANDS A ROLL!")
                
                col1, col2 = st.columns([1, 4])
                
                # --- OPTION 1: ACCEPT & ROLL ---
                with col1:
                    if st.button("✅ Roll d100", type="primary"):
                        roll_val = random.randint(1, 100)
                        result_str = "Success" if roll_val <= 50 else "Failure" 
                        roll_msg = f"🎲 **Result:** {roll_val} ({result_str})"
                        
                        st.session_state.messages.append({'role': 'user', 'content': roll_msg})
                        
                        # Feed result back to Keeper
                        with st.spinner("Resolving fate..."):
                            resolution = st.session_state.keeper.generate_narrative(f"Result: {roll_val}. Resolve the scene.")
                        
                        # Remove [ROLL_REQUIRED] tag if present in resolution to avoid loop
                        resolution = resolution.replace("[ROLL_REQUIRED]", "")
                        
                        st.session_state.messages.append({'role': 'assistant', 'content': resolution, 'avatar': '🐙'})
                        
                        # Reset state
                        st.session_state.pending_roll = False
                        
                        if st.session_state.turn_queue:
                             st.session_state.turn_queue.pop(0)

                        st.rerun()

                # --- OPTION 2: NEGOTIATE / CHANGE SKILL ---
                with col2:
                    negotiate_text = st.text_input("Negotiate / Change Skill", placeholder="Can I use Fast Talk instead?")
                    if st.button("🤔 Negotiate"):
                        if negotiate_text:
                            st.session_state.messages.append({'role': 'user', 'content': f"(Negotiating) {negotiate_text}"})
                            
                            with st.spinner("The Keeper considers..."):
                                # Send negotiation to Keeper
                                new_response = st.session_state.keeper.generate_narrative(f"Player asks: '{negotiate_text}'. Re-evaluate the skill check.")
                            
                            # Update UI
                            if "[ROLL_REQUIRED]" in new_response:
                                display_response = new_response.replace("[ROLL_REQUIRED]", "")
                                st.session_state.messages.append({'role': 'assistant', 'content': display_response, 'avatar': '🐙'})
                                st.session_state.pending_roll = True # Still pending (new roll)
                            else:
                                st.session_state.messages.append({'role': 'assistant', 'content': new_response, 'avatar': '🐙'})
                                st.session_state.pending_roll = False # Negotiation ended the roll request (rare)
                            
                            st.rerun()


            # --- NORMAL GAME LOGIC (Only if no pending roll) ---
            elif not st.session_state.turn_queue:
                # PLAYER TURN
                col1, col2 = st.columns([8, 2])
                with col2:
                    action_mode = st.radio("Phase", ["🎬 Action", "🗣️ Discuss"], label_visibility="collapsed")
                
                prompt_label = "What do you do?" if "Action" in action_mode else "Discuss plan..."

                # --- MANUAL END TURN BUTTON ---
                if "Action" in action_mode and hasattr(st.session_state.keeper, 'ai_party') and st.session_state.keeper.ai_party:
                    if st.button("⏩ End Turn (Pass to Party)"):
                        st.session_state.turn_queue = [agent.name for agent in st.session_state.keeper.ai_party]
                        st.toast("Turn passed to AI Party...")
                        st.rerun()

                if prompt := st.chat_input(prompt_label):
                    st.session_state.messages.append({'role': 'user', 'content': prompt})
                    with st.chat_message('user'):
                        st.markdown(prompt)

                    if "Action" in action_mode:
                        with st.spinner("The Keeper is watching..."):
                            keeper_response = st.session_state.keeper.generate_narrative(prompt)

                        # CHECK FOR ROLL REQUIREMENT
                        if "[ROLL_REQUIRED]" in keeper_response:
                            st.session_state.pending_roll = True
                            display_response = keeper_response.replace("[ROLL_REQUIRED]", "")
                            st.session_state.messages.append({'role': 'assistant', 'content': display_response, 'avatar': '🐙'})
                            st.rerun()

                        st.session_state.messages.append({'role': 'assistant', 'content': keeper_response, 'avatar': '🐙'})
                        with st.chat_message('assistant', avatar='🐙'):
                            st.markdown(keeper_response)
                            
                        save_current_state(current_file)
                    else:
                        with st.spinner("Discussing..."):
                            if hasattr(st.session_state.keeper, 'ai_party'):
                                for agent in st.session_state.keeper.ai_party:
                                    response = agent.generate_dialogue(
                                        user_input=prompt,
                                        narrative_state=st.session_state.keeper.narrative_state
                                    )
                                    formatted_resp = f"**{agent.name}:** {response}"
                                    st.session_state.messages.append({'role': 'agent', 'content': formatted_resp})
                                    with st.chat_message('agent', avatar='🗣️'):
                                        st.markdown(formatted_resp)
                        save_current_state(current_file)
            else:
                # AGENT TURN
                next_agent_name = st.session_state.turn_queue[0]
                agent_obj = next((a for a in st.session_state.keeper.ai_party if a.name == next_agent_name), None)
                
                if agent_obj:
                    st.divider()
                    st.info(f"👉 It is **{next_agent_name}'s** turn.")
                    if st.button(f"▶ Process {next_agent_name}'s Action"):
                        with st.spinner(f"{next_agent_name} is acting..."):
                            action_intent = agent_obj.generate_action(st.session_state.keeper.narrative_state)
                            st.session_state.messages.append({'role': 'agent', 'content': action_intent, 'avatar': '🗣️'})
                            
                            agent_resolution = st.session_state.keeper.generate_narrative(f"Resolution: {action_intent}")
                            
                            # CHECK FOR ROLL IN AGENT TURN
                            if "[ROLL_REQUIRED]" in agent_resolution:
                                st.session_state.pending_roll = True
                                display_res = agent_resolution.replace("[ROLL_REQUIRED]", "")
                                st.session_state.messages.append({'role': 'assistant', 'content': display_res, 'avatar': '🐙'})
                                # Do NOT pop queue yet; wait for roll resolution
                                st.rerun()

                            st.session_state.messages.append({'role': 'assistant', 'content': agent_resolution, 'avatar': '🐙'})
                            
                            st.session_state.turn_queue.pop(0)
                            save_current_state(current_file)
                            st.rerun()
                else:
                    st.session_state.turn_queue.pop(0)
                    st.rerun()

        except Exception as e:
            st.error(f"Game Error: {e}")
            import traceback
            st.text(traceback.format_exc())
    else:
        st.info("👈 Please select a campaign.")

# --------------------
# TAB 2: SCENARIO ARCHITECT
# --------------------
with tab2:
    st.header("📜 Scenario Architect")
    st.caption(f"Powered by: {os.getenv('SCRIPTER_PROVIDER', 'Google').upper()}")
    
    if "scripter" not in st.session_state:
        st.session_state.scripter = Scripter() # Uses env vars
        
    if "scripter_messages" not in st.session_state:
        st.session_state.scripter_messages = [{
            "role": "assistant",
            "content": "I am the Scripter. Tell me your nightmare..."
        }]

    for msg in st.session_state.scripter_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if prompt := st.chat_input("Describe your idea..."):
        st.session_state.scripter_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.spinner("Thinking..."):
            response = st.session_state.scripter.chat(st.session_state.scripter_messages)

        st.session_state.scripter_messages.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.write(response)

    st.divider()
    
    if st.button("Finalize & Generate Scenario", type="primary"):
        full_context = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.scripter_messages])

        with st.spinner("Writing the tome..."):
            try:
                yaml_content = st.session_state.scripter.generate_campaign(full_context)
                
                if "Error" in yaml_content and not yaml_content.strip().startswith("title:"):
                     st.error(yaml_content)
                else:
                    parsed_yaml = yaml.safe_load(yaml_content)
                    title = parsed_yaml.get('title', f"Scenario_{int(time.time())}")
                    safe_title = sanitize_filename(title)
                    filename = f"{safe_title}.yaml"
                    
                    filepath = os.path.join(parent_dir, 'data', 'campaigns', filename)
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(yaml_content)

                    st.success(f"Scenario saved as: `{filename}`")
                    st.balloons()
            except Exception as e:
                st.error(f"Generation Failed: {e}")
