"""Impressão ACBr independente do componente fiscal e de Node.js."""
from .client import Impressora, PROTOCOL_VERSION, SOURCE_REVISION, TIPOS_IMPRESSORA, criar_impressora, criarImpressora
from .errors import ErroAcbrImpressora
from .installer import instalar_runtime
from .runtime import RUNTIME_VERSION

__version__ = "0.1.0"
__all__ = ["Impressora", "ErroAcbrImpressora", "criar_impressora", "criarImpressora",
           "PROTOCOL_VERSION", "SOURCE_REVISION", "TIPOS_IMPRESSORA", "__version__"]
__all__.append("instalar_runtime")
__all__.append("RUNTIME_VERSION")
