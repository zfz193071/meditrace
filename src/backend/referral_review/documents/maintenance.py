"""Explicit failed-upload reconciliation; MT-18 supplies production scheduling."""

import argparse
import json

from ..config import load_settings
from ..identity.service import configured_identity
from .service import configured_documents


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=20, choices=range(1, 201), metavar="1..200")
    parser.add_argument("--retry-exhausted", action="store_true",
                        help="After operator review, reset the ten-attempt cap for selected due jobs")
    args = parser.parse_args()
    identity = None
    try:
        settings = load_settings()
        identity = configured_identity(settings)
        documents = configured_documents(settings, identity)
        if documents is None:
            parser.exit(1, "Configure identity, DATABASE_URL and private storage first.\n")
        print(json.dumps(documents.reconcile(limit=args.limit, retry_exhausted=args.retry_exhausted)))
    except Exception:
        parser.exit(1, "Upload reconciliation failed; retained reservations require another attempt after recovery.\n")
    finally:
        if identity is not None:
            identity.engine.dispose()


if __name__ == "__main__":
    main()
