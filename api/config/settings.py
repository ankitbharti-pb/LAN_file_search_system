"""Application configuration using Pydantic Settings."""

from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Paths
    watch_folder: Path = Path("./documents")
    data_folder: Path = Path("./data")

    # LLM Configuration
    llm_provider: Literal["openai", "gemini"] = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    # VLM Configuration
    vlm_provider: Literal["ollama", "huggingface"] = "ollama"
    use_vlm_extraction: bool = True
    vlm_fallback_ocr: bool = True

    # Ollama VLM settings (local inference)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3-vl:8b"
    ollama_timeout: float = 120.0

    # HuggingFace VLM settings (cloud inference)
    huggingface_api_key: str = ""
    huggingface_vlm_model: str = "Qwen/Qwen2.5-VL-32B-Instruct:fireworks-ai"
    huggingface_timeout: float = 60.0

    # Box Filtering Configuration (for layout detection post-processing)
    box_filter_enabled: bool = True
    box_filter_containment_threshold: float = 0.85  # Remove if 85%+ contained
    box_filter_iou_threshold: float = 0.5  # Suppress if IoU > 50%
    box_filter_class_agnostic: bool = True  # Apply across different classes
    box_filter_use_soft_nms: bool = True  # Use Soft-NMS instead of hard removal
    box_filter_soft_nms_sigma: float = 0.3  # Gaussian sigma for Soft-NMS

    # Embedding Configuration (upgraded for better retrieval)
    embedding_model: str = "all-mpnet-base-v2"  # MTEB 61.0 vs 56.3 for MiniLM
    embedding_dimension: int = 768

    # Chunking Configuration (larger chunks for better context)
    chunk_size: int = 1500  # ~300 tokens for better context
    chunk_overlap: int = 200  # 13% overlap
    max_chunk_size: int = 2500  # Allow larger semantic chunks
    enable_semantic_chunking: bool = True
    semantic_similarity_threshold: float = 0.80  # Higher threshold for cleaner splits

    # Cache Configuration
    cache_ttl_seconds: int = 3600
    cache_similarity_threshold: float = 0.92
    cache_max_entries: int = 2000

    # Search Configuration
    search_top_k: int = 10
    hybrid_alpha: float = 0.5  # Weight for vector vs keyword search (legacy)

    # HyDE Query Expansion (improves retrieval for complex queries)
    enable_hyde: bool = True
    hyde_num_hypotheticals: int = 1  # Number of hypothetical documents to generate

    # Enrichment Configuration
    enrichment_batch_size: int = 5
    questions_per_chunk: int = 3

    # Multi-Vector Retrieval Weights (tuned for better embedding model)
    multi_vector_weights_main: float = 0.40  # Increased - better embeddings
    multi_vector_weights_question: float = 0.20
    multi_vector_weights_bm25: float = 0.25  # Keyword matching still important
    multi_vector_weights_summary: float = 0.15

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # Database
    database_path: Path = Path("./data/sqlite/metadata.db")

    @property
    def faiss_index_path(self) -> Path:
        return self.data_folder / "faiss" / "index.faiss"

    @property
    def faiss_id_map_path(self) -> Path:
        return self.data_folder / "faiss" / "id_map.json"

    @property
    def bm25_index_path(self) -> Path:
        return self.data_folder / "bm25" / "index.pkl"

    @property
    def cache_path(self) -> Path:
        return self.data_folder / "cache" / "semantic_cache.pkl"

    # Multi-vector index paths
    @property
    def main_vector_index_path(self) -> Path:
        return self.data_folder / "faiss" / "main_index.faiss"

    @property
    def main_vector_id_map_path(self) -> Path:
        return self.data_folder / "faiss" / "main_id_map.json"

    @property
    def summary_vector_index_path(self) -> Path:
        return self.data_folder / "faiss" / "summary_index.faiss"

    @property
    def summary_vector_id_map_path(self) -> Path:
        return self.data_folder / "faiss" / "summary_id_map.json"

    @property
    def question_vector_index_path(self) -> Path:
        return self.data_folder / "faiss" / "question_index.faiss"

    @property
    def question_vector_id_map_path(self) -> Path:
        return self.data_folder / "faiss" / "question_id_map.json"

    @property
    def multi_vector_weights(self) -> dict[str, float]:
        return {
            "main_vector": self.multi_vector_weights_main,
            "question_vector": self.multi_vector_weights_question,
            "bm25": self.multi_vector_weights_bm25,
            "summary_vector": self.multi_vector_weights_summary,
        }


# Global settings instance
settings = Settings()
