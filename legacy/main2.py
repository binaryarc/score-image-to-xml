from __future__ import annotations

import glob
import os
import site
import tempfile
import logging
from contextlib import asynccontextmanager

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def configure_cuda_env() -> None:
    """CUDA 라이브러리 경로 설정 (GPU 최적화)"""
    # Colab/Linux 시스템의 기본 CUDA 경로
    cuda_paths = [
        "/usr/local/cuda/lib64",
        "/usr/local/cuda-12/lib64",
        "/usr/local/cuda-12.2/lib64",
        "/usr/local/cuda-11/lib64",
        "/usr/lib/x86_64-linux-gnu"
    ]
    
    # pip로 설치된 nvidia 패키지 경로
    lib_paths = []
    for sp in site.getsitepackages():
        # nvidia-* 패키지들 찾기
        nvidia_libs = glob.glob(os.path.join(sp, "nvidia", "*", "lib"))
        lib_paths.extend(nvidia_libs)
        
        # nvidia-cublas, nvidia-cudnn 등
        for nvidia_pkg in glob.glob(os.path.join(sp, "nvidia*")):
            if os.path.isdir(nvidia_pkg):
                lib_dir = os.path.join(nvidia_pkg, "lib")
                if os.path.exists(lib_dir):
                    lib_paths.append(lib_dir)
    
    # 존재하는 경로만 필터링
    all_paths = [p for p in (cuda_paths + lib_paths) if os.path.exists(p)]
    
    if not all_paths:
        logger.warning("⚠️ No CUDA library paths found - will use CPU mode")
        return
    
    # LD_LIBRARY_PATH 설정
    existing = os.environ.get("LD_LIBRARY_PATH", "")
    parts = [p for p in existing.split(":") if p]
    
    for path in all_paths:
        if path not in parts:
            parts.append(path)
    
    os.environ["LD_LIBRARY_PATH"] = ":".join(parts)
    logger.info(f"✅ LD_LIBRARY_PATH configured with {len(parts)} paths")
    
    # 실제로 필요한 라이브러리가 있는지 확인
    required_libs = ["libcublasLt.so.12", "libcudnn.so.9"]
    found_libs = []
    for lib in required_libs:
        for path in all_paths:
            lib_path = os.path.join(path, lib)
            if os.path.exists(lib_path):
                found_libs.append(lib)
                logger.info(f"✅ Found: {lib_path}")
                break
    
    if found_libs:
        logger.info(f"🚀 GPU mode enabled - Found libraries: {', '.join(found_libs)}")
    else:
        logger.warning("⚠️ Required CUDA libraries not found - will fallback to CPU")


def ensure_checkpoints() -> None:
    """체크포인트 파일 다운로드 및 확인"""
    from oemer import MODULE_PATH, ete

    chk_unet = os.path.join(MODULE_PATH, "checkpoints/unet_big/model.onnx")
    chk_seg = os.path.join(MODULE_PATH, "checkpoints/seg_net/model.onnx")
    
    if os.path.exists(chk_unet) and os.path.exists(chk_seg):
        logger.info("✅ Checkpoints already exist")
        return

    logger.info("📥 Downloading checkpoints...")
    for title, url in ete.CHECKPOINTS_URL.items():
        save_dir = "unet_big" if title.startswith("1st") else "seg_net"
        save_dir = os.path.join(MODULE_PATH, "checkpoints", save_dir)
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, title.split("_")[1])
        if not os.path.exists(save_path):
            logger.info(f"📥 Downloading {title}...")
            ete.download_file(title, url, save_path)
    logger.info("✅ Checkpoints ready")


def preprocess_image(data: bytes) -> str:
    """이미지 전처리 및 임시 파일 저장 (최적화 버전)"""
    img_arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(img_arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("Invalid image data - unable to decode")

    logger.info(f"📷 Image loaded: shape={img.shape}")
    
    # 이미지가 너무 크면 리사이즈 (처리 속도 향상)
    max_dimension = 2500  # 최대 가로/세로 크기
    height, width = img.shape
    
    if height > max_dimension or width > max_dimension:
        scale = max_dimension / max(height, width)
        new_width = int(width * scale)
        new_height = int(height * scale)
        img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
        logger.info(f"🔄 Image resized to: {img.shape} (scale: {scale:.2f})")
    
    # 노이즈 제거 (GPU에서는 빠르므로 적절한 값 사용)
    denoised = cv2.fastNlMeansDenoising(img, None, 15, 7, 21)
    
    # 이진화
    _, binary = cv2.threshold(
        denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    # 임시 파일 저장
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    if not cv2.imwrite(path, binary):
        raise RuntimeError("Failed to write preprocessed image")
    
    logger.info(f"💾 Preprocessed image saved to {path}")
    return path


def run_oemer(image_path: str) -> bytes:
    """OEMER을 실행하여 MusicXML 생성 (GPU 가속)"""
    from types import SimpleNamespace

    # CUDA 환경 설정
    configure_cuda_env()
    
    from oemer import MODULE_PATH, ete

    ensure_checkpoints()

    with tempfile.TemporaryDirectory() as tmpdir:
        args = SimpleNamespace(
            img_path=image_path,
            output_path=tmpdir,
            use_tf=False,  # TensorFlow 사용 안 함
            save_cache=False,
            without_deskew=False,
        )
        logger.info(f"🎵 Running OEMER on {image_path}")
        logger.info("⚡ GPU acceleration enabled")
        
        ete.clear_data()
        
        try:
            out_path = ete.extract(args)
        except Exception as e:
            logger.error(f"❌ OEMER extraction failed: {e}", exc_info=True)
            raise
        
        if not os.path.exists(out_path):
            raise RuntimeError(f"Output file not created: {out_path}")
        
        with open(out_path, "rb") as handle:
            xml_data = handle.read()
        
        logger.info(f"✅ MusicXML generated: {len(xml_data):,} bytes")
        return xml_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작/종료 시 실행"""
    logger.info("🚀 Starting up application...")
    
    # GPU 확인
    try:
        import subprocess
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("✅ GPU detected:")
            # GPU 정보 파싱
            lines = result.stdout.split('\n')
            for line in lines:
                if 'Tesla' in line or 'T4' in line or 'GPU' in line:
                    logger.info(f"   {line.strip()}")
        else:
            logger.warning("⚠️ GPU not detected - will use CPU mode")
    except Exception as e:
        logger.warning(f"⚠️ Could not check GPU: {e}")
    
    try:
        configure_cuda_env()
        ensure_checkpoints()
        logger.info("✅ Application startup complete")
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise
    
    yield
    
    logger.info("👋 Shutting down application...")


app = FastAPI(
    title="Sheet Image to MusicXML Converter",
    description="Convert sheet music images to MusicXML format with GPU acceleration",
    version="2.0.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
def upload_form() -> str:
    """업로드 폼 페이지"""
    return """
    <!doctype html>
    <html lang="ko">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>악보 이미지 → MusicXML 변환기 (GPU 가속)</title>
        <style>
          body {
            font-family: 'Segoe UI', Arial, sans-serif;
            max-width: 700px;
            margin: 50px auto;
            padding: 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
          }
          .container {
            background: white;
            padding: 40px;
            border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
          }
          h1 {
            color: #333;
            margin-bottom: 10px;
          }
          .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
          }
          .badge {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            margin-bottom: 20px;
            margin-right: 10px;
          }
          .gpu-badge {
            background: #10b981;
            color: white;
          }
          .ngrok-badge {
            background: #3b82f6;
            color: white;
          }
          form { margin-top: 20px; }
          input[type="file"] {
            display: block;
            margin: 20px 0;
            padding: 15px;
            border: 2px dashed #ddd;
            border-radius: 8px;
            width: 100%;
            box-sizing: border-box;
            cursor: pointer;
            transition: all 0.3s;
          }
          input[type="file"]:hover {
            border-color: #667eea;
            background: #f8f9ff;
          }
          button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 30px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            width: 100%;
            transition: transform 0.2s;
          }
          button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
          }
          button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
          }
          .info {
            margin-top: 30px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
            font-size: 14px;
            line-height: 1.6;
          }
          .info-item {
            margin: 10px 0;
            display: flex;
            align-items: start;
          }
          .info-icon {
            margin-right: 10px;
            font-size: 18px;
          }
          #status {
            margin-top: 20px;
            padding: 15px;
            border-radius: 8px;
            display: none;
            font-weight: bold;
          }
          #status.processing {
            background: #fff3cd;
            color: #856404;
            display: block;
          }
        </style>
      </head>
      <body>
        <div class="container">
          <span class="badge gpu-badge">⚡ GPU 가속</span>
          <span class="badge ngrok-badge">🚀 ngrok (타임아웃 없음)</span>
          <h1>🎵 악보 이미지 → MusicXML 변환</h1>
          <p class="subtitle">악보 이미지를 업로드하면 MusicXML 형식으로 변환됩니다</p>
          
          <form id="uploadForm" action="/convert" method="post" enctype="multipart/form-data">
            <input type="file" name="file" id="fileInput" accept="image/*" required />
            <button type="submit" id="submitBtn">🚀 변환하기</button>
          </form>
          
          <div id="status"></div>
          
          <div class="info">
            <div class="info-item">
              <span class="info-icon">⚡</span>
              <div><strong>GPU 가속:</strong> 2~3분 내 빠른 처리</div>
            </div>
            <div class="info-item">
              <span class="info-icon">🚀</span>
              <div><strong>ngrok 터널:</strong> 타임아웃 걱정 없음</div>
            </div>
            <div class="info-item">
              <span class="info-icon">📝</span>
              <div><strong>지원 형식:</strong> JPG, PNG, GIF, WEBP</div>
            </div>
            <div class="info-item">
              <span class="info-icon">💡</span>
              <div><strong>권장:</strong> 선명한 악보 이미지, 2500px 이하</div>
            </div>
          </div>
        </div>
        
        <script>
          document.getElementById('uploadForm').onsubmit = function(e) {
            const btn = document.getElementById('submitBtn');
            const status = document.getElementById('status');
            
            btn.disabled = true;
            btn.textContent = '⏳ 변환 중...';
            
            status.className = 'processing';
            status.textContent = '🎵 악보 분석 중... 2~3분 소요됩니다. 잠시만 기다려주세요!';
          };
        </script>
      </body>
    </html>
    """


@app.get("/health")
def health_check() -> dict:
    """헬스 체크 엔드포인트"""
    import subprocess
    
    # GPU 상태 확인
    gpu_available = False
    try:
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True, timeout=2)
        gpu_available = result.returncode == 0
    except:
        pass
    
    return {
        "status": "healthy",
        "service": "musicxml-converter",
        "gpu_enabled": gpu_available,
        "version": "2.0.0",
        "tunnel": "ngrok"
    }


@app.post("/convert")
async def convert(file: UploadFile = File(...)) -> Response:
    """이미지 업로드 및 MusicXML 변환 (GPU 가속)"""
    logger.info(f"📥 Received file: {file.filename}, content_type: {file.content_type}")
    
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400, 
            detail="이미지 파일만 업로드 가능합니다."
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")

    logger.info(f"📊 File size: {len(data):,} bytes")
    logger.info("⏳ 처리 시작 - GPU 가속 활성화")
    
    tmp_path = None
    try:
        logger.info("📝 [1/3] 이미지 전처리 중...")
        tmp_path = preprocess_image(data)
        
        logger.info("🎵 [2/3] 악보 분석 중... (GPU 가속)")
        xml = run_oemer(tmp_path)
        
        logger.info("✅ [3/3] 변환 완료!")
        
        return Response(
            content=xml,
            media_type="application/vnd.recordare.musicxml+xml",
            headers={
                "Content-Disposition": f"attachment; filename={file.filename.rsplit('.', 1)[0]}.musicxml"
            }
        )
    except ValueError as exc:
        logger.error(f"❌ Validation error: {exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"❌ Conversion failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"변환 실패: {str(exc)}"
        ) from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
                logger.info(f"🧹 Cleaned up temporary file: {tmp_path}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to remove temp file: {e}")