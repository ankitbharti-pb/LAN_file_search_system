"""Crop regions from page images."""

import logging
import shutil
from pathlib import Path

from PIL import Image

from config.settings import settings

logger = logging.getLogger(__name__)


class RegionCropper:
    """Crop detected regions from page images."""

    def get_permanent_path(
        self,
        doc_id: str,
        page_num: int,
        region_type: str,
        reading_order: int,
    ) -> Path:
        """Get permanent storage path for a cropped region.

        Args:
            doc_id: Document ID
            page_num: Page number (1-indexed)
            region_type: Type of region (figure, table, formula)
            reading_order: Reading order index

        Returns:
            Path like: data/processing/{doc_id}/images/page_001_figure_001.png
        """
        images_dir = settings.data_folder / "processing" / doc_id / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        filename = f"page_{page_num:03d}_{region_type}_{reading_order:03d}.png"
        return images_dir / filename

    def crop_region(
        self,
        image_path: Path,
        bbox: list[float],
        output_path: Path,
        padding: int = 5,
    ) -> Path:
        """Crop a region from page image.

        Args:
            image_path: Path to full page image
            bbox: [x1, y1, x2, y2] bounding box in image coordinates
            output_path: Where to save cropped image
            padding: Extra pixels around bbox for context

        Returns:
            Path to cropped image
        """
        image_path = Path(image_path)
        output_path = Path(output_path)

        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        img = Image.open(image_path)

        # Apply padding (clamped to image bounds)
        x1 = max(0, int(bbox[0]) - padding)
        y1 = max(0, int(bbox[1]) - padding)
        x2 = min(img.width, int(bbox[2]) + padding)
        y2 = min(img.height, int(bbox[3]) + padding)

        # Ensure valid crop region
        if x2 <= x1 or y2 <= y1:
            logger.warning(f"Invalid crop region: {bbox}")
            img.close()
            return output_path

        # Crop and save
        cropped = img.crop((x1, y1, x2, y2))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cropped.save(output_path, "PNG")
        cropped.close()
        img.close()

        logger.debug(f"Cropped region {bbox} to {output_path}")
        return output_path

    def cleanup_crops(self, crops_dir: Path) -> None:
        """Delete all cropped images in a directory.

        Args:
            crops_dir: Directory containing cropped images
        """
        crops_dir = Path(crops_dir)
        if crops_dir.exists():
            try:
                shutil.rmtree(crops_dir)
                logger.debug(f"Cleaned up crops directory: {crops_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup crops: {e}")

    def cleanup_file(self, file_path: Path) -> None:
        """Delete a single cropped image file.

        Args:
            file_path: Path to file to delete
        """
        file_path = Path(file_path)
        if file_path.exists():
            try:
                file_path.unlink()
                logger.debug(f"Deleted crop: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete {file_path}: {e}")


# Global instance
region_cropper = RegionCropper()
