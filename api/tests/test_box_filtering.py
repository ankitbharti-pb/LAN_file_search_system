"""Tests for box filtering module."""

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest


# Direct module import to avoid package __init__.py dependencies
def _import_module_direct(module_name: str, file_path: Path):
    """Import a module directly from its file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Import box_filtering module directly
_api_dir = Path(__file__).parent.parent
_box_filtering = _import_module_direct(
    "box_filtering_test",
    _api_dir / "processing" / "box_filtering.py"
)

BoxFilter = _box_filtering.BoxFilter
BoxFilterConfig = _box_filtering.BoxFilterConfig
FilterStats = _box_filtering.FilterStats
calculate_iou = _box_filtering.calculate_iou
calculate_area = _box_filtering.calculate_area
calculate_intersection_area = _box_filtering.calculate_intersection_area
get_containment_ratio = _box_filtering.get_containment_ratio


@dataclass
class Detection:
    """Mock Detection class matching layout_detector.Detection for testing."""
    bbox: list[float]
    label: str
    confidence: float
    reading_order: int = 0
    column_id: int = 0
    is_cross_layout: bool = False


class TestGeometricFunctions:
    """Test geometric utility functions."""

    def test_calculate_area_valid_box(self):
        """Test area calculation for a valid box."""
        assert calculate_area([0, 0, 10, 10]) == 100
        assert calculate_area([5, 5, 15, 25]) == 200

    def test_calculate_area_zero_box(self):
        """Test area calculation for zero-size boxes."""
        assert calculate_area([0, 0, 0, 0]) == 0
        assert calculate_area([5, 5, 5, 5]) == 0

    def test_calculate_area_invalid_box(self):
        """Test area calculation for inverted boxes (returns 0)."""
        assert calculate_area([10, 10, 0, 0]) == 0

    def test_calculate_intersection_area_no_overlap(self):
        """Test intersection area when boxes don't overlap."""
        bbox1 = [0, 0, 10, 10]
        bbox2 = [20, 20, 30, 30]
        assert calculate_intersection_area(bbox1, bbox2) == 0.0

    def test_calculate_intersection_area_partial_overlap(self):
        """Test intersection area with partial overlap."""
        bbox1 = [0, 0, 10, 10]
        bbox2 = [5, 5, 15, 15]
        # Intersection is [5,5,10,10] = 5*5 = 25
        assert calculate_intersection_area(bbox1, bbox2) == 25.0

    def test_calculate_intersection_area_full_overlap(self):
        """Test intersection area when one box contains another."""
        outer = [0, 0, 20, 20]
        inner = [5, 5, 15, 15]
        # Intersection is the inner box = 10*10 = 100
        assert calculate_intersection_area(outer, inner) == 100.0

    def test_calculate_iou_no_overlap(self):
        """Test IoU when boxes don't overlap."""
        bbox1 = [0, 0, 10, 10]
        bbox2 = [20, 20, 30, 30]
        assert calculate_iou(bbox1, bbox2) == 0.0

    def test_calculate_iou_full_overlap(self):
        """Test IoU for identical boxes."""
        bbox = [0, 0, 10, 10]
        assert calculate_iou(bbox, bbox) == 1.0

    def test_calculate_iou_partial_overlap(self):
        """Test IoU with partial overlap."""
        bbox1 = [0, 0, 10, 10]  # area = 100
        bbox2 = [5, 5, 15, 15]  # area = 100
        # intersection = 25, union = 100 + 100 - 25 = 175
        # iou = 25/175 ≈ 0.143
        iou = calculate_iou(bbox1, bbox2)
        assert abs(iou - 0.143) < 0.01

    def test_containment_ratio_fully_contained(self):
        """Test containment ratio when inner is fully inside outer."""
        inner = [2, 2, 8, 8]  # 36 area
        outer = [0, 0, 10, 10]  # 100 area
        ratio = get_containment_ratio(inner, outer)
        assert ratio == 1.0  # Fully contained

    def test_containment_ratio_partial(self):
        """Test containment ratio with partial overlap."""
        inner = [5, 5, 15, 15]  # area = 100
        outer = [0, 0, 10, 10]  # area = 100
        # intersection = 25, inner_area = 100
        ratio = get_containment_ratio(inner, outer)
        assert ratio == 0.25

    def test_containment_ratio_no_overlap(self):
        """Test containment ratio with no overlap."""
        inner = [20, 20, 30, 30]
        outer = [0, 0, 10, 10]
        ratio = get_containment_ratio(inner, outer)
        assert ratio == 0.0


class TestContainmentFiltering:
    """Test containment filtering algorithm."""

    def test_remove_text_inside_table(self):
        """Text box inside table should be removed (table has higher priority)."""
        detections = [
            Detection(bbox=[0, 0, 100, 100], label="table", confidence=0.9),
            Detection(bbox=[10, 10, 90, 90], label="text", confidence=0.8),
        ]
        box_filter = BoxFilter()
        result = box_filter.filter_detections(detections)

        assert len(result) == 1
        assert result[0].label == "table"

    def test_remove_text_inside_figure(self):
        """Text box inside figure should be removed."""
        detections = [
            Detection(bbox=[0, 0, 100, 100], label="figure", confidence=0.9),
            Detection(bbox=[10, 10, 90, 90], label="plain text", confidence=0.8),
        ]
        box_filter = BoxFilter()
        result = box_filter.filter_detections(detections)

        assert len(result) == 1
        assert result[0].label == "figure"

    def test_preserve_caption_inside_figure(self):
        """Caption inside figure should be preserved (allowed containment)."""
        detections = [
            Detection(bbox=[0, 0, 100, 100], label="figure", confidence=0.9),
            Detection(bbox=[10, 80, 90, 95], label="figure_caption", confidence=0.8),
        ]
        box_filter = BoxFilter()
        result = box_filter.filter_detections(detections)

        assert len(result) == 2  # Both preserved

    def test_preserve_caption_inside_table(self):
        """Caption inside table should be preserved."""
        detections = [
            Detection(bbox=[0, 0, 100, 100], label="table", confidence=0.9),
            Detection(bbox=[10, 5, 90, 15], label="table_caption", confidence=0.8),
        ]
        box_filter = BoxFilter()
        result = box_filter.filter_detections(detections)

        assert len(result) == 2  # Both preserved

    def test_preserve_footnote_inside_table(self):
        """Footnote inside table should be preserved."""
        detections = [
            Detection(bbox=[0, 0, 100, 100], label="table", confidence=0.9),
            Detection(bbox=[10, 85, 90, 98], label="table_footnote", confidence=0.8),
        ]
        box_filter = BoxFilter()
        result = box_filter.filter_detections(detections)

        assert len(result) == 2  # Both preserved

    def test_no_containment(self):
        """Non-overlapping boxes should all be preserved."""
        detections = [
            Detection(bbox=[0, 0, 50, 50], label="text", confidence=0.9),
            Detection(bbox=[60, 60, 100, 100], label="text", confidence=0.8),
        ]
        box_filter = BoxFilter()
        result = box_filter.filter_detections(detections)

        assert len(result) == 2


class TestIoUSuppression:
    """Test IoU-based suppression."""

    def test_suppress_overlapping_same_class(self):
        """Overlapping boxes of same class - keep higher confidence."""
        detections = [
            Detection(bbox=[0, 0, 50, 50], label="text", confidence=0.9),
            Detection(bbox=[10, 10, 60, 60], label="text", confidence=0.7),
        ]
        config = BoxFilterConfig(iou_threshold=0.3)
        box_filter = BoxFilter(config)
        result = box_filter.filter_detections(detections)

        assert len(result) == 1
        assert result[0].confidence == 0.9

    def test_suppress_overlapping_different_class_agnostic(self):
        """Overlapping boxes of different classes with class-agnostic NMS."""
        detections = [
            Detection(bbox=[0, 0, 50, 50], label="table", confidence=0.9),
            Detection(bbox=[5, 5, 55, 55], label="text", confidence=0.95),
        ]
        config = BoxFilterConfig(iou_threshold=0.3, class_agnostic_nms=True)
        box_filter = BoxFilter(config)
        result = box_filter.filter_detections(detections)

        # Table has higher priority (2) than text (3), so table should be kept
        assert len(result) == 1
        assert result[0].label == "table"

    def test_no_suppress_different_class_not_agnostic(self):
        """Overlapping boxes of different classes without class-agnostic NMS."""
        detections = [
            Detection(bbox=[0, 0, 50, 50], label="table", confidence=0.9),
            Detection(bbox=[5, 5, 55, 55], label="text", confidence=0.95),
        ]
        config = BoxFilterConfig(iou_threshold=0.3, class_agnostic_nms=False)
        box_filter = BoxFilter(config)
        result = box_filter.filter_detections(detections)

        # Both preserved because different classes
        assert len(result) == 2

    def test_no_suppress_below_threshold(self):
        """Boxes with IoU below threshold should not be suppressed."""
        detections = [
            Detection(bbox=[0, 0, 50, 50], label="text", confidence=0.9),
            Detection(bbox=[40, 40, 90, 90], label="text", confidence=0.8),
        ]
        config = BoxFilterConfig(iou_threshold=0.5)  # High threshold
        box_filter = BoxFilter(config)
        result = box_filter.filter_detections(detections)

        assert len(result) == 2


class TestLabelPriority:
    """Test label priority in filtering decisions."""

    def test_title_highest_priority(self):
        """Title should have highest priority."""
        detections = [
            Detection(bbox=[0, 0, 100, 30], label="title", confidence=0.8),
            Detection(bbox=[5, 5, 95, 25], label="text", confidence=0.95),
        ]
        config = BoxFilterConfig(containment_threshold=0.8)
        box_filter = BoxFilter(config)
        result = box_filter.filter_detections(detections)

        # Title has higher priority, text inside should be removed
        assert len(result) == 1
        assert result[0].label == "title"

    def test_table_beats_text(self):
        """Table should have higher priority than text."""
        detections = [
            Detection(bbox=[0, 0, 100, 100], label="table", confidence=0.7),
            Detection(bbox=[10, 10, 90, 90], label="plain text", confidence=0.9),
        ]
        box_filter = BoxFilter()
        result = box_filter.filter_detections(detections)

        assert len(result) == 1
        assert result[0].label == "table"


class TestFilterStats:
    """Test filter statistics tracking."""

    def test_stats_tracking(self):
        """Filter statistics should be tracked correctly."""
        detections = [
            Detection(bbox=[0, 0, 100, 100], label="table", confidence=0.9),
            Detection(bbox=[10, 10, 90, 90], label="text", confidence=0.8),
            Detection(bbox=[200, 200, 300, 300], label="figure", confidence=0.85),
        ]
        box_filter = BoxFilter()
        result = box_filter.filter_detections(detections)

        stats = box_filter.last_stats
        assert stats is not None
        assert stats.input_count == 3
        assert stats.output_count == 2
        assert stats.containment_removed == 1


class TestConfigOptions:
    """Test configuration options."""

    def test_disabled_filter(self):
        """When disabled, filter should return input unchanged."""
        detections = [
            Detection(bbox=[0, 0, 100, 100], label="table", confidence=0.9),
            Detection(bbox=[10, 10, 90, 90], label="text", confidence=0.8),
        ]
        config = BoxFilterConfig(enabled=False)
        box_filter = BoxFilter(config)
        result = box_filter.filter_detections(detections)

        assert len(result) == 2

    def test_custom_containment_threshold(self):
        """Custom containment threshold should be respected."""
        # Create boxes where inner is only ~56% contained in outer
        # inner: [40, 40, 90, 90] - area = 50*50 = 2500
        # outer: [0, 0, 70, 70] - area = 70*70 = 4900
        # intersection: [40, 40, 70, 70] - area = 30*30 = 900
        # containment ratio = 900/2500 = 0.36 (36% contained)
        detections = [
            Detection(bbox=[0, 0, 70, 70], label="table", confidence=0.9),
            Detection(bbox=[40, 40, 90, 90], label="text", confidence=0.8),  # ~36% contained
        ]
        # With default 0.85 threshold, the 36% contained box should NOT be removed
        config = BoxFilterConfig(containment_threshold=0.85)
        box_filter = BoxFilter(config)
        result = box_filter.filter_detections(detections)

        assert len(result) == 2

    def test_custom_iou_threshold(self):
        """Custom IoU threshold should be respected."""
        detections = [
            Detection(bbox=[0, 0, 50, 50], label="text", confidence=0.9),
            Detection(bbox=[20, 20, 70, 70], label="text", confidence=0.7),
        ]
        # With very high threshold, boxes should not be suppressed
        config = BoxFilterConfig(iou_threshold=0.9)
        box_filter = BoxFilter(config)
        result = box_filter.filter_detections(detections)

        assert len(result) == 2


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_input(self):
        """Empty input should return empty output."""
        box_filter = BoxFilter()
        result = box_filter.filter_detections([])
        assert result == []

    def test_single_detection(self):
        """Single detection should be returned unchanged."""
        detections = [
            Detection(bbox=[0, 0, 100, 100], label="text", confidence=0.9),
        ]
        box_filter = BoxFilter()
        result = box_filter.filter_detections(detections)

        assert len(result) == 1
        assert result[0] == detections[0]

    def test_zero_area_box(self):
        """Zero-area boxes should not cause errors."""
        detections = [
            Detection(bbox=[0, 0, 100, 100], label="text", confidence=0.9),
            Detection(bbox=[50, 50, 50, 50], label="text", confidence=0.8),  # Zero area
        ]
        box_filter = BoxFilter()
        # Should not raise an error
        result = box_filter.filter_detections(detections)
        assert len(result) >= 1

    def test_unknown_label(self):
        """Unknown labels should use default priority."""
        detections = [
            Detection(bbox=[0, 0, 100, 100], label="unknown_type", confidence=0.9),
            Detection(bbox=[10, 10, 90, 90], label="another_unknown", confidence=0.8),
        ]
        box_filter = BoxFilter()
        # Should not raise an error
        result = box_filter.filter_detections(detections)
        assert len(result) >= 1
