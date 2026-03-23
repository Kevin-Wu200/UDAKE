from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from deep_learning.utils.preprocessing import (
    SpatialNormalizer,
    FeatureScaler,
    DataAugmentation,
    DataSplitter,
    DataValidatorCleaner,
)
from deep_learning.utils.geojson_dataset import geojson_to_dataset
from deep_learning.utils.data_loader import BatchDataLoader


def test_spatial_normalizer_and_scaler() -> None:
    data = np.array([[1.0, 10.0], [2.0, 20.0], [3.0, 30.0]])

    normalized = SpatialNormalizer().fit_transform(data)
    assert normalized.min() >= 0.0
    assert normalized.max() <= 1.0

    scaled = FeatureScaler(method="standard").fit_transform(data)
    assert np.allclose(scaled.mean(axis=0), np.array([0.0, 0.0]), atol=1e-7)


def test_augmentation_split_validation() -> None:
    data = np.array([[1.0, np.nan], [2.0, np.inf], [1000.0, 3.0], [4.0, 5.0]])
    cleaner = DataValidatorCleaner()
    issues = cleaner.validate(data)
    assert "包含 NaN" in issues
    assert "包含无穷值" in issues

    clean = cleaner.clean(data)
    assert np.isfinite(clean).all()

    augmented = DataAugmentation(noise_std=0.01, jitter_range=0.01).apply(clean)
    assert augmented.shape == clean.shape

    split = DataSplitter(train_ratio=0.5, val_ratio=0.25, test_ratio=0.25, seed=7).split(clean)
    assert len(split.train) == 2
    assert len(split.val) == 1
    assert len(split.test) == 1


def test_geojson_dataset_and_batch_loader() -> None:
    sample_path = Path("tests/deep_learning/data/sample_geojson.json")
    payload = json.loads(sample_path.read_text(encoding="utf-8"))

    dataset = geojson_to_dataset(payload)
    assert len(dataset) == 2
    feature, target = dataset[0]
    assert feature.shape[0] >= 2
    assert float(target) > 0

    loader = BatchDataLoader(dataset, batch_size=1, shuffle=False)
    batches = list(loader)
    assert len(batches) == 2
