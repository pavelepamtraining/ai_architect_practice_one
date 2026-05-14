import json

from typing import Dict, Any, List, Optional

import requests

from pydantic import BaseModel, ValidationError

import logging

from mcp.server import MCPServer, ToolSchema, ToolResult
from memory.working_memory import WorkingMemory
from typing import TypedDict
from langgraph.graph import StateGraph, END
from dataclasses import dataclass
import time
from security.rules import SecurityGuardrails

logger = logging.getLogger(__name__)

# ============================================================
# OpenRouter Configuration
# ============================================================

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openrouter/free"  # Simple free model

class ToolCall(BaseModel):
    """Parsed tool call from LLM response."""
    name: str
    arguments: Dict[str, Any]

class AgentState(TypedDict):
    """ Agent state """
    messages: List[Dict[str, str]]
    tool_result: Optional[str]
    tool_call: Optional[Dict[str, Any]]
    # ----------------------------------------------------
    # Evaluation / observability fields
    # ----------------------------------------------------
    tools_used: List[str]
    parsing_failed: bool
    iteration_count: int

@dataclass
class AgentExecutionResult:
    """ Agent execution result """
    response: str
    tools_used: list[str]
    parsing_failed: bool
    response_time: float
    total_tool_calls: int

class AgentOrchestrator:
    """Agent orchestrator with LLM-driven tool selection."""

    def __init__(
        self,
        mcp_server: MCPServer,
        api_key: str,
        model: str = DEFAULT_MODEL,
        max_iterations: int = 5
    ):
        self.mcp_server = mcp_server
        self.model = model
        self.api_key = api_key
        self.max_iterations = max_iterations
        self.memory = WorkingMemory()
        self.graph = self._build_graph()
        self.security = SecurityGuardrails()

        self.tools: Dict[str, ToolSchema] = {}
        self._discover_tools()

    def _discover_tools(self) -> None:
        """Discover all available tools from MCP servers."""
        for tool in self.mcp_server.list_tools():
            self.tools[tool.name] = tool

    def _build_system_prompt(self) -> str:
        """Build system prompt with tool schemas."""
        tool_descriptions = []
        for tool_name, tool_schema in self.tools.items():
            tool_descriptions.append(
                f"- {tool_schema.name}: {tool_schema.description}\n"
                f"  Parameters: {json.dumps(tool_schema.input_schema, indent=2)}"
            )

        tools_text = "\n\n".join(tool_descriptions)

        return f"""
            You are an AI assistant specialized in:
            - Weather information
            - Live news retrieval
            - BBC historical news archive retrieval
            - Natural disaster analytics
            You ONLY answer questions related to these supported domains.
            If the user asks unrelated questions outside these domains:
            - politely explain the supported capabilities
            - do NOT hallucinate answers
            - do NOT invent knowledge
            You can use internal tools to gather information,
            but NEVER mention tool names, internal APIs,
            tool schemas, or system architecture to users.
            Internal tool calls are part of the hidden orchestration layer.

            INSTRUCTIONS:
            1. Analyze the user's question carefully
            2. Determine if a tool is required
            3. Tool calls are machine-readable orchestration instructions.

            You MUST NEVER invent custom XML tags. The ONLY valid tool call format is:

            <TOOL_CALL>
                {{"name": "tool_name", "arguments": {{"param": "value"}}}}
            </TOOL_CALL>

            Invalid formats include:
            - <weather>
            - <tool>
            - <get_current_weather>
            - XML-style custom tags

            AVAILABLE TOOLS:
            {tools_text}

            5. Do NOT use pseudo-code
            6. After receiving tool results, provide a concise natural language response
            7. Never hallucinate information
            8. Only use information returned from tools
            9. Only make ONE tool call at a time
            10. Wait for tool results before answering
            11. If unsure, ask for clarification

            IMPORTANT:
            - When a message with role="tool" appears, it means the tool has already executed successfully.
              You MUST:
              - read the tool result
              - answer the user naturally
              - NEVER call the same tool again for the same request
              - Do NOT repeat tool calls after receiving tool results.
            - Output ONLY valid JSON inside <TOOL_CALL>
            - Ensure JSON is strictly valid
            - Use double quotes only
            - No trailing commas
            - Never invent tool results
            - If the user asks about historical or conceptual information,
            prefer retrieve_rag_context
            - If the user asks for latest/current/recent events,
            prefer get_latest_news
        """

    def _parse_tool_call(self, response: str) -> Optional[ToolCall]:
        """Parse tool call from LLM response. Returns ToolCall object if found, None otherwise"""
        try:
            # Extract JSON between markers
            if "<TOOL_CALL>" in response and "</TOOL_CALL>" in response:
                start = response.index("<TOOL_CALL>") + len("<TOOL_CALL>")
                end = response.index("</TOOL_CALL>")
                json_str = response[start:end].strip()

                data = json.loads(json_str)

                if "arguments" not in data:
                    arguments = {
                        k: v
                        for k, v in data.items()
                        if k != "name"
                    }
                    data = {
                        "name": data["name"],
                        "arguments": arguments
                    }
                return ToolCall(**data)

            # Native tool call format
            if ("<|tool_call_start|>" in response and "<|tool_call_end|>" in response):
                start = response.index("<|tool_call_start|>") + len("<|tool_call_start|>")
                end = response.index("<|tool_call_end|>")
                tool_content = response[start:end].strip()
                tool_content = tool_content.strip("[]")
                tool_name = tool_content.split("(")[0]
                args_part = tool_content.split("(", 1)[1].rsplit(")", 1)[0]
                if args_part.startswith("{"):
                    arguments = json.loads(args_part)
                else:
                    arguments = {}
                    key, value = args_part.split("=", 1)
                    arguments[key.strip()] = value.strip().strip("'").strip('"')

                return ToolCall(
                    name=tool_name,
                    arguments=arguments
                )

        except (ValueError, json.JSONDecodeError, ValidationError) as e:
            logger.exception(f"Failed to parse tool call: {e}")

        return None

    def _build_graph(self):
        """Construct LangGraph workflow defining reasoning and tool-execution transitions."""
        workflow = StateGraph(AgentState)

        workflow.add_node("reason", self._reason_node)
        workflow.add_node("tool", self._tool_node)

        workflow.set_entry_point("reason")

        workflow.add_conditional_edges(
            "reason",
            self._should_continue,
            {
                "tool": "tool",
                "end": END
            }
        )

        workflow.add_edge("tool", "reason")

        return workflow.compile()

    def _reason_node(self, state: AgentState) -> AgentState:
        """Execute LLM reasoning step and detect whether tool invocation is required."""
        system_prompt = self._build_system_prompt()

        state["iteration_count"] += 1

        messages = [
            {"role": "system", "content": system_prompt}
        ] + state["messages"]

        response = self._call_llm(messages)

        logger.info(f"LLM response: {response[:200]}...")

        tool_call = self._parse_tool_call(response)

        contains_tool_attempt = any([
            "<TOOL_CALL>" in response,
            "<|tool_call_start|>" in response
        ])

        if (
            contains_tool_attempt and not tool_call
        ):
            state["parsing_failed"] = True

        if tool_call:
            state["messages"].append({
                "role": "assistant",
                "content": self._extract_tool_call_content(response)
            })
            state["tool_call"] = tool_call.model_dump()
            return state

        state["messages"].append({
            "role": "assistant",
            "content": response
        })

        state["tool_call"] = None

        return state

    def _extract_tool_call_content(
        self,
        response: str
    ) -> str:
        """Extract normalized tool-call segment from model response across supported formats."""

        # ----------------------------------------------------
        # XML-style TOOL_CALL format
        # ----------------------------------------------------

        if (
            "<TOOL_CALL>" in response
            and "</TOOL_CALL>" in response
        ):

            start = (
                response.index("<TOOL_CALL>")
            )

            end = (
                response.index("</TOOL_CALL>")
                + len("</TOOL_CALL>")
            )

            return response[start:end]

        # ----------------------------------------------------
        # Native tool_call_start format
        # ----------------------------------------------------

        if (
            "<|tool_call_start|>" in response
            and "<|tool_call_end|>" in response
        ):

            start = (
                response.index(
                    "<|tool_call_start|>"
                )
            )

            end = (
                response.index(
                    "<|tool_call_end|>"
                )
                + len("<|tool_call_end|>")
            )

            return response[start:end]

        return response

    def _should_continue(self, state: AgentState) -> str:
        """Determine whether orchestration should continue with tool execution or terminate."""
        if state.get("tool_call"):
            return "tool"

        return "end"

    def _tool_node(self, state: AgentState) -> AgentState:
        """Execute requested tool and append structured tool result into conversational state."""

        tool_call_data = state.get("tool_call")

        if not tool_call_data:
            return state

        tool_call = ToolCall(**tool_call_data)

        logger.info(f"Executing tool: {tool_call.name}")

        state["tools_used"].append(
            tool_call.name
        )

        tool_result = self._execute_tool(tool_call)

        if tool_result.success:

            result_text = json.dumps(
                tool_result.data,
                indent=2
            )

        else:

            result_text = (
                f"Tool execution failed: "
                f"{tool_result.error}"
            )

        logger.info(f"Tool result: {result_text[:200]}...")

        state["messages"].append({
            "role": "tool",
            "content": result_text
        })

        state["tool_call"] = None

        return state

    def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute tool via MCP server."""
        if tool_call.name not in self.tools:
            return ToolResult(
                success=False,
                error=f"Unknown tool: {tool_call.name}"
            )

        result = self.mcp_server.call_tool(tool_call.name, tool_call.arguments)

        # Store in memory
        if result.success:
            self.memory.add_tool_result(tool_call.name, result.data)

        return result

    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """Call OpenRouter API."""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Title": "MCP Chatbot"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 500
        }

        try:

            response = requests.post(
                OPENROUTER_URL,
                headers=headers,
                json=payload,
                timeout=30
            )

            response.raise_for_status()

            data = response.json()

            logger.info(f"LLM response: {json.dumps(data, indent=2)[:200]}...")

            content = data["choices"][0]["message"]["content"]

            if not content:
                raise ValueError("We are experiencing temporary technical issues. Please try again.")

            return content

        except Exception as e:
            logger.exception(f"LLM call failed: {e}")
            raise

    def process_query(self, query: str) -> AgentExecutionResult:

        start = time.time()

        validation_result = self._validate_user_input(query)
        if validation_result:
            return validation_result

        initial_state = AgentState(
            messages=[
                {
                    "role": "user",
                    "content": query
                }
            ],
            tool_result=None,
            tool_call=None,
            tools_used=[],
            parsing_failed=False,
            iteration_count=0
        )

        final_state = self.graph.invoke(initial_state)

        sanitized_response = (
            self._sanitize_output(
                query=query,
                response=final_state["messages"][-1]["content"]
            )
        )

        response_time = (time.time() - start)

        return AgentExecutionResult(
            response=sanitized_response,
            tools_used=final_state["tools_used"],
            parsing_failed=final_state["parsing_failed"],
            response_time=response_time,
            total_tool_calls=len(
                final_state["tools_used"]
            )
        )

    def _validate_user_input(
        self,
        query: str
    ) -> Optional[AgentExecutionResult]:
        """
        Validate user input before orchestration.

        Returns:
            AgentExecutionResult if validation fails,
            otherwise None.
        """

        # ----------------------------------------------------
        # Resource limits
        # ----------------------------------------------------

        resource_valid, resource_reason = (
            self.security.enforce_resource_limits(
                query
            )
        )

        if not resource_valid:

            return AgentExecutionResult(
                response=resource_reason,
                tools_used=[],
                parsing_failed=False,
                response_time=0,
                total_tool_calls=0
            )

        # ----------------------------------------------------
        # Prompt injection detection
        # ----------------------------------------------------

        injection_detected, injection_reason = (
            self.security.detect_injection_patterns(
                query
            )
        )

        if injection_detected:

            logger.warning(
                "Potential prompt injection detected: %s",
                injection_reason
            )

            return AgentExecutionResult(
                response=(
                    "Potential unsafe prompt detected. "
                    "Please rephrase your request."
                ),
                tools_used=[],
                parsing_failed=False,
                response_time=0,
                total_tool_calls=0
            )

        return None

    def _sanitize_output(
        self,
        query: str,
        response: str
    ) -> str:
        """
        Validate and sanitize final response.
        """

        response_valid, safe_response = (
            self.security.validate_factual_response(
                query=query,
                response=response
            )
        )

        return self.security.redact_sensitive_output(
            safe_response
        )

    def reset(self) -> None:
        """Reset agent state."""
        self.memory.clear()