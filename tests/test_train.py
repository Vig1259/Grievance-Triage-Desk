import pandas as pd
import pytest
from scripts import train


def test_load_rows_filters_and_samples_dataset(monkeypatch):
    records = [
        {"Consumer complaint narrative": "  complaint one  ", "Product": "Credit card"},
        {"Consumer complaint narrative": "   ", "Product": "Credit card"},
        {"Consumer complaint narrative": None, "Product": "Mortgage"},
        {"Consumer complaint narrative": "complaint two", "Product": "Mortgage"},
        {"Consumer complaint narrative": "complaint three", "Product": "Bank account"},
    ]
    calls = []

    class FakeDataset:
        def shuffle(self, *, seed):
            calls.append(("shuffle", seed))
            return iter(records)

    def fake_load_dataset(dataset_id, *, name, split):
        calls.append((dataset_id, name, split))
        return FakeDataset()

    monkeypatch.setattr(train, "load_dataset", fake_load_dataset)

    rows = train.load_rows(size=2, seed=42)
    repeat = train.load_rows(size=2, seed=42)

    assert len(rows) == 2
    assert rows.equals(repeat)
    assert set(rows["text"]).issubset({"complaint one", "complaint two", "complaint three"})
    assert all(rows["text"].str.strip())
    assert all(rows["label"].str.strip())
    assert calls == [
        (train.DATASET_ID, train.DATASET_CONFIG, "train"),
        ("shuffle", 42),
    ] * 2


def test_load_rows_rejects_empty_dataset(monkeypatch):
    class EmptyDataset:
        def shuffle(self, *, seed):
            return iter([{"Product": "Mortgage"}])

    monkeypatch.setattr(train, "load_dataset", lambda *args, **kwargs: EmptyDataset())

    with pytest.raises(ValueError, match="narrative and Product"):
        train.load_rows(size=1, seed=42)


def test_split_rows_groups_singleton_and_rare_products():
    frame = pd.DataFrame(
        {
            "text": [f"complaint {index}" for index in range(27)],
            "label": ["Major"] * 20 + ["Minor"] * 6 + ["Singleton"],
        }
    )

    train_rows, test_rows = train.split_rows(frame, seed=42, min_class_count=5)

    assert "Singleton" not in set(train_rows.label) | set(test_rows.label)
    assert train.RARE_LABEL in set(train_rows.label)
    assert train.RARE_LABEL in set(test_rows.label)