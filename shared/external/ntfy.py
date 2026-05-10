import httpx

from shared.logger import logger


async def send_ntfy(
    url: str,
    topic: str,
    message: str,
    title: str,
    click_url: str | None = None,
    tags: str | None = None,
) -> None:
    """Send a push notification via ntfy. Logs on failure, never raises."""
    headers: dict[str, str] = {"Title": title}
    if click_url:
        headers["Click"] = click_url
    if tags:
        headers["Tags"] = tags

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{url}/{topic}",
                content=message.encode("utf-8"),
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
    except Exception as exc:
        logger.warning(
            "ntfy_notification_failed",
            topic=topic,
            error=str(exc),
            error_type=type(exc).__name__,
        )
