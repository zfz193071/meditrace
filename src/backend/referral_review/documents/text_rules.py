"""Frozen text-v1 rules and Unicode code point evidence anchors."""

from dataclasses import dataclass
import hashlib
import unicodedata


class EvidenceInvalid(ValueError):
    pass


def normalize_text(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Anchor:
    start_cp: int
    end_cp: int
    quote: str
    text_hash: str


def locate_quote(page_text: str, quote: str, *, before: str = "", after: str = "") -> Anchor:
    """Only a unique exact match within a named page is evidence.

    Optional exact adjacent context disambiguates repeated quotes. A caller must
    already have checked document/revision ownership and parse_quality=ready.
    """
    if page_text != normalize_text(page_text):
        raise EvidenceInvalid("Source page does not match text-v1")
    quote, before, after = map(normalize_text, (quote, before, after))
    if not quote or not quote.strip():
        raise EvidenceInvalid("Quote is empty")
    matches = []
    start = 0
    while (index := page_text.find(quote, start)) != -1:
        end = index + len(quote)
        if (page_text[max(0, index - len(before)):index].endswith(before)
            and page_text[end:end + len(after)].startswith(after)):
            matches.append(index)
            if len(matches) > 1:
                raise EvidenceInvalid("Quote is ambiguous")
        start = index + 1
    if not matches:
        raise EvidenceInvalid("Quote does not occur in this page and context")
    index = matches[0]
    return Anchor(index, index + len(quote), quote, text_hash(page_text))


def verify_anchor(page_text: str, anchor: Anchor) -> None:
    if (page_text != normalize_text(page_text) or anchor.start_cp < 0
        or anchor.end_cp <= anchor.start_cp or anchor.end_cp > len(page_text)
        or page_text[anchor.start_cp:anchor.end_cp] != anchor.quote
        or text_hash(page_text) != anchor.text_hash):
        raise EvidenceInvalid("Evidence span or page hash does not match")
