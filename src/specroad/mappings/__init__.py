"""Passive exchange rules and external registries; no import or write authority."""
from .exchange import (ExchangeMapping, ExternalIdentityRegistry, MappingError,
                       select_mapping, select_registries)

__all__ = ("ExchangeMapping", "ExternalIdentityRegistry", "MappingError",
           "select_mapping", "select_registries")
