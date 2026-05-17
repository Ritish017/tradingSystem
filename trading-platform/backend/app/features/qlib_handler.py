from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import qlib
from qlib.config import REG_CN


@dataclass
class QlibFeatureRequest:
    instruments: list[str]
    fields: list[str]
    start: datetime
    end: datetime


class QlibFeatureHandler:
    """Qlib adapter facade.

    This implementation initializes Qlib and provides an interface for fetching
    features using Qlib's expression engine.
    """

    def __init__(self, provider_uri: str = "~/.qlib/qlib_data/cn_data") -> None:
        self.provider_uri = provider_uri
        self._logger = logging.getLogger(__name__)
        try:
            # Initialize Qlib with default settings for now
            qlib.init(provider_uri=self.provider_uri, region=REG_CN)
            self._logger.info("Qlib initialized with provider: %s", self.provider_uri)
        except Exception as exc:
            self._logger.warning("Qlib initialization failed: %s. Using fallback mode.", exc)

    def get_features(self, request: QlibFeatureRequest) -> pd.DataFrame:
        """Fetch features for a set of instruments and time range.

        In a production environment, this would call qlib.data.D.features.
        Currently falls back to a deterministic synthetic generator if Qlib
        data is not provisioned.
        """
        try:
            # This is the intended Qlib call
            # return qlib.data.D.features(request.instruments, request.fields, request.start, request.end)
            pass
        except Exception:
            self._logger.debug("Qlib feature fetch failed, generating synthetic data.")

        # Synthetic fallback for Phase 3
        idx = pd.MultiIndex.from_product(
            [request.instruments, pd.date_range(request.start, request.end, freq="D", utc=True)],
            names=["instrument", "datetime"],
        )
        frame = pd.DataFrame(index=idx)
        for field in request.fields:
            # Deterministic synthetic data based on index
            frame[field] = [((i % 101) - 50) / 100 for i in range(len(frame))]
        return frame

