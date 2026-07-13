"""Regenerates ``sample.pdf``: a minimal, hand-built 2-page PDF (page 1 has
extractable text, page 2 is intentionally blank) used to test the PDF parser
without depending on a PDF-writing library. Run with:
    python tests/fixtures/pdf/generate_sample_pdf.py
"""

from __future__ import annotations

from pathlib import Path


def make_pdf(pages_text: list[str]) -> bytes:
    objs: list[bytes] = []
    objs.append(b"<</Type/Catalog/Pages 2 0 R>>")
    kids = " ".join(f"{3 + i} 0 R" for i in range(len(pages_text)))
    objs.append(f"<</Type/Pages/Kids[{kids}]/Count {len(pages_text)}>>".encode())
    content_obj_start = 3 + len(pages_text)
    font_obj = 3 + 2 * len(pages_text)
    for _ in pages_text:
        objs.append(
            (
                f"<</Type/Page/Parent 2 0 R/Resources<</Font<</F1 {font_obj} 0 R>>>>"
                f"/MediaBox[0 0 200 200]/Contents {content_obj_start} 0 R>>"
            ).encode()
        )
        content_obj_start += 1
    for text in pages_text:
        stream = f"BT /F1 18 Tf 10 100 Td ({text}) Tj ET".encode() if text else b""
        objs.append(f"<</Length {len(stream)}>>stream\n".encode() + stream + b"\nendstream")
    objs.append(b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj".encode() + body + b"endobj\n"
    xref_offset = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer<</Size {len(objs) + 1}/Root 1 0 R>>\nstartxref\n{xref_offset}\n%%EOF".encode()
    return bytes(out)


if __name__ == "__main__":
    out_path = Path(__file__).parent / "sample.pdf"
    out_path.write_bytes(make_pdf(["Hello Kairos", ""]))
    print(f"wrote {out_path} ({out_path.stat().st_size} bytes)")
