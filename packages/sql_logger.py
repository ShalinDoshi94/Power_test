# ###################################################################
#
# Ingenero's SQL Logger module for Template Code
# Developed by : Faizan Ali (sfaizan@ingenero.com)
# Developed on : 01/09/22
# Last Modified:01/11/22
#
# ###################################################################
"""Importing required libraries"""
from pymysql.err import OperationalError as TimeOutError
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError as QueryError


class MySQLlogger:
    """Logger class for logging directly into SQL database"""

    def __init__(self, host, user, passwd, schema, table):
        """Init function for class MySQLlogger"""
        self.host = host
        self.user = user
        self.passwd = passwd
        self.schema = schema
        self.table = table
        self.status = True
        self.formatt = "%(timestamp)s,%(level)s,%(message)s"
        self.columns = self.formatt.replace(r"%(", "").replace(r")s", "")
        self.mysql_engine = ""

    def initialize(self, status):
        """Initialize logger instance"""
        self.status = status
        if self.status == "True":
            try:
                self.mysql_engine = create_engine(
                    "mysql+pymysql://{}:{}@{}/{}".format(
                        self.user, self.passwd, self.host, self.schema
                    )
                )
                self.mysql_engine.connect()
                return self.mysql_engine
            except TimeOutError as error:
                return error
        else:
            pass

    def formatter(self, log_format):
        """Set log format"""
        self.formatt = log_format
        self.columns = self.formatt.replace(r"%(", "").replace(r")s", "")

    def log(self, level, log):
        """Background function to write logs"""
        if self.status == "True":
            _ = level
            try:
                query = f"INSERT INTO {self.table} ({self.columns}) VALUES ({log})"
                self.mysql_engine.connect().execute(query)
            except QueryError as error:
                return error

    def info(self, log):
        """Log info"""
        self.log("INFO", log)

    def warning(self, log):
        """Log warning"""
        self.log("WARNING", log)

    def error(self, log):
        """Log error"""
        self.log("ERROR", log)


if __name__ == "__main__":
    logger = MySQLlogger(
        "192.168.8.205",
        "isspde_team",
        "isspde_team",
        "icap_business_logic",
        "blc_1_log",
    )
    logger.initialize("True")
    logger.formatter("message,timestamp,type,component")
    logger.error("sfsaf")
