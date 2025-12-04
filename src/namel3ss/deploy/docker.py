from __future__ import annotations

from textwrap import dedent

from namel3ss.packaging.models import BundleManifest

DEFAULT_BASE_IMAGE = "python:3.11-slim"


def generate_dockerfile(manifest: BundleManifest, base_image: str = DEFAULT_BASE_IMAGE) -> str:
    """
    Generate a Dockerfile for the given bundle manifest.
    """
    env_lines = "\n".join(f"ENV {k}=\"{v}\"" for k, v in manifest.env.items())
    return dedent(
        f"""
        FROM {base_image}
        WORKDIR /app
        COPY . /app
        RUN pip install --no-cache-dir .
        {env_lines}
        CMD ["python", "/app/{manifest.entrypoint}"]
        """
    ).strip()
