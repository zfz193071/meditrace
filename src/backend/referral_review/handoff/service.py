"""Authorize before rendering and again before delivery; no saved export objects."""
from ..errors import ApiError
from ..schemas import ErrorCode
from ..reviews import Reviews
from ..usage import Usage
from . import model, pdf


class Handoff:
    def __init__(self, identity):
        self.reviews, self.usage = Reviews(identity), Usage(identity)

    def get(self, token, packet_id, snapshot_id):
        return model.build(self.reviews.snapshot(token, packet_id, snapshot_id))

    def export(self, token, packet_id, snapshot_id, format):
        if format not in {"pdf", "txt"}:
            raise ApiError(ErrorCode.SCHEMA_INVALID)
        # Check snapshot ownership before charging the shared export attempt counter.
        view = self.get(token, packet_id, snapshot_id)
        self.usage.check_export(token, packet_id)
        data = pdf.render(view) if format == "pdf" else pdf.bounded(model.text(view).encode("utf-8"))
        current = self.reviews.snapshot(token, packet_id, snapshot_id)
        if current.historical != view.historical:
            raise ApiError(ErrorCode.REVIEW_CONFLICT)
        return data
