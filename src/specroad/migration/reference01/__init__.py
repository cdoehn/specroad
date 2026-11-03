"""Explicit reference source reading, separate from productive migration paths."""
from .reader import (SourceError, SourceOriginal, SourceInventory, inventory_bytes,
                     inventory_project, CONTRACT_ID, CONTRACT_VERSION, READER_ID)

__all__ = ('SourceError', 'SourceOriginal', 'SourceInventory', 'inventory_bytes',
           'inventory_project', 'CONTRACT_ID', 'CONTRACT_VERSION', 'READER_ID')
