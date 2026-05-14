from unittest.mock import Mock, patch

import pytest

from mcp.server import (
    MCPServerImpl,
    ToolResult
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def server():

    with patch(
        "mcp.server.DisasterDataService"
    ):

        with patch(
            "mcp.server.RAGRetriever"
        ):

            return MCPServerImpl()


# ============================================================
# Tool registration
# ============================================================

def test_tools_registered(
    server
):

    tools = server.list_tools()

    tool_names = {
        tool.name
        for tool in tools
    }

    assert (
        "get_current_weather"
        in tool_names
    )

    assert (
        "get_latest_news"
        in tool_names
    )

    assert (
        "query_disaster_data"
        in tool_names
    )

    assert (
        "retrieve_rag_context"
        in tool_names
    )


# ============================================================
# Unknown tool handling
# ============================================================

def test_unknown_tool(
    server
):

    result = server.call_tool(
        "unknown_tool",
        {}
    )

    assert result.success is False

    assert (
        "not found"
        in result.error.lower()
    )


# ============================================================
# Weather description mapping
# ============================================================

def test_weather_description_mapping(
    server
):

    assert (
        server._get_weather_description(0)
        == "Clear sky"
    )

    assert (
        server._get_weather_description(61)
        == "Slight rain"
    )

    assert (
        server._get_weather_description(999)
        == "Unknown"
    )


# ============================================================
# Coordinate lookup
# ============================================================

@patch("mcp.server.requests.get")
def test_get_coordinates(
    mock_get,
    server
):

    mock_response = Mock()

    mock_response.json.return_value = {
        "results": [
            {
                "latitude": 51.5,
                "longitude": -0.1,
                "name": "London",
                "country": "United Kingdom"
            }
        ]
    }

    mock_response.raise_for_status = Mock()

    mock_get.return_value = mock_response

    lat, lon, location = (
        server._get_coordinates(
            "London"
        )
    )

    assert lat == 51.5
    assert lon == -0.1

    assert (
        location
        == "London, United Kingdom"
    )


# ============================================================
# Weather execution
# ============================================================

@patch.object(
    MCPServerImpl,
    "_get_coordinates"
)

@patch("mcp.server.requests.get")
def test_execute_weather_tool(
    mock_get,
    mock_coordinates,
    server
):

    mock_coordinates.return_value = (
        51.5,
        -0.1,
        "London, United Kingdom"
    )

    mock_response = Mock()

    mock_response.json.return_value = {
        "current": {
            "temperature_2m": 10,
            "relative_humidity_2m": 80,
            "wind_speed_10m": 15,
            "weather_code": 61,
            "time": "2026-01-01T12:00"
        }
    }

    mock_response.raise_for_status = Mock()

    mock_get.return_value = mock_response

    result = (
        server._execute_get_current_weather(
            {"location": "London"}
        )
    )

    assert (
        result["location"]
        == "London, United Kingdom"
    )

    assert (
        result["conditions"]
        == "Slight rain"
    )

    assert (
        result["temperature_celsius"]
        == 10
    )


# ============================================================
# News execution
# ============================================================

@patch("mcp.server.feedparser.parse")
def test_execute_news_tool(
    mock_parse,
    server
):

    mock_feed = Mock()

    mock_feed.bozo = False

    mock_feed.entries = [
        {
            "title": "Test News",
            "summary": "Summary",
            "link": "https://example.com",
            "published": "Today"
        }
    ]

    mock_parse.return_value = mock_feed

    result = (
        server._execute_get_latest_news(
            {
                "category": "technology",
                "limit": 1
            }
        )
    )

    assert (
        result["category"]
        == "technology"
    )

    assert (
        result["count"]
        == 1
    )

    assert (
        result["articles"][0]["title"]
        == "Test News"
    )


# ============================================================
# Disaster routing
# ============================================================

def test_disaster_tool_routing(
    server
):

    server.disaster_service.query = Mock(
        return_value={
            "matches": 1
        }
    )

    result = (
        server._execute_query_disaster_data(
            {
                "query": "earthquake"
            }
        )
    )

    assert (
        result["matches"]
        == 1
    )

    server.disaster_service.query.assert_called_once()


# ============================================================
# RAG routing
# ============================================================

def test_rag_tool_routing(
    server
):

    server.rag_retriever.retrieve = Mock(
        return_value=[
            {
                "title": "Inflation"
            }
        ]
    )

    result = (
        server._execute_retrieve_rag_context(
            {
                "query": "inflation"
            }
        )
    )

    assert (
        result["query"]
        == "inflation"
    )

    assert (
        result["documents"][0]["title"]
        == "Inflation"
    )


# ============================================================
# call_tool success flow
# ============================================================

def test_call_tool_success(
    server
):

    with patch.object(
        server,
        "_execute_query_disaster_data",
        return_value={"matches": 2}
    ):

        result = server.call_tool(
            "query_disaster_data",
            {
                "query": "earthquake"
            }
        )

        assert isinstance(
            result,
            ToolResult
        )

        assert result.success is True

        assert (
            result.data["matches"]
            == 2
        )


# ============================================================
# call_tool exception handling
# ============================================================

def test_call_tool_exception_handling(
    server
):

    with patch.object(
        server,
        "_execute_query_disaster_data",
        side_effect=Exception(
            "Boom"
        )
    ):

        result = server.call_tool(
            "query_disaster_data",
            {
                "query": "earthquake"
            }
        )

        assert result.success is False

        assert (
            "boom"
            in result.error.lower()
        )
