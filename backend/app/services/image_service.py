"""图片预处理服务：压缩、尺寸检查、格式转换"""
import base64
import io
import logging
from typing import Optional
from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)


class ImageService:
    """图片服务：压缩与预处理"""

    @staticmethod
    def decode_base64(data: str) -> Image.Image:
        """从 base64 解码图片"""
        # 去除可能的前缀 data:image/jpeg;base64,
        if "," in data and data.startswith("data:"):
            data = data.split(",", 1)[1]
        image_bytes = base64.b64decode(data)
        return Image.open(io.BytesIO(image_bytes))

    @staticmethod
    def encode_base64(image: Image.Image, fmt: str = "JPEG", quality: int = 75) -> str:
        """将 PIL Image 编码为 base64"""
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format=fmt, quality=quality)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def compress(
        self,
        image_data: str,
        max_width: Optional[int] = None,
        max_height: Optional[int] = None,
        quality: Optional[int] = None,
        fmt: Optional[str] = None,
    ) -> dict:
        """
        压缩图片并返回结果。
        返回: {original_size, compressed_size, width, height, format, quality, data}
        """
        max_width = max_width or settings.IMAGE_MAX_WIDTH
        max_height = max_height or settings.IMAGE_MAX_HEIGHT
        quality = quality or settings.IMAGE_QUALITY
        fmt = fmt or settings.IMAGE_FORMAT

        # 解码
        original_bytes = base64.b64decode(self._strip_prefix(image_data))
        original_size = len(original_bytes)
        image = Image.open(io.BytesIO(original_bytes))

        original_dims = (image.width, image.height)

        # 缩放到限制内
        image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

        # 编码为 JPEG (更小的体积)
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format=fmt, quality=quality)
        compressed_bytes = buffer.getvalue()
        compressed_size = len(compressed_bytes)
        compressed_b64 = base64.b64encode(compressed_bytes).decode("utf-8")

        logger.info(
            f"图片压缩: {original_dims[0]}x{original_dims[1]} → {image.width}x{image.height}, "
            f"{original_size:,}B → {compressed_size:,}B "
            f"(压缩比 {original_size / max(compressed_size, 1):.1f}x)"
        )

        return {
            "original_size": original_size,
            "compressed_size": compressed_size,
            "width": image.width,
            "height": image.height,
            "format": fmt.lower(),
            "quality": quality,
            "data": compressed_b64,
        }

    def is_likely_readable(
        self, image_data: str, min_width: int = 200, min_height: int = 150
    ) -> tuple[bool, str]:
        """
        检查图片是否可能包含可读内容。
        返回: (可读, 原因说明)
        """
        image = self.decode_base64(image_data)
        if image.width < min_width or image.height < min_height:
            return False, f"图片尺寸过小 ({image.width}x{image.height})，可能无法识别内容"
        return True, "ok"

    @staticmethod
    def _strip_prefix(data: str) -> str:
        """去除 base64 中的 data:xxx;base64, 前缀"""
        if "," in data and data.startswith("data:"):
            return data.split(",", 1)[1]
        return data


image_service = ImageService()
