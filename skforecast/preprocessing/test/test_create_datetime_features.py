# Unit test create_datetime_features
# ==============================================================================
import pytest
import re
import pandas as pd
import numpy as np
from skforecast.preprocessing import create_datetime_features

# Fixtures
year_cols_onehot = [f"year_{i}" for i in [2021, 2022, 2023]]
month_cols_onehot = [f"month_{i}" for i in range(1, 13)]
week_cols_onehot = [f"week_{i}" for i in range(1, 54)]
day_of_week_cols_onehot = [f"day_of_week_{i}" for i in range(0, 7)]
day_of_month_cols_onehot = [f"day_of_month_{i}" for i in range(1, 32)]
day_of_year_cols_onehot = [f"day_of_year_{i}" for i in range(1, 366)]
weekend_cols_onehot = ["weekend_0", "weekend_1"]
hour_cols_onehot = [f"hour_{i}" for i in range(0, 24)]
minute_cols_onehot = [f"minute_{i}" for i in range(0, 60)]
second_cols_onehot = [f"second_{i}" for i in range(0, 60)]

features_all_onehot = (
    year_cols_onehot
    + month_cols_onehot
    + week_cols_onehot
    + day_of_week_cols_onehot
    + day_of_month_cols_onehot
    + day_of_year_cols_onehot
    + weekend_cols_onehot
    + hour_cols_onehot
    + minute_cols_onehot
    + second_cols_onehot
)


def test_create_datetime_features_invalid_input_type():
    """
    Test that create_datetime_features raises a ValueError when input is not a pandas DataFrame or Series.
    """
    with pytest.raises(ValueError, match="Input must be a pandas DataFrame or Series"):
        create_datetime_features([1, 2, 3])


def test_create_datetime_features_no_datetime_index():
    """
    Test that create_datetime_features raises a ValueError when input does not have a datetime index.
    """
    df = pd.DataFrame({"a": [1, 2, 3]})
    with pytest.raises(ValueError, match="Input must have a datetime index"):
        create_datetime_features(df)


def test_create_datetime_features_invalid_encoding():
    """
    Test that create_datetime_features raises a ValueError when encoding is not one of 'cyclic', 'onehot' or None.
    """
    df = pd.DataFrame(
        np.random.rand(5, 3),
        columns=["col_1", "col_2", "col_3"],
        index=pd.date_range(start="1/1/2022", end="1/5/2022", freq="D"),
    )

    with pytest.raises(
        ValueError, match="Encoding must be one of 'cyclic', 'onehot' or None"
    ):
        create_datetime_features(df, encoding="invalid encoding")


def test_create_datetime_features_invalid_feature_name():
    """
    Test that create_datetime_features raises a ValueError when a feature name is not valid.
    """
    df = pd.DataFrame(
        np.random.rand(5, 3),
        columns=["col_1", "col_2", "col_3"],
        index=pd.date_range(start="1/1/2022", end="1/5/2022", freq="D"),
    )

    err_msg = re.escape(
        "Features {'invalid_feature'} are not supported. Supported features are "
        "['year', 'month', 'week', 'day_of_week', 'day_of_year', 'day_of_month', "
        "'weekend', 'hour', 'minute', 'second']."
    )
    with pytest.raises(ValueError, match=err_msg):
        create_datetime_features(df, features=["invalid_feature"])


def test_create_datetime_features_output_columns_when_cyclic_encoding():
    """
    Test that create_datetime_features returns the expected columns when encoding is 'cyclic'.
    """
    df = pd.DataFrame(
        np.random.rand(5, 3),
        columns=["col_1", "col_2", "col_3"],
        index=pd.date_range(start="1/1/2022", end="1/5/2022", freq="D"),
    )

    results = create_datetime_features(df, encoding="cyclic")
    expected_features = [
        "year",
        "weekend",
        "month_sin",
        "month_cos",
        "week_sin",
        "week_cos",
        "day_of_week_sin",
        "day_of_week_cos",
        "day_of_month_sin",
        "day_of_month_cos",
        "day_of_year_sin",
        "day_of_year_cos",
        "hour_sin",
        "hour_cos",
        "minute_sin",
        "minute_cos",
        "second_sin",
        "second_cos",
    ]

    assert all([feature in results.columns for feature in expected_features])
    assert len(results) == len(df)


def test_create_datetime_features_output_columns_when_onehot_encoding():
    """
    Test that create_datetime_features returns the expected columns when encoding is 'onehot'.
    """
    index = pd.date_range(start="2021-01-01", end="2023-01-01", freq="H")
    df = pd.DataFrame(
            np.random.rand(len(index), 3),
            columns=["col_1", "col_2", "col_3"],
            index=index,
        )

    results = create_datetime_features(df, encoding="onehot")

    assert all([feature in features_all_onehot for feature in results.columns])
    assert len(results) == len(df)


def test_create_datetime_features_output_columns_when_None_encoding():
    """
    Test that create_datetime_features returns the expected columns when encoding is 'None'.
    """
    index = pd.date_range(start="2021-01-01", end="2023-01-01", freq="H")
    df = pd.DataFrame(
        np.random.rand(len(index), 3),
        columns=["col_1", "col_2", "col_3"],
        index=index,
    )
    results = create_datetime_features(df, encoding=None)
    expected_features = [
        "year",
        "month",
        "week",
        "day_of_week",
        "day_of_month",
        "day_of_year",
        "weekend",
        "hour",
        "minute",
        "second",
    ]
    assert all(results.columns == expected_features)
    assert len(results) == len(df)


def test_create_datetime_features_output_when_features_year_month_encoding_cyclic():
    """
    Test that create_datetime_features returns the expected columns when features
     is ['year', 'month'] and encoding is 'cyclic'.
    """
    df = pd.DataFrame(
        np.random.rand(5, 3),
        columns=["col_1", "col_2", "col_3"],
        index=pd.date_range(start="1/1/2022", end="1/5/2022", freq="D"),
    )

    results = create_datetime_features(
        df, features=["year", "month", "weekend"], encoding="cyclic"
    )
    expected = pd.DataFrame(
        {
            "year": {
                pd.Timestamp("2022-01-01 00:00:00"): 2022,
                pd.Timestamp("2022-01-02 00:00:00"): 2022,
                pd.Timestamp("2022-01-03 00:00:00"): 2022,
                pd.Timestamp("2022-01-04 00:00:00"): 2022,
                pd.Timestamp("2022-01-05 00:00:00"): 2022,
            },
            "weekend": {
                pd.Timestamp("2022-01-01 00:00:00"): 1,
                pd.Timestamp("2022-01-02 00:00:00"): 1,
                pd.Timestamp("2022-01-03 00:00:00"): 0,
                pd.Timestamp("2022-01-04 00:00:00"): 0,
                pd.Timestamp("2022-01-05 00:00:00"): 0,
            },
            "month_sin": {
                pd.Timestamp("2022-01-01 00:00:00"): 0.49999999999999994,
                pd.Timestamp("2022-01-02 00:00:00"): 0.49999999999999994,
                pd.Timestamp("2022-01-03 00:00:00"): 0.49999999999999994,
                pd.Timestamp("2022-01-04 00:00:00"): 0.49999999999999994,
                pd.Timestamp("2022-01-05 00:00:00"): 0.49999999999999994,
            },
            "month_cos": {
                pd.Timestamp("2022-01-01 00:00:00"): 0.8660254037844387,
                pd.Timestamp("2022-01-02 00:00:00"): 0.8660254037844387,
                pd.Timestamp("2022-01-03 00:00:00"): 0.8660254037844387,
                pd.Timestamp("2022-01-04 00:00:00"): 0.8660254037844387,
                pd.Timestamp("2022-01-05 00:00:00"): 0.8660254037844387,
            },
        }
    ).asfreq("D")

    pd.testing.assert_frame_equal(results, expected)

def test_create_datetime_features_output_when_features_year_month_encoding_onehot():
    """
    Test that create_datetime_features returns the expected columns when features
     is ['year', 'month'] and encoding is 'onehot'.
    """
    df = pd.DataFrame(
        np.random.rand(5, 3),
        columns=["col_1", "col_2", "col_3"],
        index=pd.date_range(start="1/1/2022", end="1/5/2022", freq="D"),
    )

    results = create_datetime_features(
        df, features=["year", "month", "weekend"], encoding="onehot"
    )
    expected = pd.DataFrame(
        {
            "year_2022": {
                pd.Timestamp("2022-01-01 00:00:00"): 1,
                pd.Timestamp("2022-01-02 00:00:00"): 1,
                pd.Timestamp("2022-01-03 00:00:00"): 1,
                pd.Timestamp("2022-01-04 00:00:00"): 1,
                pd.Timestamp("2022-01-05 00:00:00"): 1,
            },
            "month_1": {
                pd.Timestamp("2022-01-01 00:00:00"): 1,
                pd.Timestamp("2022-01-02 00:00:00"): 1,
                pd.Timestamp("2022-01-03 00:00:00"): 1,
                pd.Timestamp("2022-01-04 00:00:00"): 1,
                pd.Timestamp("2022-01-05 00:00:00"): 1,
            },
            "weekend_0": {
                pd.Timestamp("2022-01-01 00:00:00"): 0,
                pd.Timestamp("2022-01-02 00:00:00"): 0,
                pd.Timestamp("2022-01-03 00:00:00"): 1,
                pd.Timestamp("2022-01-04 00:00:00"): 1,
                pd.Timestamp("2022-01-05 00:00:00"): 1,
            },
            "weekend_1": {
                pd.Timestamp("2022-01-01 00:00:00"): 1,
                pd.Timestamp("2022-01-02 00:00:00"): 1,
                pd.Timestamp("2022-01-03 00:00:00"): 0,
                pd.Timestamp("2022-01-04 00:00:00"): 0,
                pd.Timestamp("2022-01-05 00:00:00"): 0,
            },
        }
    ).asfreq("D")

    pd.testing.assert_frame_equal(results, expected)


def test_create_datetime_features_output_when_features_year_month_encoding_None():
    """
    Test that create_datetime_features returns the expected columns when features
     is ['year', 'month'] and encoding is None.
    """
    df = pd.DataFrame(
        np.random.rand(5, 3),
        columns=["col_1", "col_2", "col_3"],
        index=pd.date_range(start="1/1/2022", end="1/5/2022", freq="D"),
    )

    results = create_datetime_features(
        df, features=["year", "month", "weekend"], encoding=None
    )
    expected = pd.DataFrame(
        {
            "year": {
                pd.Timestamp("2022-01-01 00:00:00"): 2022,
                pd.Timestamp("2022-01-02 00:00:00"): 2022,
                pd.Timestamp("2022-01-03 00:00:00"): 2022,
                pd.Timestamp("2022-01-04 00:00:00"): 2022,
                pd.Timestamp("2022-01-05 00:00:00"): 2022,
            },
            "month": {
                pd.Timestamp("2022-01-01 00:00:00"): 1,
                pd.Timestamp("2022-01-02 00:00:00"): 1,
                pd.Timestamp("2022-01-03 00:00:00"): 1,
                pd.Timestamp("2022-01-04 00:00:00"): 1,
                pd.Timestamp("2022-01-05 00:00:00"): 1,
            },
            "weekend": {
                pd.Timestamp("2022-01-01 00:00:00"): 1,
                pd.Timestamp("2022-01-02 00:00:00"): 1,
                pd.Timestamp("2022-01-03 00:00:00"): 0,
                pd.Timestamp("2022-01-04 00:00:00"): 0,
                pd.Timestamp("2022-01-05 00:00:00"): 0,
            },
        }
    ).asfreq("D")

    pd.testing.assert_frame_equal(results, expected)


def test_create_datetime_features_output_when_features_year_month_encoding_cyclic_and_custom_max_values():
    """
    Test that create_datetime_features returns the expected columns when features
    is ['year', 'month'] and encoding is 'cyclic' with custom max values.
    """

    df = pd.DataFrame(
        np.random.rand(5, 3),
        columns=["col_1", "col_2", "col_3"],
        index=pd.DatetimeIndex(
            ["2022-01-31", "2022-02-28", "2022-03-31", "2022-04-30", "2022-05-31"]
        ),
    )

    results = create_datetime_features(
        df,
        features=["year", "month", "weekend"],
        encoding="cyclic",
        max_values={"month": 6},
    )

    expected = pd.DataFrame(
        {
            "year": {
                pd.Timestamp("2022-01-31 00:00:00"): 2022,
                pd.Timestamp("2022-02-28 00:00:00"): 2022,
                pd.Timestamp("2022-03-31 00:00:00"): 2022,
                pd.Timestamp("2022-04-30 00:00:00"): 2022,
                pd.Timestamp("2022-05-31 00:00:00"): 2022,
            },
            "weekend": {
                pd.Timestamp("2022-01-31 00:00:00"): 0,
                pd.Timestamp("2022-02-28 00:00:00"): 0,
                pd.Timestamp("2022-03-31 00:00:00"): 0,
                pd.Timestamp("2022-04-30 00:00:00"): 1,
                pd.Timestamp("2022-05-31 00:00:00"): 0,
            },
            "month_sin": {
                pd.Timestamp("2022-01-31 00:00:00"): 0.8660254037844386,
                pd.Timestamp("2022-02-28 00:00:00"): 0.8660254037844387,
                pd.Timestamp("2022-03-31 00:00:00"): 1.2246467991473532e-16,
                pd.Timestamp("2022-04-30 00:00:00"): -0.8660254037844384,
                pd.Timestamp("2022-05-31 00:00:00"): -0.8660254037844386,
            },
            "month_cos": {
                pd.Timestamp("2022-01-31 00:00:00"): 0.5000000000000001,
                pd.Timestamp("2022-02-28 00:00:00"): -0.4999999999999998,
                pd.Timestamp("2022-03-31 00:00:00"): -1.0,
                pd.Timestamp("2022-04-30 00:00:00"): -0.5000000000000004,
                pd.Timestamp("2022-05-31 00:00:00"): 0.5000000000000001,
            },
        }
    )

    pd.testing.assert_frame_equal(results, expected)
