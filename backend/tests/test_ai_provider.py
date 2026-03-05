"""Tests for AI provider abstraction layer."""

import pytest

from app.services.ai_provider import get_provider, get_step_provider
from app.services.providers.anthropic import AnthropicProvider
from app.services.providers.google import GoogleProvider
from app.services.providers.openai import OpenAIProvider


class TestGetProvider:
    """Tests for the get_provider factory function."""

    def test_get_anthropic_provider(self):
        provider = get_provider("anthropic")
        assert isinstance(provider, AnthropicProvider)

    def test_get_openai_provider(self):
        provider = get_provider("openai")
        assert isinstance(provider, OpenAIProvider)

    def test_get_google_provider(self):
        provider = get_provider("google")
        assert isinstance(provider, GoogleProvider)

    def test_get_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown AI provider"):
            get_provider("unknown")


class TestGetStepProvider:
    """Tests for the get_step_provider function."""

    def test_factcheck_step_returns_configured_provider(self):
        provider, model = get_step_provider("factcheck")
        assert isinstance(provider, OpenAIProvider)  # default config
        assert model == "gpt-4o-mini"

    def test_analysis_step_returns_configured_provider(self):
        provider, model = get_step_provider("analysis")
        assert isinstance(provider, OpenAIProvider)
        assert model == "gpt-4o-mini"

    def test_script_step_returns_configured_provider(self):
        provider, model = get_step_provider("script")
        assert isinstance(provider, OpenAIProvider)
        assert model == "gpt-4o"

    def test_unconfigured_step_uses_defaults(self):
        provider, model = get_step_provider("voice")
        assert isinstance(provider, OpenAIProvider)  # default provider
        assert model == "gpt-4o-mini"  # default model
