"""VRAM budget management and model profile tracking."""

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

VRAM_BUDGET_MB: int = int(os.getenv("VRAM_BUDGET_MB", "7000"))

MODEL_PROFILES: dict[str, dict[str, Any]] = {
    "llama3.2:3b": {
        "vram_mb": 2400,
        "ollama_tag": "llama3.2:3b-instruct-q4_0",
        "use": "default_mvp",
    },
    "llama3.2:8b": {
        "vram_mb": 5200,
        "ollama_tag": "llama3.2:8b-instruct-q4_0",
        "use": "post_mvp_cloud",
    },
}

DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL_KEY", "llama3.2:3b")


class ModelNotLoadedError(Exception):
    """Raised when no model is currently loaded."""
    pass


class VRAMBudgetExceededError(Exception):
    """Raised when loading a model would exceed the VRAM budget."""
    pass


@dataclass
class ModelStatus:
    """Status of a loaded model."""
    model_key: str
    ollama_tag: str
    vram_mb: int
    is_loaded: bool


@dataclass
class ModelManager:
    """Tracks VRAM budget and which model is currently active."""

    vram_budget_mb: int = VRAM_BUDGET_MB
    _active_model_key: str | None = None
    _reserved_vram_mb: int = 0
    # Additional VRAM reserved for non-LLM usage (Whisper, CUDA overhead)
    _system_reserved_mb: int = field(default=1800)

    @property
    def active_model(self) -> str:
        """Return the Ollama tag of the active model.

        Raises:
            ModelNotLoadedError: if no model is loaded.
        """
        if self._active_model_key is None:
            raise ModelNotLoadedError("No model is currently loaded")
        profile = MODEL_PROFILES[self._active_model_key]
        return profile["ollama_tag"]

    @property
    def active_model_key(self) -> str | None:
        """Return the key of the active model, or None."""
        return self._active_model_key

    @property
    def available_vram_mb(self) -> int:
        """VRAM available for LLM after system reservations."""
        return self.vram_budget_mb - self._system_reserved_mb - self._reserved_vram_mb

    def get_profile(self, model_key: str) -> dict[str, Any]:
        """Get the profile for a model key.

        Raises:
            ValueError: if model_key is unknown.
        """
        if model_key not in MODEL_PROFILES:
            raise ValueError(
                f"Unknown model '{model_key}'. "
                f"Available: {list(MODEL_PROFILES.keys())}"
            )
        return MODEL_PROFILES[model_key]

    def can_load(self, model_key: str) -> bool:
        """Check if a model can fit within the VRAM budget."""
        profile = self.get_profile(model_key)
        required = profile["vram_mb"]
        available = self.vram_budget_mb - self._system_reserved_mb
        return required <= available

    def load(self, model_key: str | None = None) -> ModelStatus:
        """Mark a model as loaded (tracks budget, doesn't call Ollama).

        Args:
            model_key: Model to load. Defaults to DEFAULT_MODEL.

        Raises:
            VRAMBudgetExceededError: if model doesn't fit.
        """
        model_key = model_key or DEFAULT_MODEL
        profile = self.get_profile(model_key)

        if not self.can_load(model_key):
            raise VRAMBudgetExceededError(
                f"Model '{model_key}' requires {profile['vram_mb']}MB but only "
                f"{self.available_vram_mb}MB available "
                f"(budget={self.vram_budget_mb}MB, system={self._system_reserved_mb}MB)"
            )

        # Unload current model first
        if self._active_model_key is not None:
            self.unload()

        self._active_model_key = model_key
        self._reserved_vram_mb = profile["vram_mb"]
        logger.info(
            "Model '%s' loaded (tag=%s, vram=%dMB)",
            model_key, profile["ollama_tag"], profile["vram_mb"],
        )

        return ModelStatus(
            model_key=model_key,
            ollama_tag=profile["ollama_tag"],
            vram_mb=profile["vram_mb"],
            is_loaded=True,
        )

    def unload(self) -> None:
        """Unload the current model."""
        if self._active_model_key:
            logger.info("Model '%s' unloaded", self._active_model_key)
        self._active_model_key = None
        self._reserved_vram_mb = 0

    def status(self) -> dict[str, Any]:
        """Return current model and VRAM status for /health endpoint."""
        return {
            "vram_budget_mb": self.vram_budget_mb,
            "system_reserved_mb": self._system_reserved_mb,
            "model_reserved_mb": self._reserved_vram_mb,
            "available_mb": self.available_vram_mb,
            "active_model": self._active_model_key,
            "active_model_tag": (
                MODEL_PROFILES[self._active_model_key]["ollama_tag"]
                if self._active_model_key
                else None
            ),
        }
