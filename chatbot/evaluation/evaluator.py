import time

from evaluation.dataset import EVALUATION_DATASET
from evaluation.metrics import EvaluationResult

class AgentEvaluator:

    def __init__(self, agent):

        self.agent = agent

    def evaluate(self):

        results = []

        for case in EVALUATION_DATASET:

            start = time.time()

            parsing_failed = False

            try:

                response = self.agent.process_query(
                    case.query
                )

                response_lower = response.lower()

                selected_tools = []

                for tool in [
                    "get_current_weather",
                    "get_latest_news",
                    "retrieve_rag_context",
                    "query_disaster_data"
                ]:

                    if tool in response_lower:

                        selected_tools.append(tool)

            except Exception:

                parsing_failed = True

                selected_tools = []

            response_time = (
                time.time() - start
            )

            results.append(
                EvaluationResult(
                    query=case.query,
                    response_time=response_time,
                    selected_tools=selected_tools,
                    parsing_failed=parsing_failed,
                    success=not parsing_failed
                )
            )

        return results
