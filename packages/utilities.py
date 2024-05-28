# ###################################################################
#
# Ingenero's utilities module for Template Code
# Developed by : Faizan Ali (sfaizan@ingenero.com)
# Developed on : 01/09/22
# Last Modified:01/11/22
#
# ###################################################################
"""Importing required libraries"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

import pandas as pd
from sqlalchemy import create_engine


class NoDataException(Exception):
    """Raises a No Data Exception when data for next timestamp is unavailable"""


def create_logger():
    """Create a logger with default configurations."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d, %(levelname)s,%(filename)s,%(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    handler = RotatingFileHandler(
        "logs\\log.csv", maxBytes=5 * 1024 * 1024, backupCount=5
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def check_files(file_list):
    """Check required files before execution.
    ---------------------------------------------------------
    Input : file_list [list(str)] = List of required files to check before execution.
    Output : None if all files exist, else will break."""
    for file in file_list:
        if os.path.exists(file):
            pass
        else:
            print("Error while reading config files.")
            logging.error("Error while reading config files. Exiting...")
            print("Exiting...")
            sys.exit()


def get_last_run(exec_mode: str, interval, lastrun_table=None, blc_id=None, con=None):
    """Fetch last run time of the algorithm.
    ----------------------------------------
    Input : exec_mode [str] = 'connect' or 'noconnect'
            interval [int] = default interval set in config file
            lastrun_table [str] = table name to query last run time.
            blc_id [int] = Id of BLC for which last_runtime to fetch.
    Output : last_runtime [pd.datetime]
    """
    if exec_mode == "noconnect":
        last_runtime = pd.read_sql(
            f"SELECT last_runtime from {lastrun_table}\
            where id={blc_id};",
            con=con.connect(),
        )["last_runtime"][0]
        running_interval = (
            pd.read_sql(
                f"SELECT running_interval from {lastrun_table}\
            where id={blc_id};",
                con=con.connect(),
            )["running_interval"][0]
            / 60
        )
    elif exec_mode == "connect":
        last_runtime = pd.read_csv("config/last_run_time.csv")["last_run_time"][0]
        running_interval = interval
    else:
        last_runtime = ""
        print("Could not get last run time. Unknown exec_mode.")
        logging.error("Could not get last run time. Unknown exec_mode.")
    # last_runtime = "2020-01-18 05:00:00"
    return pd.to_datetime(last_runtime), int(running_interval)


def db_conn(host, user, pwd, schema):
    """Creates a database connection using provided credentials.
    ---------------------------------------------------------
    Input : host [str], user [str], pwd [str], schema [str]
    Output : connection engine
    """
    db_engine = create_engine(f"mysql+pymysql://{user}:{pwd}@{host}/{schema}")
    return db_engine


def read_input(
    exec_mode,
    taglist,
    start_time: pd.to_datetime,
    end_time=None,
    input_table=None,
    connection=None,
    input_path=None,
):
    """Reads input data either from database or csv based on the selected mode.
    --------------------------------------------------------------------------
    Input : exec_mode [str] = 'connect' or 'noconnect'.\n
            input_table [str] = Table name for reading input data.\n
            taglist [tuple] = Tuple of Tag Ids to fetch data.\n
    """
    if exec_mode == "noconnect":
        # end = start_time + delta
        query = f"SELECT * FROM {input_table} where tag in \
            {taglist} and timestamp > '{start_time}' and timestamp <= '{end_time}';"
        data = pd.read_sql(query, con=connection.connect())
    else:
        input_file = os.listdir(input_path)
        print(input_path + input_file[0])
        data = pd.read_csv(
            input_path + input_file[0],
            parse_dates=["timestamp"],
            usecols=["timestamp", "tag", "value"],
        )
        data = data[data["timestamp"] >= start_time]
    return data


def write_output(
    exec_mode,
    data,
    lastrun_time: pd.to_datetime,
    output_table=None,
    connection=None,
    lastrun_table=None,
    blc_id=None,
    output_path=None,
):
    """Write output to either database or csv file based on the selected mode."""
    if exec_mode == "noconnect":
        conn = connection.connect()
        output_query = f"INSERT INTO {output_table} VALUES \
            {list(zip(*map(data.get, data)))};".replace(
            "[", ""
        ).replace(
            "]", ""
        )
        # print(output_query)
        conn.execute(output_query)
        print("Output saved")
        last_run_query = f"UPDATE {lastrun_table} SET last_runtime ='{lastrun_time}'\
            WHERE id = {blc_id};"
        conn.execute(last_run_query)
        
        
        '''last_run_query = f"UPDATE icap_datasource_master_table SET last_run_time ='{lastrun_time}'\
            WHERE id = 770 ;"
        conn.execute(last_run_query)'''
        
        
        print("Last run updated.")
        logging.info("Last run updated.")
    else:
        # writing output.csv
        output_file = os.listdir(output_path)
        if os.path.isfile(output_path + output_file[0]):
            print("Output file found. Overwriting...")
            logging.warning("Output file found. Overwriting...")
            data.to_csv("output/output.csv", index=False)
        else:
            print("No existing output.csv file. Writing...")
            logging.warning("No existing output.csv file. Writing...")
            data.to_csv("output/output.csv", index=False)
        # updating last_run_time.csv
        last_run_file = pd.read_csv(
            "config/last_run_time.csv",
            index_col="blc_id",
            parse_dates=["last_run_time"],
        )
        last_run_file.at[blc_id, "last_run_time"] = lastrun_time
        last_run_file.to_csv("config/last_run_time.csv", index=False)
        print("Last run updated.")
        logging.info("Last run updated.")
        
def pivot_rename(df,csv_map,name_from,name_to):
    """
    This function will pivot the table from 3 column format to suitable format
    Also renames the column with provided name against id
    """   
    tag_dict=csv_map[[name_from,name_to]].set_index(name_from).to_dict()[name_to]
    resultdf = pd.pivot_table(df, values ='value', index ='timestamp',
                             columns ='tag')
    resultdf.rename(columns=tag_dict,
              inplace=True)
    return resultdf
