#!/usr/bin/env python3
"""Explicit small synthetic Private Blob roundtrip, with a cleanup receipt.

No dotenv loading, public stores, AI calls or application database access.
Receipt is written before PUT so an ambiguous network failure is recoverable.
Run with the backend virtualenv after configuring BLOB_READ_WRITE_TOKEN.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/backend"))

from referral_review.documents.storage import PrivateBlobStore, check_key, object_key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("roundtrip", "cleanup"))
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        token = os.environ.get("BLOB_READ_WRITE_TOKEN", "")
        store = PrivateBlobStore(token)
        match = re.fullmatch(r"vercel_blob_rw_([A-Za-z0-9]+)_[A-Za-z0-9_-]+", token)
        store_hash = hashlib.sha256(match[1].lower().encode()).hexdigest()
        if args.action == "cleanup":
            record = json.loads(args.receipt.read_text())
            check_key(record["key"])
            if record["store_hash"] != store_hash:
                raise ValueError()
            store.delete(record["key"])
            print("Synthetic object deletion confirmed; receipt retained.")
            return
        key = object_key(uuid4())
        with os.fdopen(os.open(args.receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as output:
            json.dump({"key": key, "store_hash": store_hash}, output)
            output.flush()
            os.fsync(output.fileno())
        body = b"MediTrace synthetic private-storage verification. No patient data.\n"
        try:
            store.write(key, body, "text/plain")
            if store.read(key) != body:
                raise ValueError()
            # This separate client carries no Authorization, cookies or SDK session.
            import httpx2
            with httpx2.Client(timeout=15, follow_redirects=False) as client:
                response = client.get(f"https://{match[1].lower()}.private.blob.vercel-storage.com/{key}")
            if response.status_code not in (401, 403, 404):
                raise ValueError()
        finally:
            store.delete(key)
        print("PASS: private upload, authenticated byte match, unauthenticated denial, deletion confirmed.")
        print("Receipt retained for repeatable cleanup. No application/OAuth acceptance implied.")
    except Exception:
        parser.exit(1, "Private Blob verification failed. No secrets displayed; use the receipt with cleanup after recovery.\n")


if __name__ == "__main__":
    main()
