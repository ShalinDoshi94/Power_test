# ###################################################################
#
# Ingenero's python module for Power Optimization 
# Developed by : Shivamkumar Kanojia (skanojia@ingenero.com)
# Developed on : 10/08/2023
# Last Modified: 12/02/2024
#
# ###################################################################
"""
# Importing standard python packages and supporting packages
"""
import configparser
import traceback
from datetime import timedelta
from time import time
import math
import sys
import pandas as pd 
from gekko import GEKKO

# from calculations import
# from packages.quality_check import out_of_bound
from packages.sql_logger import MySQLlogger
from packages.utilities import (
    check_files,
    create_logger,
    db_conn,
    get_last_run,
    read_input,
    write_output,
    pivot_rename
)

# from calculations.calculation import transition_state,optimization_model,data_quality_check


class NoDataException(Exception):
    """Raises a No Data Exception when data for next timestamp
    is unavailable"""


# Create a logger instance with default configs. For more configurations
# go to packages/utilities.py.
logging = create_logger()

logging.info("ING_BLC_SCRIPT started")

# Reading basic configurations

parser = configparser.ConfigParser()
parser.read(filenames=["config/config.ini"])
status = parser.get("DEFAULT", "status")
exec_mode = parser.get("DEFAULT", "mode")
interval = parser.get("DEFAULT", "delta")
file_list = ["config/config.ini","config/input_alias_map.csv"]
# manual_entry_table = parser.get("DB", "manual_entry_table")
error_table = parser.get('DB', 'error_table')
alert_table = parser.get('DB', 'alert_table')
recommendation_table = parser.get('DB', 'recommendation_table')
user_opt_table =parser.get('DB', 'user_opt_table')
logger_config = dict(parser["LOGGER"].items())
# Creating SQL Logger instance in case of logging directly to SQL (For error logs in ICAP)
logger = MySQLlogger(
    logger_config["host"],
    logger_config["user"],
    logger_config["pass"],
    logger_config["schema"],
    logger_config["table"],
)
logger.initialize(logger_config["status"])
logger.formatter("message,timestamp,type,component")
# logger.error(f"'Script Started','{last_run_time}','BLC', 'ICAP_BLCXYZ'")


# Read Database configurations for DB connection
db_config = dict(parser["DB"].items())
input_path = parser.get("PATH", "input")
output_path = parser.get("PATH", "output")


# def calculation(data):
#     """Calculations that need to be done in main.py file needs to
#     be defined here."""
#     data = out_of_bound(taglist, data)
#     print(data)
    # return data
# last_run_time =pd.to_datetime('2023-01-19 14:00:00')


#________________________________________________________________________________________________________________________________________________________

# import traceback

# from datetime import datetime
'''Below Function is used to check whether Equipment is under transition State if found
in transition state then the code will break in in function and will push -9999 in output 
table.
'''
def transition_state(time_upto,input_df,db_connection_1,alert_table):
    eqpt_status = []
    status= pd.read_csv('config/transition_alias.csv')
    new_status = status.dropna()

    #Below loop we have removed the transformer from list check Transition state only for Equipments.
    for i,row in new_status.iterrows():
        
        eqpt_status.append(input_df[row['alias']].values[0])
        
        if input_df[row['alias']].values[0] !=0:
            message = f"{row['Equipment list']} is under Transition State."
                    
            alert_dict = [{'timestamp':time_upto,'category':'Transition State','tag':row['Equipment list'],'message':message,}]
            alert_df = pd.DataFrame(alert_dict)
            alert_df.to_sql(alert_table, con=db_connection_1, if_exists='append', index=False)
        
    mask = status.index.isin(new_status.index)
    status = status[~mask]
    
    #In this Below Loop we are checking transition for Only Transformers.
    for i,row in status.iterrows():
        if input_df[row['alias']].values[0] > 0 and input_df[row['alias']].values[0] < 1:
            
            eqpt_status.append(1)
            
            message = f"{row['alias']} is under Transition State."
                    
            alert_dict = [{'timestamp':time_upto,'category':'Transition State','description':'-','tag':row['alias'],'message':message}]
            alert_df = pd.DataFrame(alert_dict)
            alert_df.to_sql(alert_table, con=db_connection_1, if_exists='append', index=False)
            
        else:
            eqpt_status.append(0)
            
            
    return eqpt_status

'''Below Function is Used for Data Quality Check if any tag is Out of the training range , it will effects in 
optimized value that will be retrieved by our Optimization  for that purpose if Tag will be out of bound we are 
Skipping Optimization at that Timestamp and pushing -9999 to output table '''
def data_quality_check(input_df,time_upto,alert_table,db_connection_1):
    
    #---------------------------------- Data Quality Check ----------------------------------#
    user_query = f"SELECT * From  {user_opt_table};"
    # user_query = "SELECT * FROM isspde_011.user_opt_status;"
    user_opt_status =  pd.read_sql(user_query,con=db_connection_2)
    user_opt_status=user_opt_status.set_index('Equipment_list')
    
    min_max= pd.read_csv('config/min_max_input_df.csv')
    out_of_bound = []   
    
    manual_entry_query = "SELECT * FROM isspde_011.manual_entry;"
    manual_entry_table =  pd.read_sql(manual_entry_query,con=db_connection_2)
    manual_ip21_taglist =  manual_entry_table['tag'].to_list()
    manual_entry_table = manual_entry_table.set_index('tag')
    
    for i,row in min_max.iterrows():
        
        if row['tag'] in manual_ip21_taglist and (input_df[row['DP_OPT  Tag']].values[0] < row['MIN'] or input_df[row['DP_OPT  Tag']].values[0] > row['MAX']) and  manual_entry_table.loc[row['tag'],'substitute'] != -9999:
            # print(row['tag'],input_df[row['DP_OPT  Tag']].values[0])
            input_df[row['DP_OPT  Tag']].values[0]= manual_entry_table.loc[row['tag'],'substitute']
        
        elif (input_df[row['DP_OPT  Tag']].values[0] < eval(row['Equipment'])*row['MIN'] or input_df[row['DP_OPT  Tag']].values[0] > row['MAX']):
            
            # user_opt_status.loc[row['eqpt'],'user_status']=0
            
            out_of_bound.append(1)
            
            message = f"Tag value {round(input_df[row['DP_OPT  Tag']].values[0],1)} is out of its normal operating range i.e MIN = {row['MIN']} and MAX = {row['MAX']} ."# add substitute value too
            # print(message)
            alert_dict = [{'timestamp':time_upto,'category':'Tag Out Of Bound','description':row['description'],'tag':row['tag'],'message':message,}]
            alert_df = pd.DataFrame(alert_dict)
            alert_df.to_sql(alert_table, con=db_connection_1, if_exists='append', index=False)
        
        else :
            out_of_bound.append(0)
             
        # try:
            
        #     if (input_df[row['DP_OPT  Tag']].values[0] < eval(row['Equipment'])*row['MIN'] or input_df[row['DP_OPT  Tag']].values[0] > row['MAX']) and (user_opt_status.loc[row['eqpt'],'user_status']==1):
        #         out_of_bound.append(1)
                
        #         message = f" tag value: {round(input_df[row['DP_OPT  Tag']].values[0],1)} is out of it training Range i.e MIN = {row['MIN']} and MAX = {row['MAX']}  "# add substitute value too
        #         # print(message)
        #         alert_dict = [{'timestamp':time_upto,'category':'Tag Out Of Bound','description':row['description'],'tag':row['tag'],'message':message,}]
        #         alert_df = pd.DataFrame(alert_dict)
        #         alert_df.to_sql(alert_table, con=db_connection_1, if_exists='append', index=False)
            
        #     else :
        #         out_of_bound.append(0)
                
        # except KeyError :
        #     # print("hi from except ")
        #     # print(row['eqpt'])
        #     if (input_df[row['DP_OPT  Tag']].values[0] < eval(row['Equipment'])*row['MIN'] or input_df[row['DP_OPT  Tag']].values[0] > row['MAX']) :
        #         out_of_bound.append(1)
                
        #         message = f" tag value: {round(input_df[row['DP_OPT  Tag']].values[0],1)} is out of it training Range i.e MIN = {row['MIN']} and MAX = {row['MAX']}  "# add substitute value too
        #         # print(message)
        #         alert_dict = [{'timestamp':time_upto,'category':'Tag Out Of Bound','description':row['description'],'tag':row['tag'],'message':message,}]
        #         alert_df = pd.DataFrame(alert_dict)
        #         alert_df.to_sql(alert_table, con=db_connection_1, if_exists='append', index=False)
        #     else :
        #         out_of_bound.append(0)
            
        
            
    return out_of_bound,user_opt_status

    
'''IF Transition State Check And Quality Check Test is Passed Code will Move to the below function which try to calculate 
required optimization state for current timestamp if our code wont be able to find the best optmization state for current timestamp 
it throw and error of "No Solution Found " and will break code and -9999 will be pushed in output table  '''
def optimization_model(input_df,time_upto,alert_table,db_connection_1,db_connection_2,recommendation_table):   
    
    
    #Data Quality Check Doing Here instead of outside function to avoid Multiple Alerts 
    out_of_bound,user_opt_status = data_quality_check(input_df,last_run_time+interval,alert_table,db_connection_1)
#__________________________________________________________________________________________________________________________________________________________________________________________________________________________________   
    #STG C3 Manipilation     
    if input_df['DP_OPT_RUNNING_STATUS_STG_C3'].values[0] ==1:
        if input_df['DP_OPT_400STM_PHC_GEN_C3_STG_LBH'].values[0] <10000:
        # if input_df['DP_OPT_400STM_PHC_GEN_C3_STG_LBH'].values[0] == input_df['DP_OPT_STM_PHC_CONS_PRDS_1250_400_LBH'].values[0]:
            new_steam_flow_400_STG_C3 = input_df['DP_OPT_STM_PHC_CONS_PRDS_1250_400_LBH'].values[0]
            new_PRDS_flow_1250_400 = 0
        else:
            new_steam_flow_400_STG_C3 = input_df['DP_OPT_400STM_PHC_GEN_C3_STG_LBH'].values[0]
            new_PRDS_flow_1250_400 = input_df['DP_OPT_STM_PHC_CONS_PRDS_1250_400_LBH'].values[0]
        
    else:
        new_steam_flow_400_STG_C3 = input_df['DP_OPT_400STM_PHC_GEN_C3_STG_LBH'].values[0]
        new_PRDS_flow_1250_400 = input_df['DP_OPT_STM_PHC_CONS_PRDS_1250_400_LBH'].values[0]
            
    new_steam_flow_1250_STG_C3= new_steam_flow_400_STG_C3 + input_df['DP_OPT_175STM_PHC_GEN_C3_STG_LBH'].values[0]
    
    #Header Imbalances
    header_imb_df = pd.read_csv('config/header_imbalances.csv')
    header_imb_df =header_imb_df.set_index('alias')   
    header_imb_df['values']=''
    for i, row in header_imb_df.iterrows():
        # print(eval(row['expression']))
        row['values']=eval(row['expression'])
        

    m = GEKKO(remote=False )
      
    GT_C1_RUN_STATUS = input_df['DP_OPT_RUNNING_STATUS_GT_C1'].values[0] 
    GT_C2_RUN_STATUS = input_df['DP_OPT_RUNNING_STATUS_GT_C2'].values[0] 
    GT_C4_RUN_STATUS = input_df['DP_OPT_RUNNING_STATUS_GT_HRSG_C4'].values[0] 
    GT_C5_RUN_STATUS = input_df['DP_OPT_RUNNING_STATUS_GT_HRSG_C5'].values[0] 
    GT_R5_RUN_STATUS = input_df['DP_OPT_RUNNING_STATUS_GT_HRSG_R5'].values[0] 
    GT_R6_RUN_STATUS = input_df['DP_OPT_RUNNING_STATUS_GT_HRSG_R6'].values[0] 
    
    BOILER_C1_RUN_STATUS = input_df['DP_OPT_RUNNING_STATUS_BLR_C1'].values[0] 
    BOILER_C2_RUN_STATUS = input_df['DP_OPT_RUNNING_STATUS_BLR_C2'].values[0] 
    
    STG_C3_RUN_STATUS = input_df['DP_OPT_RUNNING_STATUS_STG_C3'].values[0]  
    STG_R2_RUN_STATUS = input_df['DP_OPT_RUNNING_STATUS_STG_R2'].values[0] 
    STG_R3_RUN_STATUS = input_df['DP_OPT_RUNNING_STATUS_STG_R3'].values[0] 
    STG_R4_RUN_STATUS = input_df['DP_OPT_RUNNING_STATUS_STG_R4'].values[0] 
     
    '''
    Below we have Defined Cost And Revenue Variable which are going to be utilized to calculate the Profit For WL 
    
    Following are the variables which are going to be used into the objective function . 
    ''' 
    # OBJECTIVE VARIABLES.
    profit =m.Var(value=input_df['DP_OPT_PROFIT_POWERHOUSE_DOLLARS'].values[0],  lb=input_df['DP_OPT_PROFIT_POWERHOUSE_DOLLARS'].values[0],  ub=100000,  name='profit')
    
    
    # COST VARIABLES.
    # PP has some internal consumption if generates more than that it can sell it further which is a part of revenue 
    power_export_dollar =m.Var(value=input_df['DP_OPT_REVENUE_POWER_EXPORT_DOLLARS'].values[0],  lb=input_df['DP_OPT_REVENUE_POWER_EXPORT_DOLLARS'].values[0],  ub=1000000,  name='power_export_dollar')
    
    # PROCESS VARIABLES.
    
    # the is cost to WL for consuming required fuel for generating power
    total_fuel_within_PH_dollar =m.Var(value=input_df['DP_OPT_COST_FUEL_WITHIN_POWERHOUSE_DOLLARS'].values[0],  lb=1*0,  ub=1000000,  name='total_fuel_within_PH_dollar')
    
    # power exported to the grid
    total_power_export_MW =m.Var(value=input_df['DP_OPT_POWER_EXPORT_MW'].values[0],  lb=1*0,  ub= 360 if (input_df['DP_OPT_TRANSFORMER_T1_STATUS'].values[0]==1 and input_df['DP_OPT_TRANSFORMER_T2_STATUS'].values[0]==1 ) else 180,  name='total_power_export_MW')
    
    
    '''
    Below we have action variables which are going to be results of our optimizer code 
    ''' 
    # FINAL ACTION VARIABLE 
    GT_C1_NG_Flow_SCFH =m.Var(value=input_df['DP_OPT_NG_PHC_CONS_C1_GT_SCFH'].values[0]*GT_C1_RUN_STATUS,  lb=0,  ub=1000000,  name='GT_C1_NG_Flow_SCFH')
    GT_C2_NG_Flow_SCFH =m.Var(value=input_df['DP_OPT_NG_PHC_CONS_C2_GT_SCFH'].values[0]*GT_C2_RUN_STATUS,  lb=0,  ub=1000000,  name='GT_C2_NG_Flow_SCFH')
    GT_C4_NG_Flow_SCFH =m.Var(value=input_df['DP_OPT_NG_PHC_CONS_C4_GT_SCFH'].values[0]*GT_C4_RUN_STATUS,  lb=0,  ub=1000000,  name='GT_C4_NG_Flow_SCFH')
    GT_C5_NG_Flow_SCFH =m.Var(value=input_df['DP_OPT_NG_FLOW_PHC_C5_GT_SCFH'].values[0]*GT_C5_RUN_STATUS,  lb=0,  ub=1000000,  name='GT_C5_NG_Flow_SCFH')
    GT_R5_NG_Flow_KPPH =m.Var(value=input_df['DP_OPT_NG_RSC_CONS_TOTAL_R5_GT_KPPH'].values[0]*GT_R5_RUN_STATUS,  lb=0,  ub=100,  name='GT_R5_NG_Flow_KPPH')
    GT_R6_NG_Flow_KPPH =m.Var(value=input_df['DP_OPT_NG_RSC_CONS_TOTAL_R6_GT_KPPH'].values[0]*GT_R6_RUN_STATUS,  lb=0,  ub=100,  name='GT_R6_NG_Flow_KPPH')
    FHRSG_C1_NG_SCFH =m.Var(value=input_df['DP_OPT_NG_PHC_GEN_C1_BOILER_SCFH'].values[0]*BOILER_C1_RUN_STATUS,  lb=0,  ub=1000000,  name='FHRSG_C1_NG_SCFH')
    FHRSG_C2_NG_SCFH =m.Var(value=input_df['DP_OPT_NG_PHC_GEN_C2_BOILER_SCFH'].values[0]*BOILER_C2_RUN_STATUS,  lb=0,  ub=1000000,  name='FHRSG_C2_NG_SCFH')
    HRSG_R5_Steam_Gen_1900_KLBH =m.Var(value=input_df['DP_OPT_HPSTMOL_FLOW_RSC_R5_HRSG_KPPH'].values[0]*GT_R5_RUN_STATUS,  lb=0,  ub=600,  name='HRSG_R5_Steam_Gen_1900_KLBH')
    HRSG_R6_Steam_Gen_1900_KLBH =m.Var(value=input_df['DP_OPT_HPSTMOL_FLOW_RSC_R6_HRSG_KPPH'].values[0]*GT_R6_RUN_STATUS,  lb=0,  ub=600,  name='HRSG_R6_Steam_Gen_1900_KLBH')
    STG_C3_Steam_Cons_1250_LBH =m.Var(value=input_df['DP_OPT_1250STM_PHC_CONS_C3_STG_LBH'].values[0]*STG_C3_RUN_STATUS,  lb=0,  ub=1500000,  name='STG_C3_Steam_Cons_1250_LBH')
    STG_R2_Steam_Cons_600_KLBH =m.Var(value=input_df['DP_OPT_600STM_RS_CONS_R2_STG_KLBH'].values[0]*STG_R2_RUN_STATUS,  lb=0,  ub=400,  name='STG_R2_Steam_Cons_600_KLBH')
    STG_R3_Steam_Cons_600_KLBH =m.Var(value=input_df['DP_OPT_600STM_RS_CONS_R3_STG_KLBH'].values[0]*STG_R3_RUN_STATUS,  lb=0,  ub=400,  name='STG_R3_Steam_Cons_600_KLBH')
    STG_R4_Steam_Cons_1900_KLBH =m.Var(value=input_df['DP_OPT_STM_RSC_GEN_R4_TOT_EXHST_KLBH'].values[0]*STG_R4_RUN_STATUS,  lb=0,  ub=1200,  name='STG_R4_Steam_Cons_1900_KLBH')
    GT_C1_Power_MW =m.Var(value=input_df['DP_OPT_PWR_PHC_GEN_C1_GT_MW'].values[0]*GT_C1_RUN_STATUS,  lb=0,  ub=100,  name='GT_C1_Power_MW')
    GT_C2_Power_MW =m.Var(value=input_df['DP_OPT_PWR_PHC_GEN_C2_GT_MW'].values[0]*GT_C2_RUN_STATUS,  lb=0,  ub=100,  name='GT_C2_Power_MW')
    GT_C4_Power_MW =m.Var(value=input_df['DP_OPT_PWR_PHC_GEN_C4_GT_MW'].values[0]*GT_C4_RUN_STATUS,  lb=0,  ub=100,  name='GT_C4_Power_MW')
    GT_C5_Power_MW =m.Var(value=input_df['DP_OPT_PWR_PHC_GEN_C5_GT_MW'].values[0]*GT_C5_RUN_STATUS,  lb=0,  ub=100,  name='GT_C5_Power_MW')
    GT_R5_Power_MW =m.Var(value=input_df['DP_OPT_PWR_RSC_GEN_R5_STG_MW'].values[0]*GT_R5_RUN_STATUS,  lb=0,  ub=200,  name='GT_R5_Power_MW')
    GT_R6_Power_MW =m.Var(value=input_df['DP_OPT_PWR_RSC_GEN_R6_STG_MW'].values[0]*GT_R6_RUN_STATUS,  lb=0,  ub=200,  name='GT_R6_Power_MW')
    STG_C3_Power_MW =m.Var(value=input_df['DP_OPT_PWR_PHC_GEN_C3_STG_MW'].values[0]*STG_C3_RUN_STATUS,  lb=0,  ub=100,  name='STG_C3_Power_MW')
    STG_R2_Power_MW =m.Var(value=input_df['DP_OPT_PWR_RS_GEN_R2_STG_MW'].values[0]*STG_R2_RUN_STATUS,  lb=0,  ub=50,  name='STG_R2_Power_MW')
    STG_R3_Power_MW =m.Var(value=input_df['DP_OPT_PWR_RS_GEN_R3_STG_MW'].values[0]*STG_R3_RUN_STATUS,  lb=0,  ub=50,  name='STG_R3_Power_MW')
    STG_R4_Power_MW =m.Var(value=input_df['DP_OPT_PWR_RSC_GEN_R4_STG_MW'].values[0]*STG_R4_RUN_STATUS,  lb=0,  ub=100,  name='STG_R4_Power_MW')
    Power_Gen_MW =m.Var(value=input_df['DP_OPT_C_TOTAL_POWER_GEN_MW'].values[0],  lb=0,  ub=800,  name='Power_Gen_MW')
    Letdown_1900_TO_600_KLBH =m.Var(value=input_df['DP_OPT_LETDOWN_1900_TO_600_KLBH'].values[0],lb=0,  ub=1000,  name='Letdown_1900_TO_600_KLBH')
    BLR_C1_Steam_Gen_1250_LBH =m.Var(value=input_df['DP_OPT_1250STM_PHC_GEN_C1_BOILER_LBH'].values[0]*BOILER_C1_RUN_STATUS,  lb=0,  ub=1000000,  name='BLR_C1_Steam_Gen_1250_LBH')
    BLR_C2_Steam_Gen_1250_LBH =m.Var(value=input_df['DP_OPT_1250STM_PHC_GEN_C2_BOILER_LBH'].values[0]*BOILER_C2_RUN_STATUS,  lb=0,  ub=1000000,  name='BLR_C2_Steam_Gen_1250_LBH')
    HRSG_C4_Steam_Gen_1250_LBH =m.Var(value=input_df['DP_OPT_1250STM_PHC_GEN_C4_HRSG_LBH'].values[0]*GT_C4_RUN_STATUS,  lb=0,  ub=500000,  name='HRSG_C4_Steam_Gen_1250_LBH')
    HRSG_C5_Steam_Gen_1250_LBH =m.Var(value=input_df['DP_OPT_1250STM_PHC_GEN_C5_HRSG_LBH'].values[0]*GT_C5_RUN_STATUS,  lb=0,  ub=500000,  name='HRSG_C5_Steam_Gen_1250_LBH')
    Letdown_1250_TO_400_LBH =m.Var(value= new_PRDS_flow_1250_400,  lb=0,  ub=1400000,  name='Letdown_1250_TO_400_LBH')
    STG_R4_Steam_Gen_600_KLBH =m.Var(value=input_df['DP_OPT_600STM_RSC_GEN_R4_STG_KPPH'].values[0]*STG_R4_RUN_STATUS,  lb=0,  ub=1000,  name='STG_R4_Steam_Gen_600_KLBH')
    STG_C3_Steam_Gen_400_LBH =m.Var(value=input_df['DP_OPT_400STM_PHC_GEN_C3_STG_LBH'].values[0]*STG_C3_RUN_STATUS,  lb=0,  ub=750000,  name='STG_C3_Steam_Gen_400_LBH')
    Letdown_From_400_TO_175_LBH =m.Var(value=input_df['DP_OPT_STM_PHC_CONS_PRDS_400_175_LBH'].values[0],  lb=0,name='Letdown_From_400_TO_175_LBH')
    Letdown_From_175_TO_30_LBH =m.Var(value=input_df['DP_OPT_C_TOTAL_LETDOWN_175_30_LBH'].values[0],  lb=0,    name='Letdown_From_175_TO_30_LBH')
    STEAM_VENTING_LBH =m.Var(value=input_df['DP_OPT_STEAM_VENTING_LBH'].values[0] ,lb=0,ub =300000, name='STEAM_VENTING_LBH')
    Steam_Venting_Dollar=m.Var(lb=0,ub=500,name='Steam_Venting_Dollar')
    
    #CONSTANTS 
    #Following are the constants that would be used either in Objective function or in expressions 
    power_within_WL_dollar = input_df['DP_OPT_REVENUE_POWER_WITHIN_WL_DOLLARS'].values[0]  
    power_purchased_dollar = input_df['DP_OPT_COST_POWER_PURCHASED_DOLLARS'].values[0]
    steam_within_WL_dollar = input_df['DP_OPT_REVENUE_STEAM_WITHIN_WL_DOLLARS'].values[0]  
    steam_export_LACC_dollar = input_df['DP_OPT_REVENUE_STEAM_EXPORT_LACC_DOLLARS'].values[0]
    LMP_Price_Dollar = input_df['DP_OPT_AXIALL_LMP_PRICE_DOLLARPMWH'].values[0] 
    power_within_WL_MW = input_df['DP_OPT_C_POWER_WITHIN_POWERHOUSE_MW'].values[0] 
    
     
    #__________________________________________DEFINING OBJECTIVE FUNCTION____________________________________________________________________________________________________________________
  
    '''
    for profit maximization our main aim is to increase our revenue by cutting down the cost
    '''
    
    m.Maximize(profit)
    
    m.Equation(((power_export_dollar + power_within_WL_dollar + steam_within_WL_dollar + steam_export_LACC_dollar)-
               (power_purchased_dollar + total_fuel_within_PH_dollar+Steam_Venting_Dollar))-profit==0)
   
    m.Equation(Steam_Venting_Dollar-(STEAM_VENTING_LBH*1.5/1000)==0)
    #__________________________________________DEFINING CONSTRAINTS____________________________________________________________________________________________________________________
    
    # LEVEL_1
    '''
    power_export_dollar
    power_within_WL_dollar 
    steam_within_WL_dollar
    steam_export_LACC_dollar
    power_purchased_dollar
    total_fuel_within_PH_dollar
    Linking Variables Equations
    '''
    
    m.Equation((power_export_dollar-(total_power_export_MW*7.5*input_df['DP_OPT_HENRY_HUB_NG_PRICE_DOLLARPMMBTU'].values[0])/0.293071)==0)
    
    ## LEVEL_2_Power_Export
    '''
    total_power_export_MW
    '''
    
    '''
    Total Power Export Basis 
    
    Current Operating Data:
    Power export = Power Gen - Power consumption
    Power Gen = GT and STG produced Power
    Power Consumption = Circuit Load + Auxillary
        
    For Code: 
    Power export = Manupilated
    Power Gen = Manupilated
    Power Consumption = Fixed 
    '''
    
    m.Equation(total_power_export_MW -(Power_Gen_MW - power_within_WL_MW) ==0) 
    
    ## LEVEL_3_Power_Export
    '''
    Power_Gen_MW
    power_within_WL_MW - Defined in Optimizer table
    LMP_Price_Dollar - Defined in Optimizer table
    input_df['DP_OPT_HENRY_HUB_NG_PRICE_DOLLARPMMBTU'].values[0] - Defined in Optimizer table 
    '''
    
    m.Equation(Power_Gen_MW-(GT_C1_Power_MW + GT_C2_Power_MW + GT_C4_Power_MW + GT_C5_Power_MW + GT_R5_Power_MW + GT_R6_Power_MW
                           + STG_C3_Power_MW + STG_R2_Power_MW + STG_R3_Power_MW + STG_R4_Power_MW)==0)
    
    
    ## LEVEL_4_Power_Export
    '''
    GT_C1_Power - All are manupilated variables
    GT_C2_Power
    GT_C4_Power 
    GT_C5_Power 
    GT_R5_Power 
    GT_R6_Power
    STG_C3_Power 
    STG_R2_Power 
    STG_R3_Power 
    STG_R4_Power
    '''
    
    
    ## LEVEL_1_Total Fuel within PowerHouse
    m.Equation((((((GT_C1_NG_Flow_SCFH + GT_C2_NG_Flow_SCFH + GT_C4_NG_Flow_SCFH + GT_C5_NG_Flow_SCFH + FHRSG_C1_NG_SCFH + FHRSG_C2_NG_SCFH)*24/10**6)+
                  ((GT_R5_NG_Flow_KPPH + GT_R6_NG_Flow_KPPH )*1000*24/(input_df['DP_OPT_NG_SPECIFIC_GRAVITY_PERCENT'].values[0]*0.0806)/10**6))* 
                 input_df['DP_OPT_NG_HV_BTU_CF'].values[0]*(input_df['DP_OPT_HENRY_HUB_NG_PRICE_DOLLARPMMBTU'].values[0])/24))-(total_fuel_within_PH_dollar)==0)
   
    ## LEVEL_2_Total Fuel within PowerHouse
    '''
    GT_C1_NG_Flow_SCFH , GT_C2_NG_Flow_SCFH, GT_C4_NG_Flow_SCFH ,GT_C5_NG_Flow_SCFH ,GT_R5_NG_Flow_KPPH , GT_R6_NG_Flow_KPPH
    FHRSG_C1_NG_SCFH , FHRSG_C2_NG_SCFH -Defined In Independent Decision Variables 
    
    input_df['DP_OPT_NG_SPECIFIC_GRAVITY_PERCENT'].values[0] - Defined in OPT tables
    input_df['DP_OPT_NG_HV_BTU_CF'].values[0] - Defined in OPT tables
    input_df['DP_OPT_HENRY_HUB_NG_PRICE_DOLLARPMMBTU'].values[0] - Defined in OPT tables
    '''
 
    #___________________________________________________HEADER BALANCES____________________________________________________________________ 
 
    '''
    Steam Balance Equations - Header balances
    1900, 1250, 600, 400, 175, 30, Vent, letdown
    
    
    Steam within WL = steam going to users (400, 175, 30)
    
    1900 --> 1250 --> 600 --> 400 --> 175 --> 30
    
    ** Fixed 
    
    1900 header balance: Haeder IN = Header OUT - Imbalance
    
    
    
    m.Eq (Haeder IN - Header OUT (letdown) - Imbalance** = 0)
    
    
    1250 header balance: Haeder IN = Header OUT - Imbalance
    
    m.Eq (Haeder IN (1900 to 1250 letdown) - Header OUT (LACC** + 1250 to 600 letdown) - Imbalance** = 0)
    
    
    400 header balance: Haeder IN = Header OUT - Imbalance
    
    m.Eq (Haeder IN (600 to 400 letdown) - Header OUT (To users** + 400 to 175 letdown) - Imbalance** = 0)
    
   
    175 header balance: Haeder IN = Header OUT - Imbalance
    
    m.Eq (Haeder IN (400 to 175 letdown + STG C3 LP exhaust**) - Header OUT (Venting for Power) - Imbalance** = 0)    
    
    
    30 header balance: Haeder IN = Header OUT - Imbalance
    
    m.Eq (Haeder IN (175 to 30 letdown) - Header OUT (Venting for Power) - Imbalance** = 0)
    ''' 
 
    #1900 STEAM BALANCE
    m.Equation(((HRSG_R5_Steam_Gen_1900_KLBH)+(HRSG_R6_Steam_Gen_1900_KLBH)-(STG_R4_Steam_Cons_1900_KLBH*input_df['DP_OPT_RUNNING_STATUS_STG_R4'].values[0]) -(Letdown_1900_TO_600_KLBH))-(header_imb_df.loc['HEADER_IMBALANCE_1900_KLBH','values'])==0)
    
    #1250 STEAM BALANCE
    m.Equation(((BLR_C1_Steam_Gen_1250_LBH)+(BLR_C2_Steam_Gen_1250_LBH)+(HRSG_C4_Steam_Gen_1250_LBH)+(HRSG_C5_Steam_Gen_1250_LBH)-(STG_C3_Steam_Cons_1250_LBH)-(Letdown_1250_TO_400_LBH)-(input_df['DP_OPT_STM_EXPORT_LACC_1250_600_LBH'].values[0]))-(header_imb_df.loc['HEADER_IMBALANCE_1250_LBH','values'])==0)
    
    #600 STEAM BALANCE
    m.Equation(((STG_R4_Steam_Gen_600_KLBH)+(Letdown_1900_TO_600_KLBH)-(STG_R3_Steam_Cons_600_KLBH)-(STG_R2_Steam_Cons_600_KLBH)-(input_df['DP_OPT_600STM_CONS_TO_PROCESS_400_KLBH'].values[0]))-(header_imb_df.loc['HEADER_IMBALANCE_600_KLBH','values'])==0)
    
    #400 STEAM BALANCE
    m.Equation((STG_C3_Steam_Gen_400_LBH)+(Letdown_1250_TO_400_LBH)+(input_df['DP_OPT_600STM_CONS_TO_PROCESS_400_KLBH'].values[0]*1000)-((input_df['DP_OPT_600STM_CONS_TO_PROCESS_400_KLBH'].values[0]*1000)+(input_df['DP_OPT_400STM_PHC_CONS_400_TO_PRCS_LBH'].values[0]))-(Letdown_From_400_TO_175_LBH)-(header_imb_df.loc['HEADER_IMBALANCE_400_LBH','values'])==0)
    # m.Equation((STG_C3_Steam_Gen_400_LBH)+(Letdown_1250_TO_400_LBH)+(input_df['DP_OPT_600STM_CONS_TO_PROCESS_400_KLBH'].values[0]*1000)-(input_df['DP_OPT_C_400_Steam_Flow_LBH'].values[0])-(Letdown_From_400_TO_175_LBH)-(header_imb_df.loc['HEADER_IMBALANCE_400_LBH','values'])==0)
    
    #175 STEAM BALANCE
    m.Equation((Letdown_From_400_TO_175_LBH)+(input_df['DP_OPT_175STM_PHC_GEN_C3_STG_LBH'].values[0]*input_df['DP_OPT_RUNNING_STATUS_STG_C3'].values[0])+(input_df['DP_OPT_175STM_PHC_GEN_C4_HRSG_LBH'].values[0]*input_df['DP_OPT_RUNNING_STATUS_GT_HRSG_C4'].values[0])+(input_df['DP_OPT_175STM_PHC_GEN_C5_HRSG_LBH'].values[0]*input_df['DP_OPT_RUNNING_STATUS_GT_HRSG_C5'].values[0])-(input_df['DP_OPT_175STM_PHC_CONS_15_TO_PRCS_LBH'].values[0])-(Letdown_From_175_TO_30_LBH)-(input_df['DP_OPT_175STM_PHC_CONS_PRV1_5_LBH'].values[0])-(input_df['DP_OPT_175STM_PHC_CONS_PRV2_5_LBH'].values[0])-(input_df['DP_OPT_175STM_PHC_CONS_PRV3_5_LBH'].values[0])-(header_imb_df.loc['HEADER_IMBALANCE_175_LBH','values'])==0)
    # m.Equation((Letdown_From_400_TO_175_LBH)+input_df['DP_OPT_STM_PHC_CONS_PRDS_400_175_LBH'].values[0]+input_df['DP_OPT_175STM_PHC_GEN_C3_STG_LBH'].values[0]+(input_df['DP_OPT_175STM_PHC_GEN_C4_HRSG_LBH'].values[0])+(input_df['DP_OPT_175STM_PHC_GEN_C5_HRSG_LBH'].values[0])-(input_df['DP_OPT_175STM_PHC_CONS_15_TO_PRCS_LBH'].values[0])-(Letdown_From_175_TO_30_LBH)-(input_df['DP_OPT_175STM_PHC_CONS_PRV3_5_LBH'].values[0])-(input_df['DP_OPT_C_175HEADER_IMBALANCE_LBH'].values[0])==0)
    # m.Equation((Letdown_From_400_TO_175_LBH)+input_df['DP_OPT_175STM_PHC_GEN_C3_STG_LBH'].values[0]+(input_df['DP_OPT_175STM_PHC_GEN_C4_HRSG_LBH'].values[0])+(input_df['DP_OPT_175STM_PHC_GEN_C5_HRSG_LBH'].values[0])-(input_df['DP_OPT_175STM_PHC_CONS_15_TO_PRCS_LBH'].values[0])-(Letdown_From_175_TO_30_LBH)-(input_df['DP_OPT_175STM_PHC_CONS_PRV1_5_LBH'].values[0])-(input_df['DP_OPT_175STM_PHC_CONS_PRV2_5_LBH'].values[0])-(input_df['DP_OPT_175STM_PHC_CONS_PRV3_5_LBH'].values[0])-(header_imb_df.loc['HEADER_IMBALANCE_175_LBH','values'])==0)
    
    #30 STEAM BALANCE
    # m.Equation((Letdown_From_175_TO_30_LBH)+input_df['DP_OPT_STM_PHC_CONS_PRDS_175_30_LBH'].values[0]+(input_df['DP_OPT_STM_LP_PHC_GEN_C4_HRSG_LBH'].values[0])+(input_df['DP_OPT_STM_LP_PHC_GEN_C5_HRSG_LBH'].values[0])-(input_df['DP_OPT_C_30_Steam_Flow_LBH'].values[0])-(input_df['DP_OPT_C_30_Steam_Flow_INSIDEPWH_LBH'].values[0])-(STEAM_VENTING_LBH)-(input_df['DP_OPT_C_30HEADER_IMBALANCE_LBH'].values[0])==0)
    m.Equation((Letdown_From_175_TO_30_LBH)-(input_df['DP_OPT_C_30_Steam_Flow_LBH'].values[0])-(STEAM_VENTING_LBH)==0)
 
    # STG C3 EQUIPMENT BALANCE
    m.Equation(STG_C3_Steam_Cons_1250_LBH -(STG_C3_Steam_Gen_400_LBH + (input_df['DP_OPT_175STM_PHC_GEN_C3_STG_LBH'].values[0]*input_df['DP_OPT_RUNNING_STATUS_STG_C3'].values[0]))-header_imb_df.loc['EQPT_IMBALANCE_STG_C3_LBH','values']==0)
    # m.Equation(STG_C3_Steam_Cons_1250_LBH -(STG_C3_Steam_Gen_400_LBH + input_df['DP_OPT_175STM_PHC_GEN_C3_STG_LBH'].values[0])-header_imb_df.loc['EQPT_IMBALANCE_STG_C3_LBH','values']==0)
   
    # STG R4 EQUIPMENT BALANCE
    m.Equation(STG_R4_Steam_Cons_1900_KLBH -(STG_R4_Steam_Gen_600_KLBH + (input_df['DP_OPT_STM_RSC_GEN_R4_IP_EXHST_KLBH'].values[0]*input_df['DP_OPT_RUNNING_STATUS_STG_R4'].values[0]))-header_imb_df.loc['EQPT_IMBALANCE_STG_R4_KLBH','values']==0)
    # m.Equation(STG_R4_Steam_Cons_1900_KLBH -(STG_R4_Steam_Gen_600_KLBH + input_df['DP_OPT_STM_RSC_GEN_R4_IP_EXHST_KLBH'].values[0])-header_imb_df.loc['EQPT_IMBALANCE_STG_R4_KLBH','values']==0)
    
#___________________________________________________________________________________________________________________________________________________________________________________________    
    '''
    the scenario where user dont want to optimize certain equipment we have made that provision and that is 
    stored in a table in form of 1 and 0  in user_opt_table .
    
    '''    

    # user_query = f"SELECT * From  {user_opt_table};"
    # user_opt_status =  pd.read_sql(user_query,con=db_connection_2)
    # user_opt_status=user_opt_status.set_index('Equipment_list')
    
    #Model Accuracy Failed Logic.
    error_prcnt_tag = pd.read_csv('config/error_prcnt_tag.csv')
    error_prcnt_calc = pd.read_csv('config/error_calculation.csv')
    error_prcnt_calc = error_prcnt_calc.set_index('error_tag')
    error_prcnt_calc['value']=''
    
    for i,row in error_prcnt_calc.iterrows():
        if math.isnan(eval(row['expression'])) or math.isinf(eval(row['expression'])): 
            row['value']=0
        else:
            row['value']=eval(row['expression'])
            
    error_output_tags=pd.read_csv('config/error_output_alias_map.csv')
    error_output_tags =error_output_tags.dropna()
    tag_id=error_output_tags['tag_id'].tolist()
    no_of_error_output_tags=len(error_output_tags['tag_id'])
    
    error_op_dict={}
    error_op_dict['timestamp']=[time_upto]*no_of_error_output_tags
    error_op_dict['tag']=tag_id
    error_op_dict['value']= error_prcnt_calc['value'].tolist()
    error_op_df=pd.DataFrame(error_op_dict)
    
    
    for i,row in error_prcnt_tag.iterrows():
        
        if abs(error_prcnt_calc.loc[row['error_tag_alias'],'value']) > row['permissible_error'] :
            
            
            user_opt_status.loc[row['equipment'],'user_status']=0    
            message = f"Please note accuracy of energy coefficient model of {row['equipment']} is not acceptable.(GT and STG > 95 PRCNT, Boiler > 90 PRCNT)" # add substitute value too   
            category = "Equipment Model Accuracy Low"
            query = f"insert into {alert_table} (timestamp,category,message) values ('{time_upto}','{category}','{message}')"
            db_connection_1.execute(query)
            
        if input_df['DP_OPT_MODE_GT_Boiler_C1'].values[0] ==1 and user_opt_status.loc['BLR C1','user_status']==0 :
            user_opt_status.loc['GT C1','user_status'] ==0
            
        if input_df['DP_OPT_MODE_GT_Boiler_C2'].values[0] ==1 and user_opt_status.loc['BLR C2','user_status']==0 :
            user_opt_status.loc['GT C2','user_status'] ==0
            
    
    #Base load Logic for GT C1,C2,C4,C5 -----> if value =1 then Don't Optimize.
    base_load_df = pd.read_csv('config/base_load_tag.csv')
    for i, row in base_load_df.iterrows():
        # print(input_df[row['tag']])
        if input_df[row['tag']].values[0]==1:
            # user_opt_status.loc[row['equipment'],'user_status']=0
            message = f"Please note {row['equipment']} is Base Loaded." # add substitute value too 
            category = "Base Loaded"
            query = f"insert into {alert_table} (timestamp,category,message) values ('{time_upto}','{category}','{message}')"
            db_connection_1.execute(query)
        else:
            message = f"Please note {row['equipment']} is not Base Loaded." # add substitute value too 
            category = " Not Base Loaded"
            query = f"insert into {alert_table} (timestamp,category,message) values ('{time_upto}','{category}','{message}')"
            db_connection_1.execute(query)
            
            
    # if STG R2 and R3 are offline are we are not optimizing GT R5 and R6 
    if STG_R2_RUN_STATUS==0 and STG_R3_RUN_STATUS ==0:
        
        user_opt_status.loc['STG R4','user_status']=0
        user_opt_status.loc['GT R5','user_status']=0
        user_opt_status.loc['GT R6','user_status']=0
        
    else:
        pass
#___________________________________________________________________________________________________________________________________________________________________________________________    

    """
    VARIABLES FOR GT C1
    
    Fixed X Values :: 06D-A7023A , 06C-TI2253B.MEAS , 06D-T1013 , 06D-A1012 , 06C-C1EXH_TEMP_AVG.MEAS 
    
    X Variable : 06C-J1060A.PV(Power)
    
    Y Variable : 06C-F6004.PV (NG FLow)
    
    """    

    if user_opt_status.loc['GT C1','user_status'] == 0:
        m.Equation(GT_C1_Power_MW - GT_C1_RUN_STATUS*input_df['DP_OPT_PWR_PHC_GEN_C1_GT_MW'].values[0] ==0) #dont optimize = 1, Optimze = 0
        
        m.Equation(GT_C1_NG_Flow_SCFH - GT_C1_RUN_STATUS*input_df['DP_OPT_NG_PHC_CONS_C1_GT_SCFH'].values[0]==0)
        
    else:
        if GT_C1_RUN_STATUS ==1:
            
            m.Equation((-450.1942*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]+
                        6477.2059*GT_C1_Power_MW+
                        323.0912*input_df['DP_OPT_AIROUT_TEMP_PHC_C1_GT_F'].values[0]-
                        191.4344*input_df['DP_OPT_AMB_TEMP_F'].values[0]+
                        22.1903*input_df['DP_OPT_RELATIVE_HUMIDITY_PCNT'].values[0]+
                        88.8635*input_df['DP_OPT_EXHST_TEMP_PHC_C1_GT_F'].values[0]+
                        518927.9092)-(GT_C1_NG_Flow_SCFH)==0)
            
            if input_df['DP_OPT_GT_C1_BASELOADED'].values[0]==1:
                m.Equation(GT_C1_Power_MW <= input_df['DP_OPT_PWR_PHC_GEN_C1_GT_MW'].values[0])
            else:
                m.Equation(GT_C1_Power_MW <= ((-0.217*input_df['DP_OPT_AMB_TEMP_F'].values[0])+69+5))
            m.Equation(GT_C1_Power_MW >= 40)
            m.Equation(GT_C1_NG_Flow_SCFH <= 1000000)
            m.Equation(GT_C1_NG_Flow_SCFH >= 550000)
            
        else:
            m.Equation(GT_C1_Power_MW ==0) #dont optimize = 1, Optimze = 0
            
            m.Equation(GT_C1_NG_Flow_SCFH ==0)
            
#___________________________________________________________________________________________________________________________________________________________________________________________    

    """
    VARIABLES FOR GT C2
      
    Fixed X Values :: 06D-A7023A , 06C-C2EXH_TEMP_AVG.MEAS
    
    X Variable : 06C-J1090A.PV(Power)
    
    Y Variable : 06C-F6014.PV (NG FLow)

    """

    if user_opt_status.loc['GT C2','user_status'] == 0:
        m.Equation(GT_C2_Power_MW - GT_C2_RUN_STATUS*input_df['DP_OPT_PWR_PHC_GEN_C2_GT_MW'].values[0] ==0) #dont optimize = 1, Optimze = 0
        
        m.Equation(GT_C2_NG_Flow_SCFH - GT_C2_RUN_STATUS*input_df['DP_OPT_NG_PHC_CONS_C2_GT_SCFH'].values[0]==0)
    
    else:
        if GT_C2_RUN_STATUS == 1:
    #GT C2 Linear Equation  
            m.Equation((-890.572*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]+
                    5961.768*GT_C2_Power_MW+
                    376.4747*input_df['DP_OPT_EXHST_TEMP_PHC_C2_GT_F'].values[0]+
                    920817.2)-(GT_C2_NG_Flow_SCFH)==0)
            
            if input_df['DP_OPT_GT_C2_BASELOADED'].values[0]==1:
                m.Equation(GT_C2_Power_MW <= input_df['DP_OPT_PWR_PHC_GEN_C2_GT_MW'].values[0])
            else:
                m.Equation(GT_C2_Power_MW <=((-0.217*input_df['DP_OPT_AMB_TEMP_F'].values[0])+69+4))
            m.Equation(GT_C2_Power_MW >=30)
            m.Equation(GT_C2_NG_Flow_SCFH <=1000000)
            m.Equation(GT_C2_NG_Flow_SCFH >=400000)
            
        else:
            m.Equation(GT_C2_Power_MW ==0) #dont optimize = 1, Optimze = 0
           
            m.Equation(GT_C2_NG_Flow_SCFH ==0)
            
        
            # m.Equation(GT_C2_Power_MW - GT_C2_RUN_STATUS*GT_C2_Power_Leq_MW ==0) #dont optimize = 1, Optimze = 0
            
            # m.Equation(GT_C2_NG_Flow_SCFH - GT_C2_RUN_STATUS*GT_C2_NG_Flow_Leq_SCFH==0)

#___________________________________________________________________________________________________________________________________________________________________________________________    

    """
       VARIABLES FOR GT C4
           
       X Variable :  06C-J1135A.PV (Power)
       
       Y Variable : 06C-F0111.PV (NG FLow)
    
    """
    
    if user_opt_status.loc['GT C4','user_status'] == 0:
        
        m.Equation(GT_C4_Power_MW - GT_C4_RUN_STATUS*input_df['DP_OPT_PWR_PHC_GEN_C4_GT_MW'].values[0] ==0) #dont optimize = 1, Optimze = 0
        
        m.Equation(GT_C4_NG_Flow_SCFH - GT_C4_RUN_STATUS*input_df['DP_OPT_NG_PHC_CONS_C4_GT_SCFH'].values[0]==0) #dont optimize = 1, Optimze = 0
    
        m.Equation(HRSG_C4_Steam_Gen_1250_LBH - GT_C4_RUN_STATUS*input_df['DP_OPT_HPSTMOL_FLOW_PHC_C4_HRSG_LBH'].values[0]==0)
    
    
    else:
        
        if GT_C4_RUN_STATUS == 1:
            m.Equation((0.4895*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]+
                        8992.355*GT_C4_Power_MW +
                        225014.6)-(GT_C4_NG_Flow_SCFH)==0)
            
            """
            VARIABLES FOR HRSG C4
            
            06C-F0111.PV,06D-A7023A,06C-TI2254A.MEAS,06C-PI2247.MEAS,06D-T1013,06C-T0600,1250# Spc Enthalpy,06C-F0120.PV,06C-F0119.PV,
        
            Fixed X Values :: 
            
            X Variable : 06C-J1135A.PV
            
            Y Variable : 06C-F0121.PV (NG FLow)
        
            """
            #HRSG C4 Linear Equation 
            m.Equation((-0.072*GT_C4_NG_Flow_SCFH+
                        365.79*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]+
                        2067.307*GT_C4_Power_MW+
                        185.19*input_df['DP_OPT_AMB_TEMP1_F'].values[0]+
                        106.904*input_df['DP_OPT_DISC_TEMP_PHC_C4_GT_F'].values[0]-
                        296.365*input_df['DP_OPT_AMB_TEMP_F'].values[0]+
                        9.886*input_df['DP_OPT_RELATIVE_HUMIDITY_PCNT'].values[0]+
                        202.184*input_df['DP_OPT_DAMPOL_TEMP_PHC_C4_GT_F'].values[0]+
                        432.078*input_df['DP_OPT_1250_STMOL_ENTHALPY_PHC_C4_HRSG_BTULB'].values[0]+
                        0.757*input_df['DP_OPT_IPSTMOL_FLOW_PHC_C4_HRSG_LBH'].values[0]-
                        217.68*input_df['DP_OPT_LPBFW_OPENING_PHC_C4_HRSG_PRCNT'].values[0]-
                        1162019.041)-(HRSG_C4_Steam_Gen_1250_LBH)==0)
            
            if input_df['DP_OPT_GT_C4_BASELOADED'].values[0]==1:
                m.Equation(GT_C4_Power_MW <= input_df['DP_OPT_PWR_PHC_GEN_C4_GT_MW'].values[0])
            else:
                m.Equation(GT_C4_Power_MW <=((-0.29*input_df['DP_OPT_AMB_TEMP_F'].values[0])+97.04+8))
            m.Equation(GT_C4_Power_MW >=30)
            m.Equation(GT_C4_NG_Flow_SCFH <=1000000)
            m.Equation(GT_C4_NG_Flow_SCFH >=400000)
            m.Equation(HRSG_C4_Steam_Gen_1250_LBH <=300000)
            m.Equation(HRSG_C4_Steam_Gen_1250_LBH >=150000)
            
            
            # m.Equation(HRSG_C4_Steam_Gen_1250_LBH - GT_C4_RUN_STATUS*HRSG_C4_Steam_Gen_1250_Leq_LBH==0)
        
        else:
            m.Equation(GT_C4_Power_MW ==0) #dont optimize = 1, Optimze = 0
            
            m.Equation(GT_C4_NG_Flow_SCFH ==0) #dont optimize = 1, Optimze = 0
            
            m.Equation(HRSG_C4_Steam_Gen_1250_LBH ==0)
        
#___________________________________________________________________________________________________________________________________________________________________________________________    
    
    """
    VARIABLES FOR GT C5
    
    X Variable : 06C-J1166A.PV(Power)
    
    Y Variable : 06C-F0112 (NG FLow)

    """
    
    if user_opt_status.loc['GT C5','user_status'] == 0:
        
        m.Equation(GT_C5_Power_MW - GT_C5_RUN_STATUS*input_df['DP_OPT_PWR_PHC_GEN_C5_GT_MW'].values[0]==0) #dont optimize = 1, Optimze = 0
        
        m.Equation(GT_C5_NG_Flow_SCFH - GT_C5_RUN_STATUS*input_df['DP_OPT_NG_FLOW_PHC_C5_GT_SCFH'].values[0]==0) #dont optimize = 1, Optimze = 0
    
        m.Equation(HRSG_C5_Steam_Gen_1250_LBH - GT_C5_RUN_STATUS*input_df['DP_OPT_HPSTMOL_FLOW_PHC_C5_HRSG_LBH'].values[0]==0)
    else:
        
        if GT_C5_RUN_STATUS ==1 :
            
            m.Equation((173.2113*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]+
                        10119.22*GT_C5_Power_MW +
                        7673.417)-(GT_C5_NG_Flow_SCFH)==0)
            
            """
            VARIABLES FOR HRSG C5
            
            06C-F0112,06D-A7023A , 06C-TI2354A.MEAS, 06D-T1013, 06D-A1012, 06C-T0615, 06C-F0128, 06C-F0127.PV, LP Spc Enthalpy1010
         
            Fixed X Values :: 
            
            X Variable : 06C-J1135A.PV
            
            Y Variable : 06C-F0129.PV 
            
            """
            
            #HRSG  C5 Linear Equation
            m.Equation((0.0277*GT_C5_NG_Flow_SCFH+
                        43.0545*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]+
                        1394.7433*GT_C5_Power_MW+
                        151.5*input_df['DP_OPT_AIRIN_TEMP_PHC_C5_GT_F'].values[0]-
                        102.9065*input_df['DP_OPT_AMB_TEMP_F'].values[0]+
                        0.0658*input_df['DP_OPT_RELATIVE_HUMIDITY_PCNT'].values[0]+
                        283.4488*input_df['DP_OPT_DAMPER_OUT_TEMP_C5_GT_F'].values[0]+
                        0.0225*input_df['DP_OPT_175STM_PHC_GEN_C5_HRSG_LBH'].values[0]+
                        1.5712*input_df['DP_OPT_STM_LP_PHC_GEN_C5_HRSG_LBH'].values[0]+
                        1459.7994*input_df['DP_OPT_LPSTMOL_ENTHALPY_PHC_C5_HRSG_BTULB'].values[0]-
                        1967459.389)-(HRSG_C5_Steam_Gen_1250_LBH)==0)
            
            if input_df['DP_OPT_GT_C5_BASELOADED'].values[0]==1:
                m.Equation(GT_C5_Power_MW <= input_df['DP_OPT_PWR_PHC_GEN_C5_GT_MW'].values[0])
            else:
                m.Equation(GT_C5_Power_MW <=((-0.29*input_df['DP_OPT_AMB_TEMP_F'].values[0])+97.04))
            m.Equation(GT_C5_Power_MW >=20)
            m.Equation(GT_C5_NG_Flow_SCFH <= 1000000)
            m.Equation(GT_C5_NG_Flow_SCFH >= 400000)
            m.Equation(HRSG_C5_Steam_Gen_1250_LBH <= 260000)
            m.Equation(HRSG_C5_Steam_Gen_1250_LBH >= 100000)
            # m.Equation(GT_C5_Power_MW - GT_C5_RUN_STATUS*GT_C5_Power_Leq_MW ==0) #dont optimize = 1, Optimze = 0
            
            # m.Equation(GT_C5_NG_Flow_SCFH - GT_C5_RUN_STATUS*GT_C5_NG_Flow_Leq_SCFH==0) #dont optimize = 1, Optimze = 0
            
            # m.Equation(HRSG_C5_Steam_Gen_1250_LBH - GT_C5_RUN_STATUS*HRSG_C5_Steam_Gen_1250_Leq_LBH==0)
        
            
        else:
            m.Equation(GT_C5_Power_MW  ==0) #dont optimize = 1, Optimze = 0
            
            m.Equation(GT_C5_NG_Flow_SCFH ==0) #dont optimize = 1, Optimze = 0
            
            m.Equation(HRSG_C5_Steam_Gen_1250_LBH ==0)
        
#___________________________________________________________________________________________________________________________________________________________________________________________    
    
    """
    VARIABLES FOR GT R5
         
    X Variable : 06D-J5504
    
    Y Variable : 06D-5EKG10CF403C (NG FLow)

    """
    
    if user_opt_status.loc['GT R5','user_status'] == 0: 
        
        m.Equation(GT_R5_Power_MW - GT_R5_RUN_STATUS*input_df['DP_OPT_PWR_RSC_GEN_R5_STG_MW'].values[0] ==0) #dont optimize = 1, Optimze = 0
        
        m.Equation(GT_R5_NG_Flow_KPPH - GT_R5_RUN_STATUS*input_df['DP_OPT_NG_RSC_CONS_TOTAL_R5_GT_KPPH'].values[0]==0) #dont optimize = 1, Optimze = 0
    
        m.Equation(HRSG_R5_Steam_Gen_1900_KLBH - GT_R5_RUN_STATUS*input_df['DP_OPT_HPSTMOL_FLOW_RSC_R5_HRSG_KPPH'].values[0]==0)
       
    else:  
        
        if GT_R5_RUN_STATUS == 1 :
        #GT R5 Linear Equation 
            m.Equation((-0.0595*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]+
                        0.3713*GT_R5_Power_MW +
                        78.1426)-(GT_R5_NG_Flow_KPPH)==0)
            
            """
            VARIABLES FOR HRSG R5
                
            Fixed X Values ::  06D-5EKG10CF403C , 06D-5MBA10CT183S, 06D-T1013, 06D-A1012, 06D-5TEAVTX, 06D-FAHL5114A, LPS Inlet Spc Enthalpy
           
            X Variable : 06D-J5504
            
            Y Variable : 06D-FAHL5017A
        
            """
            #HRSG  R5 Linear Equation 
            m.Equation((-1.074*GT_R5_NG_Flow_KPPH+
                        2.22*GT_R5_Power_MW+
                        0.415*input_df['DP_OPT_AIRIN_TEMP_RSC_R5_GT_F'].values[0]+
                        0.048*input_df['DP_OPT_AMB_TEMP_F'].values[0]+
                        0.027*input_df['DP_OPT_RELATIVE_HUMIDITY_PCNT'].values[0]+
                        0.535*input_df['DP_OPT_EXHST_TEMP_RSC_R5_GT_F'].values[0]-
                        0.057*input_df['DP_OPT_STM_LP_RSC_GEN_R5_HRSG_LBH'].values[0]-
                        0.044*input_df['DP_OPT_LPSTMOL_ENTHALPY_RSC_R5_HRSG_BTULB'].values[0]-
                        414.882)-(HRSG_R5_Steam_Gen_1900_KLBH)==0)
            
            m.Equation(GT_R5_Power_MW <= ((-0.583*input_df['DP_OPT_AMB_TEMP_F'].values[0])+208.32+10))
            m.Equation(GT_R5_Power_MW >= 110 )
            m.Equation(GT_R5_NG_Flow_KPPH <= 90)
            m.Equation(GT_R5_NG_Flow_KPPH >= 40)
            m.Equation(HRSG_R5_Steam_Gen_1900_KLBH <= 550)
            m.Equation(HRSG_R5_Steam_Gen_1900_KLBH >= 300)
            
            # m.Equation(GT_R5_Power_MW - GT_R5_RUN_STATUS*GT_R5_Power_Leq_MW ==0) #dont optimize = 1, Optimze = 0
            
            # m.Equation(GT_R5_NG_Flow_KPPH - GT_R5_RUN_STATUS*GT_R5_NG_Flow_Leq_KPPH==0) #dont optimize = 1, Optimze = 0
                     
            # m.Equation(HRSG_R5_Steam_Gen_1900_KLBH - GT_R5_RUN_STATUS*HRSG_R5_Steam_Gen_1900_Leq_KLBH==0)
        
        else:
            m.Equation(GT_R5_Power_MW ==0) #dont optimize = 1, Optimze = 0
            
            m.Equation(GT_R5_NG_Flow_KPPH ==0) #dont optimize = 1, Optimze = 0
                        
            m.Equation(HRSG_R5_Steam_Gen_1900_KLBH==0)
        
#___________________________________________________________________________________________________________________________________________________________________________________________    
  
    """
    VARIABLES FOR GT R6
         
    X Variable : 06D-J6504(Power)
    
    Y Variable : 06D-6EKG10CF403C (NG FLow)

    """ 
    if user_opt_status.loc['GT R6','user_status'] == 0: 
        m.Equation(GT_R6_Power_MW - GT_R6_RUN_STATUS*input_df['DP_OPT_PWR_RSC_GEN_R6_STG_MW'].values[0] ==0) #dont optimize = 1, Optimze = 0
        
        m.Equation(GT_R6_NG_Flow_KPPH - GT_R6_RUN_STATUS*input_df['DP_OPT_NG_RSC_CONS_TOTAL_R6_GT_KPPH'].values[0]==0)
        
        m.Equation(HRSG_R6_Steam_Gen_1900_KLBH - GT_R6_RUN_STATUS*input_df['DP_OPT_HPSTMOL_FLOW_RSC_R6_HRSG_KPPH'].values[0]==0) #dont optimize = 1, Optimze = 0
        
    #GT R6 Linear Equation
    else:
        
        if GT_R6_RUN_STATUS == 1:
       
            m.Equation((0.37*GT_R6_Power_MW +
                    16.5316)-(GT_R6_NG_Flow_KPPH)==0)
            
            
            """
            VARIABLES FOR HRSG R6
               
            Fixed X Values ::  06D-6EKG10CF403C,06D-A7023A,06D-6MBA10CT183S,06D-6MBH40CT003S,06D-T1013,06D-A1012,06D-6TEAVTX,BFW Inlet Spc Enthalpy,
             HPS Inlet Spc Enthalpy,06D-FAHL6114A,LPS Inlet Spc Enthalpy,06D-FAHL6919B,06D-T6935,06D-T5911
            
            
            X Variable : 06D-J6504
                
            Y Variable : 06D-FAHL6017A
            
            """
             
            #HRSG R6 Linear Equation 
            m.Equation((-0.621*GT_R6_NG_Flow_KPPH+
                        0.039*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]+
                        1.224*GT_R6_Power_MW+
                        0.477*input_df['DP_OPT_AIRIN_TEMP_RSC_R6_GT_F'].values[0]-
                        0.306*input_df['DP_OPT_DISC_TEMP_RSC_R6_GT_F'].values[0]+
                        0.096*input_df['DP_OPT_AMB_TEMP_F'].values[0]+
                        0.018*input_df['DP_OPT_RELATIVE_HUMIDITY_PCNT'].values[0]+
                        0.393*input_df['DP_OPT_EXHST_TEMP_RSC_R6_GT_F'].values[0]+
                        0.729*input_df['DP_OPT_HPBFWIN_ENTHALPY_RSC_R6_HRSG_BTULB'].values[0]-
                        0.049*input_df['DP_OPT_HPSTMOL_ENTHALPY_RSC_R6_HRSG_BTULB'].values[0]-
                        0.368*input_df['DP_OPT_STM_LP_RSC_GEN_R6_HRSG_LBH'].values[0]+
                        0.323*input_df['DP_OPT_LPSTMOL_ENTHALPY_RSC_R6_HRSG_BTULB'].values[0]+
                        0.618*input_df['DP_OPT_COND_FLOW_RSC_R6_HRSG_KPPH'].values[0]+
                        0.285*input_df['DP_OPT_ECONOMISER_FC_IN_TEMP_R6_HRSG_F'].values[0]-
                        0.194*input_df['DP_OPT_ECONOMIZER_FC_OUT_TEMP_R5_HRSG_F'].values[0]-
                        853.796)-(HRSG_R6_Steam_Gen_1900_KLBH)==0)
            
            m.Equation(GT_R6_Power_MW <= ((-0.583*input_df['DP_OPT_AMB_TEMP_F'].values[0])+208.32+8))
            m.Equation(GT_R6_Power_MW >= 110)
            m.Equation(GT_R6_NG_Flow_KPPH <=90)
            m.Equation(GT_R6_NG_Flow_KPPH >=40)
            m.Equation(HRSG_R6_Steam_Gen_1900_KLBH <=550)
            m.Equation(HRSG_R6_Steam_Gen_1900_KLBH >=300)
            
            # m.Equation(GT_R6_Power_MW - GT_R6_RUN_STATUS*GT_R6_Power_Leq_MW ==0) #dont optimize = 1, Optimze = 0
        
            # m.Equation(GT_R6_NG_Flow_KPPH - GT_R6_RUN_STATUS*GT_R6_NG_Flow_Leq_KPPH ==0 ) #dont optimize = 1, Optimze = 0
        
            
            # m.Equation(HRSG_R6_Steam_Gen_1900_KLBH - GT_R6_RUN_STATUS*HRSG_R6_Steam_Gen_1900_Leq_KLBH==0)
            
        else:
            
            m.Equation(GT_R6_Power_MW ==0) #dont optimize = 1, Optimze = 0
        
            m.Equation(GT_R6_NG_Flow_KPPH  ==0 ) #dont optimize = 1, Optimze = 0
                 
            m.Equation(HRSG_R6_Steam_Gen_1900_KLBH ==0)
#________________________________________________________________________________________________________________________________________________     
    
    if input_df['DP_OPT_MODE_GT_Boiler_C1'].values[0] ==1:
        
        """
        VARIABLES FOR GT BOILER EQUATION C1
        
         
        Fixed X Values ::     06C-F6004.PV, 06D-A7023A, 06C-TI2253B.MEAS, 06C-PI2546.MEAS, 06D-A1012, 
        06C-C1EXH_TEMP_AVG.MEAS, BFW Inlet Spc Enthalpy, 06C-F3008.PV, 1250# Spc Enthalpy, H2/NG F Ratio,
     
        X Variable : 06C-J1060A.PV(Power)
        
        Y Variable : FHRSG_C1_NG (NG FLow)
    
        """
        
        if user_opt_status.loc['GT BLR C1','user_status'] == 0: 
            
            m.Equation(FHRSG_C1_NG_SCFH - input_df['DP_OPT_MODE_GT_Boiler_C1'].values[0]*GT_C1_RUN_STATUS*BOILER_C1_RUN_STATUS*input_df['DP_OPT_NG_PHC_GEN_C1_BOILER_SCFH'].values[0]==0)
    
            m.Equation(BLR_C1_Steam_Gen_1250_LBH-input_df['DP_OPT_MODE_GT_Boiler_C1'].values[0]*BOILER_C1_RUN_STATUS*input_df['DP_OPT_1250STM_PHC_GEN_C1_BOILER_LBH'].values[0]==0)   
            
        else:    
            #GT Boiler NG C1 Linear Equation
            if BOILER_C1_RUN_STATUS == 1 :
               
                m.Equation((-0.855629701742663*GT_C1_NG_Flow_SCFH-
                            629.189536429196*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]+
                            5152.1044937494*GT_C1_Power_MW+
                            64.6655574714934*input_df['DP_OPT_AIROUT_TEMP_PHC_C1_GT_F'].values[0]-
                            2298.66091059079*input_df['DP_OPT_DISC_PRESS_PHC_C1_GT_PSIG'].values[0]+
                            42.7750288004819*input_df['DP_OPT_RELATIVE_HUMIDITY_PCNT'].values[0]-
                            404.264651549052*input_df['DP_OPT_EXHST_TEMP_PHC_C1_GT_F'].values[0]-
                            796.559481334217*input_df['DP_OPT_BFWIN_ENTHALPY_PHC_C1_HRSG_BTULB'].values[0]+
                            1.05081583501951*BLR_C1_Steam_Gen_1250_LBH+
                            272.504945147714*input_df['DP_OPT_1250_STMOL_ENTHALPY_PHC_C1_HRSG_BTULB'].values[0]-
                            55869.9884831487*input_df['DP_OPT_H2NG_RATIO_PHC_C1_HRSG'].values[0]+
                            1198911.04159759)-(FHRSG_C1_NG_SCFH)==0)
                
                
                m.Equation(FHRSG_C1_NG_SCFH <=750000)
                m.Equation(FHRSG_C1_NG_SCFH >=180000)
                m.Equation(BLR_C1_Steam_Gen_1250_LBH <=675000)
                m.Equation(BLR_C1_Steam_Gen_1250_LBH >=100000)
                
                # m.Equation(-0.855629701742663*input_df['DP_OPT_NG_PHC_CONS_C1_GT_SCFH'].values[0]

                # m.Equation(FHRSG_C1_NG_SCFH - input_df['DP_OPT_MODE_GT_Boiler_C1'].values[0]*GT_C1_RUN_STATUS*Boiler_C1_RUN_STATUS*FHRSG_C1_NG_Leq_SCFH==0)
               
                # m.Equation(BLR_C1_Steam_Gen_1250_LBH-input_df['DP_OPT_MODE_GT_Boiler_C1'].values[0]*Boiler_C1_RUN_STATUS*BLR_C1_Steam_Gen_1250_Leq_LBH==0)   
                               
            else:
                
                m.Equation(FHRSG_C1_NG_SCFH ==0)
               
                m.Equation(BLR_C1_Steam_Gen_1250_LBH==0)   
    
    else:
        
        """
        VARIABLES FOR BOILER C1
              
        Fixed X Values :: 06C-F6004.PV,06D-A7023A,06D-T1013,06D-A1012,BFW Inlet Spc Enthalpy,1250# Spc Enthalpy,H2 LHV,H2/NG F Ratio
       
        X Variable : 06C-F3008.PV(Power)
        
        Y Variable : FHRSG_C1_NG (INLET BOILER FUEL)
    
        """
    
        if user_opt_status.loc['BLR C1','user_status'] == 0: 
        #Boiler NG C1 Linear Equation 
           
            m.Equation(FHRSG_C1_NG_SCFH - input_df['DP_OPT_MODE_BOILER_ONLY_C1'].values[0]*BOILER_C1_RUN_STATUS*input_df['DP_OPT_NG_PHC_GEN_C1_BOILER_SCFH'].values[0]==0)
        
            m.Equation(BLR_C1_Steam_Gen_1250_LBH-input_df['DP_OPT_MODE_BOILER_ONLY_C1'].values[0]*BOILER_C1_RUN_STATUS*input_df['DP_OPT_1250STM_PHC_GEN_C1_BOILER_LBH'].values[0]==0)   
        else :
            if BOILER_C1_RUN_STATUS == 1:
                
                m.Equation((0*GT_C1_NG_Flow_SCFH+
                            888.608*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]+
                            0*GT_C1_Power_MW+
                            151.282*input_df['DP_OPT_AMB_TEMP_F'].values[0]+
                            12.694*input_df['DP_OPT_RELATIVE_HUMIDITY_PCNT'].values[0]-
                            5465.777*input_df['DP_OPT_BFWIN_ENTHALPY_PHC_C1_HRSG_BTULB'].values[0]+
                            1.264*BLR_C1_Steam_Gen_1250_LBH-
                            440.133*input_df['DP_OPT_1250_STMOL_ENTHALPY_PHC_C1_HRSG_BTULB'].values[0]-
                            45316.159*input_df['DP_OPT_H2NG_RATIO_PHC_C1_HRSG'].values[0]+
                            894470.155)-(FHRSG_C1_NG_SCFH)==0)
                
               
                m.Equation(FHRSG_C1_NG_SCFH <=750000)
                m.Equation(FHRSG_C1_NG_SCFH >=180000)
                m.Equation(BLR_C1_Steam_Gen_1250_LBH <=675000)
                m.Equation(BLR_C1_Steam_Gen_1250_LBH >=100000)
                # m.Equation(FHRSG_C1_NG_SCFH - input_df['DP_OPT_MODE_BOILER_ONLY_C1'].values[0]*Boiler_C1_RUN_STATUS*FHRSG_C1_NG_Leq_SCFH==0)
                
                # m.Equation(BLR_C1_Steam_Gen_1250_LBH-input_df['DP_OPT_MODE_BOILER_ONLY_C1'].values[0]*Boiler_C1_RUN_STATUS*BLR_C1_Steam_Gen_1250_Leq_LBH==0)   
    
                
            else:
                
                m.Equation(FHRSG_C1_NG_SCFH ==0)
                
                m.Equation(BLR_C1_Steam_Gen_1250_LBH==0)   
    
#_____________________________________________________________________________________________________________________________________________    
    if input_df['DP_OPT_MODE_GT_Boiler_C2'].values[0] == 1 :
        
        """
        VARIABLES FOR GT BOILER C2
        
        Fixed X Values ::06C-F6014.PV,06D-A7023A,06C-TI2654A.MEAS,06C-TI2653A.MEAS,06D-A1012,06C-F5404,06C-T5597A,BFW Inlet Spc Enthalpy,06C-F3408.PV,
        1250# Spc Enthalpy,H2/NG F Ratio,
        
        X Variable : 06C-J1090A.PV(Power)
        
        Y Variable : FHRSG_C2_NG (NG FLow)
    
        """
    
        if user_opt_status.loc['GT BLR C2','user_status'] == 0: 
            m.Equation(FHRSG_C2_NG_SCFH - input_df['DP_OPT_MODE_GT_Boiler_C2'].values[0]*GT_C2_RUN_STATUS*BOILER_C2_RUN_STATUS*input_df['DP_OPT_NG_PHC_GEN_C2_BOILER_SCFH'].values[0]==0)
            
            m.Equation(BLR_C2_Steam_Gen_1250_LBH-input_df['DP_OPT_MODE_GT_Boiler_C2'].values[0]*BOILER_C2_RUN_STATUS*input_df['DP_OPT_1250STM_PHC_GEN_C2_BOILER_LBH'].values[0]==0)   
            
        else :
            
            if BOILER_C2_RUN_STATUS ==1 :
                
                m.Equation((-0.314*GT_C2_NG_Flow_SCFH-
                            327.851*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]-
                            371.452*GT_C2_Power_MW+
                            689.075*input_df['DP_OPT_AIRIN_TEMP_PHC_C2_GT_F'].values[0]-
                            808.352*input_df['DP_OPT_DISC_TEMP_PHC_C2_GT_F'].values[0]-
                            152.461*input_df['DP_OPT_RELATIVE_HUMIDITY_PCNT'].values[0]-
                            0.06*input_df['DP_OPT_EXHST_TO_WBOX_C2_GT_LBH'].values[0]+
                            34.486*input_df['DP_OPT_WBOX_TEMP_PHC_C2_HRSG_F'].values[0]+
                            1.145*BLR_C2_Steam_Gen_1250_LBH-
                            67.834*input_df['DP_OPT_1250_STMOL_ENTHALPY_PHC_C2_HRSG_BTULB'].values[0]-
                            59575.359*input_df['DP_OPT_H2NG_RATIO_PHC_C2_HRSG'].values[0]+
                            975964.533)-(FHRSG_C2_NG_SCFH)==0)
                
                m.Equation(FHRSG_C2_NG_SCFH <=750000)
                m.Equation(FHRSG_C2_NG_SCFH >=180000)
                m.Equation(BLR_C2_Steam_Gen_1250_LBH <=675000)
                m.Equation(BLR_C2_Steam_Gen_1250_LBH >=100000)
                # m.Equation(FHRSG_C2_NG_SCFH - input_df['DP_OPT_MODE_GT_Boiler_C2'].values[0]*GT_C2_RUN_STATUS*Boiler_C2_RUN_STATUS*FHRSG_C2_NG_Leq_SCFH==0)
        
                # m.Equation(BLR_C2_Steam_Gen_1250_LBH-input_df['DP_OPT_MODE_GT_Boiler_C2'].values[0]*Boiler_C1_RUN_STATUS*BLR_C2_Steam_Gen_1250_Leq_LBH==0)   
            
            else:
                
                m.Equation(FHRSG_C2_NG_SCFH ==0)
        
                m.Equation(BLR_C2_Steam_Gen_1250_LBH==0)   
    
    else:
        
        """
        VARIABLES FOR BOILER C2
            
        Fixed X Values :: 06C-F6014.PV,06D-A7023A,06D-T1013,06D-A1012,BFW Inlet Spc Enthalpy,1250# Spc Enthalpy,H2/NG F Ratio
        
        X Variable : 06C-F3408.PV(Power)
        
        Y Variable : FHRSG_C2_NG (NG FLow)
    
        """
    
        if user_opt_status.loc['BLR C2','user_status'] == 0: 
     
            m.Equation(FHRSG_C2_NG_SCFH - input_df['DP_OPT_MODE_BOILER_ONLY_C2'].values[0]*BOILER_C2_RUN_STATUS*input_df['DP_OPT_NG_PHC_GEN_C2_BOILER_SCFH'].values[0]==0)
            
            m.Equation(BLR_C2_Steam_Gen_1250_LBH-input_df['DP_OPT_MODE_BOILER_ONLY_C2'].values[0]*BOILER_C2_RUN_STATUS*input_df['DP_OPT_1250STM_PHC_GEN_C2_BOILER_LBH'].values[0]==0)   
           
        else:
            
            if BOILER_C2_RUN_STATUS == 1 :
            
                #Boiler NG C2 Linear Equation
                
                m.Equation((0*GT_C2_NG_Flow_SCFH+
                            513.004*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]+
                            0*GT_C2_Power_MW-
                            559.498*input_df['DP_OPT_AMB_TEMP_F'].values[0]-
                            159.753*input_df['DP_OPT_RELATIVE_HUMIDITY_PCNT'].values[0]-
                            2.103*input_df['DP_OPT_BFW_FLOW_PHC_C2_HRSG_LBH'].values[0]-
                            137.719*input_df['DP_OPT_BFW_TEMP_PHC_C1_HRSG_F'].values[0]+
                            2.894*BLR_C2_Steam_Gen_1250_LBH+
                            1153.677*input_df['DP_OPT_1250_STMOL_ENTHALPY_PHC_C2_HRSG_BTULB'].values[0]-
                            52574.144*input_df['DP_OPT_H2NG_RATIO_PHC_C2_HRSG'].values[0]-
                            1991202.108)-(FHRSG_C2_NG_SCFH)==0)
                
                m.Equation(FHRSG_C2_NG_SCFH <=750000)
                m.Equation(FHRSG_C2_NG_SCFH >=180000)
                m.Equation(BLR_C2_Steam_Gen_1250_LBH <=675000)
                m.Equation(BLR_C2_Steam_Gen_1250_LBH >=100000)
  
                # m.Equation(FHRSG_C2_NG_SCFH - input_df['DP_OPT_MODE_BOILER_ONLY_C2'].values[0]*Boiler_C2_RUN_STATUS*FHRSG_C2_NG_Leq_SCFH==0)
        
                # m.Equation(BLR_C2_Steam_Gen_1250_LBH-input_df['DP_OPT_MODE_BOILER_ONLY_C2'].values[0]*Boiler_C2_RUN_STATUS*BLR_C2_Steam_Gen_1250_Leq_LBH==0)   
                
            else:
                
                m.Equation(FHRSG_C2_NG_SCFH ==0)
        
                m.Equation(BLR_C2_Steam_Gen_1250_LBH==0)   

#_____________________________________________________________________________________________________________________________________________    
    
    """
    VARIABLES FOR STG C3
      
    Fixed X Values :: Enthalpy of 1250# Steam,Enthalpy of 400# Extraction Steam,06C-F4019.PV,Enthalpy of 175# Extraction Steam
    
    X Variable :06C-J1104A.PV
    
    Y Variable : 06C-FX3618

    """
    
    if user_opt_status.loc['STG C3','user_status'] == 0: 
            
            m.Equation(STG_C3_Steam_Cons_1250_LBH - STG_C3_RUN_STATUS*input_df['DP_OPT_1250STM_PHC_CONS_C3_STG_LBH'].values[0] == 0)
            
            m.Equation(STG_C3_Power_MW - STG_C3_RUN_STATUS*input_df['DP_OPT_PWR_PHC_GEN_C3_STG_MW'].values[0] == 0)
         
        #STG C3 Linear Equation
    else :
        
        if STG_C3_RUN_STATUS == 1:
            
            m.Equation((-821.223*input_df['DP_OPT_1250_STMIL_ENTHALPY_PHC_C3_STG_BTULB'].values[0]+
                        197.754*input_df['DP_OPT_400_STMOL_ENTHALPY_PHC_C3_STG_BTULB'].values[0]-
                        0.691*input_df['DP_OPT_175_STMOL_FLOW_PHC_C3_STG_LBH'].values[0]-
                        760.151*input_df['DP_OPT_175_STMOL_ENTHALPY_PHC_C3_STG_BTULB'].values[0]+
                        22540.494*STG_C3_Power_MW+
                        2549010.24)-(STG_C3_Steam_Cons_1250_LBH)==0)
            
            
            m.Equation(STG_C3_Power_MW <=60)
            m.Equation(STG_C3_Power_MW >=10)
            m.Equation(STG_C3_Steam_Cons_1250_LBH <=1400000)
            m.Equation(STG_C3_Steam_Cons_1250_LBH >=600000)

            # m.Equation(STG_C3_Steam_Cons_1250_LBH - STG_C3_RUN_STATUS*STG_C3_Steam_Cons_1250_Leq_LBH == 0)
            
            # m.Equation(STG_C3_Power_MW - STG_C3_RUN_STATUS*STG_C3_Power_Leq_MW == 0)
            
        else:
            
            m.Equation(STG_C3_Steam_Cons_1250_LBH == 0)
            
            m.Equation(STG_C3_Power_MW == 0)
    
#_____________________________________________________________________________________________________________________________________________    
     
    """
    VARIABLES FOR STG R4
       
    Fixed X Values ::     Enthalpy of 1900# Steam, Enthalpy of 600# Extraction Steam, 06D-R4_IP_FLOW,35# Extraction Steam Heat Flow

    X Variable :  06D-J4503
    
    Y Variable :  06D-R4THROTTLE

    """
    
    #STG R4 Linear Equation    
    if user_opt_status.loc['STG R4','user_status'] == 0:
        
        m.Equation(STG_R4_Power_MW - STG_R4_RUN_STATUS*input_df['DP_OPT_PWR_RSC_GEN_R4_STG_MW'].values[0] == 0)
        
        m.Equation(STG_R4_Steam_Cons_1900_KLBH - STG_R4_RUN_STATUS*input_df['DP_OPT_STM_RSC_GEN_R4_TOT_EXHST_KLBH'].values[0] == 0)
    
    else:
        
        if STG_R4_RUN_STATUS ==1 :
    
            m.Equation((2.5623*input_df['DP_OPT_1900_STMIL_ENTHALPY_RSC_R4_STG_BTULB'].values[0]-
                        5.1787*input_df['DP_OPT_600_STMOL_ENTHALPY_RSC_R4_STG_BTULB'].values[0]+
                        0.3837*input_df['DP_OPT_STM_RSC_GEN_R4_IP_EXHST_KLBH'].values[0]-
                        0.5523*input_df['DP_OPT_35_STMOL_ENTHALPY_RSC_R4_STG_BTULB'].values[0]+
                        11.2399*STG_R4_Power_MW+
                        4085.923)-(STG_R4_Steam_Cons_1900_KLBH)==0)
            
            m.Equation(STG_R4_Power_MW <=90)
            m.Equation(STG_R4_Power_MW >=30)
            m.Equation(STG_R4_Steam_Cons_1900_KLBH <=1200)
            m.Equation(STG_R4_Steam_Cons_1900_KLBH >=800)
            # m.Equation(STG_R4_Power_MW - STG_R4_RUN_STATUS*STG_R4_Power_Leq_MW == 0)
            
            # m.Equation(STG_R4_Steam_Cons_1900_KLBH - STG_R4_RUN_STATUS*STG_R4_Steam_Cons_1900_Leq_KLBH == 0)

        else:
            
            m.Equation(STG_R4_Power_MW  == 0)
            
            m.Equation(STG_R4_Steam_Cons_1900_KLBH == 0)

#_____________________________________________________________________________________________________________________________________________    

    """
    VARIABLES FOR STG R2
    
    X Variable :  06C-J1345A
        
    Y Variable :  06B-FAHL2001A

    """    
    #STG R2 Linear Equation 
    if user_opt_status.loc['STG R2','user_status'] == 0:
        
        m.Equation(STG_R2_Power_MW - STG_R2_RUN_STATUS*input_df['DP_OPT_PWR_RS_GEN_R2_STG_MW'].values[0] == 0)
        
        m.Equation(STG_R2_Steam_Cons_600_KLBH - STG_R2_RUN_STATUS*input_df['DP_OPT_600STM_RS_CONS_R2_STG_KLBH'].values[0] == 0)
    
           
    else :
        
        if STG_R2_RUN_STATUS == 1 :
        
            m.Equation((9.3494*STG_R2_Power_MW +
                        32.6533)-(STG_R2_Steam_Cons_600_KLBH)==0)
            
            m.Equation(STG_R2_Power_MW <=40)
            m.Equation(STG_R2_Power_MW >=13)
            m.Equation(STG_R2_Steam_Cons_600_KLBH <=330)
            m.Equation(STG_R2_Steam_Cons_600_KLBH >=50)
            
            # m.Equation(STG_R2_Power_MW - STG_R2_RUN_STATUS*STG_R2_Power_Leq_MW == 0)
            
            # m.Equation(STG_R2_Steam_Cons_600_KLBH - STG_R2_RUN_STATUS*STG_R2_Steam_Cons_600_Leq_KLBH == 0)
 
        else :
            
            m.Equation(STG_R2_Power_MW == 0)
            
            m.Equation(STG_R2_Steam_Cons_600_KLBH== 0)
 
 
    
 #_____________________________________________________________________________________________________________________________________________    

    """
    VARIABLES FOR STG R3  
       
    Fixed X Values :: 06B-T3152
    
    X Variable : 06B-J1078A 
    
    Y Variable :  06B-FAHL3708A

    """

    #STG R3 Linear Equation 
    if user_opt_status.loc['STG R3','user_status'] == 0:
        
        m.Equation(STG_R3_Power_MW - STG_R3_RUN_STATUS*input_df['DP_OPT_PWR_RS_GEN_R3_STG_MW'].values[0] == 0)
        
        m.Equation(STG_R3_Steam_Cons_600_KLBH - STG_R3_RUN_STATUS*input_df['DP_OPT_600STM_RS_CONS_R3_STG_KLBH'].values[0] == 0)
    
    else :
        
        if STG_R3_RUN_STATUS == 1 :
            
            m.Equation((0.6642*input_df['DP_OPT_CONDOL_TEMP_RS_R3_STG_F'].values[0]+
                        8.7286*STG_R3_Power_MW-41.748)-(STG_R3_Steam_Cons_600_KLBH)==0)
            
            m.Equation(STG_R3_Power_MW <=31)
            m.Equation(STG_R3_Power_MW >=3)
            m.Equation(STG_R3_Steam_Cons_600_KLBH <=350)
            m.Equation(STG_R3_Steam_Cons_600_KLBH >=12)
            
            # m.Equation(STG_R3_Power_MW - STG_R3_Run_Status*STG_R3_Power_Leq_MW == 0)
            
            # m.Equation(STG_R3_Steam_Cons_600_KLBH - STG_R3_Run_Status*STG_R3_Steam_Cons_600_Leq_KLBH == 0)
        
        else :
            
            m.Equation(STG_R3_Power_MW  == 0)
            
            m.Equation(STG_R3_Steam_Cons_600_KLBH == 0)

#_____________________________________________________________________________________________________________________________________________    
   
    # m.options.MAX_ITER = 300   # adjust maximum iterations
    # m.options.SOLVER = 2
    # m.options.COLDSTART=2
    # m.solve(disp=True)
    # m.open_folder() 
    
    
    comparison_scripts = pd.read_csv('config/actual_and_optimized_alias.csv')
    actual_list = comparison_scripts['actual'].tolist()
      
    bounds_without_leq =pd.read_csv('config/DC_var_without_bounds.csv')
    DC_var_bounds = bounds_without_leq['variable'].tolist()
    
    output_tags=pd.read_csv('config/output_alias_map.csv')
    output_tags =output_tags.dropna()
    tag_id=output_tags['tag_id'].tolist()
    no_of_output_tags=len(output_tags['tag_id'])
    
    
    try:
        try:
            m.solve(disp=False) # solve
            print("Solution Found Successfully in Default residual Tolerance")
            
        except:
            m.solver_options = ['constraint_convergence_tolerance 1.0e-2' ]
            m.options.SOLVER = 1
            m.solve(disp=False) # solve
            print("Solution Found Successfully in Second residual Tolerance")
        
        opt_val =[]
        # print(DC_var_bounds)
        for v in DC_var_bounds:
            # print(f"Optimized {v} is {globals()[v][0]}")
            opt_val.append(locals()[v][0])
            
#______________________________LOGIC FOR EXTRA CALC KPI AND PROFIT MANIPULATION_____________________________________________________________            
        
        tag_alias=list(output_tags['tag_alias'])
        length_removal = 53
        tag_alias= tag_alias[:no_of_output_tags - length_removal] 
        
        output_dict = {}
        output_dict['tag'] = tag_alias
        output_dict['value'] = opt_val
        output_df = pd.DataFrame(output_dict)
        output_df = output_df.set_index('tag')
        
        if total_power_export_MW.value[0] > 225:
            power_export_dollar_manipulated = ((total_power_export_MW.value[0]-225)*LMP_Price_Dollar+((225*7.5*input_df['DP_OPT_HENRY_HUB_NG_PRICE_DOLLARPMMBTU'].values[0])/0.293071))
            
            profit_manipulated =(power_export_dollar_manipulated + power_within_WL_dollar + steam_within_WL_dollar + steam_export_LACC_dollar)-(power_purchased_dollar + total_fuel_within_PH_dollar.value[0] +Steam_Venting_Dollar.value[0])
        
            output_df.loc['OP4_OPT_PROFIT_POWERHOUSE_DOLLARS','value']=profit_manipulated
            output_df.loc['OP4_OPT_REVENUE_POWER_EXPORT_DOLLARS','value']=power_export_dollar_manipulated

            opt_val[0]=profit_manipulated
            opt_val[1]=power_export_dollar_manipulated
            
                    
        else:
            power_export_dollar_manipulated = power_export_dollar.value[0]
            
            profit_manipulated = profit.value[0]
        
        
        
        calc_KPI=pd.read_csv('config/calculated_KPI.csv')
        calc_expression = calc_KPI['expression'].tolist()
        
        for i in calc_expression:
            kpi_val = eval(i)
            opt_val.append(kpi_val)
            
        opt_val.append(1)  # This line is opt DP_OPT CODE STATUS
           
#___________________________________________________________________________________________________________________            
        
        op_dict={}
        op_dict['timestamp']=[time_upto]*no_of_output_tags
        op_dict['tag']=tag_id
        op_dict['value']= opt_val
        op_df=pd.DataFrame(op_dict)
        
        # op_df_2=pd.DataFrame(op_dict)
        
        
        if profit_manipulated < input_df['DP_OPT_PROFIT_POWERHOUSE_DOLLARS'].values[0] :
            
           
            del op_df     # deleting previous op_df to make new one 
            
            op_dict={}
            op_dict['timestamp']=[time_upto]*no_of_output_tags
            op_dict['tag']=tag_id
            op_dict['value']= -9999
            op_df=pd.DataFrame(op_dict)
            
            message = "System at Optimized State Any further increase in power generation and export might not be so beneficial, possibly due to current LMP price of power." # add substitute value too
            category = "System is at Optimized State"
            query = f"insert into {alert_table} (timestamp,category,message) values ('{time_upto}','{category}','{message}')"
            db_connection_1.execute(query)
            print("profit manipulated is less then actual")
       
        else:
        
            reco_df = pd.read_csv('config/recommendation_tags.csv')


            for i,row in reco_df.iterrows() :
                    
                x= locals()[row['opt_2']][0]
                x= round(x,1) 
                
                y= locals()[row['opt_1']][0]
                y= round(y,1)
                
                #Overall tags
                Total_Power_Gen_PHC = GT_C1_Power_MW[0] + GT_C2_Power_MW[0] + GT_C4_Power_MW[0] + GT_C5_Power_MW[0] + STG_C3_Power_MW[0] 
                Total_Power_Gen_RSC = GT_R5_Power_MW[0] + GT_R6_Power_MW[0] + STG_R2_Power_MW[0] + STG_R3_Power_MW[0] + STG_R4_Power_MW[0]
                Total_1250_Gen = BLR_C1_Steam_Gen_1250_LBH[0] + BLR_C2_Steam_Gen_1250_LBH[0] + HRSG_C4_Steam_Gen_1250_LBH[0] + HRSG_C5_Steam_Gen_1250_LBH[0]
                Total_1900_Gen = HRSG_R5_Steam_Gen_1900_KLBH[0] + HRSG_R6_Steam_Gen_1900_KLBH[0]  
                #print(x,round(input_df[row['alias_2']].values[0],1))
                
                if input_df[row['running_status']].values[0]==1  :
                    # print(input_df[row['running_status']].values[0])
                    
                    if user_opt_status.loc[row['user_opt_status'],'user_status']==1 :
                        
                        if round(input_df[row['alias_2']].values[0],1)!=x and (x > 1.03*input_df[row['alias_2']].values[0] or x < 0.97*input_df[row['alias_2']].values[0]) :
                        #     print(user_opt_status.loc[row['user_opt_status'],'user_status'])
                            #print(round(input_df[row['alias_2']].values[0],1),x)
                
                            # message = f"optimized value for {row['Equipment']} {row['comment']} i.e {row['tag_1']} is {x} {row['uom_1']} greater than actual value {input_df[row['alias_1']].values[0]} {row['uom_1']}"
                            # message = f"Change {row['Equipment']} {row['comment']} i.e {row['tag_2']} from {round(input_df[row['alias_2']].values[0],1)} {row['uom_2']} to {x} {row['uom_2']},in steps. "
                            message = f"Change {row['comment']} i.e {row['tag_2']} from {round(input_df[row['alias_2']].values[0],1)} {row['uom_2']} to {x} {row['uom_2']},in steps. "
                            eqpt=f"{row['Equipment']}"
                            model_acc = round(100 - abs(error_prcnt_calc.loc[row['model_accuracy'],'value']),2)
                            heat_rate = round(input_df[row['heat_rate_tag']].values[0],2) if row['heat_rate_tag'] != '-' else '-'
                            impact_message = f"Change {row['comment_impact']} i.e {row['tag_1']} from {round(input_df[row['alias_1']].values[0],1)} {row['uom_1']} to {y} {row['uom_1']},in steps. "
                            plant = f"{row['plant']}"
                            #print(message)
                            query = f"insert into {recommendation_table} (timestamp,equipment,recommendation,model_accuracy,heat_rate,impact,plant) values ('{time_upto}','{eqpt}','{message}','{model_acc}','{heat_rate}','{impact_message}','{plant}')"
                            db_connection_2.execute(query)
                            # print(message)

                        else:
                            pass
                    else:
                        pass
                else:
                    pass
                   
            
    except:
        # m.open_folder()
        print('Not successful')
        print(traceback.format_exc())
        
        message = "Model could not find Optimized State" # add substitute value too
        category = "No Solution Found"
        query = f"insert into {alert_table} (timestamp,category,message) values ('{time_upto}','{category}','{message}')"
        db_connection_1.execute(query)
        
        op_dict={}
        op_dict['timestamp']=[time_upto]*no_of_output_tags
        op_dict['tag']=tag_id
        op_dict['value']= -9999
        # op_dict['value']= act_val
        op_df=pd.DataFrame(op_dict)
    
        
    # Generating Alert for Equipment which are not selected for optimization at current timestamp.
    dont_opt_list = []
    for i, row  in user_opt_status.iterrows():
        if row['user_status']==0:
            dont_opt_list.append(i)
            
    dont_opt_list= (', '.join(dont_opt_list)) #removing Brackets and Quotes from list
     
    message = f"Please note following equipment {dont_opt_list} are not Optimized for current timestamp.Reasons for not optimized are listed below." # add substitute value too
     
     # Please note either of the {residual_list_new} is being operated below their minimum operation limit. Please check 'Limits screen' for more details
    category = "Dont Optimize"
    query = f"insert into {alert_table} (timestamp,category,message) values ('{last_run_time+interval}','{category}','{message}')"
    db_connection_1.execute(query)  
    
    #Merge Optimized Data and Error Data 
    op_df = pd.concat([op_df,error_op_df],ignore_index=True)
              
    
    return op_df
#________________________________________________________________________________________________________________________________________________________
#last_run_time =pd.to_datetime('2023-05-21 03:00:00')
#last_run_time=pd.to_datetime('2022-05-12 22:00:00')
#while last_run_time < pd.to_datetime('21-May-2024'):
if __name__ == "__main__":
    # start loop (here condition can be changed as per use case)
    # get start time of code.
    start = time()
    # check required files.
    check_files(file_list)
    # reading taglist file
    taglist = pd.read_csv("config/input_alias_map.csv")
    # get tags from taglist
    tags = tuple(taglist["tag_id"])

    # start of main loop
    if status == "True":
        try:
            print(f"Mode selected : {exec_mode}")
            logging.info("Mode selected : %s", exec_mode)
            if exec_mode == "noconnect":
                db_connection_1 = db_conn(
                    db_config["host"],
                    db_config["user"],
                    db_config["pass"],
                    db_config["schema"],
                )
                print("Database connection 1 successful")
                logging.info("Database connection 1 successful")
            else:
                db_connection_1 = None
                print("Reading CSV file")
                logging.info("Reading CSV file")
                
                
            if exec_mode == "noconnect":
                db_connection_2 = db_conn(
                    db_config["host"],
                    db_config["user"],
                    db_config["pass"],
                    db_config["schema_2"],
                )
                print("Database connection 2 successful")
                logging.info("Database connection 2 successful")
            else:
                db_connection_2 = None
                print("Reading CSV file")
                logging.info("Reading CSV file")
                
                
            # Get last_run_time of BLC
            last_run_time, running_interval = get_last_run(
                exec_mode,
                interval,
                db_config["lastrun_table"],
                db_config["id"],
                db_connection_1                
            )
            interval = timedelta(minutes=running_interval)
            print(f"Last run time : {last_run_time}")
            logging.info("Last run time : %s", last_run_time)
            # Read input from input table. In case of multiple tables, call the \
            # same functions multiple times.
            input_data_DP = read_input(
                exec_mode,
                tags,
                last_run_time,
                last_run_time + interval,
                db_config["input_table"],
                db_connection_1,
                input_path
            )
            
            input_data_DP_C = read_input(
                exec_mode, 
                tags, 
                last_run_time, 
                last_run_time+interval,
                db_config['calculated_table'], 
                db_connection_1
            )
            
            input_data = pd.concat([input_data_DP, input_data_DP_C])
            
            # input_data['value'] = input_data['value'].round(decimals = 1)
            
            """ # Uncomment this part if you have multiple input tables.
                    (Only change input table name.)
            
            temp_df_2 = read_input(exec_mode, tags, last_run_time, last_run_time+interval,
                db_config['input_table2'], db_connection)
            input_data = pd.concat([temp_df_1, temp_df_2])
            """
            # Check if data is available for current timestamp. In case of no data, \
            # raise exception and exit.
            if len(input_data) == 0:
                raise NoDataException
                
                
            input_df = pivot_rename(input_data,taglist,'tag_id','tag_alias')
            
            # input_df =pd.read_csv('output/input.csv')
            # input_df
            logging.info('Input Data Pivoted Successfully') 
            
            # All the calculations need to be defined here or in Calculation function\
            # defined above.
            # The output of this function is directly stored as output, so only final\
            # results are to be returned.
            
            
            
            #Westlake Feedback
            if input_df['DP_OPT_AIROUT_TEMP_PHC_C1_GT_F'].values[0] <=500 or input_df['DP_OPT_AIROUT_TEMP_PHC_C1_GT_F'].values[0] >= 700 :
                if input_df['DP_OPT_DISC_TEMP_PHC_C4_GT_F'].values[0] >= 500 or input_df['DP_OPT_DISC_TEMP_PHC_C4_GT_F'].values[0] <= 700 :
                    input_df['DP_OPT_AIROUT_TEMP_PHC_C1_GT_F'].values[0]=input_df['DP_OPT_DISC_TEMP_PHC_C4_GT_F'].values[0]
                else:
                    pass
            else:
                pass
            
            if input_df['DP_OPT_DISC_TEMP_PHC_C4_GT_F'].values[0] <=500 or input_df['DP_OPT_DISC_TEMP_PHC_C4_GT_F'].values[0] >= 700 :
                if input_df['DP_OPT_AIROUT_TEMP_PHC_C1_GT_F'].values[0] >= 500 or input_df['DP_OPT_AIROUT_TEMP_PHC_C1_GT_F'].values[0] <= 700 :
                    input_df['DP_OPT_DISC_TEMP_PHC_C4_GT_F'].values[0]=input_df['DP_OPT_AIROUT_TEMP_PHC_C1_GT_F'].values[0]
                else:
                    pass
            else:
                pass
            
            #_______________________________________________________________________________________________________________________________#
            
            if input_df['DP_OPT_DISC_TEMP_PHC_C4_GT_F'].values[0] <=500 or input_df['DP_OPT_DISC_TEMP_PHC_C4_GT_F'].values[0] >= 700 :
                if input_df['DP_OPT_COMPRSR_C2_OUTLT_TEMP_B_DEGF'].values[0] >= 500 or input_df['DP_OPT_COMPRSR_C2_OUTLT_TEMP_B_DEGF'].values[0] <= 700 :
                    input_df['DP_OPT_DISC_TEMP_PHC_C4_GT_F'].values[0]=input_df['DP_OPT_COMPRSR_C2_OUTLT_TEMP_B_DEGF'].values[0]
                else:
                    pass
            else:
                pass
            
            if input_df['DP_OPT_COMPRSR_C2_OUTLT_TEMP_B_DEGF'].values[0] <=500 or input_df['DP_OPT_COMPRSR_C2_OUTLT_TEMP_B_DEGF'].values[0] >= 700 :
                if input_df['DP_OPT_DISC_TEMP_PHC_C4_GT_F'].values[0] >= 500 or input_df['DP_OPT_DISC_TEMP_PHC_C4_GT_F'].values[0] <= 700 :
                    input_df['DP_OPT_COMPRSR_C2_OUTLT_TEMP_B_DEGF'].values[0]=input_df['DP_OPT_DISC_TEMP_PHC_C4_GT_F'].values[0]
                else:
                    pass
            else:
                pass


#______________________________________________________CODE FLOW___________________________________________________________________________________________________________________________________________________________________________________
# '''
# Transtion State Check --PASS-->  Quality Check(Out of Bound) --PASS--> OPtimized State --PASS-->  [Profit Manipulated < Actual Profit] --PASS-->  Output Table(Optimized value) ----> (Update Last Runtime)

#            |                              |                                     |                                  | 
#           FAIL                           FAIL                           No Solution Found  <-----------------------  
#            |                              |                                     |
#            v                              v                                     v
#          -9999                          -9999                                 -9999
#     (Output Table)                  (Output Table)                        (Output Table)
#            |                              |                                     |
#            v                              v                                     v
# (Update Last Runtime)           (Update Last Runtime)                 (Update Last Runtime)
        
# '''      

#_________________________________________________________________________________________________________________________________________________________________________________________________________________________________________ 
            
            

            if (input_df['DP_OPT_C_TOTAL_POWER_GEN_MW'].values[0]== input_df['DP_OPT_C_TTL_POWER_GEN_STATUS_MW'].values[0]) and (input_df['DP_OPT_C_TOTAL_NG_CONS_MMSCFD'].values[0]== input_df['DP_OPT_C_TTL_NG_CONS_RUN_MMSCFD'].values[0]):
                
                transition_list = transition_state(last_run_time+interval,input_df,db_connection_1,alert_table)
                
                #quality_check_list = data_quality_check(input_df,last_run_time+interval,alert_table,db_connection_1)
               
                if all([v == 0 for v in transition_list]) :
                    
                    # if 1 in quality_check_list :
                    #     output_tags=pd.read_csv('config/output_alias_map.csv')
                    #     output_tags =output_tags.dropna()
                    #     tag_id=list(output_tags['tag_id'])
                    #     no_of_output_tags=len(list(output_tags['tag_id']))
                        
                    #     op_dict={}
                    #     op_dict['timestamp']=[last_run_time+interval]*no_of_output_tags
                    #     op_dict['tag']=tag_id
                    #     op_dict['value']= -9999
                    #     opt_output_data=pd.DataFrame(op_dict)
                    # else:
                     opt_output_data = optimization_model(input_df,last_run_time+interval,alert_table,db_connection_1,db_connection_2,recommendation_table)
                               
                else:
                    output_tags=pd.read_csv('config/output_alias_map.csv')
                    output_tags =output_tags.dropna()
                    tag_id=list(output_tags['tag_id'])
                    no_of_output_tags=len(list(output_tags['tag_id']))
                    
                    op_dict={}
                    op_dict['timestamp']=[last_run_time+interval]*no_of_output_tags
                    op_dict['tag']=tag_id
                    op_dict['value']= -9999
                    opt_output_data=pd.DataFrame(op_dict)
            
            else:
                
                run_status_residual_check =pd.read_csv("config/run status residual check.csv")
                residual_list = []
                for i ,row in run_status_residual_check.iterrows():
                    if input_df[row['DP_OPT_TAG']].values[0]<1:
                        print(input_df[row['DP_OPT_TAG']].values[0])
                        residual_list.append(row['Equipment'])
                    else:
                        pass
                
                output_tags=pd.read_csv('config/output_alias_map.csv')
                output_tags =output_tags.dropna()
                tag_id=list(output_tags['tag_id'])
                no_of_output_tags=len(list(output_tags['tag_id']))
                
                op_dict={}
                op_dict['timestamp']=[last_run_time+interval]*no_of_output_tags
                op_dict['tag']=tag_id
                op_dict['value']= -9999
                opt_output_data=pd.DataFrame(op_dict)
                
                # residual_list_new = str(residual_list)[1:-1]
                residual_list_new= (', '.join(residual_list)) #removing Brackets and Quotes from list
                
                message = f"Please note either of the {residual_list_new} is being operated below their minimum operation limit. Please check Optz Model-Residual Error Screen for more details." # add substitute value too
                
                # Please note either of the {residual_list_new} is being operated below their minimum operation limit. Please check 'Limits screen' for more details
                category = "Residual Value Error"
                query = f"insert into {alert_table} (timestamp,category,message) values ('{last_run_time+interval}','{category}','{message}')"
                db_connection_1.execute(query)
                
                
#___________________________________MISC CALCULATION_____________________________________________                 
            
            misc_act_tag =pd.read_csv("config/misc_actual_tag.csv") 
            misc_list =[]
            for i,row in misc_act_tag.iterrows():
                
                misc_val = input_df[row['DP_OPT_Tag']].values[0]*input_df[row['RUN_STATUS']].values[0]
                misc_list.append(misc_val)
                
            misc_output_tags=pd.read_csv('config/misc_output_alias_map.csv')
            misc_output_tags =misc_output_tags.dropna()
            misc_tag_id=list(misc_output_tags['tag_id'])
            no_of_misc_output_tags=len(list(misc_output_tags['tag_id']))
            
            misc_op_dict={}
            misc_op_dict['timestamp']=[last_run_time+interval]*no_of_misc_output_tags
            misc_op_dict['tag']=misc_tag_id
            misc_op_dict['value']= misc_list
            misc_output_data=pd.DataFrame(misc_op_dict)
            
            output_data = pd.concat([opt_output_data,misc_output_data],ignore_index=True)
    
            # print(output_data)
            # Writing output to either DB or csv based on mode selected. \
            # Structure needs to be (timestamp,tag,value).
                    
            write_output(
                exec_mode,
                output_data,
                last_run_time + interval,
                db_config["output_table"],
                db_connection_1,
                db_config["lastrun_table"],
                db_config["id"],
                output_path
            )
        except NoDataException:
            print("No data found for the timestamp")
            logging.error("No data found for the timestamp")
            # uncomment below line in case of running in loop
            # break
        except ZeroDivisionError:
            print(traceback.format_exc())
            print("Zero value found in calculations. Please check.")
            logging.error("Zero value found in calculations. Please check.")
        except Exception as e:
            # Broad exception in case of any undefined error case.
            print(f"Error : {e}")
            logging.error(e)
            print(traceback.format_exc())
    end_time = time()
    print(f"Execution completed in {end_time-start}s.")
    logging.info("Execution completed in %s.", end_time - start)
    print("X-----X----X------X------X-------X------X-----X")
    # sys.exit("Exiting....")
#_______________________________________________________________________________________________________________________________    
    
    # Comparison Scripts 
    
    '''
    comparison_scripts = pd.read_csv('config/actual_and_optimized_alias.csv')
    # comparison_scripts['actual value'] =''
    # comparison_scripts['optimized value'] =''
     
    actual =[]
    optimized = []
    for i,row in comparison_scripts.iterrows():
        print(eval(row['running status']))
        
        actual.append(input_df[row['actual']].values[0])
        optimized.append(globals()[row['optimized']][0])
        # row['actual value']= input_df[row['actual']].values[0]*(eval(row['running status']))
        # row['optimized value'] = globals()[row['optimized']][0]
        # print(row['actual value'])
        
    comparison_scripts['actual_value']=actual
    comparison_scripts['optimized_value']=optimized
    comparison_scripts = comparison_scripts.set_index('optimized')
    
    comparison_scripts.loc['profit','optimized_value']=profit_manipulated
    comparison_scripts.loc['power_export_dollar','optimized_value']=power_export_dollar_manipulated
    
    
    comparison_scripts =comparison_scripts.drop(['running status'], axis=1)
    
    
    comparison_scripts.to_csv('output/actual_vs_optimized_value.csv')
    
    # --------------------------------------------------------------
    
    header_imb_df = pd.read_csv('config/header_imbalances.csv')
    header_imb_df =header_imb_df.set_index('alias')   
    header_imb_df['values']=''
    for i, row in header_imb_df.iterrows():
        # print(eval(row['expression']))
        row['values']=eval(row['expression'])
        
    header_imb_df.to_csv('output/header_imbalance_output')
    
    # ---------------------------------------------------------
    
    df = pd.melt(input_df)
    
    # --------------------------------------------------------
    
    (((-450.194*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]+6477.206*input_df['DP_OPT_PWR_PHC_GEN_C1_GT_MW'].values[0]+323.091*input_df['DP_OPT_AIROUT_TEMP_PHC_C1_GT_F'].values[0]-191.434*input_df['DP_OPT_AMB_TEMP_F'].values[0]+22.19*input_df['DP_OPT_RELATIVE_HUMIDITY_PCNT'].values[0]+88.864*input_df['DP_OPT_EXHST_TEMP_PHC_C1_GT_F'].values[0]+518927.909)-input_df['DP_OPT_NG_PHC_CONS_C1_GT_SCFH'].values[0])/input_df['DP_OPT_NG_PHC_CONS_C1_GT_SCFH'].values[0])*100*input_df['DP_OPT_RUNNING_STATUS_GT_C1'].values[0]
    
    
    
    
    
    
    '''
    

    
        
    # comparison_scripts =comparison_scripts.drop(['actual'], axis=1)
    
    


  
    # output_tags=pd.read_csv('config/output_alias_map.csv')
    # output_tags =output_tags.dropna()
    # tag_id=list(output_tags['tag_alias'])
    # no_of_output_tags=len(list(output_tags['tag_id']))
    # length_removal =  6
    
    # tag_id = tag_id[: no_of_output_tags - length_removal ] #to make lenth same 
    
    # output_dict={}
    # # op_dict['timestamp']=[time_upto]*no_of_output_tags
    # output_dict['tag']=tag_id
    # output_dict['value']= opt_val
    # output_df=pd.DataFrame(output_dict)
    # output_df=output_df.set_index('tag')

# user_opt_status = pd.read_csv("config/user_opt_status.csv")
# user_opt_status=user_opt_status.set_index('Equipment_list')


# min_max= pd.read_csv('config/min_max_input_df.csv')
# out_of_bound = []    
# for i,row in min_max.iterrows():
#     # print(eval(row['Equipment'])*row['MIN'])
#     # print(input_df[row['DP_OPT  Tag']].values[0])
   
#     if (input_df[row['DP_OPT  Tag']].values[0] < eval(row['Equipment'])*row['MIN'] or input_df[row['DP_OPT  Tag']].values[0] > row['MAX']) and (user_opt_status.loc[row['eqpt'],'user_status']==1):
#         print('True')
        
#     else:
#         print('False')
        
        
#         out_of_bound.append(1)
        
        
#         message = f" tag value: {input_df[row['DP_OPT  Tag']].values[0]} is out of it training Range i.e MIN = {row['MIN']} and MAX = {row['MAX']}  "# add substitute value too
#         # print(message)
#         alert_dict = [{'timestamp':time_upto,'category':'Tag Out Of Bound','description':row['description'],'tag':row['tag'],'message':message,}]
#         alert_df = pd.DataFrame(alert_dict)
#         print(alert_df)
#         # alert_df.to_sql(alert_table, con=db_connection_1, if_exists='append', index=False)
        
        
#         # when we will have manual entry table we will substitute into it 
#         # input_df[row['DP_OPT  Tag']].values[0]= -9999
        
#         # print(input_df[row['DP_OPT  Tag']].values[0]  + "After")
#         # print(f"{input_df[row['DP_OPT  Tag']].values[0]} ---After ")
        
#     else :
#         out_of_bound.append(0)


# for i in user_opt_status.index:
#     print(user_opt_status.loc[i,'user_status'])
    
#_________________________________________________________________________________________________________________________________

    # power_export_dummy = m.Intermediate( total_power_export_MW -225 )
    
       
    # cond_expt_2 = m.Intermediate(((total_power_export_MW-225)*LMP_Price_Dollar+(225*7.5*input_df['DP_OPT_HENRY_HUB_NG_PRICE_DOLLARPMMBTU'].values[0])/0.293071))
    
    # cond_expt_1 = m.Intermediate((total_power_export_MW*7.5*input_df['DP_OPT_HENRY_HUB_NG_PRICE_DOLLARPMMBTU'].values[0])/0.293071)
    
    # power_export_dollar = m.if3(power_export_dummy,cond_expt_1,cond_expt_2)
    
    
    # cond_expt_2 = m.Intermediate(((total_power_export_MW-225)*LMP_Price_Dollar+(225*7.5*input_df['DP_OPT_HENRY_HUB_NG_PRICE_DOLLARPMMBTU'].values[0])/0.293071))
    
    # cond_expt_1 = m.Intermediate((total_power_export_MW*7.5*input_df['DP_OPT_HENRY_HUB_NG_PRICE_DOLLARPMMBTU'].values[0])/0.293071)
    
    # z = m.if2(total_power_export_MW-225,0,1)
    
    # m.Equation(power_export_dollar==(1-z)*cond_expt_1+z*cond_expt_2)
      