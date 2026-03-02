"""Base model for all SDD models."""

from pydantic import BaseModel, ConfigDict


class SDDBaseModel(BaseModel):
    """Base model with strict validation enabled."""

    model_config = ConfigDict(validate_assignment=True)
