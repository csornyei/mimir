from typing import Literal

from shared.external.forgejo.client import ForgejoClient
from mcp_server.decorators import traced_tool, write_tool
from shared.logger import logger
from mcp_server.config import mcp_config

forgejo_client = ForgejoClient(
    base_url=mcp_config.forgejo_url, token=mcp_config.forgejo_token
)


@traced_tool
async def list_user_repositories():
    """List repositories of the authenticated user."""
    logger.debug("list_user_repositories")
    return await forgejo_client.list_user_repositories()


@traced_tool
async def search_repositories(query: str):
    """Search repositories by name or description."""
    logger.debug("search_repositories", query=query)
    return await forgejo_client.search_repositories(query)


@traced_tool
async def get_repository(owner: str, repo_name: str):
    """Get details of a specific repository."""
    logger.debug("get_repository", owner=owner, repo_name=repo_name)
    return await forgejo_client.get_repository(owner, repo_name)


@traced_tool
async def list_repository_issues(
    owner: str,
    repo_name: str,
    state: Literal["open", "closed", "all"] = "open",
    issue_type: Literal["issue", "pulls"] = "issue",
    page: int = 1,
    per_page: int = 30,
):
    """
    List issues or pull requests of a repository.

    Args:
        owner: Repository owner username.
        repo_name: Repository name.
        state: Filter by state (open, closed, all). Default is "open".
        issue_type: Filter by type (issue, pulls). Default is "issue".
        page: Page number for pagination. Default is 1. (1-based index)
        per_page: Number of items per page for pagination. Default is 30.
    """
    logger.debug(
        "list_repository_issues",
        owner=owner,
        repo_name=repo_name,
        state=state,
        issue_type=issue_type,
        page=page,
        per_page=per_page,
    )

    return await forgejo_client.list_repository_issues(
        owner, repo_name, state, issue_type, page, per_page
    )


@write_tool
async def create_issue(
    owner: str, repo_name: str, title: str, body: str = "", **kwargs
):
    """
    Create a new issue in the specified repository.

    Args:
        owner: The owner of the repository.
        repo_name: The name of the repository.
        title: The title of the issue.
        body: The body content of the issue. Optional.
        **kwargs: Additional fields for issue creation (e.g. labels, assignees, due_date).
    """
    logger.debug(
        "create_issue",
        owner=owner,
        repo_name=repo_name,
        title=title,
        body=body,
        extra_fields=kwargs,
    )
    return await forgejo_client.create_issue(
        owner, repo_name, title, body, extra_fields=kwargs
    )
