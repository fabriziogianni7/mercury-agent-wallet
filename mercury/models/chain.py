"""Chain-related domain models."""

from pydantic import BaseModel, ConfigDict, Field


class ChainReference(BaseModel):
    """Small chain reference suitable for graph state and API boundaries."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    chain_id: int = Field(gt=0)


class ChainConfig(ChainReference):
    """Static metadata for a supported EVM chain."""

    native_symbol: str = Field(min_length=1)
    rpc_secret_ref: str = Field(min_length=1)
    block_explorer_url: str = Field(min_length=1)

    def to_reference(self) -> ChainReference:
        """Return a compact chain reference."""

        return ChainReference(name=self.name, chain_id=self.chain_id)
