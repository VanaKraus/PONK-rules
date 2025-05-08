import pandas as pd

_df = pd.read_csv('document_applicables/intervals.csv')

_INTERVAL_TYPES = ['bad', 'medium', 'good']


def get(metric: str, interval_type: str) -> tuple[float, float]:
    """Get an interval for a metric

    Args:
        metric (str)
        interval_type (str): good, medium, or bad

    Raises:
        ValueError: `interval_type` is not valid
        ValueError: intervals for `metric` not defined

    Returns:
        tuple[float, float]: [minimum, maximum] of the interval
    """
    if interval_type not in _INTERVAL_TYPES:
        raise ValueError(f'{interval_type=} not valid; must be in {_INTERVAL_TYPES}')

    feat = _df.loc[_df['feat'] == metric]

    if feat.empty:
        raise ValueError(f'intervals for {metric=} specified')

    interval = feat.loc[feat['type'] == interval_type]

    return (float(interval['minimum'].iloc[0]), float(interval['maximum'].iloc[0]))


def get_all_intervals(metric: str) -> dict[str, tuple[float, float]]:
    return {i: get(metric, i) for i in _INTERVAL_TYPES}
