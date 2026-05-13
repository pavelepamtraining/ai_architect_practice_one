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

                execution_result = (
                    self.agent.process_query(
                        case.query
                    )
                )

                selected_tools = (
                    execution_result.tools_used
                )

                parsing_failed = (
                    execution_result.parsing_failed
                )

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

    def correct_tool_selections(results):

        if not results:
            return 0

        correct = 0

        for case, result in zip(
            EVALUATION_DATASET,
            results
        ):

            expected = set(case.expected_tools)

            actual = set(result.selected_tools)

            if expected.issubset(actual):

                correct += 1

        return (
            correct / len(results)
        ) * 100


    def parsing_failure_rate(results):

        if not results:
            return 0

        return (
            sum(
                r.parsing_failed
                for r in results
            )
            / len(results)
        ) * 100


    def multi_tool_rate(results):

        multi_tool_total = sum(
            case.requires_multi_tool
            for case in EVALUATION_DATASET
        )

        if multi_tool_total == 0:
            return 0

        successes = 0

        for case, result in zip(
            EVALUATION_DATASET,
            results
        ):

            expected = set(case.expected_tools)

            actual = set(result.selected_tools)

            if (
                case.requires_multi_tool
                and expected.issubset(actual)
                and len(actual) > 1
            ):

                successes += 1

        return (
            successes / multi_tool_total
        ) * 100


    def avg_response_time(results):

        if not results:
            return 0

        return (
            sum(
                r.response_time
                for r in results
            )
            / len(results)
        )
