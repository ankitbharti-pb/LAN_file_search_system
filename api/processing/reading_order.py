"""XY-Cut++ Reading Order Detection.

Implementation based on the paper:
"XY-Cut++: Advanced Layout Ordering via Hierarchical Mask Mechanism on a Novel Benchmark"
by Shuai Liu, Youmeng Li, and Jizeng Wei (arXiv:2504.10258, April 2025)

This module implements an advanced reading order detection algorithm that achieves
98.8 BLEU overall performance through:
1. Pre-Mask Processing - Handles high-dynamic elements separately
2. Multi-Granularity Segmentation (MGS) - Adaptive XY/YX-Cut selection
3. Cross-Modal Matching (CMM) - Geometry-aware caption-to-parent linking
"""

import logging
from dataclasses import dataclass, field
from typing import Tuple, Optional
from statistics import median

logger = logging.getLogger(__name__)


# Caption types and their parent element types
CAPTION_PARENTS = {
    "figure_caption": "figure",
    "table_caption": "table",
    "table_footnote": "table_caption",
    "formula_caption": "isolate_formula",
}

# Elements that should always be treated as spanning
SPANNING_LABELS = {"title", "abandon"}

# High-dynamic elements to pre-mask before segmentation
PREMASK_LABELS = {"title", "figure", "table"}

# Label priority for semantic ordering (lower = higher priority)
LABEL_PRIORITY = {
    "title": 0,
    "section_header": 1,
    "text": 2,
    "plain text": 2,
    "figure": 3,
    "figure_caption": 4,
    "table": 3,
    "table_caption": 4,
    "table_footnote": 5,
    "isolate_formula": 3,
    "formula_caption": 4,
    "abandon": 10,
}


@dataclass
class XYCutPlusPlusConfig:
    """Configuration for XY-Cut++ algorithm.

    Based on parameters from the paper with empirically tuned defaults.
    """
    # Cross-layout detection: τ_l = β × median(widths)
    beta_scaling_factor: float = 1.3

    # Density-driven splitting: use XY-Cut if τ_d > threshold
    density_threshold: float = 0.9

    # Pre-mask labels (high-dynamic elements)
    premask_labels: set = field(default_factory=lambda: PREMASK_LABELS.copy())

    # Cross-Modal Matching weights
    weight_intersection: float = 1.0
    weight_boundary: float = 1.0
    weight_vertical: float = 1.0
    weight_horizontal: float = 1.0

    # Caption matching distance threshold
    caption_distance_threshold: float = 100

    # Column detection parameters
    min_gap_ratio: float = 0.02
    min_column_width_ratio: float = 0.1

    # Segmentation depth limit
    max_recursion_depth: int = 10

    # Minimum elements to attempt further cuts
    min_elements_for_cut: int = 2


@dataclass
class ElementWithOrder:
    """Internal representation of an element during ordering."""
    index: int  # Original index in detections list
    bbox: list[float]  # [x1, y1, x2, y2]
    label: str
    confidence: float
    column_id: int = 0
    y_center: float = 0.0
    x_center: float = 0.0
    sort_key: float = 0.0
    is_cross_layout: bool = False
    is_premask: bool = False
    parent_index: int = -1  # For caption-parent linking


class XYCutPlusPlusDetector:
    """XY-Cut++ Reading Order Detection.

    Implements the three-stage pipeline from the paper:
    1. Pre-Mask Processing
    2. Multi-Granularity Segmentation (MGS)
    3. Cross-Modal Matching (CMM)
    """

    def __init__(self, config: Optional[XYCutPlusPlusConfig] = None):
        self.config = config or XYCutPlusPlusConfig()

    def detect_reading_order(
        self,
        detections: list,
        page_width: int,
        page_height: int,
    ) -> list[dict]:
        """
        Determine reading order using XY-Cut++ algorithm.

        Args:
            detections: List of Detection objects with bbox, label, confidence
            page_width: Width of the page in pixels
            page_height: Height of the page in pixels

        Returns:
            List of dicts with original detection data plus reading_order and column_id
        """
        if not detections:
            return []

        logger.debug(f"XY-Cut++: Processing {len(detections)} elements")

        # Convert to internal representation
        elements = self._create_elements(detections)

        # Stage 1: Pre-Mask Processing
        regular_elements, premask_elements = self._premask_elements(elements)
        logger.debug(f"Pre-mask: {len(premask_elements)} masked, {len(regular_elements)} regular")

        # Stage 2: Cross-layout detection on regular elements
        self._detect_cross_layout_elements(regular_elements, page_width)

        # Separate cross-layout and column elements
        cross_layout = [e for e in regular_elements if e.is_cross_layout]
        column_elements = [e for e in regular_elements if not e.is_cross_layout]
        logger.debug(f"Cross-layout: {len(cross_layout)}, Column: {len(column_elements)}")

        # Stage 3: MGS on column elements
        region = (0, 0, page_width, page_height)
        ordered_groups = self._mgs_segment(column_elements, region, page_width, page_height)

        # Flatten groups maintaining order
        ordered_column_elements = []
        for group in ordered_groups:
            # Sort within group by position
            sorted_group = sorted(group, key=lambda e: (e.bbox[1], e.bbox[0]))
            ordered_column_elements.extend(sorted_group)

        # Assign sort keys to column elements
        for i, elem in enumerate(ordered_column_elements):
            elem.sort_key = float(i)

        # Stage 4: Interleave cross-layout and premask elements
        all_elements = self._interleave_elements(
            ordered_column_elements, cross_layout, premask_elements
        )

        # Stage 5: CMM - Link captions using cross-modal matching
        self._link_captions_cmm(all_elements, page_width, page_height)

        # Stage 6: Final sort with label-aware ordering
        all_elements.sort(key=lambda e: self._label_aware_sort_key(e))

        # Build result
        return self._build_result(all_elements, detections)

    def _create_elements(self, detections: list) -> list[ElementWithOrder]:
        """Convert detections to internal representation."""
        elements = []
        for i, det in enumerate(detections):
            bbox = det.bbox if isinstance(det.bbox, list) else list(det.bbox)
            x1, y1, x2, y2 = bbox
            elements.append(ElementWithOrder(
                index=i,
                bbox=bbox,
                label=det.label,
                confidence=det.confidence,
                y_center=(y1 + y2) / 2,
                x_center=(x1 + x2) / 2,
            ))
        return elements

    def _premask_elements(
        self,
        elements: list[ElementWithOrder]
    ) -> Tuple[list[ElementWithOrder], list[ElementWithOrder]]:
        """
        Stage 1: Pre-Mask Processing.

        Separate high-dynamic elements (titles, figures, tables) from regular
        content to avoid the L-shaped region problem during segmentation.

        Returns:
            (regular_elements, premask_elements)
        """
        regular = []
        premask = []

        for elem in elements:
            if elem.label in self.config.premask_labels:
                elem.is_premask = True
                premask.append(elem)
            else:
                regular.append(elem)

        return regular, premask

    def _detect_cross_layout_elements(
        self,
        elements: list[ElementWithOrder],
        page_width: int
    ) -> None:
        """
        Identify cross-layout (spanning) elements using adaptive threshold.

        Uses τ_l = β × median(widths) where β = 1.3 (from paper)
        """
        if not elements:
            return

        # Calculate element widths
        widths = [(e.bbox[2] - e.bbox[0]) for e in elements]

        if not widths:
            return

        # Adaptive threshold based on median width
        median_width = median(widths)
        tau_l = self.config.beta_scaling_factor * median_width

        # Also consider page-relative threshold
        page_threshold = page_width * 0.7  # 70% of page width

        for elem in elements:
            elem_width = elem.bbox[2] - elem.bbox[0]
            # Element is cross-layout if wider than adaptive threshold
            # or explicitly marked as spanning label
            if elem_width >= tau_l or elem_width >= page_threshold or elem.label in SPANNING_LABELS:
                elem.is_cross_layout = True
            else:
                elem.is_cross_layout = False

    def _calculate_density_ratio(
        self,
        elements: list[ElementWithOrder],
        region: Tuple[float, float, float, float]
    ) -> float:
        """
        Calculate content density ratio for a region.

        Returns ratio indicating whether content is more column-like (high ratio)
        or row-like (low ratio).
        """
        x1, y1, x2, y2 = region
        region_width = x2 - x1
        region_height = y2 - y1

        if region_width <= 0 or region_height <= 0 or not elements:
            return 1.0

        # Filter elements within region
        region_elements = [
            e for e in elements
            if e.x_center >= x1 and e.x_center <= x2 and
               e.y_center >= y1 and e.y_center <= y2
        ]

        if not region_elements:
            return 1.0

        # Create density bands
        num_bands = 10
        h_bands = [0] * num_bands  # Horizontal bands (for vertical analysis)
        v_bands = [0] * num_bands  # Vertical bands (for horizontal analysis)

        for elem in region_elements:
            # Horizontal band index
            h_idx = min(num_bands - 1, int((elem.y_center - y1) / region_height * num_bands))
            h_bands[h_idx] += 1

            # Vertical band index
            v_idx = min(num_bands - 1, int((elem.x_center - x1) / region_width * num_bands))
            v_bands[v_idx] += 1

        # Calculate variance in each direction
        h_mean = sum(h_bands) / num_bands
        v_mean = sum(v_bands) / num_bands

        h_variance = sum((x - h_mean) ** 2 for x in h_bands)
        v_variance = sum((x - v_mean) ** 2 for x in v_bands)

        # Higher ratio means more column-like distribution
        total_variance = h_variance + v_variance
        if total_variance == 0:
            return 1.0

        return h_variance / total_variance

    def _select_cut_direction(
        self,
        elements: list[ElementWithOrder],
        region: Tuple[float, float, float, float]
    ) -> str:
        """
        Select XY-Cut or YX-Cut based on density ratio.

        From paper: Use XY-Cut if τ_d > 0.9, otherwise YX-Cut

        Returns: 'xy' or 'yx'
        """
        density_ratio = self._calculate_density_ratio(elements, region)
        return 'xy' if density_ratio > self.config.density_threshold else 'yx'

    def _find_horizontal_gaps(
        self,
        elements: list[ElementWithOrder],
        region: Tuple[float, float, float, float]
    ) -> list[float]:
        """Find significant horizontal gaps (for horizontal cuts)."""
        x1, y1, x2, y2 = region
        region_height = y2 - y1

        if region_height <= 0 or not elements:
            return []

        # Create projection profile
        num_bins = 100
        bin_height = region_height / num_bins
        coverage = [0] * num_bins

        for elem in elements:
            ey1, ey2 = elem.bbox[1], elem.bbox[3]
            start_bin = max(0, int((ey1 - y1) / bin_height))
            end_bin = min(num_bins - 1, int((ey2 - y1) / bin_height))
            for b in range(start_bin, end_bin + 1):
                coverage[b] += 1

        # Find gaps
        min_gap_bins = max(2, int(num_bins * self.config.min_gap_ratio))
        gaps = []
        gap_start = None

        for i, count in enumerate(coverage):
            if count == 0:
                if gap_start is None:
                    gap_start = i
            else:
                if gap_start is not None:
                    gap_length = i - gap_start
                    if gap_length >= min_gap_bins:
                        # Record gap center
                        gap_center = y1 + (gap_start + i) / 2 * bin_height
                        gaps.append(gap_center)
                    gap_start = None

        return gaps

    def _find_vertical_gaps(
        self,
        elements: list[ElementWithOrder],
        region: Tuple[float, float, float, float]
    ) -> list[float]:
        """Find significant vertical gaps (for vertical cuts)."""
        x1, y1, x2, y2 = region
        region_width = x2 - x1

        if region_width <= 0 or not elements:
            return []

        # Create projection profile
        num_bins = 100
        bin_width = region_width / num_bins
        coverage = [0] * num_bins

        for elem in elements:
            ex1, ex2 = elem.bbox[0], elem.bbox[2]
            start_bin = max(0, int((ex1 - x1) / bin_width))
            end_bin = min(num_bins - 1, int((ex2 - x1) / bin_width))
            for b in range(start_bin, end_bin + 1):
                coverage[b] += 1

        # Find gaps
        min_gap_bins = max(2, int(num_bins * self.config.min_gap_ratio))
        gaps = []
        gap_start = None

        for i, count in enumerate(coverage):
            if count == 0:
                if gap_start is None:
                    gap_start = i
            else:
                if gap_start is not None:
                    gap_length = i - gap_start
                    if gap_length >= min_gap_bins:
                        # Record gap center
                        gap_center = x1 + (gap_start + i) / 2 * bin_width
                        gaps.append(gap_center)
                    gap_start = None

        return gaps

    def _horizontal_cut(
        self,
        elements: list[ElementWithOrder],
        region: Tuple[float, float, float, float]
    ) -> list[Tuple[list[ElementWithOrder], Tuple[float, float, float, float]]]:
        """
        Perform horizontal cut to split elements into rows.

        Returns list of (element_group, sub_region) tuples.
        """
        if not elements:
            return []

        x1, y1, x2, y2 = region
        gaps = self._find_horizontal_gaps(elements, region)

        if not gaps:
            return [(elements, region)]

        # Sort gaps
        gaps = sorted(gaps)

        # Create groups based on gaps
        groups = []
        current_y = y1

        for gap_y in gaps:
            # Elements above this gap
            group = [e for e in elements if e.y_center >= current_y and e.y_center < gap_y]
            if group:
                sub_region = (x1, current_y, x2, gap_y)
                groups.append((group, sub_region))
            current_y = gap_y

        # Last group
        group = [e for e in elements if e.y_center >= current_y]
        if group:
            sub_region = (x1, current_y, x2, y2)
            groups.append((group, sub_region))

        return groups if groups else [(elements, region)]

    def _vertical_cut(
        self,
        elements: list[ElementWithOrder],
        region: Tuple[float, float, float, float]
    ) -> list[Tuple[list[ElementWithOrder], Tuple[float, float, float, float]]]:
        """
        Perform vertical cut to split elements into columns.

        Returns list of (element_group, sub_region) tuples.
        """
        if not elements:
            return []

        x1, y1, x2, y2 = region
        gaps = self._find_vertical_gaps(elements, region)

        if not gaps:
            return [(elements, region)]

        # Sort gaps
        gaps = sorted(gaps)

        # Create groups based on gaps
        groups = []
        current_x = x1

        for gap_x in gaps:
            # Elements left of this gap
            group = [e for e in elements if e.x_center >= current_x and e.x_center < gap_x]
            if group:
                sub_region = (current_x, y1, gap_x, y2)
                groups.append((group, sub_region))
            current_x = gap_x

        # Last group
        group = [e for e in elements if e.x_center >= current_x]
        if group:
            sub_region = (current_x, y1, x2, y2)
            groups.append((group, sub_region))

        return groups if groups else [(elements, region)]

    def _mgs_segment(
        self,
        elements: list[ElementWithOrder],
        region: Tuple[float, float, float, float],
        page_width: int,
        page_height: int,
        depth: int = 0
    ) -> list[list[ElementWithOrder]]:
        """
        Multi-Granularity Segmentation using adaptive XY/YX-Cut.

        Returns list of element groups in reading order.
        """
        if not elements:
            return []

        if depth >= self.config.max_recursion_depth:
            return [elements]

        if len(elements) < self.config.min_elements_for_cut:
            return [elements]

        # Select cut direction based on density
        cut_direction = self._select_cut_direction(elements, region)

        if cut_direction == 'xy':
            # XY-Cut: Horizontal cut first, then vertical within each row
            h_groups = self._horizontal_cut(elements, region)

            result = []
            for h_group, h_region in h_groups:
                # Vertical cut within this horizontal band
                v_groups = self._vertical_cut(h_group, h_region)

                for v_group, v_region in v_groups:
                    if len(v_group) > self.config.min_elements_for_cut:
                        # Recurse
                        sub_result = self._mgs_segment(
                            v_group, v_region, page_width, page_height, depth + 1
                        )
                        result.extend(sub_result)
                    else:
                        result.append(v_group)
        else:
            # YX-Cut: Vertical cut first, then horizontal within each column
            v_groups = self._vertical_cut(elements, region)

            result = []
            for v_group, v_region in v_groups:
                # Horizontal cut within this vertical band
                h_groups = self._horizontal_cut(v_group, v_region)

                for h_group, h_region in h_groups:
                    if len(h_group) > self.config.min_elements_for_cut:
                        # Recurse
                        sub_result = self._mgs_segment(
                            h_group, h_region, page_width, page_height, depth + 1
                        )
                        result.extend(sub_result)
                    else:
                        result.append(h_group)

        return result if result else [elements]

    def _interleave_elements(
        self,
        column_elements: list[ElementWithOrder],
        cross_layout: list[ElementWithOrder],
        premask_elements: list[ElementWithOrder]
    ) -> list[ElementWithOrder]:
        """
        Interleave cross-layout and premask elements with column elements.

        Cross-layout and premask elements are inserted at their Y position
        relative to the column content.
        """
        all_elements = list(column_elements)

        # Add cross-layout elements
        for elem in cross_layout:
            # Find insertion point based on Y position
            insert_idx = 0
            for i, col_elem in enumerate(all_elements):
                if col_elem.y_center > elem.y_center:
                    break
                insert_idx = i + 1

            # Set sort key just before the element it precedes
            if insert_idx < len(all_elements):
                elem.sort_key = all_elements[insert_idx].sort_key - 0.5
            elif all_elements:
                elem.sort_key = all_elements[-1].sort_key + 0.5
            else:
                elem.sort_key = 0.0

            all_elements.insert(insert_idx, elem)

        # Add premask elements (titles, figures, tables)
        for elem in premask_elements:
            insert_idx = 0
            for i, existing in enumerate(all_elements):
                if existing.y_center > elem.y_center:
                    break
                insert_idx = i + 1

            if insert_idx < len(all_elements):
                elem.sort_key = all_elements[insert_idx].sort_key - 0.5
            elif all_elements:
                elem.sort_key = all_elements[-1].sort_key + 0.5
            else:
                elem.sort_key = 0.0

            all_elements.insert(insert_idx, elem)

        # Reassign sort keys sequentially
        for i, elem in enumerate(all_elements):
            elem.sort_key = float(i)

        return all_elements

    def _calculate_iou(self, bbox1: list[float], bbox2: list[float]) -> float:
        """Calculate Intersection over Union between two bounding boxes."""
        x1 = max(bbox1[0], bbox2[0])
        y1 = max(bbox1[1], bbox2[1])
        x2 = min(bbox1[2], bbox2[2])
        y2 = min(bbox1[3], bbox2[3])

        if x2 <= x1 or y2 <= y1:
            return 0.0

        intersection = (x2 - x1) * (y2 - y1)
        area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
        area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
        union = area1 + area2 - intersection

        return intersection / union if union > 0 else 0.0

    def _calculate_boundary_distance(
        self,
        bbox1: list[float],
        bbox2: list[float]
    ) -> float:
        """Calculate minimum boundary distance between two boxes."""
        # Horizontal distance
        if bbox1[2] < bbox2[0]:
            h_dist = bbox2[0] - bbox1[2]
        elif bbox2[2] < bbox1[0]:
            h_dist = bbox1[0] - bbox2[2]
        else:
            h_dist = 0

        # Vertical distance
        if bbox1[3] < bbox2[1]:
            v_dist = bbox2[1] - bbox1[3]
        elif bbox2[3] < bbox1[1]:
            v_dist = bbox1[1] - bbox2[3]
        else:
            v_dist = 0

        return (h_dist ** 2 + v_dist ** 2) ** 0.5

    def _calculate_cmm_distance(
        self,
        caption: ElementWithOrder,
        parent: ElementWithOrder,
        page_width: int,
        page_height: int
    ) -> float:
        """
        Calculate Cross-Modal Matching distance.

        Uses four geometric constraints with weights scaled by page dimensions:
        1. Intersection constraint (IoU-based)
        2. Boundary proximity (edge margins)
        3. Vertical continuity (baseline alignment)
        4. Horizontal ordering (center alignment)
        """
        max_dim = max(page_width, page_height)

        # Dynamic weights as per paper
        weights = [
            self.config.weight_intersection * (max_dim ** 2),
            self.config.weight_boundary * max_dim,
            self.config.weight_vertical * 1,
            self.config.weight_horizontal * (1 / max_dim) if max_dim > 0 else 0
        ]

        cap_bbox = caption.bbox
        par_bbox = parent.bbox

        # 1. Intersection constraint (lower is better for non-overlapping)
        iou = self._calculate_iou(cap_bbox, par_bbox)
        intersection_score = 1 - iou

        # 2. Boundary proximity
        boundary_dist = self._calculate_boundary_distance(cap_bbox, par_bbox)
        # Normalize by max dimension
        boundary_score = boundary_dist / max_dim if max_dim > 0 else 0

        # 3. Vertical continuity (caption should be below parent)
        vertical_dist = cap_bbox[1] - par_bbox[3]  # Caption top to parent bottom
        # Penalize captions above their parent
        if vertical_dist < -20:
            vertical_score = abs(vertical_dist) * 2
        else:
            vertical_score = abs(vertical_dist)
        # Normalize
        vertical_score = vertical_score / max_dim if max_dim > 0 else 0

        # 4. Horizontal alignment (center alignment)
        cap_center = (cap_bbox[0] + cap_bbox[2]) / 2
        par_center = (par_bbox[0] + par_bbox[2]) / 2
        horizontal_dist = abs(cap_center - par_center)
        horizontal_score = horizontal_dist / max_dim if max_dim > 0 else 0

        # Weighted distance
        distance = (
            weights[0] * intersection_score +
            weights[1] * boundary_score +
            weights[2] * vertical_score +
            weights[3] * horizontal_score
        )

        return distance

    def _link_captions_cmm(
        self,
        elements: list[ElementWithOrder],
        page_width: int,
        page_height: int
    ) -> None:
        """
        Link captions to parent elements using Cross-Modal Matching.

        Captions are positioned immediately after their parent element.
        """
        # Find caption elements
        captions = [e for e in elements if e.label in CAPTION_PARENTS]

        if not captions:
            return

        for caption in captions:
            parent_label = CAPTION_PARENTS[caption.label]

            # Handle table_footnote specially
            if caption.label == "table_footnote":
                parent_label = "table_caption"

            # Find potential parents
            potential_parents = [
                e for e in elements
                if e.label == parent_label
            ]

            if not potential_parents:
                continue

            # Find best parent using CMM distance
            best_parent = None
            best_distance = float('inf')

            for parent in potential_parents:
                distance = self._calculate_cmm_distance(
                    caption, parent, page_width, page_height
                )

                # Also check proximity threshold
                boundary_dist = self._calculate_boundary_distance(
                    caption.bbox, parent.bbox
                )

                if boundary_dist <= self.config.caption_distance_threshold:
                    if distance < best_distance:
                        best_distance = distance
                        best_parent = parent

            if best_parent is not None:
                caption.parent_index = best_parent.index
                # Position caption just after parent
                caption.sort_key = best_parent.sort_key + 0.1

    def _label_aware_sort_key(self, elem: ElementWithOrder) -> Tuple:
        """
        Create sort key with label priority for semantic ordering.

        Order: (sort_key, label_priority, y1, x1)
        """
        priority = LABEL_PRIORITY.get(elem.label, 5)
        return (elem.sort_key, priority, elem.bbox[1], elem.bbox[0])

    def _build_result(
        self,
        elements: list[ElementWithOrder],
        detections: list
    ) -> list[dict]:
        """Build final result list with reading order."""
        result = []

        for order, elem in enumerate(elements):
            det = detections[elem.index]
            result.append({
                "bbox": det.bbox if isinstance(det.bbox, list) else list(det.bbox),
                "label": det.label,
                "confidence": det.confidence,
                "reading_order": order + 1,  # 1-indexed for display
                "column_id": elem.column_id,
                "is_cross_layout": elem.is_cross_layout,
            })

        return result


# Backward compatibility: Keep the old class name as an alias
class ReadingOrderDetector(XYCutPlusPlusDetector):
    """Alias for backward compatibility."""

    def __init__(
        self,
        min_gap_ratio: float = 0.02,
        spanning_threshold: float = 0.7,
        caption_distance_threshold: float = 100,
    ):
        config = XYCutPlusPlusConfig(
            min_gap_ratio=min_gap_ratio,
            caption_distance_threshold=caption_distance_threshold,
        )
        super().__init__(config)


def sort_detections_by_reading_order(
    detections: list,
    page_width: int,
    page_height: int,
) -> list[dict]:
    """
    Convenience function to sort detections by reading order using XY-Cut++.

    Args:
        detections: List of Detection objects
        page_width: Page width in pixels
        page_height: Page height in pixels

    Returns:
        List of dicts with bbox, label, confidence, reading_order, column_id
    """
    detector = XYCutPlusPlusDetector()
    return detector.detect_reading_order(detections, page_width, page_height)


# Global instance for reuse
reading_order_detector = XYCutPlusPlusDetector()
