from abc import ABC, abstractmethod
from typing import List, Optional

from vllm.config import TokenizerPoolConfig
from vllm.lora.request import LoRARequest
from vllm.transformers_utils.tokenizer import AnyTokenizer


class BaseTokenizerGroup(ABC):
    """A group of tokenizers that can be used for LoRA adapters."""

    @classmethod
    @abstractmethod
    def from_config(
        cls, tokenizer_pool_config: Optional[TokenizerPoolConfig], **init_kwargs
    ) -> "BaseTokenizerGroup":
        pass

    @abstractmethod
    def ping(self) -> bool:
        """Check if the tokenizer group is alive."""
        pass

    @abstractmethod
    def get_max_input_len(
        self,
        lora_request: Optional[LoRARequest] = None,
    ) -> Optional[int]:
        """Get the maximum input length for the LoRA request."""
        pass

    @abstractmethod
    def encode(
        self,
        prompt: str,
        request_id: Optional[str] = None,
        lora_request: Optional[LoRARequest] = None,
    ) -> List[int]:
        """Encode a prompt using the tokenizer group."""
        pass

    @abstractmethod
    async def encode_async(
        self,
        prompt: str,
        request_id: Optional[str] = None,
        lora_request: Optional[LoRARequest] = None,
    ) -> List[int]:
        """Encode a prompt using the tokenizer group."""
        pass

    @abstractmethod
    def get_lora_tokenizer(
        self,
        lora_request: Optional[LoRARequest] = None,
    ) -> AnyTokenizer:
        """Get a tokenizer for a LoRA request."""
        pass

    @abstractmethod
    async def get_lora_tokenizer_async(
        self,
        lora_request: Optional[LoRARequest] = None,
    ) -> AnyTokenizer:
        """Get a tokenizer for a LoRA request."""
        pass

    def check_health(self):
        """Raise exception if the tokenizer group is unhealthy."""
        return
