from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from playwright.async_api import async_playwright, Browser
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from web_fetch.fetcher import fetch_httpx, fetch_playwright, fetch_reddit
from shared.logger import logger
from shared.telemetry import setup_tracing
from shared.config import shared_config

setup_tracing(service_name=shared_config.service_name)

_playwright = None
_browser: Browser | None = None


async def get_browser() -> Browser:
    global _playwright, _browser
    if _playwright is None:
        _playwright = await async_playwright().start()
    if _browser is None or not _browser.is_connected():
        _browser = await _playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
    return _browser


async def close_browser():
    global _playwright, _browser
    if _browser is not None:
        await _browser.close()
        _browser = None
    if _playwright is not None:
        await _playwright.stop()
        _playwright = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_browser()


app = FastAPI(lifespan=lifespan)
FastAPIInstrumentor().instrument_app(app)


@app.get("/fetch")
async def root(
    url: str,
    browser: Browser = Depends(get_browser),
):
    try:
        if "reddit.com" in url:
            result = await fetch_reddit(url)
            if result is not None:
                return result

        result = await fetch_httpx(url)
        if result is not None:
            return result

        logger.info("httpx_failed_fallback_to_playwright", url={url})
        result = await fetch_playwright(browser, url)
        if result is not None:
            return result

        return {"error": "Failed to fetch the URL with both methods."}
    except Exception as e:
        return {"error": str(e)}
