import logging
import os
import re
import time
import unicodedata

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response

from pipeline import merge_musicxml, run_pipeline


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Score Image to MusicXML",
    description="Staff-line split + OEMER pipeline for higher accuracy",
    version="0.1.0",
)


def sanitize_filename(filename: str) -> str:
    if not filename:
        return "converted"
    name_without_ext = filename.rsplit(".", 1)[0]
    normalized = unicodedata.normalize("NFKD", name_without_ext)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", ascii_name)
    safe_name = re.sub(r"_+", "_", safe_name).strip("_")
    return safe_name or "converted"


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """
    <!doctype html>
    <html lang="ko">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>악보 이미지 → MusicXML</title>
      </head>
      <body>
        <h2>악보 이미지 → MusicXML 변환</h2>
        <form action="/convert" method="post" enctype="multipart/form-data">
          <input type="file" name="file" accept="image/*" required />
          <button type="submit">변환</button>
        </form>
      </body>
    </html>
    """


@app.post("/convert")
async def convert(file: UploadFile = File(...)) -> Response:
    logger.info("Received: %s (%s)", file.filename, file.content_type)

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")

    try:
        results = run_pipeline(data)
        merged = merge_musicxml(results)
    except Exception as exc:
        logger.error("Conversion failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"변환 실패: {exc}") from exc

    output_name = f"{sanitize_filename(file.filename)}.musicxml"
    output_dir = os.getenv("OUTPUT_DIR", "").strip()
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        saved_name = f"{sanitize_filename(file.filename)}_{timestamp}.musicxml"
        output_path = os.path.join(output_dir, saved_name)
        with open(output_path, "wb") as handle:
            handle.write(merged)
        logger.info("Saved output: %s", output_path)

    return Response(
        content=merged,
        media_type="application/vnd.recordare.musicxml+xml",
        headers={"Content-Disposition": f'attachment; filename="{output_name}"'},
    )


__all__ = ["app"]
