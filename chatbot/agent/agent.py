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

        return f"""You are a helpful AI assistant with access to tools for answering questions.

AVAILABLE TOOLS:
{tools_text}

INSTRUCTIONS:
1. Analyze the user's question carefully
2. Determine if you need to use a tool to answer
3. If you need a tool, respond with a JSON tool call in this EXACT format:
   <TOOL_CALL>
   {{"name": "tool_name", "arguments": {{"param": "value"}}}}
   </TOOL_CALL>
   Do not use XML.
   Do not use pseudo-code.
   Do not use natural language before or after tool calls.
4. If you don't need a tool, or after receiving tool results, provide a natural language answer
5. Be concise and accurate
6. Do not hallucinate information - only use data from tool results

IMPORTANT:
- Output ONLY valid JSON inside <TOOL_CALL>
- If the user asks about historical or conceptual information, prefer the retrieve_rag_context.
- If the user asks for latest/current/recent events, prefer the get_latest_news.
- Do NOT include any extra text inside TOOL_CALL
- Ensure JSON is strictly valid (double quotes, no trailing commas)
- Only make ONE tool call at a time
- Wait for tool results before answering
- Never invent tool results
- If unsure, ask for clarification
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
            state["parsing_failed"] = True

        return None

    def _build_graph(self):

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

        system_prompt = self._build_system_prompt()

        state["iteration_count"] += 1

        messages = [
            {"role": "system", "content": system_prompt}
        ] + state["messages"]

        response = self._call_llm(messages)

        logger.info(f"LLM response: {response[:200]}...")

        tool_call = self._parse_tool_call(response)

        if tool_call:
            state["tool_call"] = tool_call.model_dump()
            return state

        state["messages"].append({
            "role": "assistant",
            "content": response
        })

        state["tool_call"] = None

        return state

    def _should_continue(self, state: AgentState) -> str:

        if state.get("tool_call"):
            return "tool"

        return "end"

    def _tool_node(self, state: AgentState) -> AgentState:

        tool_call_data = state.get("tool_call")

        state["tools_used"].append(
            tool_call.name
        )

        if not tool_call_data:
            return state

        tool_call = ToolCall(**tool_call_data)

        logger.info(f"Executing tool: {tool_call.name}")

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

    def process_query(self, query: str) -> str:

        start = time.time()

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

        response_time = (time.time() - start)

        return AgentExecutionResult(
            response=final_state["messages"][-1]["content"],
            tools_used=final_state["tools_used"],
            parsing_failed=final_state["parsing_failed"],
            response_time=response_time,
            total_tool_calls=len(
                final_state["tools_used"]
            )
        )

    def reset(self) -> None:
        """Reset agent state."""
        self.memory.clear()