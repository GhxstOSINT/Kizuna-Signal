"""Time-based, title-grouped splitting: all state rows of a title stay together."""
import pandas as pd


def time_split(titles: pd.DataFrame, test_frac: float = 0.2) -> tuple[set[str], set[str]]:
    """Latest `test_frac` of titles by release date are the held-out test set."""
    ordered = titles.sort_values("release_date")["title_id"].tolist()
    n_test = max(1, round(len(ordered) * test_frac))
    return set(ordered[:-n_test]), set(ordered[-n_test:])


def franchise_time_split(titles: pd.DataFrame, test_frac: float = 0.2) -> tuple[set[str], set[str]]:
    """Time split where a whole franchise stays on one side (seasons of one show are near-duplicates).

    Franchises are ordered by their first release; the latest ones holding at least
    `test_frac` of the titles become the test set.
    """
    first = titles.groupby("franchise_id")["release_date"].min().sort_values()
    size = titles.groupby("franchise_id").size()
    target = max(1, round(len(titles) * test_frac))
    test_franchises, count = set(), 0
    for fid in reversed(first.index.tolist()):
        if count >= target:
            break
        test_franchises.add(fid)
        count += int(size[fid])
    in_test = titles["franchise_id"].isin(test_franchises)
    return set(titles.loc[~in_test, "title_id"]), set(titles.loc[in_test, "title_id"])


def grouped_time_folds(titles: pd.DataFrame, n_folds: int = 4):
    """Expanding-window folds over the training titles: train on earlier, validate on the next block."""
    ordered = titles.sort_values("release_date")["title_id"].tolist()
    size = len(ordered) // (n_folds + 1)
    for k in range(1, n_folds + 1):
        yield set(ordered[: k * size]), set(ordered[k * size : (k + 1) * size])
