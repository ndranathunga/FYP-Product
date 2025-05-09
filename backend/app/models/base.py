from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseModelInterface(ABC):
    @abstractmethod
    def predict(self, text: str, prompt: Optional[str] = None) -> Any:
        pass

class SentimentModelInterface(BaseModelInterface):
    @abstractmethod
    def predict(self, text: str, prompt: Optional[str] = None) -> Dict[str, Any]:
        pass

class LanguageModelInterface(BaseModelInterface):
    @abstractmethod
    def predict(self, text: str, prompt: Optional[str] = None) -> Dict[str, Any]:
        pass
