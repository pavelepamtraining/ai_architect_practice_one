from dataclasses import dataclass

@dataclass
class EvaluationResult:

    query: str

    response_time: float

    selected_tools: list[str]

    parsing_failed: bool

    success: bool