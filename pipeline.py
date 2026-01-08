import io
import logging
import os
import site
import tempfile
from dataclasses import dataclass
from glob import glob
from importlib import import_module
import enum
import pkgutil
from typing import Iterable, Optional, Tuple

import cv2
import numpy as np
from PIL import Image
import xml.etree.ElementTree as ET


logger = logging.getLogger(__name__)
_KEY_ENUM_PATCHED = False


@dataclass
class SegmentResult:
    xml: bytes
    source_bounds: Optional[Tuple[int, int]] = None


def configure_cuda_env() -> None:
    """Configure CUDA library paths for OEMER."""
    cuda_paths = [
        "/usr/local/cuda/lib64",
        "/usr/local/cuda-12/lib64",
        "/usr/local/cuda-12.2/lib64",
        "/usr/local/cuda-11/lib64",
        "/usr/lib/x86_64-linux-gnu",
    ]

    lib_paths: list[str] = []
    for sp in site.getsitepackages():
        lib_paths.extend(glob(os.path.join(sp, "nvidia", "*", "lib")))
        for pkg in glob(os.path.join(sp, "nvidia*")):
            if os.path.isdir(pkg):
                lib_dir = os.path.join(pkg, "lib")
                if os.path.exists(lib_dir):
                    lib_paths.append(lib_dir)

    all_paths = [p for p in (cuda_paths + lib_paths) if os.path.exists(p)]
    if not all_paths:
        logger.warning("No CUDA library paths found - CPU mode only")
        return

    existing = os.environ.get("LD_LIBRARY_PATH", "")
    parts = [p for p in existing.split(":") if p]
    for path in all_paths:
        if path not in parts:
            parts.append(path)
    os.environ["LD_LIBRARY_PATH"] = ":".join(parts)


def ensure_checkpoints() -> None:
    """Ensure OEMER checkpoints are available."""
    from oemer import MODULE_PATH, ete

    chk_unet = os.path.join(MODULE_PATH, "checkpoints/unet_big/model.onnx")
    chk_seg = os.path.join(MODULE_PATH, "checkpoints/seg_net/model.onnx")
    if os.path.exists(chk_unet) and os.path.exists(chk_seg):
        return

    logger.info("Downloading OEMER checkpoints...")
    for title, url in ete.CHECKPOINTS_URL.items():
        save_dir = "unet_big" if title.startswith("1st") else "seg_net"
        save_dir = os.path.join(MODULE_PATH, "checkpoints", save_dir)
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, title.split("_")[1])
        if not os.path.exists(save_path):
            ete.download_file(title, url, save_path)


def _patch_oemer_key_enum() -> None:
    """Patch OEMER Key enum to clamp invalid values."""
    global _KEY_ENUM_PATCHED
    if _KEY_ENUM_PATCHED:
        return

    try:
        import oemer

        patched = 0
        for modinfo in pkgutil.walk_packages(oemer.__path__, oemer.__name__ + "."):
            try:
                module = import_module(modinfo.name)
            except Exception:
                continue

            for obj in module.__dict__.values():
                if isinstance(obj, enum.EnumMeta) and obj.__name__ == "Key":
                    def _missing_(cls, value):
                        try:
                            num = int(value)
                        except Exception:
                            return None
                        members = list(cls)
                        numeric = []
                        for member in members:
                            try:
                                numeric.append((member, int(member.value)))
                            except Exception:
                                pass
                        if not numeric:
                            return None
                        return min(numeric, key=lambda mv: abs(mv[1] - num))[0]

                    obj._missing_ = classmethod(_missing_)
                    patched += 1

        if patched:
            logger.warning("Patched %d OEMER Key enum(s)", patched)
    except Exception as exc:
        logger.warning("Failed to patch OEMER Key enum: %s", exc)
    finally:
        _KEY_ENUM_PATCHED = True


def preprocess_image(data: bytes) -> np.ndarray:
    """Preprocess image for staff detection and OEMER."""
    img = Image.open(io.BytesIO(data)).convert("L")
    arr = np.array(img)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(16, 16))
    enhanced = clahe.apply(arr)
    blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    if binary.mean() < 127:
        binary = cv2.bitwise_not(binary)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    return binary


def _group_consecutive(rows: Iterable[int]) -> list[tuple[int, int]]:
    rows = list(rows)
    if not rows:
        return []
    groups = []
    start = prev = rows[0]
    for r in rows[1:]:
        if r == prev + 1:
            prev = r
        else:
            groups.append((start, prev))
            start = prev = r
    groups.append((start, prev))
    return groups


def detect_staff_regions(binary: np.ndarray) -> list[tuple[int, int]]:
    """Detect staff regions as (top, bottom) bounds."""
    height, width = binary.shape
    ink = (binary == 0).astype(np.uint8)
    row_density = ink.mean(axis=1)

    if np.max(row_density) < 0.05:
        return []

    threshold = max(0.2, np.percentile(row_density, 90) * 0.7)
    line_rows = np.where(row_density >= threshold)[0]
    bands = _group_consecutive(line_rows)
    centers = [(start + end) // 2 for start, end in bands]

    if len(centers) < 5:
        return []

    diffs = np.diff(centers)
    spacing = int(np.median(diffs)) if len(diffs) else 0
    if spacing <= 0:
        return []

    staffs: list[list[int]] = []
    i = 0
    while i + 4 < len(centers):
        group = centers[i : i + 5]
        group_diffs = np.diff(group)
        if all(abs(d - spacing) <= spacing * 0.6 for d in group_diffs):
            staffs.append(group)
            i += 5
        else:
            i += 1

    regions: list[tuple[int, int]] = []
    margin = int(spacing * 3)
    for group in staffs:
        top = max(0, group[0] - margin)
        bottom = min(height, group[-1] + margin)
        if bottom - top > spacing * 4:
            regions.append((top, bottom))

    return regions


def split_into_staff_images(binary: np.ndarray) -> list[np.ndarray]:
    """Split into staff-line regions; fallback to full image."""
    regions = detect_staff_regions(binary)
    if not regions:
        return [binary]
    return [binary[top:bottom, :] for top, bottom in regions]


def _find_recovery(tmpdir_path: str) -> Optional[str]:
    candidates = []
    candidates.extend(glob(os.path.join(tmpdir_path, "*.xml")))
    candidates.extend(glob(os.path.join(tmpdir_path, "*.musicxml")))
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def run_oemer(image_path: str) -> bytes:
    """Run OEMER on a single image path."""
    from types import SimpleNamespace
    from oemer import ete

    ensure_checkpoints()
    _patch_oemer_key_enum()
    args = SimpleNamespace(
        img_path=image_path,
        output_path=os.path.dirname(image_path),
        use_tf=False,
        save_cache=True,
        without_deskew=False,
    )

    ete.clear_data()
    try:
        out_path = ete.extract(args)
    except (ValueError, KeyError) as exc:
        logger.warning("OEMER extraction error: %s", exc)
        recovered = _find_recovery(os.path.dirname(image_path))
        if recovered:
            out_path = recovered
            logger.warning("Recovering MusicXML from %s", out_path)
        elif isinstance(exc, KeyError) and not args.without_deskew:
            logger.warning("Retrying OEMER with deskew disabled after KeyError")
            retry_args = SimpleNamespace(**{**vars(args), "without_deskew": True})
            out_path = ete.extract(retry_args)
        else:
            raise

    if not os.path.exists(out_path):
        raise RuntimeError(f"Output file not created: {out_path}")

    with open(out_path, "rb") as handle:
        return handle.read()


def run_pipeline(data: bytes) -> list[SegmentResult]:
    """Full pipeline: preprocess, split, run OEMER per segment."""
    configure_cuda_env()
    binary = preprocess_image(data)
    segments = split_into_staff_images(binary)

    results: list[SegmentResult] = []
    for segment in segments:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = os.path.join(tmpdir, "segment.png")
            cv2.imwrite(tmp_path, segment, [cv2.IMWRITE_PNG_COMPRESSION, 0])
            xml = run_oemer(tmp_path)
            results.append(SegmentResult(xml=xml))
    return results


def _sanitize_key_fifths(root: ET.Element) -> None:
    for key in root.findall(".//{*}key"):
        for child in list(key):
            if not child.tag.endswith("fifths"):
                continue
            if not child.text:
                key.remove(child)
                continue
            try:
                value = int(child.text.strip())
            except Exception:
                key.remove(child)
                continue
            if value < -7 or value > 7:
                child.text = str(max(-7, min(7, value)))


def _indent_xml(elem: ET.Element, level: int = 0) -> None:
    indent = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        for child in elem:
            _indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent


def merge_musicxml(results: list[SegmentResult]) -> bytes:
    """Merge multiple MusicXML parts into a single document."""
    if not results:
        raise ValueError("No MusicXML segments produced")

    roots = [ET.fromstring(r.xml) for r in results]
    base = roots[0]
    base_part = base.find(".//{*}part")
    if base_part is None:
        raise ValueError("Base MusicXML has no part")

    measure_no = 1
    for measure in base_part.findall("./{*}measure"):
        measure.set("number", str(measure_no))
        measure_no += 1

    for root in roots[1:]:
        part = root.find(".//{*}part")
        if part is None:
            continue
        for measure in part.findall("./{*}measure"):
            measure.set("number", str(measure_no))
            measure_no += 1
            base_part.append(measure)

    _sanitize_key_fifths(base)
    _indent_xml(base)
    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_body = ET.tostring(base, encoding="unicode")
    return (xml_declaration + xml_body).encode("utf-8")
