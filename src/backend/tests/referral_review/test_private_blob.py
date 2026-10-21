"""Run the installed official SDK against an HTTP transport, not a fake SDK."""

from uuid import uuid4

import httpx2
import pytest

from referral_review.documents.storage import MAX_BYTES, PrivateBlobStore, StorageUnavailable, object_key

TOKEN = "vercel_blob_rw_syntheticstore_syntheticsecret"


def test_installed_sdk_private_write_read_delete_contract():
    key = object_key(uuid4())
    calls = []
    body = b"Synthetic document"
    url = f"https://syntheticstore.private.blob.vercel-storage.com/{key}"

    def transport(request):
        calls.append(request)
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        if request.method == "PUT":
            assert request.url.host == "vercel.com"
            assert request.headers["x-vercel-blob-access"] == "private"
            assert request.headers["x-allow-overwrite"] == "0"
            assert request.headers["x-add-random-suffix"] == "0"
            assert request.content == body
            return httpx2.Response(200, json={"url": url, "downloadUrl": url + "?download=1", "pathname": key,
                "contentType": "text/plain", "contentDisposition": "attachment", "etag": '"synthetic"'})
        if request.method == "GET":
            assert str(request.url) == url
            return httpx2.Response(200, content=body, headers={"Content-Length": str(len(body))})
        assert request.method == "POST" and request.url.path.endswith("/delete")
        return httpx2.Response(200, json={})

    store = PrivateBlobStore(TOKEN, http_client_factory=lambda: httpx2.Client(transport=httpx2.MockTransport(transport)))
    store.write(key, body, "text/plain")
    assert store.read(key) == body
    store.delete(key)
    assert [r.method for r in calls] == ["PUT", "GET", "POST"]


@pytest.mark.parametrize("status", [301, 403, 429, 500])
def test_provider_failure_is_sanitized_without_retries_or_redirects(status):
    calls = []
    def transport(request):
        calls.append(request)
        return httpx2.Response(status, text="secret-provider-body", headers={"Location": "https://evil.invalid"})
    store = PrivateBlobStore(TOKEN, http_client_factory=lambda: httpx2.Client(transport=httpx2.MockTransport(transport)))
    with pytest.raises(StorageUnavailable) as exc:
        store.read(object_key(uuid4()))
    assert "secret-provider-body" not in str(exc.value)
    assert len(calls) == 1


def test_sdk_download_and_object_key_are_bounded():
    calls = []
    def transport(request):
        calls.append(request)
        return httpx2.Response(200, content=b"x" * (MAX_BYTES + 1))
    store = PrivateBlobStore(TOKEN, http_client_factory=lambda: httpx2.Client(transport=httpx2.MockTransport(transport)))
    with pytest.raises(StorageUnavailable):
        store.read("https://attacker.invalid/document")
    assert not calls
    with pytest.raises(StorageUnavailable):
        store.read(object_key(uuid4()))
    assert len(calls) == 1
