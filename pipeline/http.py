from __future__ import annotations
import json, ssl, time, urllib.error, urllib.request

try:  # Prefer certifi's CA bundle: some Python builds ship without system roots.
    import certifi

    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CONTEXT = ssl.create_default_context()


def get_json(url: str, timeout: int = 60):
    error = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "SeriesDashboard/1.0"}
            )
            with urllib.request.urlopen(
                request, timeout=timeout, context=_SSL_CONTEXT
            ) as response:
                return json.load(response)
        except (
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
            OSError,
        ) as exc:
            error = exc
            if attempt < 2:
                time.sleep(0.5 * (2**attempt))
    raise RuntimeError(f"No se pudo descargar JSON de {url}: {error}") from error
