#!/usr/bin/env python3
"""Upload local product images to a Supabase Storage bucket.

Default behavior is a dry run. Add --apply to upload files.
The object path keeps the same relative path used in products.hero_image,
for example assets/products/uploads/foo.webp -> uploads/foo.webp.
"""
from __future__ import annotations

import argparse
import mimetypes
import os
import sys
from pathlib import Path
from urllib import error as url_error, parse, request as url_request

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

DEFAULT_BUCKET = "product-images"
DEFAULT_ROOT = Path("assets/products")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def load_local_secrets() -> dict[str, str]:
    path = Path(".streamlit/secrets.toml")
    if not path.exists() or tomllib is None:
        return {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {str(key): str(value) for key, value in data.items() if isinstance(value, (str, int, float))}


def setting(name: str, secrets: dict[str, str]) -> str:
    return str(os.environ.get(name) or secrets.get(name) or "").strip()


def normalize_supabase_url(raw_url: str) -> str:
    raw_url = raw_url.strip().rstrip("/")
    if raw_url.endswith("/rest/v1"):
        raw_url = raw_url[: -len("/rest/v1")]
    return raw_url


def iter_images(root: Path) -> list[Path]:
    if not root.exists():
        return []
    images: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if "originals" in path.relative_to(root).parts:
            continue
        images.append(path)
    return sorted(images)


def upload_file(base_url: str, api_key: str, bucket: str, root: Path, path: Path) -> None:
    object_path = path.relative_to(root).as_posix()
    encoded_bucket = parse.quote(bucket.strip("/"), safe="")
    encoded_path = parse.quote(object_path, safe="/")
    url = f"{base_url}/storage/v1/object/{encoded_bucket}/{encoded_path}"
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    data = path.read_bytes()
    req = url_request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
            "Content-Type": content_type,
            "x-upsert": "true",
        },
    )
    try:
        with url_request.urlopen(req, timeout=30) as response:
            response.read()
    except url_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{path}: upload failed {exc.code} {detail}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload product images to Supabase Storage.")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Local product image root. Default: assets/products")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET, help="Supabase Storage bucket. Default: product-images")
    parser.add_argument("--apply", action="store_true", help="Actually upload files. Without this, only prints a dry run.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    images = iter_images(root)
    print(f"Found {len(images)} product image(s) under {root}")
    for path in images:
        print(path.relative_to(root).as_posix())
    if not args.apply:
        print("Dry run only. Add --apply to upload to Supabase Storage.")
        return 0

    secrets = load_local_secrets()
    base_url = normalize_supabase_url(setting("SUPABASE_URL", secrets))
    api_key = setting("SUPABASE_SERVICE_KEY", secrets) or setting("SUPABASE_KEY", secrets)
    if not base_url or not api_key:
        print("ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_KEY in env or .streamlit/secrets.toml.", file=sys.stderr)
        return 1

    for index, path in enumerate(images, start=1):
        upload_file(base_url, api_key, args.bucket, root, path)
        print(f"[{index}/{len(images)}] uploaded {path.relative_to(root).as_posix()}")
    print(f"Done. Bucket: {args.bucket}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
