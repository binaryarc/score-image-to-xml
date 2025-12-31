import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response

from .logging_config import configure_logging
from .services.cuda import configure_cuda_env, ensure_checkpoints
from .services.oemer import run_oemer
from .services.preprocess import preprocess_image_advanced
from .services.musicxml import fix_musicxml_complete
from .ui import upload_form_html
from .utils.filename import sanitize_filename

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작/종료 시 실행."""
    logger.info("🚀 Starting up application...")

    try:
        import subprocess

        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("✅ GPU detected:")
            lines = result.stdout.split("\n")
            for line in lines:
                if "Tesla" in line or "T4" in line or "GPU" in line:
                    logger.info("   %s", line.strip())
        else:
            logger.warning("⚠️ GPU not detected - will use CPU mode")
    except Exception as exc:
        logger.warning("⚠️ Could not check GPU: %s", exc)

    try:
        configure_cuda_env()
        ensure_checkpoints()
        logger.info("✅ Application startup complete")
    except Exception as exc:
        logger.error("❌ Startup failed: %s", exc)
        raise

    yield

    logger.info("👋 Shutting down application...")


app = FastAPI(
    title="Sheet Image to MusicXML Converter",
    description="Convert sheet music images to MusicXML format with advanced preprocessing and error correction",
    version="3.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
def upload_form() -> str:
    """업로드 폼 페이지."""
    return upload_form_html()


@app.get("/health")
def health_check() -> dict:
    """헬스 체크 엔드포인트."""
    import subprocess

    gpu_available = False
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=2)
        gpu_available = result.returncode == 0
    except Exception:
        pass

    return {
        "status": "healthy",
        "service": "musicxml-converter",
        "gpu_enabled": gpu_available,
        "version": "3.1.0",
        "preprocessing": "advanced-10-steps",
        "error_correction": "enabled",
        "output_format": "musicxml-3.1",
    }


@app.post("/convert")
async def convert(file: UploadFile = File(...)) -> Response:
    """이미지 업로드 및 MusicXML 변환 (오류 자동 수정)."""
    logger.info("📥 Received: %s, type: %s", file.filename, file.content_type)

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")

    logger.info("📊 File size: %d bytes", len(data))
    logger.info("⏳ 변환 시작 - 고급 전처리 + 오류 수정 활성화")

    tmp_path = None
    try:
        logger.info("📝 [1/4] 고급 이미지 전처리 (10단계)...")
        tmp_path = preprocess_image_advanced(data)

        logger.info("🎵 [2/4] AI 악보 인식 (GPU 가속)...")
        xml = run_oemer(tmp_path)

        logger.info("🔧 [3/4] MusicXML 오류 자동 수정...")
        xml = fix_musicxml_complete(xml)

        logger.info("✅ [4/4] 변환 완료!")

        safe_name = sanitize_filename(file.filename)
        output_filename = f"{safe_name}.musicxml"

        logger.info("📁 Output filename: %s", output_filename)

        return Response(
            content=xml,
            media_type="application/vnd.recordare.musicxml+xml",
            headers={"Content-Disposition": f'attachment; filename="{output_filename}"'},
        )
    except ValueError as exc:
        logger.error("❌ Validation error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("❌ Conversion failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"변환 실패: {str(exc)}") from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
                logger.info("🧹 Cleaned up: %s", tmp_path)
            except Exception as exc:
                logger.warning("⚠️ Cleanup failed: %s", exc)
