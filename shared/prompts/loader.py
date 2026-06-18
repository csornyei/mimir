from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from shared.logger import logger

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)


def render(template_name: str, **kwargs: object) -> str:
    logger.debug("rendering_template", template_name=template_name, kwargs=kwargs)
    return _env.get_template(template_name).render(**kwargs)
