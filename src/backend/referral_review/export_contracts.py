"""Export contracts without importing main.py, reading .env, or connecting to a service."""

import argparse
import json
from pathlib import Path
from typing import Union

from pydantic import TypeAdapter

from . import CONTRACT_VERSION
from .app import create_app
from .config import Settings
from .schemas import DOMAIN_CONTRACTS
from .extraction.contracts import Extraction, ExtractionRevision, ModelOutput


def artifacts() -> dict[str, dict]:
    adapter = TypeAdapter(Union[DOMAIN_CONTRACTS + (Extraction, ExtractionRevision, ModelOutput)])
    domain_schema = adapter.json_schema()
    domain_schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    domain_schema["title"] = "MediTrace referral domain contracts"
    domain_schema["x-contract-version"] = CONTRACT_VERSION
    openapi = create_app(Settings()).openapi()
    components = adapter.json_schema(ref_template="#/components/schemas/{model}").get("$defs", {})
    openapi.setdefault("components", {}).setdefault("schemas", {}).update(components)
    openapi["x-contract-version"] = CONTRACT_VERSION
    return {"openapi.json": openapi, "domain.schema.json": domain_schema}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in artifacts().items():
        (args.output_dir / name).write_text(json.dumps(content, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
