import logging
import os
import tempfile
from glob import glob
from types import SimpleNamespace

from .cuda import configure_cuda_env, ensure_checkpoints
from .musicxml import validate_musicxml_quality

logger = logging.getLogger(__name__)


def run_oemer(image_path: str) -> bytes:
    """OEMER을 실행하여 MusicXML 생성 (GPU 가속)."""
    configure_cuda_env()

    from oemer import ete

    ensure_checkpoints()

    with tempfile.TemporaryDirectory() as tmpdir:
        args = SimpleNamespace(
            img_path=image_path,
            output_path=tmpdir,
            use_tf=False,
            save_cache=True,
            without_deskew=False,
        )
        logger.info("🎵 Running OEMER on %s", image_path)
        logger.info("⚡ GPU acceleration enabled")

        ete.clear_data()

        try:
            out_path = ete.extract(args)
        except ValueError as exc:
            # OEMER can raise ValueError for invalid key signatures; try to recover a partial XML.
            logger.warning("OEMER extraction ValueError: %s", exc)
            candidates = []
            candidates.extend(glob(os.path.join(tmpdir, "*.xml")))
            candidates.extend(glob(os.path.join(tmpdir, "*.musicxml")))
            if candidates:
                out_path = max(candidates, key=os.path.getmtime)
                logger.warning("Recovering MusicXML from %s", out_path)
            else:
                logger.error("OEMER extraction failed: %s", exc, exc_info=True)
                raise
        except Exception as exc:
            logger.error("??OEMER extraction failed: %s", exc, exc_info=True)
            raise

        if not os.path.exists(out_path):
            raise RuntimeError(f"Output file not created: {out_path}")

        with open(out_path, "rb") as handle:
            xml_data = handle.read()

        quality_score = validate_musicxml_quality(xml_data)
        logger.info("✅ MusicXML generated: %d bytes (quality: %.1f%%)", len(xml_data), quality_score)

        return xml_data
