
"""Box filtering for overlapping/nested bounding boxes in layout detection.

This module provides algorithms to filter overlapping and nested bounding boxes
that can cause duplicate content extraction in document layout analysis.

Algorithms:
1. Containment Filtering - Removes boxes fully inside other boxes
2. IoU-Based Suppression - Removes highly overlapping boxes
3. Soft-NMS (optional) - Reduces confidence of overlapping boxes

Usage:
    from processing.box_filtering import box_filter

    filtered = box_filter.filter_detections(detections, page_width, page_height)
"""

import logging
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from processing.layout_detector import Detection

logger = logging.getLogger(__name__)


# Label priority for conflict resolution (lower = higher priority = keep)
DEFAULT_LABEL_PRIORITY = {
    "title": 0,
    "section-header": 1,
    "table": 2,
    "figure": 2,
    "isolate_formula": 2,
    "text": 3,
    "plain text": 3,
    "table_caption": 4,
    "figure_caption": 4,
    "formula_caption": 4,
    "table_footnote": 5,
    "page-header": 8,
    "page-footer": 8,
    "abandon": 10,
}

# Allowed parent-child containment pairs that should be preserved
DEFAULT_ALLOWED_CONTAINMENTS = {
    ("table", "table_caption"),
    ("table", "table_footnote"),
    ("figure", "figure_caption"),
    ("isolate_formula", "formula_caption"),
}


@dataclass
class BoxFilterConfig:
    """Configuration for box filtering algorithms."""

    # Enable/disable filtering
    enabled: bool = True

    # Containment filtering thresholds
    containment_threshold: float = 0.85  # Remove if 85%+ of box is contained
    min_area_ratio: float = 0.1  # Skip if inner is too small relative to outer

    # IoU-based suppression
    iou_threshold: float = 0.5  # Suppress if IoU > 50%
    class_agnostic_nms: bool = True  # Apply across different classes

    # Label priority mapping (lower number = higher priority = keep)
    label_priority: dict[str, int] = field(
        default_factory=lambda: DEFAULT_LABEL_PRIORITY.copy()
    )

    # Allowed containment relationships (parent, child) that should be preserved
    allowed_containments: set[tuple[str, str]] = field(
        default_factory=lambda: DEFAULT_ALLOWED_CONTAINMENTS.copy()
    )

    # Soft-NMS (optional, disabled by default)
    use_soft_nms: bool = False
    soft_nms_sigma: float = 0.5
    soft_nms_min_score: float = 0.1


@dataclass
class FilterStats:
    """Statistics from a filtering operation."""
    input_count: int = 0
    output_count: int = 0
    containment_removed: int = 0
    iou_removed: int = 0
    soft_nms_removed: int = 0
    removed_by_label: dict[str, int] = field(default_factory=dict)

    def __str__(self) -> str:
        return (
            f"FilterStats(in={self.input_count}, out={self.output_count}, "
            f"containment_removed={self.containment_removed}, "
            f"iou_removed={self.iou_removed}, soft_nms_removed={self.soft_nms_removed})"
        )


def calculate_area(bbox: list[float]) -> float:
    """Calculate area of a bounding box [x1, y1, x2, y2]."""
    return max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])


def calculate_intersection(bbox1: list[float], bbox2: list[float]) -> tuple[float, float, float, float]:
    """Calculate intersection box coordinates."""
    x1 = max(bbox1[0], bbox2[0])
    y1 = max(bbox1[1], bbox2[1])
    x2 = min(bbox1[2], bbox2[2])
    y2 = min(bbox1[3], bbox2[3])
    return (x1, y1, x2, y2)


def calculate_intersection_area(bbox1: list[float], bbox2: list[float]) -> float:
    """Calculate intersection area between two bboxes."""
    x1, y1, x2, y2 = calculate_intersection(bbox1, bbox2)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    return (x2 - x1) * (y2 - y1)


def calculate_iou(bbox1: list[float], bbox2: list[float]) -> float:
    """Calculate Intersection over Union between two bounding boxes."""
    intersection = calculate_intersection_area(bbox1, bbox2)
    if intersection == 0:
        return 0.0

    area1 = calculate_area(bbox1)
    area2 = calculate_area(bbox2)
    union = area1 + area2 - intersection

    return intersection / union if union > 0 else 0.0


def get_containment_ratio(inner: list[float], outer: list[float]) -> float:
    """Calculate how much of inner box is contained in outer box.

    Returns intersection_area / inner_area (1.0 = fully contained).
    """
    inner_area = calculate_area(inner)
    if inner_area == 0:
        return 0.0

    intersection = calculate_intersection_area(inner, outer)
    return intersection / inner_area


class BoxFilter:
    """Filter overlapping and nested bounding boxes from layout detection.

    This class implements multiple filtering strategies to remove duplicate
    and overlapping detections that can cause content duplication during
    text extraction.

    Example:
        config = BoxFilterConfig(iou_threshold=0.6)
        filter = BoxFilter(config)
        filtered = filter.filter_detections(detections)
    """

    def __init__(self, config: BoxFilterConfig | None = None):
        """Initialize box filter with configuration.

        Args:
            config: Filter configuration. Uses defaults if None.
        """
        self.config = config or BoxFilterConfig()
        self._last_stats: FilterStats | None = None

    @property
    def last_stats(self) -> FilterStats | None:
        """Get statistics from the last filter operation."""
        return self._last_stats

    def filter_detections(
        self,
        detections: list,
        page_width: int | None = None,
        page_height: int | None = None,
    ) -> list:
        """Apply all filtering algorithms to remove overlapping boxes.

        Filtering pipeline:
        1. Containment filtering (remove boxes inside other boxes)
        2. IoU-based suppression (remove highly overlapping boxes)
        3. Soft-NMS (optional, reduce confidence of overlapping boxes)

        Args:
            detections: List of Detection objects from YOLO
            page_width: Page width in pixels (for context, optional)
            page_height: Page height in pixels (for context, optional)

        Returns:
            Filtered list of Detection objects
        """
        if not self.config.enabled or not detections:
            return detections

        self._last_stats = FilterStats(input_count=len(detections))

        logger.debug(f"Box filtering: {len(detections)} input detections")

        # Step 1: Containment filtering
        result = self._filter_containments(detections)
        self._last_stats.containment_removed = len(detections) - len(result)

        # Step 2: IoU-based suppression
        before_iou = len(result)
        result = self._apply_iou_suppression(result)
        self._last_stats.iou_removed = before_iou - len(result)

        # Step 3: Optional Soft-NMS
        if self.config.use_soft_nms:
            before_soft = len(result)
            result = self._apply_soft_nms(result)
            self._last_stats.soft_nms_removed = before_soft - len(result)

        self._last_stats.output_count = len(result)

        logger.debug(
            f"Box filtering complete: {self._last_stats.input_count} -> "
            f"{self._last_stats.output_count} "
            f"(containment: -{self._last_stats.containment_removed}, "
            f"iou: -{self._last_stats.iou_removed})"
        )

        return result

    def _filter_containments(self, detections: list) -> list:
        """Remove boxes that are fully contained within other boxes.

        Uses label priority to determine which box to keep when one
        is contained within another. Preserves allowed containment
        relationships (e.g., caption inside figure).
        """
        n = len(detections)
        if n <= 1:
            return detections

        to_remove = set()

        for i in range(n):
            if i in to_remove:
                continue

            for j in range(i + 1, n):
                if j in to_remove:
                    continue

                bbox_i = detections[i].bbox
                bbox_j = detections[j].bbox
                area_i = calculate_area(bbox_i)
                area_j = calculate_area(bbox_j)

                # Skip if either area is zero
                if area_i == 0 or area_j == 0:
                    continue

                # Skip if areas are too dissimilar (not a containment case)
                area_ratio = min(area_i, area_j) / max(area_i, area_j)
                if area_ratio < self.config.min_area_ratio:
                    continue

                # Determine inner/outer based on area
                if area_i < area_j:
                    inner_idx, outer_idx = i, j
                    inner_bbox, outer_bbox = bbox_i, bbox_j
                else:
                    inner_idx, outer_idx = j, i
                    inner_bbox, outer_bbox = bbox_j, bbox_i

                containment = get_containment_ratio(inner_bbox, outer_bbox)

                if containment >= self.config.containment_threshold:
                    outer_label = detections[outer_idx].label.lower()
                    inner_label = detections[inner_idx].label.lower()

                    # Check if this is an allowed containment pair
                    if self._is_allowed_containment(outer_label, inner_label):
                        continue

                    # Compare priorities (lower number = higher priority = keep)
                    outer_priority = self._get_label_priority(outer_label)
                    inner_priority = self._get_label_priority(inner_label)

                    if outer_priority <= inner_priority:
                        # Outer has higher or equal priority, remove inner
                        to_remove.add(inner_idx)
                        self._record_removal(inner_label)
                    # If inner has higher priority, keep both (unusual but possible)

        return [d for i, d in enumerate(detections) if i not in to_remove]

    def _apply_iou_suppression(self, detections: list) -> list:
        """Apply IoU-based non-maximum suppression.

        For overlapping boxes above the IoU threshold:
        - Keep the one with higher label priority
        - If same priority, keep the one with higher confidence
        """
        if not detections:
            return detections

        # Sort by priority (ascending) then confidence (descending) - best first
        sorted_indices = sorted(
            range(len(detections)),
            key=lambda i: (
                self._get_label_priority(detections[i].label),
                -detections[i].confidence
            )
        )

        keep = []
        suppressed = set()

        for idx in sorted_indices:
            if idx in suppressed:
                continue

            keep.append(idx)
            current_bbox = detections[idx].bbox
            current_label = detections[idx].label.lower()

            # Check against remaining boxes
            for other_idx in sorted_indices:
                if other_idx in suppressed or other_idx in keep:
                    continue

                other_label = detections[other_idx].label.lower()

                # Skip if not class-agnostic and different classes
                if not self.config.class_agnostic_nms and current_label != other_label:
                    continue

                iou = calculate_iou(current_bbox, detections[other_idx].bbox)

                if iou > self.config.iou_threshold:
                    suppressed.add(other_idx)
                    self._record_removal(other_label)

        # Return in original order for consistency
        return [detections[i] for i in sorted(keep)]

    def _apply_soft_nms(self, detections: list) -> list:
        """Apply Gaussian Soft-NMS.

        Instead of hard removal, reduces confidence of overlapping boxes.
        Boxes with confidence below min_score are removed.

        new_score = score * exp(-iou^2 / sigma)
        """
        if not detections:
            return detections

        # Work with mutable confidence scores
        scores = [d.confidence for d in detections]

        for i in range(len(detections)):
            for j in range(i + 1, len(detections)):
                iou = calculate_iou(detections[i].bbox, detections[j].bbox)

                if iou > 0:
                    # Gaussian weight decay
                    weight = math.exp(-(iou ** 2) / self.config.soft_nms_sigma)

                    # Apply weight to lower priority box
                    pri_i = self._get_label_priority(detections[i].label)
                    pri_j = self._get_label_priority(detections[j].label)

                    if pri_i < pri_j:
                        scores[j] *= weight
                    elif pri_j < pri_i:
                        scores[i] *= weight
                    else:
                        # Same priority, apply to lower confidence
                        if scores[i] > scores[j]:
                            scores[j] *= weight
                        else:
                            scores[i] *= weight

        # Build result with updated confidences, filtering low scores
        result = []
        for i, det in enumerate(detections):
            if scores[i] >= self.config.soft_nms_min_score:
                # Import here to avoid circular import at module load
                from processing.layout_detector import Detection
                result.append(Detection(
                    bbox=det.bbox,
                    label=det.label,
                    confidence=scores[i],
                    reading_order=det.reading_order,
                    column_id=det.column_id,
                    is_cross_layout=det.is_cross_layout,
                ))
            else:
                self._record_removal(det.label)

        return result

    def _is_allowed_containment(self, outer_label: str, inner_label: str) -> bool:
        """Check if this parent-child containment is allowed to be preserved."""
        return (outer_label, inner_label) in self.config.allowed_containments

    def _get_label_priority(self, label: str) -> int:
        """Get priority for a label (lower = higher priority = keep).

        Unknown labels default to priority 5.
        """
        return self.config.label_priority.get(label.lower(), 5)

    def _record_removal(self, label: str) -> None:
        """Record a removal for statistics tracking."""
        if self._last_stats:
            label = label.lower()
            self._last_stats.removed_by_label[label] = \
                self._last_stats.removed_by_label.get(label, 0) + 1


def create_box_filter_from_settings() -> BoxFilter:
    """Create BoxFilter using application settings."""
    try:
        from config.settings import settings

        config = BoxFilterConfig(
            enabled=getattr(settings, 'box_filter_enabled', True),
            containment_threshold=getattr(settings, 'box_filter_containment_threshold', 0.85),
            iou_threshold=getattr(settings, 'box_filter_iou_threshold', 0.5),
            class_agnostic_nms=getattr(settings, 'box_filter_class_agnostic', True),
            use_soft_nms=getattr(settings, 'box_filter_use_soft_nms', False),
            soft_nms_sigma=getattr(settings, 'box_filter_soft_nms_sigma', 0.5),
        )
        return BoxFilter(config)
    except ImportError:
        return BoxFilter()


# Global instance initialized from settings
box_filter = create_box_filter_from_settings()
