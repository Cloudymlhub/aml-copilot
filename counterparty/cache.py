"""Compute cache for intermediate DataFrames during graph computation."""

from __future__ import annotations

import logging
import os
from typing import List, Optional

import pandas as pd
from pyspark.sql import DataFrame, SparkSession

logger = logging.getLogger(__name__)


class _ComputeCache:
    """
    Cache for intermediate DataFrames during computation.

    Saves/loads DataFrames as parquet files under:
        {cache_path}/{batch_id}/{step_name}.parquet

    Usage:
        cache = _ComputeCache(spark, "/data/cache", "batch_2024_03")
        df = cache.get_or_compute("edge_table", lambda: expensive_computation())
    """

    def __init__(
        self,
        spark: SparkSession,
        cache_path: str,
        batch_id: str,
        overwrite: bool = False,
    ):
        self._spark = spark
        self._overwrite = overwrite
        self.base_path = os.path.join(cache_path, batch_id)

    def _step_path(self, step: str) -> str:
        return os.path.join(self.base_path, f"{step}.parquet")

    def has(self, step: str) -> bool:
        return not self._overwrite and os.path.exists(self._step_path(step))

    def cached_steps(self) -> List[str]:
        if not os.path.exists(self.base_path):
            return []
        return [
            f.replace(".parquet", "")
            for f in os.listdir(self.base_path)
            if f.endswith(".parquet")
            and (not self._overwrite)
        ]

    def get_or_compute(
        self,
        step: str,
        compute_fn,
    ) -> Optional[DataFrame]:
        path = self._step_path(step)

        if self.has(step):
            logger.info(f"[Cache] Loading cached '{step}' from {path}")
            return self._spark.read.parquet(path)

        logger.debug(f"[Cache] Computing '{step}' (not cached)")
        result = compute_fn()

        if result is not None:
            os.makedirs(self.base_path, exist_ok=True)
            write_mode = "overwrite" if self._overwrite else "errorifexists"
            result.write.mode(write_mode).parquet(path)
            logger.debug(f"[Cache] Saved '{step}' to {path}")

        return result

    def write_spark(self, step: str, df: DataFrame) -> None:
        """Write Spark DataFrame to cache as parquet."""
        os.makedirs(self.base_path, exist_ok=True)
        path = self._step_path(step)
        mode = "overwrite" if self._overwrite else "errorifexists"
        df.write.mode(mode).parquet(path)
        logger.debug(f"[Cache] Wrote Spark DF '{step}' to {path}")

    def read_pandas(self, step: str) -> pd.DataFrame:
        """Read cached parquet as pandas DataFrame."""
        path = self._step_path(step)
        logger.debug(f"[Cache] Reading pandas DF '{step}' from {path}")
        return pd.read_parquet(path)


def _cached(
    cache: Optional[_ComputeCache], step: str, compute_fn
) -> Optional[DataFrame]:
    """Compute or load from cache. When cache is None, just compute."""
    if cache:
        return cache.get_or_compute(step, compute_fn)
    return compute_fn()
