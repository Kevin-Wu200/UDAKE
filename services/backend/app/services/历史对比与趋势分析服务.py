"""
历史对比与趋势分析服务
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats
from sklearn.metrics import r2_score

from ..config import settings
from ..schemas.历史对比与趋势分析模型 import (
    AnomalyPoint,
    ArchiveSnapshotsRequest,
    ArchiveSnapshotsResponse,
    ComparisonSummary,
    ExportFormat,
    ForecastEvaluation,
    ForecastPoint,
    HeatmapComparison,
    HistoryExportRequest,
    HistoryExportResponse,
    HistoryImportRequest,
    HistoryImportResponse,
    HistoryReportRequest,
    HistoryReportResponse,
    LinearTrendResult,
    MannKendallResult,
    PeriodicComponent,
    SnapshotCreateRequest,
    SnapshotMetadata,
    SnapshotListResponse,
    TrendAnalysisRequest,
    TrendAnalysisResponse,
    TimeSeriesRecord,
    ValueDiffItem,
    VersionComparisonRequest,
    VersionComparisonResponse,
)


class HistoryComparisonTrendService:
    """历史对比与趋势分析服务"""

    def __init__(self, storage_dir: Optional[Path] = None, report_dir: Optional[Path] = None):
        base_storage = storage_dir or (settings.RESULTS_DIR / "history_analysis")
        base_report = report_dir or (settings.RESULTS_DIR / "history_reports")
        self.storage_dir = Path(base_storage)
        self.archive_dir = self.storage_dir / "archive"
        self.report_dir = Path(base_report)
        self.lock = threading.Lock()

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def _safe_dataset_id(self, dataset_id: str) -> str:
        return dataset_id.replace("/", "_").replace("..", "_").strip()

    def _dataset_dir(self, dataset_id: str) -> Path:
        safe_id = self._safe_dataset_id(dataset_id)
        path = self.storage_dir / safe_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _index_path(self, dataset_id: str) -> Path:
        return self._dataset_dir(dataset_id) / "index.json"

    def _snapshot_path(self, dataset_id: str, file_name: str) -> Path:
        return self._dataset_dir(dataset_id) / file_name

    def _load_index(self, dataset_id: str) -> List[Dict[str, Any]]:
        index_path = self._index_path(dataset_id)
        if not index_path.exists():
            return []
        with index_path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        if not isinstance(data, list):
            return []
        return data

    def _save_index(self, dataset_id: str, items: List[Dict[str, Any]]) -> None:
        index_path = self._index_path(dataset_id)
        with index_path.open("w", encoding="utf-8") as fp:
            json.dump(items, fp, ensure_ascii=False, indent=2)

    def _parse_metadata(self, item: Dict[str, Any]) -> SnapshotMetadata:
        return SnapshotMetadata(
            dataset_id=item["dataset_id"],
            version=int(item["version"]),
            version_label=item.get("version_label"),
            created_at=datetime.fromisoformat(item["created_at"]),
            record_count=int(item["record_count"]),
            compressed=bool(item.get("compressed", True)),
            file_name=item["file_name"],
            metadata=item.get("metadata", {}),
        )

    def _serialize_metadata(self, meta: SnapshotMetadata) -> Dict[str, Any]:
        payload = meta.model_dump(mode="json")
        payload["created_at"] = meta.created_at.isoformat()
        return payload

    def _load_snapshot_payload(self, dataset_id: str, version: int) -> Dict[str, Any]:
        index = self._load_index(dataset_id)
        item = next((entry for entry in index if int(entry["version"]) == version), None)
        if not item:
            raise ValueError(f"未找到数据集 {dataset_id} 的版本 {version}")

        file_path = self._snapshot_path(dataset_id, item["file_name"])
        if not file_path.exists():
            raise ValueError(f"版本文件不存在: {file_path.name}")

        with gzip.open(file_path, "rt", encoding="utf-8") as fp:
            payload = json.load(fp)
        return payload

    def _to_records(self, raw_records: List[Dict[str, Any]]) -> List[TimeSeriesRecord]:
        records = [TimeSeriesRecord(**item) for item in raw_records]
        records.sort(key=lambda r: r.timestamp)
        return records

    def create_snapshot(self, request: SnapshotCreateRequest) -> SnapshotMetadata:
        """创建快照并写入压缩存储"""
        with self.lock:
            index = self._load_index(request.dataset_id)
            next_version = 1 if not index else max(int(i["version"]) for i in index) + 1

            records = sorted(request.records, key=lambda r: r.timestamp)
            file_name = f"v{next_version:04d}.json.gz"
            file_path = self._snapshot_path(request.dataset_id, file_name)
            created_at = datetime.now()

            payload = {
                "dataset_id": request.dataset_id,
                "version": next_version,
                "version_label": request.version_label,
                "created_at": created_at.isoformat(),
                "metadata": request.metadata,
                "records": [item.model_dump(mode="json") for item in records],
            }

            with gzip.open(file_path, "wt", encoding="utf-8") as fp:
                json.dump(payload, fp, ensure_ascii=False)

            snapshot_meta = SnapshotMetadata(
                dataset_id=request.dataset_id,
                version=next_version,
                version_label=request.version_label,
                created_at=created_at,
                record_count=len(records),
                compressed=True,
                file_name=file_name,
                metadata=request.metadata,
            )
            index.append(self._serialize_metadata(snapshot_meta))
            index.sort(key=lambda item: int(item["version"]))
            self._save_index(request.dataset_id, index)

            return snapshot_meta

    def list_snapshots(self, dataset_id: str) -> SnapshotListResponse:
        """获取快照版本列表"""
        with self.lock:
            index = self._load_index(dataset_id)
            metas = [self._parse_metadata(item) for item in sorted(index, key=lambda d: int(d["version"]))]
            return SnapshotListResponse(dataset_id=dataset_id, total_versions=len(metas), versions=metas)

    def delete_snapshot(self, dataset_id: str, version: int) -> None:
        """删除指定版本快照并更新索引"""
        with self.lock:
            index = self._load_index(dataset_id)
            if not index:
                raise ValueError(f"数据集 {dataset_id} 暂无历史版本")

            target = next((item for item in index if int(item["version"]) == version), None)
            if target is None:
                raise ValueError(f"未找到数据集 {dataset_id} 的版本 {version}")

            file_path = self._snapshot_path(dataset_id, target["file_name"])
            if not file_path.exists():
                raise ValueError(f"版本文件不存在: {target['file_name']}")

            updated_index = [item for item in index if int(item["version"]) != version]
            sorted_updated = sorted(updated_index, key=lambda item: int(item["version"]))

            # 先更新索引，文件删除失败时回滚索引，避免留下无索引文件。
            self._save_index(dataset_id, sorted_updated)
            try:
                file_path.unlink()
            except OSError as exc:
                self._save_index(dataset_id, index)
                raise ValueError(f"删除快照文件失败: {exc}") from exc

    def get_snapshot_records(self, dataset_id: str, version: Optional[int] = None) -> Tuple[int, List[TimeSeriesRecord]]:
        """读取指定或最新版本记录"""
        with self.lock:
            index = self._load_index(dataset_id)
            if not index:
                raise ValueError(f"数据集 {dataset_id} 暂无历史版本")
            if version is None:
                version = max(int(item["version"]) for item in index)

            payload = self._load_snapshot_payload(dataset_id, version)
            raw_records = payload.get("records", [])
            if not isinstance(raw_records, list):
                raise ValueError("快照记录格式无效")
            return version, self._to_records(raw_records)

    def compare_versions(self, request: VersionComparisonRequest) -> VersionComparisonResponse:
        """版本对比与差值分析"""
        from_version, from_records = self.get_snapshot_records(request.dataset_id, request.from_version)
        to_version, to_records = self.get_snapshot_records(request.dataset_id, request.to_version)

        max_len = max(len(from_records), len(to_records))
        diffs: List[ValueDiffItem] = []
        changed_points = 0
        unchanged_points = 0

        for idx in range(max_len):
            from_rec = from_records[idx] if idx < len(from_records) else None
            to_rec = to_records[idx] if idx < len(to_records) else None

            from_value = from_rec.value if from_rec else None
            to_value = to_rec.value if to_rec else None

            if from_value is not None and to_value is not None:
                absolute_diff = float(abs(to_value - from_value))
                relative_diff = (absolute_diff / abs(from_value)) if from_value != 0 else None
                changed = absolute_diff > 1e-12
            else:
                fallback = to_value if to_value is not None else from_value
                absolute_diff = float(abs(fallback or 0.0))
                relative_diff = None
                changed = True

            key = (
                (to_rec.point_id if to_rec else None)
                or (from_rec.point_id if from_rec else None)
                or f"index:{idx}"
            )

            if changed:
                changed_points += 1
            else:
                unchanged_points += 1

            diffs.append(
                ValueDiffItem(
                    key=key,
                    from_value=from_value,
                    to_value=to_value,
                    absolute_diff=absolute_diff,
                    relative_diff=relative_diff,
                    timestamp=(to_rec.timestamp if to_rec else None) or (from_rec.timestamp if from_rec else None),
                    x=(to_rec.x if to_rec else None) if (to_rec and to_rec.x is not None) else (from_rec.x if from_rec else None),
                    y=(to_rec.y if to_rec else None) if (to_rec and to_rec.y is not None) else (from_rec.y if from_rec else None),
                )
            )

        abs_values = [item.absolute_diff for item in diffs] or [0.0]
        summary = ComparisonSummary(
            total_points=max_len,
            changed_points=changed_points,
            unchanged_points=unchanged_points,
            avg_absolute_diff=float(sum(abs_values) / len(abs_values)),
            max_absolute_diff=float(max(abs_values)),
            min_absolute_diff=float(min(abs_values)),
        )

        heatmap = self._build_heatmap(diffs, request.heatmap_grid_size)

        return VersionComparisonResponse(
            dataset_id=request.dataset_id,
            from_version=from_version,
            to_version=to_version,
            summary=summary,
            diffs=diffs,
            heatmap=heatmap,
        )

    def _build_heatmap(self, diffs: List[ValueDiffItem], grid_size: int) -> HeatmapComparison:
        rows = grid_size
        cols = grid_size
        matrix = [[0.0 for _ in range(cols)] for _ in range(rows)]
        counts = [[0 for _ in range(cols)] for _ in range(rows)]

        valid_points = [d for d in diffs if d.x is not None and d.y is not None]
        if valid_points:
            min_x = min(float(d.x) for d in valid_points)
            max_x = max(float(d.x) for d in valid_points)
            min_y = min(float(d.y) for d in valid_points)
            max_y = max(float(d.y) for d in valid_points)
            span_x = max(max_x - min_x, 1e-12)
            span_y = max(max_y - min_y, 1e-12)

            for item in valid_points:
                col = int((float(item.x) - min_x) / span_x * (cols - 1))
                row = int((float(item.y) - min_y) / span_y * (rows - 1))
                matrix[row][col] += item.absolute_diff
                counts[row][col] += 1
        else:
            # 没有空间坐标时，按序列索引投影到中间行
            mid_row = rows // 2
            total = len(diffs)
            for idx, item in enumerate(diffs):
                if total <= 1:
                    col = 0
                else:
                    col = int(idx / (total - 1) * (cols - 1))
                matrix[mid_row][col] += item.absolute_diff
                counts[mid_row][col] += 1

        for r in range(rows):
            for c in range(cols):
                if counts[r][c] > 0:
                    matrix[r][c] = float(matrix[r][c] / counts[r][c])

        return HeatmapComparison(rows=rows, cols=cols, matrix=matrix)

    def analyze_trend(self, request: TrendAnalysisRequest) -> TrendAnalysisResponse:
        """趋势分析（线性趋势 + Mann-Kendall + FFT + 异常检测 + 预测）"""
        version, records = self.get_snapshot_records(request.dataset_id, request.version)
        if len(records) < 2:
            raise ValueError("趋势分析至少需要两条记录")

        values = np.array([r.value for r in records], dtype=float)
        timestamps = [r.timestamp for r in records]

        linear = self._analyze_linear_trend(values)
        mann_kendall = self._mann_kendall_test(values, request.alpha)
        periodic_components = self._analyze_periodic_components(values)

        inferred_period = self._infer_seasonal_period(periodic_components, len(values))
        seasonal_period = request.seasonal_period or inferred_period

        anomalies = self._detect_anomalies(values, timestamps, request.anomaly_z_threshold)
        forecast, evaluation = self._forecast_with_uncertainty(
            values,
            timestamps,
            request.forecast_horizon,
            seasonal_period,
        )

        return TrendAnalysisResponse(
            dataset_id=request.dataset_id,
            version=version,
            sample_size=len(records),
            linear_trend=linear,
            mann_kendall=mann_kendall,
            periodic_components=periodic_components,
            anomalies=anomalies,
            forecast=forecast,
            evaluation=evaluation,
        )

    def _analyze_linear_trend(self, values: np.ndarray) -> LinearTrendResult:
        x = np.arange(len(values), dtype=float)
        result = stats.linregress(x, values)
        slope = float(result.slope)
        intercept = float(result.intercept)
        r_squared = float(result.rvalue ** 2)

        threshold = max(float(np.std(values)) * 0.01, 1e-9)
        if slope > threshold:
            direction = "increasing"
        elif slope < -threshold:
            direction = "decreasing"
        else:
            direction = "stable"

        return LinearTrendResult(
            slope=slope,
            intercept=intercept,
            r_squared=r_squared,
            direction=direction,
        )

    def _mann_kendall_test(self, values: np.ndarray, alpha: float) -> MannKendallResult:
        n = len(values)
        if n < 2:
            return MannKendallResult(tau=0.0, s=0.0, z=0.0, p_value=1.0, has_trend=False)

        s = 0.0
        for i in range(n - 1):
            s += float(np.sum(np.sign(values[i + 1 :] - values[i])))

        unique_values, counts = np.unique(values, return_counts=True)
        _ = unique_values
        tie_term = sum(int(c * (c - 1) * (2 * c + 5)) for c in counts if c > 1)
        var_s = (n * (n - 1) * (2 * n + 5) - tie_term) / 18.0

        if var_s <= 0:
            z = 0.0
            p_value = 1.0
        else:
            if s > 0:
                z = (s - 1) / np.sqrt(var_s)
            elif s < 0:
                z = (s + 1) / np.sqrt(var_s)
            else:
                z = 0.0
            p_value = float(2 * (1 - stats.norm.cdf(abs(z))))

        denom = 0.5 * n * (n - 1)
        tau = float(s / denom) if denom > 0 else 0.0

        return MannKendallResult(
            tau=tau,
            s=float(s),
            z=float(z),
            p_value=p_value,
            has_trend=p_value < alpha,
        )

    def _analyze_periodic_components(self, values: np.ndarray) -> List[PeriodicComponent]:
        n = len(values)
        if n < 4:
            return []

        centered = values - np.mean(values)
        spectrum = np.fft.rfft(centered)
        freqs = np.fft.rfftfreq(n, d=1.0)
        amplitudes = (2.0 / n) * np.abs(spectrum)

        candidates: List[PeriodicComponent] = []
        order = np.argsort(amplitudes[1:])[::-1]  # 跳过直流分量
        for idx in order:
            freq_idx = int(idx + 1)
            frequency = float(freqs[freq_idx])
            amplitude = float(amplitudes[freq_idx])
            if frequency <= 0 or amplitude <= 1e-10:
                continue

            period = 1.0 / frequency
            if period < 2 or period > n:
                continue

            candidates.append(
                PeriodicComponent(
                    frequency=frequency,
                    period=float(period),
                    amplitude=amplitude,
                )
            )
            if len(candidates) >= 3:
                break

        return candidates

    def _infer_seasonal_period(self, components: List[PeriodicComponent], sample_size: int) -> Optional[int]:
        if not components:
            return None
        period = int(round(components[0].period))
        if period < 2:
            return None
        if period > max(2, sample_size // 2):
            return None
        return period

    def _detect_anomalies(
        self,
        values: np.ndarray,
        timestamps: List[datetime],
        z_threshold: float,
    ) -> List[AnomalyPoint]:
        anomalies: Dict[int, AnomalyPoint] = {}
        if len(values) < 3:
            return []

        std = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
        mean = float(np.mean(values))

        if std > 0:
            z_scores = (values - mean) / std
            for idx, score in enumerate(z_scores):
                if abs(float(score)) >= z_threshold:
                    anomalies[idx] = AnomalyPoint(
                        index=idx,
                        timestamp=timestamps[idx],
                        value=float(values[idx]),
                        score=float(abs(score)),
                        anomaly_type="zscore",
                    )

        # 简易突变点检测：前后窗口均值差 / 联合标准差
        window = max(3, min(10, len(values) // 6))
        if len(values) >= window * 2 + 1:
            for idx in range(window, len(values) - window):
                left = values[idx - window : idx]
                right = values[idx : idx + window]
                pooled = float(np.std(np.concatenate([left, right]), ddof=1))
                if pooled <= 0:
                    continue

                shift_score = abs(float(np.mean(right) - np.mean(left))) / pooled
                if shift_score >= 2.5:
                    current = anomalies.get(idx)
                    if (current is None) or (shift_score > current.score):
                        anomalies[idx] = AnomalyPoint(
                            index=idx,
                            timestamp=timestamps[idx],
                            value=float(values[idx]),
                            score=float(shift_score),
                            anomaly_type="change_point",
                        )

        return [anomalies[idx] for idx in sorted(anomalies.keys())]

    def _infer_time_step(self, timestamps: List[datetime]) -> timedelta:
        if len(timestamps) < 2:
            return timedelta(days=1)

        deltas = []
        for i in range(1, len(timestamps)):
            diff = timestamps[i] - timestamps[i - 1]
            if diff.total_seconds() > 0:
                deltas.append(diff)

        if not deltas:
            return timedelta(days=1)

        seconds = sorted(delta.total_seconds() for delta in deltas)
        median_seconds = seconds[len(seconds) // 2]
        return timedelta(seconds=median_seconds)

    def _predict_future_values(
        self,
        values: np.ndarray,
        horizon: int,
        seasonal_period: Optional[int],
    ) -> np.ndarray:
        n = len(values)
        if n == 0:
            return np.zeros(horizon, dtype=float)

        if n == 1:
            return np.array([float(values[0])] * horizon, dtype=float)

        x = np.arange(n, dtype=float)
        trend = stats.linregress(x, values)
        slope = float(trend.slope)
        intercept = float(trend.intercept)

        seasonal_pattern: Optional[np.ndarray] = None
        if seasonal_period and seasonal_period >= 2 and n >= seasonal_period:
            seasonal_pattern = values[-seasonal_period:]

        preds: List[float] = []
        for step in range(1, horizon + 1):
            idx = n + step - 1
            linear_pred = intercept + slope * idx
            if seasonal_pattern is not None:
                seasonal_pred = float(seasonal_pattern[(step - 1) % len(seasonal_pattern)])
                pred = 0.7 * linear_pred + 0.3 * seasonal_pred
            else:
                pred = linear_pred
            preds.append(float(pred))

        return np.array(preds, dtype=float)

    def _forecast_with_uncertainty(
        self,
        values: np.ndarray,
        timestamps: List[datetime],
        horizon: int,
        seasonal_period: Optional[int],
    ) -> Tuple[List[ForecastPoint], ForecastEvaluation]:
        preds = self._predict_future_values(values, horizon, seasonal_period)

        n = len(values)
        x = np.arange(n, dtype=float)
        trend = stats.linregress(x, values)
        fitted = trend.intercept + trend.slope * x
        residual = values - fitted
        residual_std = float(np.std(residual, ddof=1)) if len(residual) > 1 else 0.0
        ci = 1.96 * residual_std

        step = self._infer_time_step(timestamps)
        last_ts = timestamps[-1]

        forecast_points: List[ForecastPoint] = []
        for idx, pred in enumerate(preds, start=1):
            forecast_points.append(
                ForecastPoint(
                    index=idx,
                    timestamp=last_ts + step * idx,
                    predicted_value=float(pred),
                    lower_bound=float(pred - ci),
                    upper_bound=float(pred + ci),
                )
            )

        evaluation = self._evaluate_forecast(values, seasonal_period)
        return forecast_points, evaluation

    def _evaluate_forecast(self, values: np.ndarray, seasonal_period: Optional[int]) -> ForecastEvaluation:
        n = len(values)
        if n < 5:
            return ForecastEvaluation(mae=0.0, mape=0.0, r2=1.0, accuracy=100.0)

        holdout = max(1, min(10, n // 5))
        train = values[:-holdout]
        test = values[-holdout:]

        if len(train) == 0:
            baseline = np.array([float(values[-1])] * holdout, dtype=float)
            preds = baseline
        else:
            preds = self._predict_future_values(train, holdout, seasonal_period)

        abs_error = np.abs(test - preds)
        mae = float(np.mean(abs_error))

        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.where(test != 0, abs_error / np.abs(test), np.nan)
        mape = float(np.nanmean(ratio) * 100) if np.any(~np.isnan(ratio)) else 0.0

        if len(test) > 1:
            try:
                r2 = float(r2_score(test, preds))
            except ValueError:
                r2 = 0.0
        else:
            r2 = 1.0 if float(test[0]) == float(preds[0]) else 0.0

        accuracy = float(max(0.0, min(100.0, 100.0 - mape)))
        return ForecastEvaluation(mae=mae, mape=max(0.0, mape), r2=r2, accuracy=accuracy)

    def generate_report(self, request: HistoryReportRequest) -> HistoryReportResponse:
        """生成历史对比与趋势分析报告"""
        comparison = self.compare_versions(
            VersionComparisonRequest(
                dataset_id=request.dataset_id,
                from_version=request.from_version,
                to_version=request.to_version,
            )
        )
        trend = self.analyze_trend(
            TrendAnalysisRequest(
                dataset_id=request.dataset_id,
                version=request.to_version,
                forecast_horizon=request.forecast_horizon,
            )
        )

        report_id = str(uuid.uuid4())
        report_file = self.report_dir / f"{report_id}.json"
        generated_at = datetime.now()

        payload = {
            "report_id": report_id,
            "dataset_id": request.dataset_id,
            "generated_at": generated_at.isoformat(),
            "comparison": comparison.model_dump(mode="json"),
            "trend": trend.model_dump(mode="json"),
        }

        with report_file.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2)

        return HistoryReportResponse(
            report_id=report_id,
            dataset_id=request.dataset_id,
            generated_at=generated_at,
            download_url=f"/results/history_reports/{report_file.name}",
            comparison=comparison,
            trend=trend,
        )

    def export_history(self, request: HistoryExportRequest) -> HistoryExportResponse:
        """导出历史数据"""
        if request.format == ExportFormat.JSON:
            snapshots = []
            snapshot_list = self.list_snapshots(request.dataset_id)
            for meta in snapshot_list.versions:
                payload = self._load_snapshot_payload(request.dataset_id, meta.version)
                snapshots.append(payload)

            content = json.dumps(
                {
                    "dataset_id": request.dataset_id,
                    "exported_at": datetime.now().isoformat(),
                    "snapshots": snapshots,
                },
                ensure_ascii=False,
                indent=2,
            )
            return HistoryExportResponse(dataset_id=request.dataset_id, format=request.format, content=content)

        version, records = self.get_snapshot_records(request.dataset_id, None)
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=["timestamp", "value", "point_id", "x", "y", "metadata"])
        writer.writeheader()
        for item in records:
            writer.writerow(
                {
                    "timestamp": item.timestamp.isoformat(),
                    "value": item.value,
                    "point_id": item.point_id or "",
                    "x": "" if item.x is None else item.x,
                    "y": "" if item.y is None else item.y,
                    "metadata": json.dumps(item.metadata, ensure_ascii=False),
                }
            )
        csv_content = buffer.getvalue()
        buffer.close()
        _ = version
        return HistoryExportResponse(dataset_id=request.dataset_id, format=request.format, content=csv_content)

    def import_history(self, request: HistoryImportRequest) -> HistoryImportResponse:
        """导入历史数据"""
        records: List[TimeSeriesRecord] = []

        if request.format == ExportFormat.JSON:
            payload = json.loads(request.content)
            if isinstance(payload, dict) and isinstance(payload.get("records"), list):
                source_records = payload["records"]
            elif isinstance(payload, dict) and isinstance(payload.get("snapshots"), list) and payload["snapshots"]:
                latest_snapshot = payload["snapshots"][-1]
                source_records = latest_snapshot.get("records", [])
            elif isinstance(payload, list):
                source_records = payload
            else:
                raise ValueError("JSON导入内容格式不支持")

            records = [TimeSeriesRecord(**item) for item in source_records]
        else:
            reader = csv.DictReader(io.StringIO(request.content))
            for row in reader:
                metadata_text = row.get("metadata") or "{}"
                try:
                    metadata = json.loads(metadata_text)
                except json.JSONDecodeError:
                    metadata = {}

                records.append(
                    TimeSeriesRecord(
                        timestamp=row["timestamp"],
                        value=float(row["value"]),
                        point_id=row.get("point_id") or None,
                        x=float(row["x"]) if row.get("x") not in (None, "") else None,
                        y=float(row["y"]) if row.get("y") not in (None, "") else None,
                        metadata=metadata,
                    )
                )

        if not records:
            raise ValueError("导入内容为空")

        snapshot = self.create_snapshot(
            SnapshotCreateRequest(
                dataset_id=request.dataset_id,
                version_label=request.version_label,
                records=records,
                metadata={"imported": True, "format": request.format.value},
            )
        )

        return HistoryImportResponse(
            dataset_id=request.dataset_id,
            imported_version=snapshot.version,
            imported_records=snapshot.record_count,
        )

    def archive_snapshots(self, request: ArchiveSnapshotsRequest) -> ArchiveSnapshotsResponse:
        """归档旧版本快照"""
        with self.lock:
            index = self._load_index(request.dataset_id)
            if len(index) <= request.keep_latest:
                return ArchiveSnapshotsResponse(
                    dataset_id=request.dataset_id,
                    archived_count=0,
                    kept_count=len(index),
                )

            sorted_index = sorted(index, key=lambda item: int(item["version"]))
            keep_items = sorted_index[-request.keep_latest :]
            archive_items = sorted_index[: -request.keep_latest]

            archive_dataset_dir = self.archive_dir / self._safe_dataset_id(request.dataset_id)
            archive_dataset_dir.mkdir(parents=True, exist_ok=True)

            archived_count = 0
            for item in archive_items:
                src = self._snapshot_path(request.dataset_id, item["file_name"])
                dst = archive_dataset_dir / item["file_name"]
                if src.exists():
                    src.rename(dst)
                    archived_count += 1

            self._save_index(request.dataset_id, keep_items)

            return ArchiveSnapshotsResponse(
                dataset_id=request.dataset_id,
                archived_count=archived_count,
                kept_count=len(keep_items),
            )


history_comparison_trend_service = HistoryComparisonTrendService()
