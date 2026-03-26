"""Pure utility functions with no dependencies on library modules."""

import typing as t
from urllib.parse import quote, urlencode, urljoin


def join_url(
    base: str,
    *parts: t.Union[str, int],
    params: t.Optional[dict] = None,
    leading_slash: bool = False,
    trailing_slash: bool = False,
) -> str:
    """Construct a full ("absolute") URL by combining a "base URL" (base) with another URL (url) parts.

    :param base: base URL part
    :param parts: another url parts that should be joined
    :param params: dict with query params
    :param leading_slash: flag to force leading slash
    :param trailing_slash: flag to force trailing slash

    :return: full URL
    """
    url = base
    if parts:
        quoted_and_stripped_parts = [quote(str(part).strip("/"), safe=": /") for part in parts]
        url = "/".join([base.strip("/"), *quoted_and_stripped_parts])

    # trailing slash can be important
    if trailing_slash:
        url = f"{url}/"
    # as well as a leading slash
    if leading_slash:
        url = f"/{url}"

    if params:
        url = urljoin(url, f"?{urlencode(params)}")

    return url
