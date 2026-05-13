import os
import streamlit as st
from agent.agent import AgentOrchestrator
from mcp.server import MCPServerImpl
from evaluation.evaluator import AgentEvaluator
from evaluation.dataset import EVALUATION_DATASET


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

        st.header("Navigation")

        selected_page = st.radio(
            label="Select Page",
            options=[
                "Chat",
                "Evaluation Framework"
            ]
        )

        st.markdown("---")

        st.header("Configuration")

        st.markdown(f"""
### Available MCP Tools

#### 🌦 Weather Tool
Provides current weather conditions using Open-Meteo API.

#### 📰 Live News Tool
Retrieves latest news headlines from RSS feeds.

#### 📚 BBC News Archive RAG Tool
Performs semantic retrieval over embedded BBC news articles using FAISS vector search.

#### 🌪️ Disaster Analytics Tool
Queries historical natural disaster dataset using Pandas filtering and aggregation.

""")

        st.markdown("---")

        if st.button("Clear Conversation"):

            st.session_state.messages = []

            st.session_state.agent.reset()

            st.rerun()

    return selected_page


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

                result = (st.session_state.agent.process_query(user_input))

                response = result.response

            except Exception as e:
                response = "We are experiencing temporary technical issues. Please try again."

            st.markdown(response)

    # Store assistant response
    st.session_state.messages.append({
        "role": "assistant",
        "content": response
    })

def render_evaluation_tab() -> None:

    st.header("Evaluation Framework")

    st.markdown("""
        Please note: this demo uses free-tier AI models and external services,
        so responses may occasionally be slower than expected or temporarily unavailable due to provider/network limitations.
    """)

    st.subheader("Evaluation Dataset")

    dataset_rows = []

    for case in EVALUATION_DATASET:

        dataset_rows.append({
            "Scenario": case.name,
            "Query": case.query,
            "Expected Tools": ", ".join(
                case.expected_tools
            ),
            "Multi Tool": case.requires_multi_tool
        })

    st.dataframe(
        dataset_rows,
        width="stretch"
    )

    if st.button("Run Evaluation"):

        evaluator = AgentEvaluator(
            st.session_state.agent
        )

        with st.spinner("Running evaluation..."):

            results = evaluator.evaluate()

            st.subheader("Execution Results")

            result_rows = []

            for result in results:

                result_rows.append({
                    "Query": result.query,
                    "Tools Used": ", ".join(
                        result.selected_tools
                    ),
                    "Response Time (s)": round(
                        result.response_time,
                        2
                    ),
                    "Parsing Failed":
                        result.parsing_failed,
                    "Tool Calls":
                        len(result.selected_tools)
                })

            st.dataframe(
                result_rows,
                width="stretch"
            )

def main() -> None:
    """Main Streamlit application."""

    st.set_page_config(
        page_title="MCP/RAG Chatbot",
        layout="wide"
    )

    if not OPENROUTER_API_KEY:

        st.error("OPENROUTER_API_KEY is not configured")

        st.info("""
Configure API key using:

- Environment variable:
  OPENROUTER_API_KEY

""")

        st.stop()

    initialize_session_state()

    selected_page = render_sidebar()

    if selected_page == "Chat":

        st.title("MCP/RAG Chatbot")

        st.markdown("""
        This application demonstrates:

        - MCP-style tool orchestration
        - Weather retrieval via Open-Meteo
        - News retrieval via RSS feeds
        - Agent-based tool selection using OpenRouter
        """)

        render_chat_history()

        user_input = st.chat_input("Ask about weather, news, RAG retrieval, or disasters...")

        if user_input:

            process_user_input(user_input)


    elif selected_page == "Evaluation Framework":

        render_evaluation_tab()


if __name__ == "__main__":
    main()
