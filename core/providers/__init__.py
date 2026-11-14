"""翻譯 Provider 抽象介面與實作。"""

from .base import BaseProvider
from .google_web_method import GoogleWebMethod
from .manager import ProviderManager

__all__ = ["BaseProvider", "GoogleWebMethod", "ProviderManager"]
