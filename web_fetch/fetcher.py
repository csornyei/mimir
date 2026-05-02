import httpx
import trafilatura
from opentelemetry import trace
from urllib.parse import urlparse, urljoin, urlunparse
from playwright.async_api import Browser, Route
from lxml import html as lxml_html

from shared.logger import logger

_tracer = trace.get_tracer("web_fetch.fetcher")


BLOCKED_RESOURCES = {"image", "stylesheet", "font", "media"}
TIMEOUT_MS = 15_000


async def block_resource(route: Route):
    if route.request.resource_type in BLOCKED_RESOURCES:
        await route.abort()
    else:
        await route.continue_()


async def fetch_httpx(url: str) -> dict | None:
    with _tracer.start_as_current_span("fetch_httpx") as span:
        span.set_attribute("fetch.url", url)
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            try:
                response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                response.raise_for_status()

                html = response.text

                content = trafilatura.extract(
                    html,
                    output_format="markdown",
                    include_comments=False,
                    favor_recall=True,
                )

                if content and len(content.strip()) > 200:
                    links = _extract_links_httpx(html, str(response.url))
                    span.set_attribute("fetch.result", "success")
                    return {
                        "url": str(response.url),
                        "content": content.strip(),
                        "links": links,
                        "fetched_with": "httpx",
                    }

                else:
                    logger.info(
                        "httpx_fetch_insufficient_content",
                        url=url,
                        content_length=len(content) if content else 0,
                    )
                    span.set_attribute("fetch.result", "insufficient_content")
                    return None
            except Exception as e:
                logger.error("httpx_fetch_error", url={url}, error={e}, exc_info=True)
                span.set_attribute("fetch.result", "error")
                span.set_status(trace.StatusCode.ERROR, str(e))
                return None


async def fetch_reddit(url: str) -> dict | None:
    with _tracer.start_as_current_span("fetch_reddit") as span:
        span.set_attribute("fetch.url", url)
        parsed = urlparse(url)
        json_path = parsed.path.rstrip("/") + ".json"
        json_url = urlunparse(parsed._replace(path=json_path, query="", fragment=""))

        headers = {
            "User-Agent": "personal-assistant:mimir:1.0 (personal use)",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            try:
                response = await client.get(json_url, headers=headers)
                response.raise_for_status()
                data = response.json()

                post = data[0]["data"]["children"][0]["data"]
                title = post.get("title", "")
                body = post.get("selftext", "").strip()
                subreddit = post.get("subreddit_name_prefixed", "")

                comments = []
                for child in data[1]["data"]["children"]:
                    if child.get("kind") != "t1":
                        continue
                    d = child["data"]
                    text = d.get("body", "")
                    if text in ("[deleted]", "[removed]", ""):
                        continue
                    comments.append(
                        f"**{d.get('author', '')}** (↑{d.get('score', 0)})\n{text}"
                    )

                parts = [f"# {title}", f"*{subreddit}*"]
                if body:
                    parts.append(body)
                if comments:
                    parts.append("## Top Comments")
                    parts.extend(comments[:20])

                span.set_attribute("fetch.result", "success")
                return {
                    "url": url,
                    "title": title,
                    "content": "\n\n".join(parts),
                    "links": [],
                    "fetched_with": "reddit_json",
                }
            except Exception as e:
                logger.error("reddit_fetch_error", url=url, error=str(e), exc_info=True)
                span.set_attribute("fetch.result", "error")
                span.set_status(trace.StatusCode.ERROR, str(e))
                return None


def _path_depth(path: str) -> int:
    return len([s for s in path.split("/") if s])


def _filter_links(hrefs: list[str], base_url: str) -> list[str]:
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc
    min_depth = _path_depth(parsed_base.path)
    current = urlunparse(parsed_base._replace(query="", fragment=""))
    seen = set()
    links = []
    for href in hrefs:
        parsed = urlparse(href)
        if parsed.scheme not in ("http", "https") or parsed.netloc != base_domain:
            continue
        clean = urlunparse(parsed._replace(query="", fragment=""))
        if clean == current:
            continue
        if _path_depth(parsed.path) < min_depth:
            continue
        if clean not in seen:
            seen.add(clean)
            links.append(clean)
    return links[:50]


def _extract_links_httpx(html_text: str, base_url: str) -> list[str]:
    tree = lxml_html.fromstring(html_text)
    hrefs = [urljoin(base_url, el.get("href", "")) for el in tree.cssselect("a[href]")]
    return _filter_links(hrefs, base_url)


async def _extract_links_playwright(page, base_url: str) -> list[str]:
    hrefs = await page.evaluate("""
        () => Array.from(document.querySelectorAll('a[href]'))
              .map(a => a.href)
    """)
    return _filter_links(hrefs, base_url)


async def fetch_playwright(browser: Browser, url: str) -> dict | None:
    with _tracer.start_as_current_span("fetch_playwright") as span:
        span.set_attribute("fetch.url", url)
        ctx = await browser.new_context()

        try:
            page = await ctx.new_page()

            await page.route("**/*", block_resource)

            await page.goto(url, timeout=TIMEOUT_MS, wait_until="networkidle")

            html = await page.content()
            title = await page.title()

            content = trafilatura.extract(
                html, output_format="markdown", favor_recall=True
            )
            links = await _extract_links_playwright(page, url)

            span.set_attribute("fetch.result", "success")
            return {
                "url": url,
                "title": title,
                "content": content.strip() if content else "",
                "links": links,
                "fetched_with": "playwright",
            }
        except Exception as e:
            logger.error("playwright_fetch_error", url={url}, error={e}, exc_info=True)
            span.set_attribute("fetch.result", "error")
            span.set_status(trace.StatusCode.ERROR, str(e))
            return None
        finally:
            await page.close()
            await ctx.close()
