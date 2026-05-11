import os
import streamlit as st
from agent.agent import AgentOrchestrator
from mcp.server import MCPServerImpl


import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

# ============================================================
# Configuration
# ============================================================

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or st.secrets.get("OPENROUTER_API_KEY")

# ============================================================
# Streamlit Page Setup
# ============================================================

def initialize_session_state() -> None:
    """Initialize Streamlit session state."""

    if "agent" not in st.session_state:

        mcp_server = MCPServerImpl()

        st.session_state.agent = AgentOrchestrator(
            mcp_server=mcp_server,
            api_key=OPENROUTER_API_KEY
        )

    if "messages" not in st.session_state:
        st.session_state.messages = []


def render_sidebar() -> None:
    """Render sidebar UI."""

    with st.sidebar:

        st.header("Configuration")

        st.markdown(f"""
### Available MCP Tools

#### 🌦 Weather Tool
Examples:
- Weather in London
- Temperature in Tokyo

#### 📰 News Tool
Examples:
- Latest technology news
- Business news
- World news
""")

        st.markdown("---")

        if st.button("Clear Conversation"):

            st.session_state.messages = []

            st.session_state.agent.reset()

            st.rerun()


def render_chat_history() -> None:
    """Render previous chat messages."""

    for message in st.session_state.messages:

        with st.chat_message(message["role"]):

            st.markdown(message["content"])


def process_user_input(user_input: str) -> None:
    """Process user message and render response."""

    # Store user message
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })

    # Render user message
    with st.chat_message("user"):

        st.markdown(user_input)

    # Generate assistant response
    with st.chat_message("assistant"):

        with st.spinner("Thinking..."):

            try:

                response = st.session_state.agent.process_query(user_input)

            except Exception as e:

                response = f"ERROR: {str(e)}"

            st.markdown(response)

    # Store assistant response
    st.session_state.messages.append({
        "role": "assistant",
        "content": response
    })


def main() -> None:
    """Main Streamlit application."""

    st.set_page_config(
        page_title="MCP/RAG Chatbot",
        layout="wide"
    )

    st.title("MCP/RAG Chatbot")

    st.markdown("""
This application demonstrates:

- MCP-style tool orchestration
- Weather retrieval via Open-Meteo
- News retrieval via RSS feeds
- Agent-based tool selection using OpenRouter
""")

    if not OPENROUTER_API_KEY:

        st.error("OPENROUTER_API_KEY is not configured")

        st.info("""
Configure API key using:

- Environment variable:
  OPENROUTER_API_KEY

""")

        st.stop()

    initialize_session_state()

    render_sidebar()

    render_chat_history()

    user_input = st.chat_input(
        "Ask about weather, latest news, or anything else..."
    )

    if user_input:

        process_user_input(user_input)


if __name__ == "__main__":
    main()
