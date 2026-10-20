#!/usr/bin/env python3
"""Render all non-corrupt source PDFs for offline visual QA, never launch a UI.

PDFium is a project-local fallback when system Poppler is unavailable. Output is
disposable; do not put these images into the public demo or the gold manifest.
"""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw
import pypdfium2 as pdfium

from referral_fixtures import FIXTURES, ROOT, write


def render(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    images = []
    for split in ["dev", "test"]:
        for packet_path in sorted((FIXTURES / split).glob("*/packet.json")):
            packet = json.loads(packet_path.read_text())
            for document in packet["documents"]:
                if document["kind"] != "pdf" or document["fixture_variant"] == "corrupt":
                    continue
                source = packet_path.parent / document["source_path"]
                password = "synthetic-only" if document["fixture_variant"] == "encrypted" else None
                with pdfium.PdfDocument(source, password=password) as pdf:
                    for number in range(len(pdf)):
                        page = pdf[number]
                        bitmap = page.render(scale=1.5)
                        image = bitmap.to_pil().convert("RGB")
                        name = f"{packet['key']}-{source.stem}-p{number + 1:02}.png"
                        image.save(output / name)
                        images.append(name)
                        bitmap.close()
                        page.close()
    for start in range(0, len(images), 12):
        names = images[start:start + 12]
        sheet = Image.new("RGB", (3 * 320, 4 * 438), "#e7edef")
        draw = ImageDraw.Draw(sheet)
        for i, name in enumerate(names):
            with Image.open(output / name) as image:
                image.thumbnail((306, 396))
                x, y = (i % 3) * 320 + 7, (i // 3) * 438 + 24
                sheet.paste(image, (x, y))
                draw.text((x, y - 16), name, fill="black")
        sheet.save(output / f"contact-{start // 12 + 1}.png")
    write(output / "index.json", (json.dumps({"renderer": str(pdfium.PYPDFIUM_INFO), "pages": images}, indent=2) + "\n").encode())
    print(f"Rendered {len(images)} pages to {output}. Inspect individual images and contact sheets.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=ROOT / ".scratch/referral-pdf-qa")
    render(parser.parse_args().output_root)
