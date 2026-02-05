"""Hierarchical chunker that respects markdown structure and layout detection."""

import hashlib
import re
from dataclasses import dataclass, field
from typing import Literal

from models.chunk import Chunk
from config.settings import settings


@dataclass
class MarkdownNode:
    """Represents a node in the markdown document tree."""

    level: int  # 0=root, 1=h1, 2=h2, etc.
    heading: str | None = None
    content: str = ""
    children: list["MarkdownNode"] = field(default_factory=list)
    start_line: int = 0
    end_line: int = 0
    node_type: Literal["root", "heading", "paragraph", "table", "list", "figure", "code"] = "paragraph"


@dataclass
class LayoutBox:
    """Represents a layout detection bounding box."""

    label: str  # title, text, table, figure, list, etc.
    bbox: list[float]  # [x1, y1, x2, y2]
    page: int
    text: str | None = None


class HierarchicalChunker:
    """Creates chunks that respect markdown structure and layout detection boxes."""

    def __init__(
        self,
        max_chunk_size: int | None = None,
        min_chunk_size: int = 100,
    ):
        self.max_chunk_size = max_chunk_size or settings.max_chunk_size
        self.min_chunk_size = min_chunk_size
        self._chunk_index = 0

    def chunk_document(
        self,
        markdown: str,
        layout_data: list[dict] | None,
        document_id: str,
        file_name: str = "",
        detected_doc_type: str = "unknown",
        entities: dict | None = None,
    ) -> list[Chunk]:
        """
        Create hierarchical chunks from markdown and optional layout data.

        Args:
            markdown: The markdown content to chunk
            layout_data: Optional layout detection results with bounding boxes
            document_id: Parent document ID
            file_name: Original file name for context
            detected_doc_type: Document type for context
            entities: Document-level entities for context

        Returns:
            List of Chunk objects with parent-child relationships
        """
        self._chunk_index = 0
        entities = entities or {}

        # Parse markdown into tree structure
        root = self._parse_markdown_tree(markdown)

        # Parse layout boxes if available
        layout_boxes = self._parse_layout_data(layout_data) if layout_data else []

        # Create chunks from tree
        chunks = self._tree_to_chunks(
            root,
            document_id=document_id,
            file_name=file_name,
            detected_doc_type=detected_doc_type,
            entities=entities,
            layout_boxes=layout_boxes,
        )

        # Establish inter-chunk navigation links
        for i in range(len(chunks)):
            if i > 0:
                chunks[i].prev_chunk_id = chunks[i - 1].id
            if i < len(chunks) - 1:
                chunks[i].next_chunk_id = chunks[i + 1].id

        return chunks

    def _parse_markdown_tree(self, markdown: str) -> MarkdownNode:
        """Parse markdown into a tree structure based on headings."""
        root = MarkdownNode(level=0, node_type="root")
        lines = markdown.split("\n")

        # Stack to track current position in hierarchy
        stack: list[MarkdownNode] = [root]
        current_content: list[str] = []
        content_start_line = 0
        in_code_block = False
        in_table = False

        for i, line in enumerate(lines):
            # Track code blocks
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                current_content.append(line)
                continue

            if in_code_block:
                current_content.append(line)
                continue

            # Detect tables
            if line.strip().startswith("|") and not in_table:
                # Flush current content before table
                if current_content:
                    self._flush_content(stack[-1], current_content, content_start_line, i - 1)
                    current_content = []
                in_table = True
                content_start_line = i

            if in_table:
                if not line.strip().startswith("|") and line.strip():
                    # End of table
                    self._flush_content(stack[-1], current_content, content_start_line, i - 1, "table")
                    current_content = []
                    in_table = False
                    content_start_line = i
                else:
                    current_content.append(line)
                    continue

            # Check for heading
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading_match:
                # Flush accumulated content
                if current_content:
                    self._flush_content(stack[-1], current_content, content_start_line, i - 1)
                    current_content = []

                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()

                # Create new heading node
                new_node = MarkdownNode(
                    level=level,
                    heading=heading_text,
                    node_type="heading",
                    start_line=i,
                )

                # Pop stack until we find appropriate parent
                while len(stack) > 1 and stack[-1].level >= level:
                    stack.pop()

                # Add as child of current stack top
                stack[-1].children.append(new_node)
                stack.append(new_node)
                content_start_line = i + 1
            else:
                # Check for list items
                if re.match(r"^\s*[-*+]\s+", line) or re.match(r"^\s*\d+\.\s+", line):
                    if not current_content or not self._is_list_content("\n".join(current_content)):
                        if current_content:
                            self._flush_content(stack[-1], current_content, content_start_line, i - 1)
                            current_content = []
                            content_start_line = i

                current_content.append(line)

        # Flush remaining content
        if current_content:
            node_type = "table" if in_table else ("list" if self._is_list_content("\n".join(current_content)) else "paragraph")
            self._flush_content(stack[-1], current_content, content_start_line, len(lines) - 1, node_type)

        return root

    def _is_list_content(self, content: str) -> bool:
        """Check if content is primarily list items."""
        lines = [l for l in content.strip().split("\n") if l.strip()]
        if not lines:
            return False
        list_lines = sum(1 for l in lines if re.match(r"^\s*[-*+]\s+", l) or re.match(r"^\s*\d+\.\s+", l))
        return list_lines > len(lines) / 2

    def _flush_content(
        self,
        parent: MarkdownNode,
        content_lines: list[str],
        start_line: int,
        end_line: int,
        node_type: str = "paragraph",
    ) -> None:
        """Add accumulated content as a child node."""
        content = "\n".join(content_lines).strip()
        if not content:
            return

        # Detect figures
        if "![" in content or "<img" in content.lower():
            node_type = "figure"

        # Detect code blocks
        if content.startswith("```"):
            node_type = "code"

        child = MarkdownNode(
            level=parent.level + 1,
            content=content,
            node_type=node_type,
            start_line=start_line,
            end_line=end_line,
        )
        parent.children.append(child)

    def _parse_layout_data(self, layout_data: list[dict]) -> list[LayoutBox]:
        """Parse layout detection data into LayoutBox objects."""
        boxes = []
        for item in layout_data:
            if isinstance(item, dict):
                # Handle both flat and nested structures
                if "regions" in item:
                    # Per-page format
                    page_num = item.get("page", 0)
                    for region in item.get("regions", []):
                        boxes.append(LayoutBox(
                            label=region.get("label", "text"),
                            bbox=region.get("bbox", [0, 0, 0, 0]),
                            page=page_num,
                            text=region.get("text"),
                        ))
                else:
                    # Flat format
                    boxes.append(LayoutBox(
                        label=item.get("label", "text"),
                        bbox=item.get("bbox", [0, 0, 0, 0]),
                        page=item.get("page", 0),
                        text=item.get("text"),
                    ))
        return boxes

    def _tree_to_chunks(
        self,
        node: MarkdownNode,
        document_id: str,
        file_name: str,
        detected_doc_type: str,
        entities: dict,
        layout_boxes: list[LayoutBox],
        parent_chunk_id: str | None = None,
        heading_path: list[str] | None = None,
    ) -> list[Chunk]:
        """Convert markdown tree to chunks with hierarchy."""
        chunks = []
        heading_path = heading_path or []

        # Process heading nodes
        if node.heading:
            new_heading_path = heading_path + [node.heading]

            # Create chunk for heading itself if there's content under it
            if node.children or node.content:
                chunk = self._create_chunk(
                    document_id=document_id,
                    text=node.heading,
                    content_type=self._get_content_type(node.level, node.node_type),
                    hierarchy_level=node.level,
                    parent_chunk_id=parent_chunk_id,
                    heading_path=" > ".join(new_heading_path),
                    file_name=file_name,
                    detected_doc_type=detected_doc_type,
                    entities=entities,
                    layout_label=self._find_layout_label(node, layout_boxes),
                )
                chunks.append(chunk)
                parent_chunk_id = chunk.id
        else:
            new_heading_path = heading_path

        # Process content
        if node.content:
            # Split large content if needed
            content_chunks = self._split_content(
                node.content,
                node.level,
                node.node_type,
            )

            for content in content_chunks:
                chunk = self._create_chunk(
                    document_id=document_id,
                    text=content,
                    content_type=self._get_content_type(node.level, node.node_type),
                    hierarchy_level=node.level,
                    parent_chunk_id=parent_chunk_id,
                    heading_path=" > ".join(new_heading_path) if new_heading_path else None,
                    file_name=file_name,
                    detected_doc_type=detected_doc_type,
                    entities=entities,
                    layout_label=self._find_layout_label(node, layout_boxes),
                )
                chunks.append(chunk)

        # Process children
        for child in node.children:
            child_chunks = self._tree_to_chunks(
                child,
                document_id=document_id,
                file_name=file_name,
                detected_doc_type=detected_doc_type,
                entities=entities,
                layout_boxes=layout_boxes,
                parent_chunk_id=parent_chunk_id,
                heading_path=new_heading_path,
            )
            chunks.extend(child_chunks)

        return chunks

    def _split_content(
        self,
        content: str,
        level: int,
        node_type: str,
    ) -> list[str]:
        """Split content into chunks if it exceeds max size."""
        if len(content) <= self.max_chunk_size:
            return [content]

        chunks = []

        # Split by paragraphs first
        paragraphs = re.split(r"\n\n+", content)

        current_chunk = ""
        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 <= self.max_chunk_size:
                current_chunk += ("\n\n" if current_chunk else "") + para
            else:
                if current_chunk:
                    chunks.append(current_chunk)

                # Handle paragraphs larger than max size
                if len(para) > self.max_chunk_size:
                    # Split by sentences
                    sentences = re.split(r"(?<=[.!?])\s+", para)
                    current_chunk = ""
                    for sentence in sentences:
                        if len(current_chunk) + len(sentence) + 1 <= self.max_chunk_size:
                            current_chunk += (" " if current_chunk else "") + sentence
                        else:
                            if current_chunk:
                                chunks.append(current_chunk)
                            current_chunk = sentence
                else:
                    current_chunk = para

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _get_content_type(
        self,
        level: int,
        node_type: str,
    ) -> str:
        """Map markdown node type to chunk content type."""
        if node_type == "heading":
            if level == 1:
                return "title"
            return "section_header"
        if node_type == "table":
            return "table"
        if node_type == "list":
            return "list"
        if node_type == "figure":
            return "figure"
        return "paragraph"

    def _find_layout_label(
        self,
        node: MarkdownNode,
        layout_boxes: list[LayoutBox],
    ) -> str | None:
        """Find matching layout box label for a markdown node."""
        if not layout_boxes:
            return None

        # Try to match by text content
        node_text = (node.heading or node.content or "").lower()[:100]
        if not node_text:
            return None

        for box in layout_boxes:
            if box.text and node_text in box.text.lower():
                return box.label

        return None

    def _create_chunk(
        self,
        document_id: str,
        text: str,
        content_type: str,
        hierarchy_level: int,
        parent_chunk_id: str | None,
        heading_path: str | None,
        file_name: str,
        detected_doc_type: str,
        entities: dict,
        layout_label: str | None = None,
        bbox: list[float] | None = None,
        page: int | None = None,
    ) -> Chunk:
        """Create a chunk with contextualized text."""
        chunk_id = self._generate_chunk_id(document_id, self._chunk_index)
        self._chunk_index += 1

        # Build contextualized text
        context_parts = []
        if file_name:
            context_parts.append(f"Document: {file_name}")
        if detected_doc_type and detected_doc_type != "unknown":
            context_parts.append(f"Type: {detected_doc_type}")
        if heading_path:
            context_parts.append(f"Section: {heading_path}")
        if entities:
            top_entities = list(entities.items())[:5]
            if top_entities:
                entity_str = ", ".join(f"{k}: {v}" for k, v in top_entities)
                context_parts.append(f"Key info: {entity_str}")

        context = "\n".join(context_parts)
        contextualized_text = f"{context}\n\n{text}" if context else text

        return Chunk(
            id=chunk_id,
            document_id=document_id,
            text=text,
            contextualized_text=contextualized_text,
            content_type=content_type,
            chunk_index=self._chunk_index - 1,
            parent_chunk_id=parent_chunk_id,
            hierarchy_level=hierarchy_level,
            heading_path=heading_path,
            layout_label=layout_label,
            bbox=bbox,
            page=page,
            entities=entities,
        )

    def _generate_chunk_id(self, document_id: str, chunk_index: int) -> str:
        """Generate unique chunk ID."""
        combined = f"{document_id}:{chunk_index}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]


# Global instance
hierarchical_chunker = HierarchicalChunker()
