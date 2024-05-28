# ###################################################################
#
# Ingenero's quality check module for Template Code
# Developed by : Sheetal (Sheetal@ingenero.com)
# Developed on : 01/09/22
# Last Modified: 01/11/22
#
# ###################################################################
"""Importing required libraries"""
import numpy as np
import pandas as pd


def out_of_bound(taglist, in_df):
    """input_data_df is used in quality check and calculation block by setting timestamp as index."""
    # input_data_df = input_df[-1:].apply(pd.to_numeric, errors='coerce')
    input_data_df = [
        1
    ]  # for iterating the timestamps in input, here only 1 timestamp is considered
    taglist = taglist.set_index("tag_name")
    tags_list = taglist.index.tolist()
    breach_tag = []
    tag_not_included = []

    for _ in input_data_df:
        for tag in tags_list:
            # in_df = input_df.set_index("tag")
            # fetching min max value from taglist_new1 csv
            min_value = taglist.loc[tag, "min"]
            max_value = taglist.loc[tag, "max"]

            if min_value and max_value == -9999:
                tag_not_included.append(tag)
            else:
                tag_min_value = float(min_value)
                tag_actual_value_min = in_df.loc[tag]["value"]

                tag_max_value = float(max_value)
                tag_actual_value_max = in_df.loc[tag]["value"]
            # min max condition for quality check of Limit Breach tags
            if (
                tag_actual_value_min <= tag_min_value
                or tag_actual_value_max >= tag_max_value
            ):
                breach_tag.append(tag)
    del taglist, tags_list, in_df, input_data_df
    return breach_tag


def tag_stuck(input_df, data_pulling_period):
    """input_data_df is used in quality check and calculation block by setting timestamp as index."""
    input_data_df = input_df.set_index("timestamp")
    input_data_df = input_data_df.apply(pd.to_numeric, errors="coerce")
    # tags = taglist
    # Standard deviation for tag stuck
    tag_stuck_name = []
    tag_stuck_timestamp = []
    tag_stuck_error = []

    # select columns from input_data_df whose standard deviation is calculated
    cols = input_data_df.columns
    # creating std_df empty dataframe
    std_df = pd.DataFrame(columns=cols)

    for col in input_data_df.columns:
        # find standard deviation by taking rolling average
        std = input_data_df[col].rolling(data_pulling_period).std()
        std_df[col] = pd.DataFrame(std)

    std_df = np.trunc(10 * std_df) / 10
    # check std_df dataframe contain 0 standard deviation
    std_df_result = std_df[0.0]
    std_df_col_list = std_df_result.any()
    std_cols_name = list(std_df_col_list[std_df_col_list == True].index)

    for col in std_cols_name:
        rows = list(std_df_result[col][std_df_result[col] == True].index)
        for row in rows:
            tag_stuck_name.append(col)
            tag_stuck_timestamp.append(row)
            tag_stuck_error.append("tag is stuck")

    # creating dataframe for tag stuck
    quality_check2 = pd.DataFrame(
        data={
            "timestamp": tag_stuck_timestamp,
            "Tag_name": tag_stuck_name,
            "error": tag_stuck_error,
        }
    )
    print(f"\nquality_check for tag stuck \n{quality_check2}")
    return quality_check2
