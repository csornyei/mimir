from httpx import AsyncClient

from typing import Literal


class ForgejoClient:
    def __init__(self, base_url: str, token: str):
        self.__base_url = base_url
        self.__token = token
        self.client = AsyncClient(
            base_url=self.__base_url, headers={"Authorization": f"token {self.__token}"}
        )

    async def list_user_repositories(self):
        response = await self.client.get("/api/v1/user/repos")
        response.raise_for_status()
        return response.json()

    async def search_repositories(self, query: str):
        response = await self.client.get(f"/api/v1/repos/search?q={query}")
        response.raise_for_status()
        return response.json()

    async def get_repository(self, owner: str, repo_name: str):
        response = await self.client.get(f"/api/v1/repos/{owner}/{repo_name}")
        response.raise_for_status()
        return response.json()

    async def list_repository_issues(
        self,
        owner: str,
        repo_name: str,
        state: Literal["open", "closed", "all"] = "open",
        issue_type: Literal["issue", "pulls"] = "issue",
        page: int = 1,
        per_page: int = 30,
    ):
        response = await self.client.get(
            f"/api/v1/repos/{owner}/{repo_name}/issues",
            params={
                "state": state,
                "type": issue_type,
                "page": page,
                "per_page": per_page,
            },
        )
        response.raise_for_status()
        return response.json()

    async def create_issue(
        self,
        owner: str,
        repo_name: str,
        title: str,
        body: str = "",
        extra_fields: dict | None = None,
    ):
        """
        Create a new issue in the specified repository.

        Args:
            owner (str): The owner of the repository.
            repo_name (str): The name of the repository.
            title (str): The title of the issue.
            body (str, optional): The body content of the issue. Defaults to "".
            extra_fields (dict, optional): Additional fields to include in the issue payload. Defaults to None.

        Example extra_fields:
            - assignees (list): A list of usernames to assign the issue to.
            - labels (list): A list of labels to attach to the issue.
            - due_date (str): The due date for the issue in ISO 8601 format. Only date is considered, time is ignored.

        Returns:
            dict: The created issue's data.
        """
        payload = {"title": title, "body": body}
        payload.update(extra_fields or {})
        response = await self.client.post(
            f"/api/v1/repos/{owner}/{repo_name}/issues", json=payload
        )
        response.raise_for_status()
        return response.json()
