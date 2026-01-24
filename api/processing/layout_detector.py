"""Layout detection using DocLayout-YOLO."""

import logging
from pathlib import Path
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    """A single layout detection result."""
    bbox: list[float]  # [x1, y1, x2, y2]
    label: str
    confidence: float
    reading_order: int = 0  # Reading order index (1-indexed)
    column_id: int = 0      # Column assignment (-1 = spanning)
    is_cross_layout: bool = False  # XY-Cut++: element spans multiple columns


@dataclass
class DetectionResult:
    """Detection result with both filtered and unfiltered results."""
    filtered_detections: list[Detection]
    unfiltered_detections: list[Detection]
    filter_stats: "FilterStats | None" = None  # From box_filtering module


# Colors for visualization (RGB) - matches DocStructBench model labels
LABEL_COLORS = {
    "title": (0, 0, 139),             # Dark blue
    "plain text": (0, 128, 0),        # Green
    "text": (0, 128, 0),              # Green (alias)
    "figure": (255, 0, 255),          # Magenta
    "figure_caption": (128, 0, 128),  # Purple
    "table": (255, 0, 0),             # Red
    "table_caption": (200, 0, 0),     # Dark red
    "table_footnote": (150, 0, 0),    # Darker red
    "isolate_formula": (255, 165, 0), # Orange
    "formula_caption": (200, 130, 0), # Dark orange
    "abandon": (128, 128, 128),       # Gray
}


class LayoutDetector:
    """DocLayout-YOLO layout detector with CPU support."""

    def __init__(self):
        self._model = None

    @property
    def model(self):
        """Lazy load the DocLayout-YOLO model."""
        if self._model is None:
            try:
                from doclayout_yolo import YOLOv10
                from huggingface_hub import hf_hub_download

                logger.info("Loading DocLayout-YOLO model...")

                # Download the weights file explicitly from HuggingFace
                model_path = hf_hub_download(
                    repo_id="juliozhao/DocLayout-YOLO-DocStructBench",
                    filename="doclayout_yolo_docstructbench_imgsz1024.pt",
                )

                # Load from the downloaded file
                self._model = YOLOv10(model_path)
                logger.info("DocLayout-YOLO model loaded successfully")

            except ImportError as e:
                logger.error(
                    "doclayout-yolo not installed. Install with: pip install doclayout-yolo"
                )
                raise ImportError(
                    "doclayout-yolo not installed. Install with: pip install doclayout-yolo"
                ) from e
            except Exception as e:
                logger.error(f"Failed to load DocLayout-YOLO model: {e}")
                raise RuntimeError(f"Failed to load DocLayout-YOLO model: {e}") from e
        return self._model

    def detect(
        self,
        image_path: Path,
        conf: float = 0.2,
        imgsz: int = 1024,
    ) -> list[Detection]:
        """Run layout detection on a page image.

        Args:
            image_path: Path to the page image
            conf: Confidence threshold (default 0.2)
            imgsz: Image size for detection (default 1024)

        Returns:
            List of Detection objects with bounding boxes, labels, confidence scores,
            reading order, and column assignment - sorted by reading order.
        """
        logger.debug(f"Running layout detection on: {image_path}")

        # Get image dimensions for reading order detection
        img = Image.open(image_path)
        page_width, page_height = img.size
        img.close()

        results = self.model.predict(
            str(image_path),
            imgsz=imgsz,
            conf=conf,
            device="cpu",  # CPU mode
            verbose=False,
        )

        detections = []
        if results and len(results) > 0 and results[0].boxes is not None:
            result = results[0]

            for i in range(len(result.boxes)):
                box = result.boxes[i]
                cls_id = int(box.cls.item())

                # Get label directly from model's names dict (NOT hardcoded!)
                label = result.names.get(cls_id, f"Unknown_{cls_id}")

                detections.append(Detection(
                    bbox=box.xyxy[0].tolist(),  # [x1, y1, x2, y2]
                    label=label,
                    confidence=float(box.conf.item()),
                ))

        # Apply box filtering to remove overlapping/nested boxes
        if detections:
            from processing.box_filtering import box_filter
            initial_count = len(detections)
            detections = box_filter.filter_detections(
                detections, page_width, page_height
            )
            if len(detections) < initial_count:
                logger.debug(
                    f"Box filtering: {initial_count} -> {len(detections)} detections"
                )

        # Apply reading order detection
        if detections:
            from processing.reading_order import reading_order_detector
            ordered = reading_order_detector.detect_reading_order(
                detections, page_width, page_height
            )

            # Update detections with reading order and sort
            detection_map = {i: det for i, det in enumerate(detections)}
            sorted_detections = []

            for item in sorted(ordered, key=lambda x: x["reading_order"]):
                # Find matching detection by bbox
                for i, det in detection_map.items():
                    if det.bbox == item["bbox"]:
                        det.reading_order = item["reading_order"]
                        det.column_id = item["column_id"]
                        det.is_cross_layout = item.get("is_cross_layout", False)
                        sorted_detections.append(det)
                        del detection_map[i]
                        break

            detections = sorted_detections

        logger.debug(f"Found {len(detections)} layout elements (sorted by reading order)")
        return detections

    def detect_with_filter_info(
        self,
        image_path: Path,
        conf: float = 0.2,
        imgsz: int = 1024,
    ) -> DetectionResult:
        """Run layout detection and return both filtered and unfiltered results.

        This method is useful for comparing before/after filtering in the UI.

        Args:
            image_path: Path to the page image
            conf: Confidence threshold (default 0.2)
            imgsz: Image size for detection (default 1024)

        Returns:
            DetectionResult with filtered detections, unfiltered detections, and filter stats.
        """
        logger.debug(f"Running layout detection with filter info on: {image_path}")

        # Get image dimensions for reading order detection
        img = Image.open(image_path)
        page_width, page_height = img.size
        img.close()

        results = self.model.predict(
            str(image_path),
            imgsz=imgsz,
            conf=conf,
            device="cpu",
            verbose=False,
        )

        # Collect raw YOLO detections (unfiltered)
        raw_detections = []
        if results and len(results) > 0 and results[0].boxes is not None:
            result = results[0]

            for i in range(len(result.boxes)):
                box = result.boxes[i]
                cls_id = int(box.cls.item())
                label = result.names.get(cls_id, f"Unknown_{cls_id}")

                raw_detections.append(Detection(
                    bbox=box.xyxy[0].tolist(),
                    label=label,
                    confidence=float(box.conf.item()),
                ))

        # Create deep copy for unfiltered (before reading order applied)
        import copy
        unfiltered_detections = copy.deepcopy(raw_detections)

        # Apply box filtering
        filter_stats = None
        filtered_detections = raw_detections
        if raw_detections:
            from processing.box_filtering import box_filter
            filtered_detections = box_filter.filter_detections(
                raw_detections, page_width, page_height
            )
            filter_stats = box_filter.last_stats

        # Apply reading order detection to BOTH sets
        if filtered_detections:
            from processing.reading_order import reading_order_detector
            ordered = reading_order_detector.detect_reading_order(
                filtered_detections, page_width, page_height
            )

            detection_map = {i: det for i, det in enumerate(filtered_detections)}
            sorted_detections = []

            for item in sorted(ordered, key=lambda x: x["reading_order"]):
                for i, det in detection_map.items():
                    if det.bbox == item["bbox"]:
                        det.reading_order = item["reading_order"]
                        det.column_id = item["column_id"]
                        det.is_cross_layout = item.get("is_cross_layout", False)
                        sorted_detections.append(det)
                        del detection_map[i]
                        break

            filtered_detections = sorted_detections

        # Apply reading order to unfiltered detections too
        if unfiltered_detections:
            from processing.reading_order import reading_order_detector
            ordered = reading_order_detector.detect_reading_order(
                unfiltered_detections, page_width, page_height
            )

            detection_map = {i: det for i, det in enumerate(unfiltered_detections)}
            sorted_detections = []

            for item in sorted(ordered, key=lambda x: x["reading_order"]):
                for i, det in detection_map.items():
                    if det.bbox == item["bbox"]:
                        det.reading_order = item["reading_order"]
                        det.column_id = item["column_id"]
                        det.is_cross_layout = item.get("is_cross_layout", False)
                        sorted_detections.append(det)
                        del detection_map[i]
                        break

            unfiltered_detections = sorted_detections

        logger.debug(
            f"Detection complete: {len(unfiltered_detections)} unfiltered, "
            f"{len(filtered_detections)} filtered"
        )

        return DetectionResult(
            filtered_detections=filtered_detections,
            unfiltered_detections=unfiltered_detections,
            filter_stats=filter_stats,
        )

    def annotate(
        self,
        image_path: Path,
        output_path: Path,
        detections: list[Detection] | None = None,
        conf: float = 0.2,
    ) -> Path:
        """Draw detection boxes on image and save.

        Args:
            image_path: Path to the original page image
            output_path: Path to save the annotated image
            detections: Pre-computed detections (if None, will run detection)
            conf: Confidence threshold if running detection

        Returns:
            Path to the annotated image
        """
        # Load original image
        img = Image.open(image_path).convert("RGB")

        # Get detections if not provided
        if detections is None:
            detections = self.detect(image_path, conf=conf)

        # Draw boxes
        draw = ImageDraw.Draw(img)

        # Try to get fonts, fall back to default if not available
        try:
            font = ImageFont.truetype("arial.ttf", 14)
            order_font = ImageFont.truetype("arial.ttf", 18)
        except (IOError, OSError):
            font = ImageFont.load_default()
            order_font = font

        for det in detections:
            x1, y1, x2, y2 = det.bbox
            color = LABEL_COLORS.get(det.label, (128, 128, 128))

            # Draw rectangle
            draw.rectangle([x1, y1, x2, y2], outline=color, width=2)

            # Draw reading order number (large, prominent)
            if det.reading_order > 0:
                order_text = str(det.reading_order)
                # Draw order number background circle
                order_x = x1 + 5
                order_y = y1 + 5
                order_bbox = draw.textbbox((order_x, order_y), order_text, font=order_font)
                padding = 4
                circle_bbox = [
                    order_bbox[0] - padding,
                    order_bbox[1] - padding,
                    order_bbox[2] + padding,
                    order_bbox[3] + padding,
                ]
                draw.ellipse(circle_bbox, fill=(255, 200, 0), outline=(0, 0, 0))
                draw.text((order_x, order_y), order_text, fill="black", font=order_font)

            # Draw label background (offset down if reading order is shown)
            label_y = y1 + 30 if det.reading_order > 0 else y1
            label_text = f"{det.label} ({det.confidence:.2f})"
            bbox = draw.textbbox((x1, label_y), label_text, font=font)
            label_bg = [bbox[0] - 2, bbox[1] - 2, bbox[2] + 2, bbox[3] + 2]
            draw.rectangle(label_bg, fill=color)

            # Draw label text
            draw.text((x1, label_y), label_text, fill="white", font=font)

        # Save annotated image
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path)

        logger.debug(f"Saved annotated image to: {output_path}")
        return output_path

    def detections_to_dict(self, detections: list[Detection]) -> list[dict]:
        """Convert detections to JSON-serializable format."""
        return [
            {
                "bbox": det.bbox,
                "label": det.label,
                "confidence": det.confidence,
                "reading_order": det.reading_order,
                "column_id": det.column_id,
                "is_cross_layout": det.is_cross_layout,
            }
            for det in detections
        ]

    def dict_to_detections(self, data: list[dict]) -> list[Detection]:
        """Convert JSON data back to Detection objects."""
        return [
            Detection(
                bbox=d["bbox"],
                label=d["label"],
                confidence=d["confidence"],
                reading_order=d.get("reading_order", 0),
                column_id=d.get("column_id", 0),
                is_cross_layout=d.get("is_cross_layout", False),
            )
            for d in data
        ]


# Global instance
layout_detector = LayoutDetector()
