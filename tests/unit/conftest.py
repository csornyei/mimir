from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_file_api_client():
    """Mock File API client for unit tests."""
    mock_client = AsyncMock()
    # Default: read returns empty string (file not found)
    mock_client.read_file = AsyncMock(return_value="")
    mock_client.write = AsyncMock()
    mock_client.save_file = AsyncMock()
    mock_client.append_line = AsyncMock()
    return mock_client


@pytest.fixture
def patch_file_api(mock_file_api_client):
    """Patch get_file_api_client to return the mock."""
    with patch(
        "agent_core.memory.semantic.get_file_api_client",
        return_value=mock_file_api_client,
    ):
        yield mock_file_api_client
