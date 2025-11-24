from enum import Enum
import logging

from wallets.implementations.polymarket.PolymarketTranslator import PolymarketTranslator

logger = logging.getLogger(__name__)

_translator_instances = {}


class PlatformRegistry(Enum):
    POLYMARKET = "polymarket"
    
    def getTranslator(self):
        if self not in _translator_instances:
            _translator_instances[self] = self._createTranslator()
        return _translator_instances[self]
    
    def _createTranslator(self):
        if self == PlatformRegistry.POLYMARKET:
            return PolymarketTranslator()
        raise NotImplementedError(f"Translator not implemented for: {self.value}")
    
    @classmethod
    def fromString(cls, platformName: str):
        platformName = platformName.lower()
        for platform in cls:
            if platform.value == platformName:
                return platform
        raise ValueError(f"Unsupported platform: {platformName}")
    
    @classmethod
    def getSupportedPlatforms(cls):
        return [platform.value for platform in cls]
