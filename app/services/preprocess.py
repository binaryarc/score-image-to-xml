import io
import logging
import os
import tempfile

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


def preprocess_image_advanced(data: bytes) -> str:
    """고급 전처리 - 최대 인식률."""
    img_pil = Image.open(io.BytesIO(data))

    if img_pil.mode != "L":
        img_pil = img_pil.convert("L")

    img = np.array(img_pil)

    if img is None or img.size == 0:
        raise ValueError("Invalid image data - unable to decode")

    original_shape = img.shape
    logger.info("📷 Original: %s, brightness: %.1f", original_shape, img.mean())

    target_height = 4000
    if img.shape[0] < target_height:
        scale = target_height / img.shape[0]
        new_width = int(img.shape[1] * scale)
        new_height = int(img.shape[0] * scale)
        img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        logger.info("🔄 Upscaled to: %s (scale: %.2fx)", img.shape, scale)
    elif img.shape[0] > 5000:
        scale = 5000 / img.shape[0]
        new_width = int(img.shape[1] * scale)
        new_height = int(img.shape[0] * scale)
        img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
        logger.info("🔄 Downscaled to: %s (scale: %.2fx)", img.shape, scale)

    mean_brightness = img.mean()

    if mean_brightness < 100:
        img = cv2.normalize(img, None, 30, 255, cv2.NORM_MINMAX)
        logger.info("💡 Brightness normalized: %.1f → %.1f", mean_brightness, img.mean())
    elif mean_brightness > 200:
        img = cv2.normalize(img, None, 0, 240, cv2.NORM_MINMAX)
        logger.info("💡 Contrast enhanced: %.1f → %.1f", mean_brightness, img.mean())

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(16, 16))
    enhanced = clahe.apply(img)
    logger.info("✨ CLAHE applied")

    gaussian = cv2.GaussianBlur(enhanced, (0, 0), 2.0)
    unsharp = cv2.addWeighted(enhanced, 1.5, gaussian, -0.5, 0)
    logger.info("🔍 Unsharp masking applied")

    denoised = cv2.fastNlMeansDenoising(unsharp, None, h=7, templateWindowSize=7, searchWindowSize=21)
    logger.info("🧹 Denoising applied")

    blurred = cv2.GaussianBlur(denoised, (3, 3), 0)
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    if binary.mean() < 127:
        binary = cv2.bitwise_not(binary)
        logger.info("🔄 Image inverted")

    logger.info("⚫⚪ Adaptive thresholding applied")

    kernel_small = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_small)

    kernel_connect = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_connect)
    logger.info("🧩 Morphological operations applied")

    coords = cv2.findNonZero(cv2.bitwise_not(binary))
    if coords is not None:
        x, y, w, h = cv2.boundingRect(coords)
        margin = 20
        x = max(0, x - margin)
        y = max(0, y - margin)
        w = min(binary.shape[1] - x, w + 2 * margin)
        h = min(binary.shape[0] - y, h + 2 * margin)

        binary = binary[y : y + h, x : x + w]
        logger.info("✂️ Cropped: %s → %s", original_shape, binary.shape)

    kernel_sharpen = np.array(
        [
            [-1, -1, -1],
            [-1, 9, -1],
            [-1, -1, -1],
        ]
    )
    binary = cv2.filter2D(binary, -1, kernel_sharpen)
    logger.info("✨ Final sharpening applied")

    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)

    success = cv2.imwrite(path, binary, [cv2.IMWRITE_PNG_COMPRESSION, 0])

    if not success:
        raise RuntimeError("Failed to write preprocessed image")

    file_size = os.path.getsize(path)
    logger.info("💾 Saved: %s (%d bytes)", path, file_size)
    logger.info("📊 Final: %s, brightness: %.1f", binary.shape, binary.mean())

    return path
