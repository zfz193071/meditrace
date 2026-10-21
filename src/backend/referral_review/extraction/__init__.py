"""Extraction public interface; no endpoint or implicit provider dispatch."""
from .adapters import DeepSeekAdapter, ExtractionError, FakeAdapter
from .contracts import Extraction, ExtractionRevision
from .service import extract

__all__ = ["DeepSeekAdapter", "ExtractionError", "FakeAdapter", "Extraction", "ExtractionRevision", "extract"]
