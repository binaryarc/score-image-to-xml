import logging
import os
import tempfile
from glob import glob
from types import SimpleNamespace
import enum
import pkgutil
from importlib import import_module

from .cuda import configure_cuda_env, ensure_checkpoints
from .musicxml import validate_musicxml_quality

logger = logging.getLogger(__name__)
_KEY_ENUM_PATCHED = False


def _patch_oemer_key_enum() -> None:
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
            logger.warning("Patched %d OEMER Key enum(s) to clamp invalid values", patched)
    except Exception as exc:
        logger.warning("Failed to patch OEMER Key enum: %s", exc)
    finally:
        _KEY_ENUM_PATCHED = True


def run_oemer(image_path: str) -> bytes:
    """OEMER을 실행하여 MusicXML 생성 (GPU 가속)."""
    configure_cuda_env()

    from oemer import ete

    ensure_checkpoints()

    def _find_recovery(tmpdir_path: str) -> str | None:
        candidates = []
        candidates.extend(glob(os.path.join(tmpdir_path, "*.xml")))
        candidates.extend(glob(os.path.join(tmpdir_path, "*.musicxml")))
        if not candidates:
            return None
        return max(candidates, key=os.path.getmtime)

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
        _patch_oemer_key_enum()

        try:
            out_path = ete.extract(args)
        except (ValueError, KeyError) as exc:
            # OEMER can raise ValueError for invalid key signatures or KeyError during build.
            logger.warning("OEMER extraction error: %s", exc)
            recovered = _find_recovery(tmpdir)
            if recovered:
                out_path = recovered
                logger.warning("Recovering MusicXML from %s", out_path)
            elif isinstance(exc, KeyError) and not args.without_deskew:
                logger.warning("Retrying OEMER with deskew disabled after KeyError")
                retry_args = SimpleNamespace(**{**vars(args), "without_deskew": True})
                out_path = ete.extract(retry_args)
            else:
                logger.error("??OEMER extraction failed: %s", exc, exc_info=True)
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
