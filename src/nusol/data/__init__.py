"""Data adapter layer — read and standardize different data sources."""

from nusol.data.base import DataAdapterBase
from nusol.data.fndds import FNDDSDataAdapter
from nusol.data.sr_legacy import SRLegacyDataAdapter
from nusol.data.foundation import FoundationFoodsAdapter
from nusol.data.branded import BrandedDataAdapter

__all__ = [
    "DataAdapterBase",
    "FNDDSDataAdapter",
    "SRLegacyDataAdapter",
    "FoundationFoodsAdapter",
    "BrandedDataAdapter",
]
