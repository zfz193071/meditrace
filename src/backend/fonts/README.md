# Handoff PDF fonts

The renderer embeds subsets of these bundled fonts; no runtime font download occurs.

- `SourceHanSansCN-Regular.ttf`: existing repository font. Internal family name **Source Han Sans SC**, copyright © 2014-2025 Adobe, reserved name “Source”. SIL Open Font License 1.1; the full upstream license is included in `SourceHanSans-LICENSE.txt`. Upstream: https://github.com/adobe-fonts/source-han-sans/blob/master/LICENSE.txt
- `SourceSans3-Regular.ttf`: unmodified Adobe Source Sans 3 regular font, downloaded from https://raw.githubusercontent.com/adobe-fonts/source-sans/release/TTF/SourceSans3-Regular.ttf . SIL Open Font License 1.1; copyright and full license in `SourceSans3-LICENSE.md`.

OFL permits embedding and redistribution with the license. These files are not sold independently, renamed, or modified. PDFs embed only used glyphs through fpdf2. Latin (including extended names), Greek, Cyrillic and available CJK glyphs are covered. Unsupported glyphs or scripts requiring unavailable shaping cause an explicit PDF error; the complete UTF-8 text export remains available. No silent glyph removal or transliteration.

SHA-256 at MT-13 implementation:

- Source Sans 3: `4644c81b86ec9caaa76b634889968ed3c4f4f52f054855933acc7c2b21e53b0f`
- Source Han Sans SC: `f1d8611151880c6c336aabeac4640ef434fa13cbfbf1ffe82d0a71b2a5637256`
