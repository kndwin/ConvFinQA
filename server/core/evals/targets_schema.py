from typing import Any

from pydantic import BaseModel, ConfigDict


class TargetSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    id: str
    approach: Any
    prompt: Any | None = None
    context_version: str
    context_hash: str
    ensemble_config: Any | None = None

    def metadata(self, model: str) -> dict[str, str]:
        metadata = {
            "target": self.id,
            "agent_approach": str(self.approach),
            "context_version": self.context_version,
            "context_hash": self.context_hash,
            "model": model,
        }
        if self.prompt is not None:
            metadata.update(
                prompt_version=self.prompt.id,
                prompt_hash=self.prompt.content_hash,
            )
        if self.ensemble_config is not None:
            reviewer_version = getattr(self.ensemble_config, "reviewer_prompt_version", None)
            reviewer_hash = getattr(self.ensemble_config, "reviewer_prompt_hash", None)
            if reviewer_version is not None:
                metadata["reviewer_prompt_version"] = reviewer_version
            if reviewer_hash is not None:
                metadata["reviewer_prompt_hash"] = reviewer_hash
        return metadata
