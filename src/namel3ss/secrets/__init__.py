"""
Secrets subsystem.
"""

from .models import Secret
from .manager import SecretsManager

__all__ = ["Secret", "SecretsManager"]
