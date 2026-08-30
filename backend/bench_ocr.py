"""Synthetic OCR quality bench — no real patient data.

Generates 8 document types, pushes each through the REAL pipeline
(API upload -> worker -> PaddleOCR -> normalized result) and prints
what the engine actually produced plus how it was classified.
"""
import io
import json
import random
import urllib.request

import pymupdf
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = "http://localhost:8000"
H = {"X-User-Role": "patient", "Content-Type": "application/json"}
ARIAL = "C:/Windows/Fonts/arial.ttf"
HAND = "C:/Windows/Fonts/Inkfree.ttf"


def font(path, size):
    return ImageFont.truetype(path, size)


def page_image(lines, fnt, size=(1000, 420), pad=40, gap=64, color=(20, 20, 20), bg=(255, 255, 255)):
    img = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        d.text((pad, pad + i * gap), line, font=fnt, fill=color)
    return img


def degrade(img):
    img = img.resize((img.width // 2, img.height // 2)).resize(img.size)  # pixelation
    img = img.filter(ImageFilter.GaussianBlur(1.6))
    px = img.load()
    rnd = random.Random(7)
    for _ in range(img.width * img.height // 12):  # noise
        x, y = rnd.randrange(img.width), rnd.randrange(img.height)
        v = rnd.randrange(256)
        px[x, y] = (v, v, v)
    return img


def to_png(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_pdf(page_lines, fnt_size=28):
    """Scanned-style PDF: text baked into page images, no text layer."""
    doc = pymupdf.open()
    for lines in page_lines:
        img = page_image(lines, font(ARIAL, fnt_size), size=(1200, 500))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        page = doc.new_page(width=img.width, height=img.height)
        page.insert_image(page.rect, stream=buf.getvalue())
    data = doc.tobytes()
    doc.close()
    return data


DOCS = [
    ("printed-rx.png", "image/png", to_png(page_image(
        ["Tab. Metformin 500 mg", "1-0-1 after food", "Review in 4 weeks"], font(ARIAL, 36)))),
    ("handwritten-rx.png", "image/png", to_png(page_image(
        ["Tab. Atorvastatin 20 mg", "0-0-1 at night"], font(HAND, 40)))),
    ("medicine-strip.png", "image/png", to_png(page_image(
        ["TELMISARTAN 40", "10 TABLETS", "MRP Rs. 85.00"], font(ARIAL, 44), size=(1000, 300), gap=70))),
    ("multiline-rx.png", "image/png", to_png(page_image(
        ["Dr. R. Menon MBBS MD", "Reg No: 12345", "Rx", "1. Amlodipine 5 mg OD",
         "2. Metformin 500 mg BD", "3. Vitamin D3 60k weekly", "Next visit: 4 weeks"],
        font(ARIAL, 30), size=(1100, 560), gap=62))),
    ("poor-quality.png", "image/png", to_png(degrade(page_image(
        ["Tab. Metformin 500 mg", "1-0-1 after food"], font(ARIAL, 34), color=(90, 90, 90), bg=(245, 243, 238))))),
    ("rotated.png", "image/png", to_png(page_image(
        ["Tab. Metformin 500 mg", "1-0-1 after food"], font(ARIAL, 36)).rotate(90, expand=True))),
    ("noise.png", "image/png", to_png(Image.effect_noise((900, 400), 60).convert("RGB"))),
    ("scanned-3page.pdf", "application/pdf", make_pdf([
        ["DISCHARGE SUMMARY", "Patient stable at discharge"],
        ["MEDICATIONS", "Metformin 500 mg twice daily"],
        ["FOLLOW UP", "Renal panel in 4 weeks"]])) ,
]


def req(method, path, data=None, raw=None):
    body = json.dumps(data).encode() if data is not None else raw
    r = urllib.request.Request(BASE + path, data=body, method=method, headers=H)
    with urllib.request.urlopen(r) as resp:
        payload = resp.read()
        return json.loads(payload) if payload else None


def main():
    pid = req("POST", "/v1/patients", {"full_name": "Bench Synthetic", "date_of_birth": "1980-01-01", "sex": "female"})["id"]
    jobs = []
    for name, ctype, data in DOCS:
        up = req("POST", f"/v1/patients/{pid}/records/upload", {"filename": name, "content_type": ctype})
        req("PUT", up["upload_url"].replace(BASE, ""), raw=data)
        job = req("POST", f"/v1/records/{up['record_id']}/complete")
        jobs.append((name, up["record_id"], job["id"]))

    from ocr_worker.run import Worker  # one worker, engine warmed up once
    worker = Worker()
    for _ in jobs:
        worker.process_next()

    print("\n===== BENCH RESULTS =====")
    for name, rid, jid in jobs:
        rec = req("GET", f"/v1/patients/{pid}/records")
        rec = next(r for r in rec if r["id"] == rid)
        print(f"\n--- {name} -> status={rec['status']}")
        if rec["status"] == "failed":
            print(f"    error_code={rec['latest_job']['error_code']}  attempts={rec['latest_job']['attempt_count']}")
            continue
        ocr = req("GET", f"/v1/records/{rid}/ocr", )
        m = ocr["result_json"]["metrics"]
        print(f"    engine={ocr['engine']} pages={ocr['page_count']} mean_conf={ocr['mean_confidence']} low_conf_lines={m['low_confidence_lines']} failed_pages={m['failed_pages']}")
        for p in ocr["result_json"]["pages"]:
            for l in p["lines"]:
                flag = "REVIEW" if l["needs_review"] else "ok"
                conf = f"{l['confidence']:.2f}" if l["confidence"] is not None else " n/a"
                print(f"    p{p['page_number']} [{flag}] conf={conf}  {l['text']!r}")


if __name__ == "__main__":
    main()
