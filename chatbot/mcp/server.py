from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

import requests
import feedparser

from pydantic import BaseModel, Field

class ToolSchema(BaseModel):
    """Strict tool schema following MCP specification."""
    name: str = Field(..., description="Unique tool identifier")
    description: str = Field(..., description="Clear description of tool purpose")
    input_schema: Dict[str, Any] = Field(..., description="JSON Schema for tool arguments")

class ToolResult(BaseModel):
    """Standardized tool execution result."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None

class MCPServer(ABC):
    """Abstract base class for MCP server."""

    def __init__(self, name: str):
        self.name = name
        self._tools: Dict[str, ToolSchema] = {}
        self._register_tools()

    @abstractmethod
    def _register_tools(self) -> None:
        """Register all tools provided by this server."""
        pass

    def list_tools(self) -> List[ToolSchema]:
        """Return all available tools from this server."""
        return list(self._tools.values())

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute a tool by name with provided arguments.

        Args:
            name: Tool identifier
            arguments: Tool parameters

        Returns:
            ToolResult with success status and data/error
        """
        if name not in self._tools:
            return ToolResult(
                success=False,
                error=f"Tool '{name}' not found in server '{self.name}'"
            )

        try:
            method_name = f"_execute_{name}"
            if not hasattr(self, method_name):
                return ToolResult(
                    success=False,
                    error=f"Implementation for '{name}' not found"
                )

            result = getattr(self, method_name)(arguments)
            return ToolResult(success=True, data=result)

        except Exception as e:
            print(f"Tool execution failed: {name}", exc_info=True)
            return ToolResult(success=False, error=str(e))

    def _add_tool(self, schema: ToolSchema) -> None:
        """Internal method to register a tool schema."""
        self._tools[schema.name] = schema

class MCPServerImpl(MCPServer):
    """MCP Server for weather and news data.

    Provides tools for:
    - Current weather conditions (Open-Meteo API)
    - Latest news headlines (RSS feeds)

    """

    # Weather API endpoints
    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
    WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

    # News RSS feeds by category
    RSS_FEEDS = {
        "general": "http://rss.cnn.com/rss/edition.rss",
        "technology": "http://rss.cnn.com/rss/edition_technology.rss",
        "business": "http://rss.cnn.com/rss/edition_business.rss",
        "world": "http://rss.cnn.com/rss/edition_world.rss"
    }

    def __init__(self):
        super().__init__("unified")

    def _register_tools(self) -> None:
        """Register all tools (weather + news)."""
        self._add_tool(ToolSchema(
            name="get_current_weather",
            description="Get current weather conditions for a specific location. Returns temperature, conditions, wind speed, and humidity.",
            input_schema={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name or location (e.g., 'London', 'New York')"
                    }
                },
                "required": ["location"]
            }
        ))

        self._add_tool(ToolSchema(
            name="get_latest_news",
            description="Get the latest news headlines. Can filter by category (general, technology, business, world). Returns top news stories with titles and summaries.",
            input_schema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "News category: general, technology, business, or world",
                        "enum": ["general", "technology", "business", "world"]
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of articles to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["category"]
            }
        ))

    # ========== Weather Tool Implementation ==========

    def _get_coordinates(self, location: str) -> Tuple[float, float, str]:
        """Convert location name to coordinates using geocoding.

        Returns:
            Tuple of (latitude, longitude, full_location_name)
        """
        response = requests.get(
            self.GEOCODING_URL,
            params={"name": location, "count": 1, "language": "en", "format": "json"},
            timeout=10
        )
        response.raise_for_status()

        data = response.json()
        if not data.get("results"):
            raise ValueError(f"Location not found: {location}")

        result = data["results"][0]
        return (
            result["latitude"],
            result["longitude"],
            f"{result['name']}, {result.get('country', '')}"
        )

    def _execute_get_current_weather(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Implementation of get_current_weather tool."""
        location = arguments["location"]

        # Get coordinates for location
        lat, lon, full_location = self._get_coordinates(location)

        # Fetch weather data
        response = requests.get(
            self.WEATHER_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
                "temperature_unit": "celsius",
                "wind_speed_unit": "kmh"
            },
            timeout=10
        )
        response.raise_for_status()

        data = response.json()
        current = data["current"]

        # Map weather codes to conditions
        weather_code = current["weather_code"]
        conditions = self._get_weather_description(weather_code)

        return {
            "location": full_location,
            "temperature_celsius": current["temperature_2m"],
            "conditions": conditions,
            "humidity_percent": current["relative_humidity_2m"],
            "wind_speed_kmh": current["wind_speed_10m"],
            "timestamp": current["time"]
        }

    def _get_weather_description(self, code: int) -> str:
        """Map WMO weather code to description."""
        code_map = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Foggy",
            48: "Foggy",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            71: "Slight snow",
            73: "Moderate snow",
            75: "Heavy snow",
            95: "Thunderstorm"
        }
        return code_map.get(code, "Unknown")

    # ========== News Tool Implementation ==========

    def _execute_get_latest_news(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Implementation of get_latest_news tool."""
        category = arguments["category"]
        limit = arguments.get("limit", 5)

        if category not in self.RSS_FEEDS:
            raise ValueError(f"Unknown category: {category}")

        # Fetch RSS feed
        feed_url = self.RSS_FEEDS[category]
        feed = feedparser.parse(feed_url)

        if feed.bozo:
            raise ValueError(f"Failed to parse RSS feed: {feed_url}")

        # Extract articles
        articles = []
        for entry in feed.entries[:limit]:
            articles.append({
                "title": entry.get("title", "No title"),
                "summary": entry.get("summary", "No summary"),
                "link": entry.get("link", ""),
                "published": entry.get("published", "")
            })

        return {
            "category": category,
            "count": len(articles),
            "articles": articles,
            "retrieved_at": datetime.now().isoformat()
        }
