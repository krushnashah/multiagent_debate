import streamlit as st
import os
import sys
import time
import threading
import logging
from dotenv import load_dotenv
from updated_base_agent import DebateAgent
from updated_business_agent import BusinessAgent
from updated_creative_agent import CreativeAgent
from updated_critical_agent import CriticalAgent
from updated_technical_agent import TechnicalAgent
from updated_direct import run_semi_agentic_debate

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("DebateApp")

# Ensure API key exists
if not os.getenv("OPENAI_API_KEY"):
    st.error("Missing `OPENAI_API_KEY` in environment. Please add it in `.env`.")
    st.stop()

# Initialize Streamlit session state
if "debate_output" not in st.session_state:
    st.session_state.debate_output = []  # Stores messages in real-time
if "debate_running" not in st.session_state:
    st.session_state.debate_running = False  # Keeps track of debate progress

# Function to run the debate and capture responses
def run_debate_thread(problem, agents, use_knowledge, document_dir, output_dir, no_web_search, no_ai_generation):
    """Executes the debate in a separate thread and stores updates in Streamlit session state."""
    knowledge_config = {"document_dir": document_dir, "use_web_search": not no_web_search, "use_ai_generation": not no_ai_generation} if use_knowledge else None

    try:
        output_dir, results = run_semi_agentic_debate(problem, agents, output_dir, knowledge_config)
    except Exception as e:
        st.session_state.debate_output.append(f"Error: {str(e)}")
    finally:
        st.session_state.debate_running = False  # Mark debate as finished

# Function to create custom agents
def create_custom_agent(name, role, expertise, thinking_style, priorities, personality_traits, model="gpt-4o"):
    expertise = [e.strip() for e in expertise.split(",")] if isinstance(expertise, str) else expertise
    priorities = [p.strip() for p in priorities.split(",")] if isinstance(priorities, str) else priorities
    personality_traits = [t.strip() for t in personality_traits.split(",")] if isinstance(personality_traits, str) else personality_traits

    return DebateAgent(name=name, role=role, expertise=expertise, thinking_style=thinking_style, priorities=priorities, personality_traits=personality_traits, model=model)

# Main UI
def main():
    st.title("🗣️ Multi-Agent Debate System")
    st.write("AI agents debate topics and generate synthesized solutions.")

    # Sidebar Configuration
    with st.sidebar:
        st.header("Debate Configuration")
        problem = st.text_area("Problem Statement", "How can AI improve professional content reliability?")
        model = st.selectbox("LLM Model", ["gpt-4o", "gpt-4-turbo", "gpt-4"], index=0)

        # Built-in Agent Selection
        st.subheader("Select Built-in Agents")
        use_business = st.checkbox("Business Agent", value=True)
        use_creative = st.checkbox("Creative Agent", value=True)
        use_critical = st.checkbox("Critical Agent", value=True)
        use_technical = st.checkbox("Technical Agent", value=True)

        # Custom Agent Configuration
        st.subheader("Custom Agents")
        add_custom_agent = st.checkbox("Add Custom Agent", value=False)
        custom_agents = []

        if add_custom_agent:
            with st.expander("Custom Agent Configuration", expanded=True):
                custom_name = st.text_input("Name", value="Custom_Agent")
                custom_role = st.text_input("Role", value="Domain Expert")
                custom_expertise = st.text_input("Expertise (comma-separated)", value="analysis, problem-solving")
                custom_thinking = st.text_input("Thinking Style", value="analytical and creative")
                custom_priorities = st.text_input("Priorities (comma-separated)", value="evidence, innovation")
                custom_traits = st.text_input("Personality Traits (comma-separated)", value="curious, methodical")

                if st.button("Add This Agent"):
                    agent = create_custom_agent(custom_name, custom_role, custom_expertise, custom_thinking, custom_priorities, custom_traits, model)
                    custom_agents.append(agent)
                    st.success(f"Added custom agent: {custom_name}")

        # Knowledge Integration
        st.subheader("Knowledge Integration")
        use_knowledge = st.checkbox("Enable Knowledge Integration", value=False)
        document_dir = st.text_input("Document Directory", value="documents") if use_knowledge else "documents"
        no_web_search = st.checkbox("Disable Web Search", value=False) if use_knowledge else False
        no_ai_generation = st.checkbox("Disable AI Generation", value=False) if use_knowledge else False

        # Start Debate Button
        start_debate = st.button("Start Debate", type="primary")

    # Main Debate Output Section
    output_container = st.empty()

    if start_debate and not st.session_state.debate_running:
        # Ensure at least 2 agents are selected
        agent_count = sum([use_business, use_creative, use_critical, use_technical]) + len(custom_agents)
        if agent_count < 2:
            st.error("At least 2 agents are required for the debate!")
        else:
            # Initialize Selected Agents
            agents = []
            if use_business:
                agents.append(BusinessAgent(model=model))
            if use_creative:
                agents.append(CreativeAgent(model=model))
            if use_critical:
                agents.append(CriticalAgent(model=model))
            if use_technical:
                agents.append(TechnicalAgent(model=model))
            agents.extend(custom_agents)

            # Reset Debate State
            st.session_state.debate_output = []
            st.session_state.debate_running = True  # Set debate as running

            # Start Debate in a Separate Thread
            debate_thread = threading.Thread(
                target=run_debate_thread,
                args=(problem, agents, use_knowledge, document_dir, f"output_{int(time.time())}", no_web_search, no_ai_generation)
            )
            debate_thread.start()
            st.success("Debate started! Watch the progress below.")

    # Live UI updates
    if st.session_state.debate_running:
        st.info("Debate in progress... updates will appear below.")

    for message in st.session_state.debate_output:
        st.write(message)

    # Show completion message
    if not st.session_state.debate_running and st.session_state.debate_output:
        st.success("Debate completed!")

# Run the App
if __name__ == "__main__":
    main()
