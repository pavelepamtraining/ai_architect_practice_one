from dataclasses import dataclass

@dataclass
class EvaluationCase:

    name: str

    query: str

    expected_tools: list[str]

    requires_multi_tool: bool = False


EVALUATION_DATASET = [

    EvaluationCase(
        name="Weather Query",
        query="Weather in London",
        expected_tools=["get_current_weather"]
    ),

    EvaluationCase(
        name="Live News Query",
        query="Latest AI news",
        expected_tools=["get_latest_news"]
    ),

    EvaluationCase(
        name="RAG Query",
        query="Economic impact of inflation",
        expected_tools=["retrieve_rag_context"]
    ),

    EvaluationCase(
        name="Disaster Query",
        query="Earthquakes in Japan",
        expected_tools=["query_disaster_data"]
    ),

    EvaluationCase(
        name="Multi Tool Query",
        query=(
            "What are recent business news trends related to inflation?"
        ),
        expected_tools=[
            "retrieve_rag_context",
            "get_latest_news"
        ],
        requires_multi_tool=True
    )
]