"""
Provider abstraction layer for fact-checking with web search capabilities.

Supports:
- OpenAI (Responses API with web_search_preview)
- Gemini (with google_search_retrieval grounding)
"""

import json
import os
import re
import time
import requests
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


def resolve_redirect_urls(text: str) -> str:
    """Replace Vertex AI redirect URLs with actual target URLs.

    Finds URLs like https://vertexaisearch.cloud.google.com/grounding-api-redirect/...
    and resolves them to their actual target URLs.
    """
    redirect_pattern = r'https://vertexaisearch\.cloud\.google\.com/grounding-api-redirect/[^\s\)\]\"\'<>]+'

    def resolve_single_url(match):
        redirect_url = match.group(0)
        try:
            # Follow the redirect with HEAD request to get actual URL
            response = requests.head(redirect_url, allow_redirects=True, timeout=10)
            actual_url = response.url
            if actual_url != redirect_url:
                return actual_url
        except Exception:
            pass
        return redirect_url

    # Find all redirect URLs and resolve them
    resolved_text = re.sub(redirect_pattern, resolve_single_url, text)
    return resolved_text


def safe_serialize(obj: Any) -> Any:
    """Safely convert an object to a JSON-serializable form.

    Returns the object if it's already serializable, otherwise returns
    "[non-serializable: ClassName]".
    """
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [safe_serialize(item) for item in obj]
    if isinstance(obj, dict):
        return {k: safe_serialize(v) for k, v in obj.items()}
    # Try to convert to dict if it has __dict__
    if hasattr(obj, '__dict__'):
        try:
            return {k: safe_serialize(v) for k, v in obj.__dict__.items() if not k.startswith('_')}
        except Exception:
            pass
    # Last resort: try json.dumps
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return f"[non-serializable: {type(obj).__name__}]"


@dataclass
class FactCheckResponse:
    """Unified response format from fact-checking providers."""
    output_text: str
    model: str
    raw_response: dict  # Provider-specific response data for logging


class FactCheckProvider(ABC):
    """Abstract base class for fact-checking providers."""

    @abstractmethod
    def submit_and_wait(
        self,
        system_message: str,
        user_message: str,
        reasoning_effort: str = "high"
    ) -> FactCheckResponse:
        """Submit a fact-check request with web search and wait for completion."""
        pass

    @abstractmethod
    def simple_completion(
        self,
        system_message: str,
        user_message: str,
        reasoning_effort: str = "high"
    ) -> str:
        """Simple completion without background processing (for post-processing)."""
        pass


class OpenAIProvider(FactCheckProvider):
    """OpenAI provider using Responses API with web search."""

    def __init__(self, model: str = "gpt-5.1", api_key: Optional[str] = None,
                 organization: Optional[str] = None):
        from openai import OpenAI

        self.model = model
        self.client = OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY"),
            organization=organization or os.environ.get("OPENAI_ORG_ID")
        )

    def submit_and_wait(
        self,
        system_message: str,
        user_message: str,
        reasoning_effort: str = "high",
        poll_interval: int = 30
    ) -> FactCheckResponse:
        """Submit fact-check with web search and wait for completion."""

        full_prompt = [
            {"role": "developer", "content": system_message},
            {"role": "user", "content": user_message}
        ]

        reasoning = {"effort": reasoning_effort}

        # Start background task
        response = self.client.responses.create(
            model=self.model,
            reasoning=reasoning,
            input=full_prompt,
            tools=[
                {"type": "web_search_preview"},
                {"type": "code_interpreter", "container": {"type": "auto", "file_ids": []}}
            ],
            background=True
        )

        if response.status != "queued":
            raise Exception(f"Failed to start research task: {response.status}")

        task_id = response.id
        print(f"  Research task started. Task ID: {task_id}")

        # Poll until complete
        while response.status in {"queued", "in_progress"}:
            print(f"  Current status: {response.status}")
            time.sleep(poll_interval)
            response = self.client.responses.retrieve(task_id)

        return FactCheckResponse(
            output_text=response.output_text,
            model=response.model,
            raw_response=json.loads(response.model_dump_json())
        )

    def simple_completion(
        self,
        system_message: str,
        user_message: str,
        reasoning_effort: str = "high"
    ) -> str:
        """Simple completion for post-processing."""

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]

        reasoning = {"effort": reasoning_effort}

        response = self.client.responses.create(
            model=self.model,
            reasoning=reasoning,
            input=messages,
            tools=[{"type": "web_search_preview"}],
            tool_choice="auto",
        )

        return response.output_text


class GeminiProvider(FactCheckProvider):
    """Gemini provider supporting both standard models and Deep Research."""

    # Mapping from OpenAI-style effort levels to Gemini thinking budget
    # Max allowed is 65535
    THINKING_BUDGET = {
        "low": 8192,
        "medium": 32768,
        "high": 65535,
    }

    # Default model for post-processing when using deep-research for main task
    POSTPROCESS_MODEL = "gemini-3-pro-preview"

    def __init__(self, model: str = "gemini-2.5-flash", api_key: Optional[str] = None):
        from google import genai
        from google.genai import types

        self.model = model
        self.is_deep_research = model.lower().startswith("deep-research")
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set. Run: source env.sh")
        self.client = genai.Client(api_key=self.api_key)
        self.types = types

    def _submit_deep_research(self, system_message: str, user_message: str,
                               poll_interval: int = 30) -> FactCheckResponse:
        """Submit fact-check using Deep Research Interactions API."""

        # Combine system and user message for deep research input
        full_input = f"{system_message}\n\n{user_message}"

        print(f"  Starting Gemini Deep Research (agent: {self.model})...")

        # Start the deep research interaction in background
        interaction = self.client.interactions.create(
            input=full_input,
            agent=self.model,
            background=True
        )

        interaction_id = interaction.id
        print(f"  Interaction started. ID: {interaction_id}")

        # Poll until complete
        while True:
            interaction = self.client.interactions.get(interaction_id)
            if interaction.status == "completed":
                print(f"  Research completed")
                break
            elif interaction.status == "failed":
                error_msg = getattr(interaction, 'error', 'Unknown error')
                raise Exception(f"Deep Research failed: {error_msg}")
            print(f"  Current status: {interaction.status}")
            time.sleep(poll_interval)

        # Extract output text from interaction.outputs[-1].text
        output_text = ""
        if hasattr(interaction, 'outputs') and interaction.outputs:
            output_text = interaction.outputs[-1].text or ""

        # Resolve redirect URLs to actual URLs
        if output_text:
            print(f"  Resolving redirect URLs...")
            output_text = resolve_redirect_urls(output_text)

        # Build raw response for logging
        raw_response = safe_serialize({
            "interaction_id": interaction_id,
            "model": self.model,
            "status": interaction.status,
            "outputs": interaction.outputs if hasattr(interaction, 'outputs') else None,
        })

        return FactCheckResponse(
            output_text=output_text,
            model=self.model,
            raw_response=raw_response
        )

    def _submit_standard(self, system_message: str, user_message: str,
                         reasoning_effort: str = "high") -> FactCheckResponse:
        """Submit fact-check using standard Gemini with grounding tools."""

        # Configure tools
        tools = [
            # Google Search for web research
            self.types.Tool(google_search=self.types.GoogleSearch()),
            # Code execution for calculations and data analysis
            self.types.Tool(code_execution=self.types.ToolCodeExecution()),
            # URL context for fetching and reading web pages
            self.types.Tool(url_context=self.types.UrlContext()),
        ]

        # Configure thinking/reasoning
        thinking_budget = self.THINKING_BUDGET.get(reasoning_effort, 65535)
        thinking_config = self.types.ThinkingConfig(
            thinking_budget=thinking_budget
        )

        # Create generation config
        config = self.types.GenerateContentConfig(
            system_instruction=system_message,
            tools=tools,
            thinking_config=thinking_config,
        )

        print(f"  Submitting to Gemini (thinking budget: {thinking_budget})...")

        response = self.client.models.generate_content(
            model=self.model,
            contents=user_message,
            config=config,
        )

        # Extract text from response
        output_text = response.text if response.text else ""

        # Build raw response for logging
        raw_response = {
            "model": self.model,
            "candidates": [],
            "grounding_metadata": None,
        }

        if response.candidates:
            for candidate in response.candidates:
                candidate_data = {
                    "content": {
                        "parts": [{"text": p.text} for p in candidate.content.parts if hasattr(p, 'text') and p.text]
                    },
                    "grounding_metadata": None
                }
                if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                    gm = candidate.grounding_metadata
                    candidate_data["grounding_metadata"] = {
                        "search_entry_point": safe_serialize(getattr(gm, 'search_entry_point', None)),
                        "grounding_chunks": [
                            {"web": safe_serialize({"uri": chunk.web.uri, "title": chunk.web.title})}
                            for chunk in (gm.grounding_chunks or [])
                            if hasattr(chunk, 'web') and chunk.web
                        ],
                        "grounding_supports": [
                            {
                                "segment": safe_serialize({"text": s.segment.text}) if hasattr(s, 'segment') and s.segment else None,
                                "grounding_chunk_indices": list(s.grounding_chunk_indices) if hasattr(s, 'grounding_chunk_indices') else []
                            }
                            for s in (gm.grounding_supports or [])
                        ] if gm.grounding_supports else []
                    }
                raw_response["candidates"].append(candidate_data)

        return FactCheckResponse(
            output_text=output_text,
            model=self.model,
            raw_response=raw_response
        )

    def submit_and_wait(
        self,
        system_message: str,
        user_message: str,
        reasoning_effort: str = "high"
    ) -> FactCheckResponse:
        """Submit fact-check - uses Deep Research API or standard Gemini based on model."""

        if self.is_deep_research:
            return self._submit_deep_research(system_message, user_message)
        else:
            return self._submit_standard(system_message, user_message, reasoning_effort)

    def simple_completion(
        self,
        system_message: str,
        user_message: str,
        reasoning_effort: str = "high"
    ) -> str:
        """Simple completion for post-processing. Uses standard Gemini model for deep-research."""

        # For post-processing, use standard Gemini model when main model is deep-research
        if self.is_deep_research:
            model_to_use = self.POSTPROCESS_MODEL
            print(f"  Warning: Using {model_to_use} for post-processing (deep-research not supported)")
        else:
            model_to_use = self.model

        # Configure tools
        tools = [
            self.types.Tool(google_search=self.types.GoogleSearch()),
        ]

        thinking_budget = self.THINKING_BUDGET.get(reasoning_effort, 65535)
        thinking_config = self.types.ThinkingConfig(
            thinking_budget=thinking_budget
        )

        config = self.types.GenerateContentConfig(
            system_instruction=system_message,
            tools=tools,
            thinking_config=thinking_config,
        )

        response = self.client.models.generate_content(
            model=model_to_use,
            contents=user_message,
            config=config,
        )

        return response.text if response.text else ""


DEFAULT_MODEL = "gpt-5.1"


def detect_provider(model: str) -> str:
    """Detect the provider from the model name.

    Args:
        model: Model name (e.g., "gpt-5.1", "gemini-2.5-flash", "deep-research-pro-preview-12-2025")

    Returns:
        Provider name ("openai" or "gemini")
    """
    model_lower = model.lower()

    if model_lower.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai"
    elif model_lower.startswith(("gemini", "deep-research")):
        return "gemini"
    else:
        raise ValueError(
            f"Cannot detect provider for model '{model}'. "
            f"Model name should start with 'gpt-', 'o1', 'o3', 'o4' (OpenAI) or 'gemini', 'deep-research' (Google)."
        )


def get_provider(model: str, **kwargs) -> FactCheckProvider:
    """Factory function to get a provider instance based on model name.

    Args:
        model: Model name - provider is auto-detected from the name
        **kwargs: Additional provider-specific arguments

    Returns:
        FactCheckProvider instance
    """
    provider_name = detect_provider(model)

    providers = {
        "openai": OpenAIProvider,
        "gemini": GeminiProvider,
    }

    provider_class = providers[provider_name]
    return provider_class(model=model, **kwargs)
