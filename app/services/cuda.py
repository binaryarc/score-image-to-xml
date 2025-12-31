import glob
import logging
import os
import site

logger = logging.getLogger(__name__)


def configure_cuda_env() -> None:
    """CUDA 라이브러리 경로 설정 (GPU 최적화)."""
    cuda_paths = [
        "/usr/local/cuda/lib64",
        "/usr/local/cuda-12/lib64",
        "/usr/local/cuda-12.2/lib64",
        "/usr/local/cuda-11/lib64",
        "/usr/lib/x86_64-linux-gnu",
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
    logger.info("✅ LD_LIBRARY_PATH configured with %d paths", len(parts))

    required_libs = ["libcublasLt.so.12", "libcudnn.so.9"]
    found_libs = []
    for lib in required_libs:
        for path in all_paths:
            lib_path = os.path.join(path, lib)
            if os.path.exists(lib_path):
                found_libs.append(lib)
                break

    if found_libs:
        logger.info("🚀 GPU mode enabled - Found libraries: %s", ", ".join(found_libs))
    else:
        logger.warning("⚠️ Required CUDA libraries not found - will fallback to CPU")


def ensure_checkpoints() -> None:
    """체크포인트 파일 다운로드 및 확인."""
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
            logger.info("📥 Downloading %s...", title)
            ete.download_file(title, url, save_path)
    logger.info("✅ Checkpoints ready")
