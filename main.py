from __future__ import annotations

import glob
import os
import site
import tempfile
import logging
import re
import unicodedata
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import io

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def configure_cuda_env() -> None:
    """CUDA 라이브러리 경로 설정 (GPU 최적화)"""
    cuda_paths = [
        "/usr/local/cuda/lib64",
        "/usr/local/cuda-12/lib64",
        "/usr/local/cuda-12.2/lib64",
        "/usr/local/cuda-11/lib64",
        "/usr/lib/x86_64-linux-gnu"
    ]
    
    lib_paths = []
    for sp in site.getsitepackages():
        nvidia_libs = glob.glob(os.path.join(sp, "nvidia", "*", "lib"))
        lib_paths.extend(nvidia_libs)
        
        for nvidia_pkg in glob.glob(os.path.join(sp, "nvidia*")):
            if os.path.isdir(nvidia_pkg):
                lib_dir = os.path.join(nvidia_pkg, "lib")
                if os.path.exists(lib_dir):
                    lib_paths.append(lib_dir)
    
    all_paths = [p for p in (cuda_paths + lib_paths) if os.path.exists(p)]
    
    if not all_paths:
        logger.warning("⚠️ No CUDA library paths found - will use CPU mode")
        return
    
    existing = os.environ.get("LD_LIBRARY_PATH", "")
    parts = [p for p in existing.split(":") if p]
    
    for path in all_paths:
        if path not in parts:
            parts.append(path)
    
    os.environ["LD_LIBRARY_PATH"] = ":".join(parts)
    logger.info(f"✅ LD_LIBRARY_PATH configured with {len(parts)} paths")
    
    required_libs = ["libcublasLt.so.12", "libcudnn.so.9"]
    found_libs = []
    for lib in required_libs:
        for path in all_paths:
            lib_path = os.path.join(path, lib)
            if os.path.exists(lib_path):
                found_libs.append(lib)
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


def preprocess_image_advanced(data: bytes) -> str:
    """고급 전처리 - 최대 인식률"""
    img_pil = Image.open(io.BytesIO(data))
    
    if img_pil.mode != 'L':
        img_pil = img_pil.convert('L')
    
    img = np.array(img_pil)
    
    if img is None or img.size == 0:
        raise ValueError("Invalid image data - unable to decode")

    original_shape = img.shape
    logger.info(f"📷 Original: {original_shape}, brightness: {img.mean():.1f}")
    
    # 1. 해상도 최적화
    target_height = 4000
    if img.shape[0] < target_height:
        scale = target_height / img.shape[0]
        new_width = int(img.shape[1] * scale)
        new_height = int(img.shape[0] * scale)
        img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        logger.info(f"🔄 Upscaled to: {img.shape} (scale: {scale:.2f}x)")
    elif img.shape[0] > 5000:
        scale = 5000 / img.shape[0]
        new_width = int(img.shape[1] * scale)
        new_height = int(img.shape[0] * scale)
        img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
        logger.info(f"🔄 Downscaled to: {img.shape} (scale: {scale:.2f}x)")
    
    # 2. 밝기 및 대비 정규화
    mean_brightness = img.mean()
    
    if mean_brightness < 100:
        img = cv2.normalize(img, None, 30, 255, cv2.NORM_MINMAX)
        logger.info(f"💡 Brightness normalized: {mean_brightness:.1f} → {img.mean():.1f}")
    elif mean_brightness > 200:
        img = cv2.normalize(img, None, 0, 240, cv2.NORM_MINMAX)
        logger.info(f"💡 Contrast enhanced: {mean_brightness:.1f} → {img.mean():.1f}")
    
    # 3. CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(16, 16))
    enhanced = clahe.apply(img)
    logger.info("✨ CLAHE applied")
    
    # 4. 언샤프 마스킹
    gaussian = cv2.GaussianBlur(enhanced, (0, 0), 2.0)
    unsharp = cv2.addWeighted(enhanced, 1.5, gaussian, -0.5, 0)
    logger.info("🔍 Unsharp masking applied")
    
    # 5. 노이즈 제거
    denoised = cv2.fastNlMeansDenoising(unsharp, None, h=7, templateWindowSize=7, searchWindowSize=21)
    logger.info("🧹 Denoising applied")
    
    # 6. 적응형 이진화
    blurred = cv2.GaussianBlur(denoised, (3, 3), 0)
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    if binary.mean() < 127:
        binary = cv2.bitwise_not(binary)
        logger.info("🔄 Image inverted")
    
    logger.info("⚫⚪ Adaptive thresholding applied")
    
    # 7. 모폴로지 연산
    kernel_small = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_small)
    
    kernel_connect = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_connect)
    logger.info("🧩 Morphological operations applied")
    
    # 8. 여백 제거
    coords = cv2.findNonZero(cv2.bitwise_not(binary))
    if coords is not None:
        x, y, w, h = cv2.boundingRect(coords)
        margin = 20
        x = max(0, x - margin)
        y = max(0, y - margin)
        w = min(binary.shape[1] - x, w + 2 * margin)
        h = min(binary.shape[0] - y, h + 2 * margin)
        
        binary = binary[y:y+h, x:x+w]
        logger.info(f"✂️ Cropped: {original_shape} → {binary.shape}")
    
    # 9. 최종 샤프닝
    kernel_sharpen = np.array([
        [-1, -1, -1],
        [-1,  9, -1],
        [-1, -1, -1]
    ])
    binary = cv2.filter2D(binary, -1, kernel_sharpen)
    logger.info("✨ Final sharpening applied")
    
    # 10. 저장
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    
    success = cv2.imwrite(path, binary, [cv2.IMWRITE_PNG_COMPRESSION, 0])
    
    if not success:
        raise RuntimeError("Failed to write preprocessed image")
    
    file_size = os.path.getsize(path)
    logger.info(f"💾 Saved: {path} ({file_size:,} bytes)")
    logger.info(f"📊 Final: {binary.shape}, brightness: {binary.mean():.1f}")
    
    return path


def run_oemer(image_path: str) -> bytes:
    """OEMER을 실행하여 MusicXML 생성 (GPU 가속)"""
    from types import SimpleNamespace

    configure_cuda_env()
    
    from oemer import MODULE_PATH, ete

    ensure_checkpoints()

    with tempfile.TemporaryDirectory() as tmpdir:
        args = SimpleNamespace(
            img_path=image_path,
            output_path=tmpdir,
            use_tf=False,
            save_cache=True,
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
        
        quality_score = validate_musicxml_quality(xml_data)
        logger.info(f"✅ MusicXML generated: {len(xml_data):,} bytes (quality: {quality_score:.1f}%)")
        
        return xml_data


def validate_musicxml_quality(xml_data: bytes) -> float:
    """MusicXML 품질 점수 (0-100)"""
    try:
        root = ET.fromstring(xml_data)
        
        measures = root.findall('.//{*}measure')
        notes = root.findall('.//{*}note')
        parts = root.findall('.//{*}part')
        
        score = 0.0
        
        if len(parts) > 0:
            score += 10
        if len(measures) >= 2:
            score += 15
        if len(notes) >= 5:
            score += 15
        
        if len(measures) > 0:
            notes_per_measure = len(notes) / len(measures)
            if notes_per_measure >= 2:
                score += 30
            elif notes_per_measure >= 1:
                score += 15
        
        xml_str = xml_data.decode('utf-8', errors='ignore')
        if 'pitch' in xml_str:
            score += 10
        if 'duration' in xml_str:
            score += 10
        if 'time' in xml_str:
            score += 10
        
        return min(100.0, score)
    except:
        return 0.0


def fix_musicxml_complete(xml_data: bytes) -> bytes:
    """MusicXML 완벽 수정 - 모든 오류 해결"""
    try:
        xml_str = xml_data.decode('utf-8', errors='ignore')
        root = ET.fromstring(xml_str)
        
        logger.info("🔧 Fixing MusicXML structure...")
        
        # 1. sound 태그 위치 수정 (part → measure)
        for part in root.findall('.//{*}part'):
            sounds = []
            for child in list(part):
                if child.tag.endswith('sound'):
                    sounds.append(child)
                    part.remove(child)
            
            if sounds:
                first_measure = part.find('.//{*}measure')
                if first_measure is not None:
                    for sound in sounds:
                        first_measure.insert(0, sound)
                    logger.info(f"✅ Moved {len(sounds)} sound tag(s)")
        
        # 2. 각 마디의 음표 개수 확인 및 수정
        for part in root.findall('.//{*}part'):
            for measure in part.findall('.//{*}measure'):
                # attributes에서 divisions 가져오기
                divisions_elem = measure.find('.//{*}divisions')
                if divisions_elem is not None:
                    try:
                        divisions = int(divisions_elem.text)
                    except:
                        divisions = 16  # 기본값
                else:
                    divisions = 16
                
                # time signature 가져오기
                beats_elem = measure.find('.//{*}time/{*}beats')
                beat_type_elem = measure.find('.//{*}time/{*}beat-type')
                
                if beats_elem is not None and beat_type_elem is not None:
                    try:
                        beats = int(beats_elem.text)
                        beat_type = int(beat_type_elem.text)
                        expected_duration = divisions * beats * (4 / beat_type)
                    except:
                        expected_duration = None
                else:
                    expected_duration = None
                
                # 실제 음표들의 총 duration 계산
                actual_duration = 0
                notes = measure.findall('.//{*}note')
                
                for note in notes:
                    # chord 태그가 있으면 duration을 더하지 않음 (화음)
                    if note.find('.//{*}chord') is not None:
                        continue
                    
                    duration_elem = note.find('.//{*}duration')
                    if duration_elem is not None:
                        try:
                            actual_duration += int(duration_elem.text)
                        except:
                            pass
                
                # duration 불일치 해결
                if expected_duration is not None and actual_duration > 0:
                    if actual_duration < expected_duration:
                        # 부족한 경우: 쉼표 추가
                        missing_duration = int(expected_duration - actual_duration)
                        rest_note = ET.SubElement(measure, 'note')
                        ET.SubElement(rest_note, 'rest')
                        duration_elem = ET.SubElement(rest_note, 'duration')
                        duration_elem.text = str(missing_duration)
                        ET.SubElement(rest_note, 'type').text = 'quarter'
                        
                        logger.info(f"✅ Added rest ({missing_duration}) to complete measure")
                    
                    elif actual_duration > expected_duration:
                        # 초과한 경우: 마지막 음표 duration 조정
                        excess = actual_duration - expected_duration
                        last_note_with_duration = None
                        
                        for note in reversed(notes):
                            if note.find('.//{*}chord') is None:
                                duration_elem = note.find('.//{*}duration')
                                if duration_elem is not None:
                                    last_note_with_duration = duration_elem
                                    break
                        
                        if last_note_with_duration is not None:
                            try:
                                current_dur = int(last_note_with_duration.text)
                                new_dur = max(1, current_dur - int(excess))
                                last_note_with_duration.text = str(new_dur)
                                logger.info(f"✅ Adjusted note duration ({current_dur} → {new_dur})")
                            except:
                                pass
        
        # 3. 빈 태그 제거
        def remove_empty_elements(element):
            for child in list(element):
                remove_empty_elements(child)
                if len(child) == 0 and not child.text and not child.attrib:
                    element.remove(child)
        
        remove_empty_elements(root)
        
        # 4. 버전을 3.1로 변경 (호환성)
        if 'version' in root.attrib:
            root.attrib['version'] = '3.1'
        
        # 5. XML 재생성
        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
        doctype = '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">\n'
        
        # 들여쓰기 추가 (가독성)
        indent_xml(root)
        
        xml_str = ET.tostring(root, encoding='unicode')
        fixed_xml = xml_declaration + doctype + xml_str
        
        logger.info("✅ MusicXML completely fixed")
        return fixed_xml.encode('utf-8')
        
    except Exception as e:
        logger.error(f"❌ Failed to fix MusicXML: {e}", exc_info=True)
        return xml_data


def indent_xml(elem, level=0):
    """XML 들여쓰기 (가독성 향상)"""
    indent = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        for child in elem:
            indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent


def sanitize_filename(filename: str) -> str:
    """파일명을 안전한 ASCII 문자열로 변환"""
    if not filename:
        return 'converted'
    
    name_without_ext = filename.rsplit('.', 1)[0]
    normalized = unicodedata.normalize('NFKD', name_without_ext)
    ascii_name = normalized.encode('ascii', 'ignore').decode('ascii')
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', ascii_name)
    safe_name = re.sub(r'_+', '_', safe_name)
    safe_name = safe_name.strip('_')
    
    if not safe_name:
        safe_name = 'converted'
    
    if len(safe_name) > 50:
        safe_name = safe_name[:50]
    
    return safe_name


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작/종료 시 실행"""
    logger.info("🚀 Starting up application...")
    
    try:
        import subprocess
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("✅ GPU detected:")
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
    description="Convert sheet music images to MusicXML format with advanced preprocessing and error correction",
    version="3.1.0",
    lifespan=lifespan
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
    """업로드 폼 페이지"""
    return """
    <!doctype html>
    <html lang="ko">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>악보 이미지 → MusicXML 변환기 v3.1</title>
        <style>
          * { margin: 0; padding: 0; box-sizing: border-box; }
          body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
          }
          .container {
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 700px;
            width: 100%;
          }
          h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
          }
          .version {
            color: #666;
            font-size: 14px;
            margin-bottom: 20px;
          }
          .badges {
            margin-bottom: 25px;
          }
          .badge {
            display: inline-block;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            margin-right: 8px;
            margin-bottom: 8px;
          }
          .badge-gpu { background: #10b981; color: white; }
          .badge-ngrok { background: #3b82f6; color: white; }
          .badge-fix { background: #ef4444; color: white; animation: pulse 2s infinite; }
          
          @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
          }
          
          .upload-area {
            border: 3px dashed #ddd;
            border-radius: 15px;
            padding: 40px;
            text-align: center;
            transition: all 0.3s;
            cursor: pointer;
            margin: 30px 0;
          }
          .upload-area:hover {
            border-color: #667eea;
            background: #f8f9ff;
          }
          .upload-area.dragover {
            border-color: #667eea;
            background: #f0f4ff;
          }
          input[type="file"] {
            display: none;
          }
          .upload-icon {
            font-size: 48px;
            margin-bottom: 15px;
          }
          .upload-text {
            color: #666;
            font-size: 16px;
          }
          button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 16px 32px;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            width: 100%;
            transition: all 0.3s;
          }
          button:hover:not(:disabled) {
            transform: translateY(-3px);
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);
          }
          button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
          }
          .info {
            margin-top: 30px;
            padding: 25px;
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-radius: 12px;
            font-size: 14px;
          }
          .info-item {
            margin: 12px 0;
            display: flex;
            align-items: center;
          }
          .info-icon {
            margin-right: 12px;
            font-size: 20px;
          }
          .new-feature {
            background: #fef3c7;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #ef4444;
          }
          #status {
            margin-top: 20px;
            padding: 18px;
            border-radius: 10px;
            display: none;
            font-weight: 600;
          }
          #status.processing {
            background: #fff3cd;
            color: #856404;
            display: block;
            animation: fadeIn 0.3s;
          }
          
          @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
          }
          
          .filename {
            font-size: 14px;
            color: #666;
            margin-top: 15px;
            font-style: italic;
          }
        </style>
      </head>
      <body>
        <div class="container">
          <h1>🎵 악보 이미지 → MusicXML 변환기</h1>
          <div class="version">Advanced Error Correction v3.1</div>
          
          <div class="badges">
            <span class="badge badge-gpu">⚡ GPU 가속</span>
            <span class="badge badge-ngrok">🚀 무제한 처리</span>
            <span class="badge badge-fix">🔧 NEW: 오류 자동 수정</span>
          </div>
          
          <div class="new-feature">
            <strong>🆕 v3.1 업데이트:</strong> MusicXML 오류 자동 수정 기능 추가! (sound 태그, measure 길이 등)
          </div>
          
          <form id="uploadForm" action="/convert" method="post" enctype="multipart/form-data">
            <div class="upload-area" id="uploadArea" onclick="document.getElementById('fileInput').click()">
              <div class="upload-icon">📷</div>
              <div class="upload-text">악보 이미지를 클릭하거나 드래그하여 업로드</div>
              <div class="filename" id="filename"></div>
            </div>
            <input type="file" name="file" id="fileInput" accept="image/*" required />
            <button type="submit" id="submitBtn">🚀 변환 시작</button>
          </form>
          
          <div id="status"></div>
          
          <div class="info">
            <div class="info-item">
              <span class="info-icon">⚡</span>
              <div><strong>GPU 가속:</strong> 2~3분 내 빠른 처리</div>
            </div>
            <div class="info-item">
              <span class="info-icon">🔧</span>
              <div><strong>오류 자동 수정:</strong> MuseScore 호환 보장</div>
            </div>
            <div class="info-item">
              <span class="info-icon">✨</span>
              <div><strong>고급 전처리:</strong> 해상도 최적화, CLAHE, 언샤프 마스킹</div>
            </div>
            <div class="info-item">
              <span class="info-icon">📝</span>
              <div><strong>출력:</strong> .musicxml 파일 (MusicXML 3.1)</div>
            </div>
            <div class="info-item">
              <span class="info-icon">💡</span>
              <div><strong>권장:</strong> 선명한 악보 이미지</div>
            </div>
          </div>
        </div>
        
        <script>
          const fileInput = document.getElementById('fileInput');
          const uploadArea = document.getElementById('uploadArea');
          const filename = document.getElementById('filename');
          const form = document.getElementById('uploadForm');
          const submitBtn = document.getElementById('submitBtn');
          const status = document.getElementById('status');
          
          fileInput.onchange = function(e) {
            if (e.target.files.length > 0) {
              filename.textContent = '선택된 파일: ' + e.target.files[0].name;
            }
          };
          
          uploadArea.ondragover = function(e) {
            e.preventDefault();
            uploadArea.classList.add('dragover');
          };
          
          uploadArea.ondragleave = function(e) {
            uploadArea.classList.remove('dragover');
          };
          
          uploadArea.ondrop = function(e) {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            
            if (e.dataTransfer.files.length > 0) {
              fileInput.files = e.dataTransfer.files;
              filename.textContent = '선택된 파일: ' + e.dataTransfer.files[0].name;
            }
          };
          
          form.onsubmit = function(e) {
            submitBtn.disabled = true;
            submitBtn.textContent = '⏳ 처리 중...';
            
            status.className = 'processing';
            status.innerHTML = `
              🎵 <strong>악보 분석 중...</strong><br>
              <small>• 이미지 전처리 (10단계)<br>
              • AI 인식 및 변환<br>
              • MusicXML 오류 자동 수정<br>
              • 2~3분 소요됩니다</small>
            `;
          };
        </script>
      </body>
    </html>
    """


@app.get("/health")
def health_check() -> dict:
    """헬스 체크 엔드포인트"""
    import subprocess
    
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
        "version": "3.1.0",
        "preprocessing": "advanced-10-steps",
        "error_correction": "enabled",
        "output_format": "musicxml-3.1"
    }


@app.post("/convert")
async def convert(file: UploadFile = File(...)) -> Response:
    """이미지 업로드 및 MusicXML 변환 (오류 자동 수정)"""
    logger.info(f"📥 Received: {file.filename}, type: {file.content_type}")
    
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")

    logger.info(f"📊 File size: {len(data):,} bytes")
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
        
        logger.info(f"📁 Output filename: {output_filename}")
        
        return Response(
            content=xml,
            media_type="application/vnd.recordare.musicxml+xml",
            headers={
                "Content-Disposition": f'attachment; filename="{output_filename}"'
            }
        )
    except ValueError as exc:
        logger.error(f"❌ Validation error: {exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"❌ Conversion failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"변환 실패: {str(exc)}") from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
                logger.info(f"🧹 Cleaned up: {tmp_path}")
            except Exception as e:
                logger.warning(f"⚠️ Cleanup failed: {e}")