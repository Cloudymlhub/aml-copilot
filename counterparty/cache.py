"""Compute cache for intermediate DataFrames during graph computation.

Works with both local paths and HDFS paths (hdfs://...) by using
Spark's Hadoop filesystem API for path existence checks.
"""

from __future__ import annotations

import logging
from typing import List, Optional

import pandas as pd
from pyspark.sql import DataFrame, SparkSession

logger = logging.getLogger(__name__)


def _join_path(base: str, child: str) -> str:
    """Join paths, handling both local and HDFS URIs."""
    return f"{base.rstrip('/')}/{child}"


class _ComputeCache:
    """
    Cache for intermediate DataFrames during computation.

    Saves/loads DataFrames as parquet files under:
        {cache_path}/{batch_id}/{step_name}.parquet

    Works with local paths and HDFS paths via Hadoop filesystem API.

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
        self.base_path = _join_path(cache_path, batch_id)

    def _step_path(self, step: str) -> str:
        return _join_path(self.base_path, f"{step}.parquet")

    def _path_exists(self, path: str) -> bool:
        """Check if path exists using Hadoop filesystem (works for local + HDFS)."""
        jvm = self._spark._jvm
        hadoop_conf = self._spark._jsc.hadoopConfiguration()
        uri = jvm.java.net.URI(path)
        fs = jvm.org.apache.hadoop.fs.FileSystem.get(uri, hadoop_conf)
        return fs.exists(jvm.org.apache.hadoop.fs.Path(path))

    def _list_dir(self, path: str) -> List[str]:
        """List directory contents using Hadoop filesystem."""
        jvm = self._spark._jvm
        hadoop_conf = self._spark._jsc.hadoopConfiguration()
        uri = jvm.java.net.URI(path)
        fs = jvm.org.apache.hadoop.fs.FileSystem.get(uri, hadoop_conf)
        hadoop_path = jvm.org.apache.hadoop.fs.Path(path)
        if not fs.exists(hadoop_path):
            return []
        statuses = fs.listStatus(hadoop_path)
        return [s.getPath().getName() for s in statuses]

    def has(self, step: str) -> bool:
        return not self._overwrite and self._path_exists(self._step_path(step))

    def cached_steps(self) -> List[str]:
        if self._overwrite:
            return []
        return [
            name.replace(".parquet", "")
            for name in self._list_dir(self.base_path)
            if name.endswith(".parquet")
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
            write_mode = "overwrite" if self._overwrite else "errorifexists"
            result.write.mode(write_mode).parquet(path)
            logger.debug(f"[Cache] Saved '{step}' to {path}")

        return result

    def write_spark(self, step: str, df: DataFrame) -> None:
        """Write Spark DataFrame to cache as parquet."""
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
