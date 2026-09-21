"""Comprehensive Pytest Test Suite for Prompts Service, Templates, Repositories, and API."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services.prompts.api import get_prompt_service, router
from src.services.prompts.prompt_service import PromptService
from src.services.prompts.repositories.reader import LocalPromptRepository
from src.services.prompts.templates import CANONICAL_PROMPTS_LIST, get_prompt_template


@pytest.fixture
def prompt_service():
    repo = LocalPromptRepository()
    return PromptService(repository=repo)


def test_list_and_get_prompts(prompt_service):
    prompts = prompt_service.list_prompts()
    assert len(prompts) >= 3
    versions = [p["version"] for p in prompts]
    assert "v2.0" in versions
    assert "v1.0" in versions

    # Get existing
    p = prompt_service.get_prompt("account_scoring", "v2.0")
    assert p is not None
    assert p["version"] == "v2.0"

    # Get non-existing
    p_none = prompt_service.get_prompt("nonexistent", "v99.0")
    assert p_none is not None


def test_get_templates_and_canonical():
    t2 = get_prompt_template("v2.0")
    assert "{account_context}" in t2
    assert "tier_1_critical" in t2

    t1 = get_prompt_template("v1.0")
    assert "{account_context}" in t1

    # Fallback to default
    t_def = get_prompt_template("unknown_version")
    assert "{account_context}" in t_def

    assert len(CANONICAL_PROMPTS_LIST) >= 2


def test_register_prompt(prompt_service):
    registered = prompt_service.register_prompt(
        name="account_scoring",
        version="v3.0-custom",
        template="Custom prompt: {account_context}",
        prompt_type="scoring",
    )
    assert registered["version"] == "v3.0-custom"
    fetched = prompt_service.get_prompt("account_scoring", "v3.0-custom")
    assert fetched is not None
    assert fetched["template"] == "Custom prompt: {account_context}"


def test_prompts_api_endpoints(prompt_service):
    api_app = FastAPI()
    api_app.include_router(router)
    api_app.dependency_overrides[get_prompt_service] = lambda: prompt_service
    client = TestClient(api_app)

    # List
    r = client.get("/api/prompts")
    assert r.status_code == 200
    data = r.json()
    prompts_list = data["prompts"] if isinstance(data, dict) and "prompts" in data else data
    assert len(prompts_list) >= 3

    # Get
    r = client.get("/api/prompts/account_scoring/v2.0")
    assert r.status_code == 200

    # Register
    r = client.post(
        "/api/prompts",
        json={"name": "account_scoring", "version": "v5.0-test", "template": "Test {account_context}"},
    )
    assert r.status_code == 200

    # Delete custom prompt
    r = client.delete("/api/prompts/account_scoring/v5.0-test")
    assert r.status_code == 200
    assert r.json()["success"] is True

    # Attempt to delete canonical prompt should fail
    r = client.delete("/api/prompts/account_scoring/v2.0")
    assert r.status_code == 400

    api_app.dependency_overrides.clear()


def test_delete_prompt_service(prompt_service):
    # Register and delete
    prompt_service.register_prompt(
        name="test_prompt",
        version="v1.0-del",
        template="Content",
    )
    assert prompt_service.get_prompt("test_prompt", "v1.0-del") is not None
    res = prompt_service.delete_prompt("test_prompt", "v1.0-del")
    assert res is True
    res_fake = prompt_service.delete_prompt("test_prompt", "nonexistent-version-99")
    assert res_fake is False
