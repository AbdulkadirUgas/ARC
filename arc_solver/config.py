"""Configuration settings for the Neuro-Symbolic ARC Solver."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv
load_dotenv()

@dataclass
class Config:
    """Configuration for the ARC Solver."""

    # Model Configuration
    MODEL_ID: str = os.getenv("MODEL_ID", "deepseek-reasoner")
    API_KEY: str = os.getenv("API_KEY", "")
    API_BASE_URL: str = os.getenv("API_BASE_URL", "https://api.deepseek.com")

    # Solver Parameters
    MAX_RETRIES: int = 5
    TIMEOUT_SECONDS: int = 30
    TEMPERATURE: float = 0.7

    # Execution Safety
    SANDBOX_TIMEOUT: int = 10
    MAX_CODE_LENGTH: int = 2000

    # Local LLM settings (for vLLM or similar)
    USE_LOCAL_LLM: bool = bool(os.getenv("USE_LOCAL_LLM", "False"))
    LOCAL_LLM_BASE_URL: str = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:8001/v1")
    LOCAL_LLM_MODEL: str = os.getenv("LOCAL_LLM_MODEL", "Qwen/Qwen3-14B")
    LOCAL_LLM_API_KEY: str = os.getenv("LOCAL_LLM_API_KEY", "")

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.API_KEY and not self.USE_LOCAL_LLM and self.MODEL_ID != "mock":
            import warnings

            warnings.warn(
                "API_KEY not set. Using mock mode. Set via environment variable.",
                UserWarning,
            )


# Global config instance
config = Config()
