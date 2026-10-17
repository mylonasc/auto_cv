"""One set of application defaults and explicit model/policy dependencies."""

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .analysis import SelectionPolicy

PROVIDER_DEFAULTS = {"ollama": "gemma4:31b", "google": "models/gemini-2.5-flash-preview-05-20"}


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, validate_assignment=True)


class ModelConfig(ConfigModel):
    provider: Literal["ollama", "google"] = "ollama"
    model: str = PROVIDER_DEFAULTS["ollama"]
    config: dict[str, Any] | None = None


class RewritePolicy(ConfigModel):
    max_section_items_keep: int = 5
    min_section_items_keep: int = 1
    min_relevance_score: int = 4

    @model_validator(mode="after")
    def valid_policy(self):
        self.selection_policy()
        return self

    def selection_policy(self) -> SelectionPolicy:
        return SelectionPolicy(min_items=self.min_section_items_keep,
                               max_items=self.max_section_items_keep, min_score=self.min_relevance_score)


class AnalysisPolicy(ConfigModel):
    max_section_parse_retries: int = Field(default=3, deprecated=True,
        description="Reserved legacy setting; structured-output parsing does not use an application retry loop.")


class OutputsConfig(ConfigModel):
    include_cover_letter: bool = Field(default=False, description="CLI-only output; HTTP jobs reject this option.")
    render_pdf: bool = True
    include_latex: bool = True
    include_scoring_comments: bool = True


class BackendConfig(ConfigModel):
    analysis_model: ModelConfig = Field(default_factory=ModelConfig)
    statement_editor_model: ModelConfig = Field(default_factory=ModelConfig)
    cover_letter_editor_model: ModelConfig = Field(default_factory=ModelConfig)
    rewrite_policy: RewritePolicy = Field(default_factory=RewritePolicy)
    analysis_policy: AnalysisPolicy = Field(default_factory=AnalysisPolicy)
    outputs: OutputsConfig = Field(default_factory=OutputsConfig)
    concurrency_limit: int = Field(default=5, ge=1)


def build_model(config: ModelConfig):
    from .models import ModelFactory
    return ModelFactory(model_provider=config.provider, model_str=config.model,
                        config=config.config).get_llm_model()


def public_config(config: BackendConfig) -> BackendConfig:
    """Persist effective model settings, never request-supplied credentials.

    Runtime model construction still receives the original config. Subsequent
    rescoring resolves credentials through the provider's environment/key setup.
    """
    def clean(value):
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                normalized = ''.join(character.lower() for character in key if character.isalnum())
                if normalized.endswith('apikey') or normalized in {
                    'token', 'accesstoken', 'accesskey', 'authorization', 'password', 'secret',
                }:
                    continue
                result[key] = clean(item)
            return result
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value
    return BackendConfig.model_validate(clean(config.model_dump()))
