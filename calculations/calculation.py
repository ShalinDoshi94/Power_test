# -*- coding: utf-8 -*-
"""
Created on Thu Oct 26 11:15:21 2023

@author: skanojia
"""

import pandas as pd 
from gekko import GEKKO
import traceback

from datetime import datetime

def transition_state(time_upto,input_df,db_connection_1,alert_table):
    eqpt_status = []
    status= pd.read_csv('config/transition_alias.csv')
    new_status = status.dropna()
    for i,row in new_status.iterrows():
        
        eqpt_status.append(input_df[row['alias']].values[0])
        
        if input_df[row['alias']].values[0] !=0:
            message = f"{row['Equipment list']} is under Transition State"
                    
            alert_dict = [{'timestamp':time_upto,'category':'transition state','tag':row['Equipment list'],'message':message,}]
            alert_df = pd.DataFrame(alert_dict)
            alert_df.to_sql(alert_table, con=db_connection_1, if_exists='append', index=False)
        
    mask = status.index.isin(new_status.index)
    status = status[~mask]
    
    for i,row in status.iterrows():
        
        # eqpt_status.append(input_df[row['alias']].values[0])
        
        if input_df[row['alias']].values[0] > 0 and input_df[row['alias']].values[0] < 1:
            
            eqpt_status.append(1)
            
            message = f"{row['alias']} is under Transition State"
                    
            alert_dict = [{'timestamp':time_upto,'category':'transition state','tag':row['alias'],'message':message,}]
            alert_df = pd.DataFrame(alert_dict)
            alert_df.to_sql(alert_table, con=db_connection_1, if_exists='append', index=False)
            
        else:
            eqpt_status.append(0)
            
            
    return eqpt_status


def data_quality_check(input_df,time_upto,alert_table,db_connection_1):
    
    #---------------------------------- Data Quality Check ----------------------------------#
    
    min_max= pd.read_csv('config/min_max_input_df.csv')
    out_of_bound = []    
    for i,row in min_max.iterrows():
        # print(eval(row['Equipment'])*row['MIN'])  
        # print(input_df[row['DP_OPT  Tag']].values[0])
       
        if (input_df[row['DP_OPT  Tag']].values[0] < eval(row['Equipment'])*row['MIN'] or input_df[row['DP_OPT  Tag']].values[0] > row['MAX']):
            out_of_bound.append(1)
            
            message = f"{row['tag']} {input_df[row['DP_OPT  Tag']].values[0]} is out of it training Range i.e MIN = {row['MIN']} and MAX = {row['MAX']}  "# add substitute value too
            
            alert_dict = [{'timestamp':time_upto,'category':'Out Of Bound','tag':row['DP_OPT  Tag'],'message':message,}]
            alert_df = pd.DataFrame(alert_dict)
            alert_df.to_sql(alert_table, con=db_connection_1, if_exists='append', index=False)
            
            
            # when we will have manual entry table we will substitute into it 
            # input_df[row['DP_OPT  Tag']].values[0]= -9999
            
            # print(input_df[row['DP_OPT  Tag']].values[0]  + "After")
            # print(f"{input_df[row['DP_OPT  Tag']].values[0]} ---After ")
            
        else :
            out_of_bound.append(0)
            # print(row['DP_OPT  Tag']+'in Range')
            
    return out_of_bound
    

def optimization_model(input_df,time_upto,alert_table,db_connection_1,db_connection_2,recommendation_table):  

    # bounds = pd.read_csv('config/DC_var_bounds.csv').set_index('variable')
    
    # input_df = input_df
    print("sds")
    
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
    
    # # COST VARIABLES.
    profit =m.Var(value=input_df['DP_OPT_PROFIT_POWERHOUSE_DOLLARS'].values[0],  lb=input_df['DP_OPT_PROFIT_POWERHOUSE_DOLLARS'].values[0],  ub=100000,  name='profit')
    power_export_dollar =m.Var(value=input_df['DP_OPT_REVENUE_POWER_EXPORT_DOLLARS'].values[0],  lb=1*0,  ub=1000000,  name='power_export_dollar')
    total_fuel_within_PH_dollar =m.Var(value=input_df['DP_OPT_COST_FUEL_WITHIN_POWERHOUSE_DOLLARS'].values[0],  lb=1*0,  ub=1000000,  name='total_fuel_within_PH_dollar')
    total_power_export_MW =m.Var(value=input_df['DP_OPT_POWER_EXPORT_MW'].values[0],  lb=1*0, ub= 360 if (input_df['DP_OPT_TRANSFORMER_T1_STATUS'].values[0]==1 and input_df['DP_OPT_TRANSFORMER_T2_STATUS'].values[0]==1 ) else 180,  name='total_power_export_MW')
    GT_C1_NG_Flow_SCFH =m.Var(value=input_df['DP_OPT_NG_PHC_CONS_C1_GT_SCFH'].values[0],  lb=GT_C1_RUN_STATUS*500000,  ub=800000,  name='GT_C1_NG_Flow_SCFH')
    GT_C2_NG_Flow_SCFH =m.Var(value=input_df['DP_OPT_NG_PHC_CONS_C2_GT_SCFH'].values[0],  lb=GT_C2_RUN_STATUS*500000,  ub=800000,  name='GT_C2_NG_Flow_SCFH')
    GT_C4_NG_Flow_SCFH =m.Var(value=input_df['DP_OPT_NG_PHC_CONS_C4_GT_SCFH'].values[0],  lb=GT_C4_RUN_STATUS*500000,  ub=1000000,  name='GT_C4_NG_Flow_SCFH')
    GT_C5_NG_Flow_SCFH =m.Var(value=input_df['DP_OPT_NG_FLOW_PHC_C5_GT_SCFH'].values[0],  lb=GT_C5_RUN_STATUS*500000,  ub=1000000,  name='GT_C5_NG_Flow_SCFH')
    GT_R5_NG_Flow_KPPH =m.Var(value=input_df['DP_OPT_NG_RSC_CONS_TOTAL_R5_GT_KPPH'].values[0],  lb=GT_R5_RUN_STATUS*50,  ub=85,  name='GT_R5_NG_Flow_KPPH')
    GT_R6_NG_Flow_KPPH =m.Var(value=input_df['DP_OPT_NG_RSC_CONS_TOTAL_R6_GT_KPPH'].values[0],  lb=GT_R6_RUN_STATUS*50,  ub=85,  name='GT_R6_NG_Flow_KPPH')
    FHRSG_C1_NG_SCFH =m.Var(value=input_df['DP_OPT_NG_FLOW_PHC_C1_HRSG_SCFH'].values[0],  lb=BOILER_C1_RUN_STATUS*50000,  ub=1000000,  name='FHRSG_C1_NG_SCFH')
    FHRSG_C2_NG_SCFH =m.Var(value=input_df['DP_OPT_NG_FLOW_PHC_C2_HRSG_SCFH'].values[0],  lb=BOILER_C2_RUN_STATUS*50000,  ub=1000000,  name='FHRSG_C2_NG_SCFH')
    HRSG_R5_Steam_Gen_1900_KLBH =m.Var(value=input_df['DP_OPT_HPSTMOL_FLOW_RSC_R5_HRSG_KPPH'].values[0],  lb=GT_R5_RUN_STATUS*200,  ub=600,  name='HRSG_R5_Steam_Gen_1900_KLBH')
    HRSG_R6_Steam_Gen_1900_KLBH =m.Var(value=input_df['DP_OPT_HPSTMOL_FLOW_RSC_R6_HRSG_KPPH'].values[0],  lb=GT_R6_RUN_STATUS*200,  ub=600,  name='HRSG_R6_Steam_Gen_1900_KLBH')
    STG_C3_Steam_Cons_1250_LBH =m.Var(value=input_df['DP_OPT_1250STM_PHC_CONS_C3_STG_LBH'].values[0],  lb=STG_C3_RUN_STATUS*300000,  ub=1400000,  name='STG_C3_Steam_Cons_1250_LBH')
    STG_R2_Steam_Cons_600_KLBH =m.Var(value=input_df['DP_OPT_600STM_RS_CONS_R2_STG_KLBH'].values[0],  lb=STG_R2_RUN_STATUS*100,  ub=320,  name='STG_R2_Steam_Cons_600_KLBH')
    STG_R3_Steam_Cons_600_KLBH =m.Var(value=input_df['DP_OPT_600STM_RS_CONS_R3_STG_KLBH'].values[0],  lb=STG_R3_RUN_STATUS*100,  ub=350,  name='STG_R3_Steam_Cons_600_KLBH')
    STG_R4_Steam_Cons_1900_KLBH =m.Var(value=input_df['DP_OPT_STM_RSC_GEN_R4_TOT_EXHST_KLBH'].values[0],  lb=STG_R4_RUN_STATUS*450,  ub=1150,  name='STG_R4_Steam_Cons_1900_KLBH')
    GT_C1_Power_MW =m.Var(value=input_df['DP_OPT_PWR_PHC_GEN_C1_GT_MW'].values[0],  lb=GT_C1_RUN_STATUS*40,  ub=65,  name='GT_C1_Power_MW')
    GT_C2_Power_MW =m.Var(value=input_df['DP_OPT_PWR_PHC_GEN_C2_GT_MW'].values[0],  lb=GT_C2_RUN_STATUS*30,  ub=65,  name='GT_C2_Power_MW')
    GT_C4_Power_MW =m.Var(value=input_df['DP_OPT_PWR_PHC_GEN_C4_GT_MW'].values[0],  lb=GT_C4_RUN_STATUS*40,  ub=85,  name='GT_C4_Power_MW')
    GT_C5_Power_MW =m.Var(value=input_df['DP_OPT_PWR_PHC_GEN_C5_GT_MW'].values[0],  lb=GT_C5_RUN_STATUS*30,  ub=90,  name='GT_C5_Power_MW')
    GT_R5_Power_MW =m.Var(value=input_df['DP_OPT_PWR_RSC_GEN_R5_STG_MW'].values[0],  lb=GT_R5_RUN_STATUS*80,  ub=200,  name='GT_R5_Power_MW')
    GT_R6_Power_MW =m.Var(value=input_df['DP_OPT_PWR_RSC_GEN_R6_STG_MW'].values[0],  lb=GT_R6_RUN_STATUS*80,  ub=200,  name='GT_R6_Power_MW')
    STG_C3_Power_MW =m.Var(value=input_df['DP_OPT_PWR_PHC_GEN_C3_STG_MW'].values[0],  lb=STG_C3_RUN_STATUS*5,  ub=60,  name='STG_C3_Power_MW')
    STG_R2_Power_MW =m.Var(value=input_df['DP_OPT_PWR_RS_GEN_R2_STG_MW'].values[0],  lb=STG_R2_RUN_STATUS*5,  ub=35,  name='STG_R2_Power_MW')
    STG_R3_Power_MW =m.Var(value=input_df['DP_OPT_PWR_RS_GEN_R3_STG_MW'].values[0],  lb=STG_R3_RUN_STATUS*5,  ub=40,  name='STG_R3_Power_MW')
    STG_R4_Power_MW =m.Var(value=input_df['DP_OPT_PWR_RSC_GEN_R4_STG_MW'].values[0],  lb=STG_R4_RUN_STATUS*10,  ub=90,  name='STG_R4_Power_MW')
    Power_Gen_MW =m.Var(value=input_df['DP_OPT_TOTAL_PWR_GEN_MW'].values[0],  lb=1*0,  ub=800,  name='Power_Gen_MW')
    Letdown_1900_TO_600_KLBH =m.Var( input_df['DP_OPT_LETDOWN_1900_TO_600_KLBH'].values[0],lb=1*0,  ub=1000,  name='Letdown_1900_TO_600_KLBH')
    BLR_C1_Steam_Gen_1250_LBH =m.Var(value=input_df['DP_OPT_1250STM_PHC_GEN_C1_BOILER_LBH'].values[0],  lb=BOILER_C1_RUN_STATUS*100000,  ub=750000,  name='BLR_C1_Steam_Gen_1250_LBH')
    BLR_C2_Steam_Gen_1250_LBH =m.Var(value=input_df['DP_OPT_1250STM_PHC_GEN_C2_BOILER_LBH'].values[0],  lb=BOILER_C2_RUN_STATUS*100000,  ub=750000,  name='BLR_C2_Steam_Gen_1250_LBH')
    HRSG_C4_Steam_Gen_1250_LBH =m.Var(value=input_df['DP_OPT_1250STM_PHC_GEN_C4_HRSG_LBH'].values[0],  lb=GT_C4_RUN_STATUS*100000,  ub=300000,  name='HRSG_C4_Steam_Gen_1250_LBH')
    HRSG_C5_Steam_Gen_1250_LBH =m.Var(value=input_df['DP_OPT_1250STM_PHC_GEN_C5_HRSG_LBH'].values[0],  lb=GT_C5_RUN_STATUS*60000,  ub=300000,  name='HRSG_C5_Steam_Gen_1250_LBH')
    Letdown_1250_TO_400_LBH =m.Var(value=input_df['DP_OPT_STM_PHC_CONS_PRDS_1250_400_LBH'].values[0],  lb=1*0,  ub=1400000,  name='Letdown_1250_TO_400_LBH')
    STG_R4_Steam_Gen_600_KLBH =m.Var(value=input_df['DP_OPT_600STM_RSC_GEN_R4_STG_KPPH'].values[0],  lb=STG_R4_RUN_STATUS*100,  ub=1000,  name='STG_R4_Steam_Gen_600_KLBH')
    STG_C3_Steam_Gen_400_LBH =m.Var(value=input_df['DP_OPT_400STM_PHC_GEN_C3_STG_LBH'].values[0],  lb=STG_C3_RUN_STATUS*100000,  ub=750000,  name='STG_C3_Steam_Gen_400_LBH')
    Letdown_From_400_TO_175_LBH =m.Var(value=input_df['DP_OPT_STM_PHC_CONS_PRDS_400_175_LBH'].values[0],  lb=-input_df['DP_OPT_STM_PHC_CONS_PRDS_400_175_LBH'].values[0]*0-109013,    name='Letdown_From_400_TO_175_LBH')
    Letdown_From_175_TO_30_LBH =m.Var(value=input_df['DP_OPT_STM_PHC_CONS_PRDS_175_30_LBH'].values[0],  lb=0,    name='Letdown_From_175_TO_30_LBH')
    STEAM_VENTING_LBH =m.Var(value=input_df['DP_OPT_STEAM_VENTING_LBH'].values[0] ,lb=0, name='STEAM_VENTING_LBH')
    
    
    # for i ,row in bounds.iterrows():
    #     row['variable']=m.Var(lb =row['lower_bound'],ub=row['upper_bound'])
    #     print(row['variable'])
    
    power_within_WL_dollar = input_df['DP_OPT_REVENUE_POWER_WITHIN_WL_DOLLARS'].values[0]  
    power_purchased_dollar = input_df['DP_OPT_COST_POWER_PURCHASED_DOLLARS'].values[0]
    steam_within_WL_dollar = input_df['DP_OPT_REVENUE_STEAM_WITHIN_WL_DOLLARS'].values[0]  
    steam_export_LACC_dollar = input_df['DP_OPT_REVENUE_STEAM_EXPORT_LACC_DOLLARS'].values[0]
    LMP_Price_Dollar = input_df['DP_OPT_AXIALL_LMP_PRICE_DOLLARPMWH'].values[0] 
    power_within_WL_MW = input_df['DP_OPT_C_POWER_WITHIN_POWERHOUSE_MW'].values[0] 
    
    GT_C1_Run_Status = input_df['DP_OPT_RUNNING_STATUS_GT_C1'].values[0] 
    GT_C2_Run_Status = input_df['DP_OPT_RUNNING_STATUS_GT_C2'].values[0] 
    GT_C4_Run_Status = input_df['DP_OPT_RUNNING_STATUS_GT_HRSG_C4'].values[0] 
    GT_C5_Run_Status = input_df['DP_OPT_RUNNING_STATUS_GT_HRSG_C5'].values[0] 
    GT_R5_Run_Status = input_df['DP_OPT_RUNNING_STATUS_GT_HRSG_R5'].values[0] 
    GT_R6_Run_Status = input_df['DP_OPT_RUNNING_STATUS_GT_HRSG_R6'].values[0] 
    
    Boiler_C1_Run_Status = input_df['DP_OPT_RUNNING_STATUS_BLR_C1'].values[0] 
    Boiler_C2_Run_Status = input_df['DP_OPT_RUNNING_STATUS_BLR_C2'].values[0] 
    
    STG_C3_Run_Status = input_df['DP_OPT_RUNNING_STATUS_STG_C3'].values[0]  
    STG_R2_Run_Status = input_df['DP_OPT_RUNNING_STATUS_STG_R2'].values[0] 
    STG_R3_Run_Status = input_df['DP_OPT_RUNNING_STATUS_STG_R3'].values[0] 
    STG_R4_Run_Status = input_df['DP_OPT_RUNNING_STATUS_STG_R4'].values[0] 
    
    
    # OBJECTIVE VARIABLES.
    
    #_______________________________________________________________________________________________________________________________________________________________
    
    m.Maximize(profit)
    
    m.Equation(((power_export_dollar + power_within_WL_dollar + steam_within_WL_dollar + steam_export_LACC_dollar)-
               (power_purchased_dollar + total_fuel_within_PH_dollar))-profit==0)
    
    
    m.Equation((power_export_dollar-(total_power_export_MW*7.5*input_df['DP_OPT_HENRY_HUB_NG_PRICE_DOLLARPMMBTU'].values[0])/0.293071)==0)
   
    # m.Equation( total_power_export_MW - power_export_dummy-225 == 0)
       
    # cond_expt_1 = (((total_power_export_MW-225)*LMP_Price_Dollar+(225*7.5*input_df['DP_OPT_HENRY_HUB_NG_PRICE_DOLLARPMMBTU'].values[0])/0.293071))
    
    # cond_expt_2 = ((total_power_export_MW*7.5*input_df['DP_OPT_HENRY_HUB_NG_PRICE_DOLLARPMMBTU'].values[0])/0.293071)
    
    # power_export_dollar = m.if3(total_power_export_MW,cond_expt_1,cond_expt_2)
    
    # power_export_dummy = m.Intermediate( total_power_export_MW -225 )
   
       
    # cond_expt_2 = m.Intermediate(((total_power_export_MW-225)*LMP_Price_Dollar+(225*7.5*input_df['DP_OPT_HENRY_HUB_NG_PRICE_DOLLARPMMBTU'].values[0])/0.293071))
    
    # cond_expt_1 = m.Intermediate((total_power_export_MW*7.5*input_df['DP_OPT_HENRY_HUB_NG_PRICE_DOLLARPMMBTU'].values[0])/0.293071)
    
    # power_export_dollar = m.if3(power_export_dummy,cond_expt_1,cond_expt_2)
    
    
    
    m.Equation(total_power_export_MW -(Power_Gen_MW - power_within_WL_MW) ==0) 
    
    
    m.Equation(Power_Gen_MW-(GT_C1_Power_MW + GT_C2_Power_MW + GT_C4_Power_MW + GT_C5_Power_MW + GT_R5_Power_MW + GT_R6_Power_MW
                           + STG_C3_Power_MW + STG_R2_Power_MW + STG_R3_Power_MW + STG_R4_Power_MW)==0)
    
    m.Equation((((((GT_C1_NG_Flow_SCFH + GT_C2_NG_Flow_SCFH + GT_C4_NG_Flow_SCFH + GT_C5_NG_Flow_SCFH + FHRSG_C1_NG_SCFH + FHRSG_C2_NG_SCFH)*24/10**6)+
                  ((GT_R5_NG_Flow_KPPH + GT_R6_NG_Flow_KPPH )*1000*24/(input_df['DP_OPT_NG_SPECIFIC_GRAVITY_PERCENT'].values[0]*0.0806)/10**6))* 
                 input_df['DP_OPT_NG_HV_BTU_CF'].values[0]*(input_df['DP_OPT_HENRY_HUB_NG_PRICE_DOLLARPMMBTU'].values[0])/24))-(total_fuel_within_PH_dollar)==0)
    
    m.Equation(((HRSG_R5_Steam_Gen_1900_KLBH)+(HRSG_R6_Steam_Gen_1900_KLBH)-(STG_R4_Steam_Cons_1900_KLBH) -(Letdown_1900_TO_600_KLBH))-(input_df['DP_OPT_C_1900HEADER_IMBALANCE_KLBH'].values[0])==0)
    
    m.Equation(((BLR_C1_Steam_Gen_1250_LBH)+(BLR_C2_Steam_Gen_1250_LBH)+(HRSG_C4_Steam_Gen_1250_LBH)+(HRSG_C5_Steam_Gen_1250_LBH)-(STG_C3_Steam_Cons_1250_LBH)-(Letdown_1250_TO_400_LBH)-(input_df['DP_OPT_STM_EXPORT_LACC_1250_600_LBH'].values[0]))-(input_df['DP_OPT_C_1250HEADER_IMBALANCE_LBH'].values[0])==0)
    
    m.Equation(((STG_R4_Steam_Gen_600_KLBH)+(Letdown_1900_TO_600_KLBH)-(STG_R3_Steam_Cons_600_KLBH)-(STG_R2_Steam_Cons_600_KLBH)-input_df['DP_OPT_STM_RSC_GEN_R4_IP_EXHST_KLBH'].values[0]-(input_df['DP_OPT_600STM_CONS_TO_PROCESS_400_KLBH'].values[0]))-(input_df['DP_OPT_C_600HEADER_IMBALANCE_LBH'].values[0])==0)
    
    m.Equation((STG_C3_Steam_Gen_400_LBH)+(Letdown_1250_TO_400_LBH)+(input_df['DP_OPT_600STM_CONS_TO_PROCESS_400_KLBH'].values[0]*1000)-(input_df['DP_OPT_C_400_Steam_Flow_LBH'].values[0])-(Letdown_From_400_TO_175_LBH)-(input_df['DP_OPT_C_400HEADER_IMBALANCE_LBH'].values[0])==0)
       
    m.Equation((Letdown_From_400_TO_175_LBH)+input_df['DP_OPT_STM_PHC_CONS_PRDS_400_175_LBH'].values[0]+input_df['DP_OPT_175_EXT_STMOL_FLOW_PHC_C3_STG_LBH'].values[0]+(input_df['DP_OPT_175STM_PHC_GEN_C4_HRSG_LBH'].values[0])+(input_df['DP_OPT_175STM_PHC_GEN_C5_HRSG_LBH'].values[0])-(input_df['DP_OPT_175STM_PHC_CONS_15_TO_PRCS_LBH'].values[0])-(Letdown_From_175_TO_30_LBH)-(input_df['DP_OPT_175STM_PHC_CONS_PRV3_5_LBH'].values[0])-(input_df['DP_OPT_C_175HEADER_IMBALANCE_LBH'].values[0])==0)
    # m.Equation((Letdown_From_400_TO_175_LBH)+(-input_df['DP_OPT_STM_PHC_CONS_PRDS_400_175_LBH'].values[0]*0+109013)+input_df['DP_OPT_175_EXT_STMOL_FLOW_PHC_C3_STG_LBH'].values[0]+(input_df['DP_OPT_175STM_PHC_GEN_C4_HRSG_LBH'].values[0])+(input_df['DP_OPT_175STM_PHC_GEN_C5_HRSG_LBH'].values[0])-(input_df['DP_OPT_175STM_PHC_CONS_15_TO_PRCS_LBH'].values[0])-(Letdown_From_175_TO_30_LBH)-(input_df['DP_OPT_175STM_PHC_CONS_PRV1_5_LBH'].values[0])-(input_df['DP_OPT_175STM_PHC_CONS_PRV2_5_LBH'].values[0])-(input_df['DP_OPT_175STM_PHC_CONS_PRV3_5_LBH'].values[0])-(input_df['DP_OPT_C_175HEADER_IMBALANCE_LBH'].values[0])==0)

    
    m.Equation((Letdown_From_175_TO_30_LBH)+input_df['DP_OPT_STM_PHC_CONS_PRDS_175_30_LBH'].values[0]+(input_df['DP_OPT_STM_LP_PHC_GEN_C4_HRSG_LBH'].values[0])+(input_df['DP_OPT_STM_LP_PHC_GEN_C5_HRSG_LBH'].values[0])-(input_df['DP_OPT_C_30_Steam_Flow_LBH'].values[0])-(input_df['DP_OPT_C_30_Steam_Flow_INSIDEPWH_LBH'].values[0])-(STEAM_VENTING_LBH)-(input_df['DP_OPT_C_30HEADER_IMBALANCE_LBH'].values[0])==0)
    # m.Equation((Letdown_From_175_TO_30_LBH)-(input_df['DP_OPT_C_30_Steam_Flow_LBH'].values[0])-(STEAM_VENTING_LBH)==0)
        
    
    m.Equation(STG_C3_Steam_Cons_1250_LBH -(STG_C3_Steam_Gen_400_LBH + input_df['DP_OPT_175_EXT_STMOL_FLOW_PHC_C3_STG_LBH'].values[0])==0)

    # m.Equation(STG_R4_Steam_Cons_1900_KLBH -( STG_R4_Steam_Gen_600_KLBH + input_df['DP_OPT_STM_RSC_GEN_R4_IP_EXHST_KLBH'].values[0])==0)

    user_opt_status = pd.read_csv("config/user_opt_status.csv")
    user_opt_status=user_opt_status.set_index('Equipment_list')
    
    
    if user_opt_status.loc['GT C1','user_status'] == 0:
        m.Equation(GT_C1_Power_MW - GT_C1_Run_Status*input_df['DP_OPT_PWR_PHC_GEN_C1_GT_MW'].values[0] ==0) #dont optimize = 1, Optimze = 0
        
        m.Equation(GT_C1_NG_Flow_SCFH - GT_C1_Run_Status*input_df['DP_OPT_NG_PHC_CONS_C1_GT_SCFH'].values[0]==0)
        
    else:
        if GT_C1_Run_Status ==1:
            
            m.Equation((-450.1942*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]+
                        6477.2059*GT_C1_Power_MW+
                        323.0912*input_df['DP_OPT_AIROUT_TEMP_PHC_C1_GT_F'].values[0]-
                        191.4344*input_df['DP_OPT_AMB_TEMP_F'].values[0]+
                        22.1903*input_df['DP_OPT_RELATIVE_HUMIDITY_PCNT'].values[0]+
                        88.8635*input_df['DP_OPT_EXHST_TEMP_PHC_C1_GT_F'].values[0]+
                        518927.9092)-(GT_C1_NG_Flow_SCFH)==0)
        else:
            m.Equation(GT_C1_Power_MW ==0) #dont optimize = 1, Optimze = 0
            
            m.Equation(GT_C1_NG_Flow_SCFH ==0)
            
            
    
        # m.Equation(GT_C1_Power_MW - GT_C1_Run_Status*GT_C1_Power_Leq_MW ==0) #dont optimize = 1, Optimze = 0
        
        # m.Equation(GT_C1_NG_Flow_SCFH - GT_C1_Run_Status*GT_C1_NG_Flow_Leq_SCFH==0)
        
        
    if user_opt_status.loc['GT C2','user_status'] == 0:
        m.Equation(GT_C2_Power_MW - GT_C2_Run_Status*input_df['DP_OPT_PWR_PHC_GEN_C2_GT_MW'].values[0] ==0) #dont optimize = 1, Optimze = 0
        
        m.Equation(GT_C2_NG_Flow_SCFH - GT_C2_Run_Status*input_df['DP_OPT_NG_PHC_CONS_C2_GT_SCFH'].values[0]==0)
    
    else:
        if GT_C2_Run_Status == 1:
    #GT C2 Linear Equation  
            m.Equation((-890.572*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]+
                    5961.768*GT_C2_Power_MW+
                    376.4747*input_df['DP_OPT_EXHST_TEMP_PHC_C2_GT_F'].values[0]+
                    920817.2)-(GT_C2_NG_Flow_SCFH)==0)
            
        else:
            m.Equation(GT_C2_Power_MW ==0) #dont optimize = 1, Optimze = 0
           
            m.Equation(GT_C2_NG_Flow_SCFH ==0)
            
        
            # m.Equation(GT_C2_Power_MW - GT_C2_Run_Status*GT_C2_Power_Leq_MW ==0) #dont optimize = 1, Optimze = 0
            
            # m.Equation(GT_C2_NG_Flow_SCFH - GT_C2_Run_Status*GT_C2_NG_Flow_Leq_SCFH==0)
        
    
    if user_opt_status.loc['GT C4','user_status'] == 0:
        
        m.Equation(GT_C4_Power_MW - GT_C4_Run_Status*input_df['DP_OPT_PWR_PHC_GEN_C4_GT_MW'].values[0] ==0) #dont optimize = 1, Optimze = 0
        
        m.Equation(GT_C4_NG_Flow_SCFH - GT_C4_Run_Status*input_df['DP_OPT_NG_PHC_CONS_C4_GT_SCFH'].values[0]==0) #dont optimize = 1, Optimze = 0
    
        m.Equation(HRSG_C4_Steam_Gen_1250_LBH - GT_C4_Run_Status*input_df['DP_OPT_HPSTMOL_FLOW_PHC_C4_HRSG_LBH'].values[0]==0)
    
    
    else:
        
        if GT_C4_Run_Status == 1:
            m.Equation((0.4895*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]+
                        8992.355*GT_C4_Power_MW +
                        225014.6)-(GT_C4_NG_Flow_SCFH)==0)
            
            # m.Equation(GT_C4_Power_MW - GT_C4_Run_Status*GT_C4_Power_Leq_MW ==0) #dont optimize = 1, Optimze = 0
            
            # m.Equation(GT_C4_NG_Flow_SCFH - GT_C4_Run_Status*GT_C4_NG_Flow_Leq_SCFH==0) #dont optimize = 1, Optimze = 0
              
            #HRSG C4 Linear Equation 
            m.Equation((-0.0707*GT_C4_NG_Flow_SCFH+
                        372.021*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]+
                        2074.494*GT_C4_Power_MW +
                        231.4401*input_df['DP_OPT_AMB_TEMP1_F'].values[0]+
                        97.0417*input_df['DP_OPT_DISC_TEMP_PHC_C4_GT_F'].values[0]-
                        321.842*input_df['DP_OPT_AMB_TEMP_F'].values[0]+
                        6.6348*input_df['DP_OPT_RELATIVE_HUMIDITY_PCNT'].values[0]+
                        199.1414*input_df['DP_OPT_DAMPOL_TEMP_PHC_C4_GT_F'].values[0]+
                        415.2927*input_df['DP_OPT_1250_STMOL_ENTHALPY_PHC_C4_HRSG_BTULB'].values[0]+
                        0.7661*input_df['DP_OPT_IPSTMOL_FLOW_PHC_C4_HRSG_LBH'].values[0]-
                        207.162*input_df['DP_OPT_LPBFW_OPENING_PHC_C4_HRSG_PRCNT'].values[0]-
                        1138247)-(HRSG_C4_Steam_Gen_1250_LBH)==0)
            
            # m.Equation(HRSG_C4_Steam_Gen_1250_LBH - GT_C4_Run_Status*HRSG_C4_Steam_Gen_1250_Leq_LBH==0)
        
        else:
            m.Equation(GT_C4_Power_MW ==0) #dont optimize = 1, Optimze = 0
            
            m.Equation(GT_C4_NG_Flow_SCFH ==0) #dont optimize = 1, Optimze = 0
            
            m.Equation(HRSG_C4_Steam_Gen_1250_LBH ==0)
        
        
    if user_opt_status.loc['GT C5','user_status'] == 0:
        
        m.Equation(GT_C5_Power_MW - GT_C5_Run_Status*input_df['DP_OPT_PWR_PHC_GEN_C5_GT_MW'].values[0]==0) #dont optimize = 1, Optimze = 0
        
        m.Equation(GT_C5_NG_Flow_SCFH - GT_C5_Run_Status*input_df['DP_OPT_NG_FLOW_PHC_C5_GT_SCFH'].values[0]==0) #dont optimize = 1, Optimze = 0
    
        m.Equation(HRSG_C5_Steam_Gen_1250_LBH - GT_C5_Run_Status*input_df['DP_OPT_HPSTMOL_FLOW_PHC_C5_HRSG_LBH'].values[0]==0)
    else:
        
        if GT_C5_Run_Status ==1 :
            
            m.Equation((173.2113*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]+
                        10119.22*GT_C5_Power_MW +
                        7673.417)-(GT_C5_NG_Flow_SCFH)==0)
            
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
            
            # m.Equation(GT_C5_Power_MW - GT_C5_Run_Status*GT_C5_Power_Leq_MW ==0) #dont optimize = 1, Optimze = 0
            
            # m.Equation(GT_C5_NG_Flow_SCFH - GT_C5_Run_Status*GT_C5_NG_Flow_Leq_SCFH==0) #dont optimize = 1, Optimze = 0
            
            # m.Equation(HRSG_C5_Steam_Gen_1250_LBH - GT_C5_Run_Status*HRSG_C5_Steam_Gen_1250_Leq_LBH==0)
        
            
        else:
            m.Equation(GT_C5_Power_MW  ==0) #dont optimize = 1, Optimze = 0
            
            m.Equation(GT_C5_NG_Flow_SCFH ==0) #dont optimize = 1, Optimze = 0
            
            m.Equation(HRSG_C5_Steam_Gen_1250_LBH ==0)
        
    
    if user_opt_status.loc['GT R5','user_status'] == 0: 
        
        m.Equation(GT_R5_Power_MW - GT_R5_Run_Status*input_df['DP_OPT_PWR_RSC_GEN_R5_STG_MW'] ==0) #dont optimize = 1, Optimze = 0
        
        m.Equation(GT_R5_NG_Flow_KPPH - GT_R5_Run_Status*input_df['DP_OPT_NG_RSC_CONS_TOTAL_R5_GT_KPPH']==0) #dont optimize = 1, Optimze = 0
    
        m.Equation(HRSG_R5_Steam_Gen_1900_KLBH - GT_R5_Run_Status*input_df['DP_OPT_HPSTMOL_FLOW_RSC_R5_HRSG_KPPH']==0)
       
    else:  
        
        if GT_R5_Run_Status == 1 :
        #GT R5 Linear Equation 
            m.Equation((-0.0595*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]+
                        0.3713*GT_R5_Power_MW +
                        78.1426)-(GT_R5_NG_Flow_KPPH)==0)
            
            #HRSG  R5 Linear Equation 
            m.Equation((-1.0639*GT_R5_NG_Flow_KPPH+
                        2.2142*GT_R5_Power_MW+
                        0.4056*input_df['DP_OPT_AIRIN_TEMP_RSC_R5_GT_F'].values[0]+
                        0.0492*input_df['DP_OPT_AMB_TEMP_F'].values[0]+
                        0.026*input_df['DP_OPT_RELATIVE_HUMIDITY_PCNT'].values[0]+
                        0.5403*input_df['DP_OPT_EXHST_TEMP_RSC_R5_GT_F'].values[0]-
                        0.0571*input_df['DP_OPT_STM_LP_RSC_GEN_R5_HRSG_LBH'].values[0]+
                        0.0000179*input_df['DP_OPT_LPSTMOL_ENTHALPY_RSC_R5_HRSG_BTULB'].values[0]-
                        473.331)-(HRSG_R5_Steam_Gen_1900_KLBH)==0)
            
            # m.Equation(GT_R5_Power_MW - GT_R5_Run_Status*GT_R5_Power_Leq_MW ==0) #dont optimize = 1, Optimze = 0
            
            # m.Equation(GT_R5_NG_Flow_KPPH - GT_R5_Run_Status*GT_R5_NG_Flow_Leq_KPPH==0) #dont optimize = 1, Optimze = 0
             
            
            # m.Equation(HRSG_R5_Steam_Gen_1900_KLBH - GT_R5_Run_Status*HRSG_R5_Steam_Gen_1900_Leq_KLBH==0)
        
        else:
            m.Equation(GT_R5_Power_MW ==0) #dont optimize = 1, Optimze = 0
            
            m.Equation(GT_R5_NG_Flow_KPPH ==0) #dont optimize = 1, Optimze = 0
                        
            m.Equation(HRSG_R5_Steam_Gen_1900_KLBH==0)
        
   
    if user_opt_status.loc['GT R6','user_status'] == 0: 
        m.Equation(GT_R6_Power_MW - GT_R6_Run_Status*input_df['DP_OPT_PWR_RSC_GEN_R6_STG_MW'].values[0] ==0) #dont optimize = 1, Optimze = 0
        
        m.Equation(GT_R6_NG_Flow_KPPH - GT_R6_Run_Status*input_df['DP_OPT_NG_RSC_CONS_TOTAL_R6_GT_KPPH'].values[0]==0)
        
        m.Equation(HRSG_R6_Steam_Gen_1900_KLBH - GT_R6_Run_Status*input_df['DP_OPT_HPSTMOL_FLOW_RSC_R6_HRSG_KPPH'].values[0]==0) #dont optimize = 1, Optimze = 0
        
    #GT R6 Linear Equation
    else:
        
        if GT_R6_Run_Status == 1:
       
            m.Equation((0.37*GT_R6_Power_MW +
                    16.5316)-(GT_R6_NG_Flow_KPPH)==0)
             
            #HRSG R6 Linear Equation 
            m.Equation((0.2494*GT_R6_NG_Flow_KPPH+
                        0.0557*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]+
                        0.9041*GT_R6_Power_MW+
                        0.488*input_df['DP_OPT_AIRIN_TEMP_RSC_R6_GT_F'].values[0]-
                        0.3013*input_df['DP_OPT_DISC_TEMP_RSC_R6_GT_F'].values[0]+
                        0.1039*input_df['DP_OPT_AMB_TEMP_F'].values[0]+
                        0.0006*input_df['DP_OPT_RELATIVE_HUMIDITY_PCNT'].values[0]+
                        0.404*input_df['DP_OPT_EXHST_TEMP_RSC_R6_GT_F'].values[0]+
                        0.6315*input_df['DP_OPT_HPBFWIN_ENTHALPY_RSC_R6_HRSG_BTULB'].values[0]-
                        0.0468*input_df['DP_OPT_HPSTMOL_ENTHALPY_RSC_R6_HRSG_BTULB'].values[0]-
                        0.3474*input_df['DP_OPT_STM_LP_RSC_GEN_R6_HRSG_LBH'].values[0]+
                        0.2126*input_df['DP_OPT_LPSTMOL_ENTHALPY_RSC_R6_HRSG_BTULB'].values[0]+
                        0.6025*input_df['DP_OPT_COND_FLOW_RSC_R6_HRSG_KPPH'].values[0]+
                        0.334*input_df['DP_OPT_ECONOMISER_FC_IN_TEMP_R6_HRSG_F'].values[0]-
                        0.2739*input_df['DP_OPT_ECONOMIZER_FC_OUT_TEMP_R5_HRSG_F'].values[0]-
                        724.563)-(HRSG_R6_Steam_Gen_1900_KLBH)==0)
            
            # m.Equation(GT_R6_Power_MW - GT_R6_Run_Status*GT_R6_Power_Leq_MW ==0) #dont optimize = 1, Optimze = 0
        
            # m.Equation(GT_R6_NG_Flow_KPPH - GT_R6_Run_Status*GT_R6_NG_Flow_Leq_KPPH ==0 ) #dont optimize = 1, Optimze = 0
        
            
            # m.Equation(HRSG_R6_Steam_Gen_1900_KLBH - GT_R6_Run_Status*HRSG_R6_Steam_Gen_1900_Leq_KLBH==0)
            
        else:
            
            m.Equation(GT_R6_Power_MW ==0) #dont optimize = 1, Optimze = 0
        
            m.Equation(GT_R6_NG_Flow_KPPH  ==0 ) #dont optimize = 1, Optimze = 0
                 
            m.Equation(HRSG_R6_Steam_Gen_1900_KLBH ==0)
#________________________________________________________________________________________________________________________________________________     
    
    if input_df['DP_OPT_MODE_GT_Boiler_C1'].values[0] ==1:
        
        if user_opt_status.loc['GT BLR C1','user_status'] == 0: 
            
            m.Equation(FHRSG_C1_NG_SCFH - input_df['DP_OPT_MODE_GT_Boiler_C1'].values[0]*GT_C1_Run_Status*Boiler_C1_Run_Status*input_df['DP_OPT_NG_FLOW_PHC_C1_HRSG_SCFH'].values[0]==0)
    
            m.Equation(BLR_C1_Steam_Gen_1250_LBH-input_df['DP_OPT_MODE_GT_Boiler_C1'].values[0]*Boiler_C1_Run_Status*input_df['DP_OPT_STMOL_FLOW_PHC_C1_HRSG_LBH'].values[0]==0)   
            
        else:    
            #GT Boiler NG C1 Linear Equation
            if Boiler_C1_Run_Status == 1 :
                m.Equation((-1.0123*GT_C1_NG_Flow_SCFH+
                            13.7159*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]+
                            4239.507*GT_C1_Power_MW+
                            183.1065*input_df['DP_OPT_AIROUT_TEMP_PHC_C1_GT_F'].values[0]-
                            172.75*input_df['DP_OPT_DISC_PRESS_PHC_C1_GT_PSIG'].values[0]+
                            158.9877*input_df['DP_OPT_RELATIVE_HUMIDITY_PCNT'].values[0]-
                            129.866*input_df['DP_OPT_EXHST_TEMP_PHC_C1_GT_F'].values[0]-
                            2388.32*input_df['DP_OPT_BFWIN_ENTHALPY_PHC_C1_HRSG_BTULB'].values[0]+
                            0.7813*BLR_C1_Steam_Gen_1250_LBH +
                            381.9226*input_df['DP_OPT_1250_STMOL_ENTHALPY_PHC_C1_HRSG_BTULB'].values[0]-
                            15864.7*input_df['DP_OPT_H2NG_RATIO_PHC_C1_HRSG'].values[0]+
                            365915.2)-(FHRSG_C1_NG_SCFH)==0)
                
                # m.Equation(FHRSG_C1_NG_SCFH - input_df['DP_OPT_MODE_GT_Boiler_C1'].values[0]*GT_C1_Run_Status*Boiler_C1_Run_Status*FHRSG_C1_NG_Leq_SCFH==0)
               
                # m.Equation(BLR_C1_Steam_Gen_1250_LBH-input_df['DP_OPT_MODE_GT_Boiler_C1'].values[0]*Boiler_C1_Run_Status*BLR_C1_Steam_Gen_1250_Leq_LBH==0)   
                               
            else:
                
                m.Equation(FHRSG_C1_NG_SCFH ==0)
               
                m.Equation(BLR_C1_Steam_Gen_1250_LBH==0)   
    
    else:
    
        if user_opt_status.loc['BLR C1','user_status'] == 0: 
        #Boiler NG C1 Linear Equation 
           
            m.Equation(FHRSG_C1_NG_SCFH - input_df['DP_OPT_MODE_BOILER_ONLY_C1'].values[0]*Boiler_C1_Run_Status*input_df['DP_OPT_NG_FLOW_PHC_C1_HRSG_SCFH'].values[0]==0)
        
            m.Equation(BLR_C1_Steam_Gen_1250_LBH-input_df['DP_OPT_MODE_BOILER_ONLY_C1'].values[0]*Boiler_C1_Run_Status*input_df['DP_OPT_STMOL_FLOW_PHC_C1_HRSG_LBH'].values[0]==0)   
        else :
            if Boiler_C1_Run_Status == 1:
                m.Equation((-0.0285*GT_C1_NG_Flow_SCFH+
                            938.0759*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]-
                            6323.44*GT_C1_Power_MW +
                            459.2144*input_df['DP_OPT_AMB_TEMP_F'].values[0]+
                            223.7203*input_df['DP_OPT_RELATIVE_HUMIDITY_PCNT'].values[0]-
                            3184.74*input_df['DP_OPT_BFWIN_ENTHALPY_PHC_C1_HRSG_BTULB'].values[0]+
                            1.206*BLR_C1_Steam_Gen_1250_LBH-
                            224.247*input_df['DP_OPT_1250_STMOL_ENTHALPY_PHC_C1_HRSG_BTULB'].values[0]-
                            11223.9*input_df['DP_OPT_H2NG_RATIO_PHC_C1_HRSG'].values[0]+
                            41274.74)-(FHRSG_C1_NG_SCFH)==0)
                
                # m.Equation(FHRSG_C1_NG_SCFH - input_df['DP_OPT_MODE_BOILER_ONLY_C1'].values[0]*Boiler_C1_Run_Status*FHRSG_C1_NG_Leq_SCFH==0)
                
                # m.Equation(BLR_C1_Steam_Gen_1250_LBH-input_df['DP_OPT_MODE_BOILER_ONLY_C1'].values[0]*Boiler_C1_Run_Status*BLR_C1_Steam_Gen_1250_Leq_LBH==0)   
    
                
            else:
                
                m.Equation(FHRSG_C1_NG_SCFH ==0)
                
                m.Equation(BLR_C1_Steam_Gen_1250_LBH==0)   
    
#_____________________________________________________________________________________________________________________________________________    
    if input_df['DP_OPT_MODE_GT_Boiler_C2'].values[0] == 1 :
    
        if user_opt_status.loc['GT BLR C2','user_status'] == 0: 
            m.Equation(FHRSG_C2_NG_SCFH - input_df['DP_OPT_MODE_GT_Boiler_C2'].values[0]*GT_C2_Run_Status*Boiler_C2_Run_Status*input_df['DP_OPT_NG_FLOW_PHC_C2_HRSG_SCFH'].values[0]==0)
            
            m.Equation(BLR_C2_Steam_Gen_1250_LBH-input_df['DP_OPT_MODE_GT_Boiler_C2'].values[0]*Boiler_C2_Run_Status*input_df['DP_OPT_STMOL_FLOW_PHC_C2_HRSG_LBH'].values[0]==0)   
            
        else :
            
            if Boiler_C2_Run_Status ==1 :
            
                #GT Boiler NG C2 Linear Equation   
                m.Equation((-0.6267*GT_C2_NG_Flow_SCFH-
                            523.106*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]+
                            2129.671*GT_C2_Power_MW+
                            155.7917*input_df['DP_OPT_AIRIN_TEMP_PHC_C2_GT_F'].values[0]-
                            721.318*input_df['DP_OPT_DISC_TEMP_PHC_C2_GT_F'].values[0]-
                            115.094*input_df['DP_OPT_RELATIVE_HUMIDITY_PCNT'].values[0]-
                            0.0563*input_df['DP_OPT_EXHST_TO_WBOX_C2_GT_LBH'].values[0]+
                            20.231*input_df['DP_OPT_WBOX_TEMP_PHC_C2_HRSG_F'].values[0]+
                            1.0986*BLR_C2_Steam_Gen_1250_LBH+
                            417.2921*input_df['DP_OPT_1250_STMOL_ENTHALPY_PHC_C2_HRSG_BTULB'].values[0]-
                            58991.3*input_df['DP_OPT_H2NG_RATIO_PHC_C2_HRSG'].values[0]+
                            537467.8)-(FHRSG_C2_NG_SCFH)==0)
                
                # m.Equation(FHRSG_C2_NG_SCFH - input_df['DP_OPT_MODE_GT_Boiler_C2'].values[0]*GT_C2_Run_Status*Boiler_C2_Run_Status*FHRSG_C2_NG_Leq_SCFH==0)
        
                # m.Equation(BLR_C2_Steam_Gen_1250_LBH-input_df['DP_OPT_MODE_GT_Boiler_C2'].values[0]*Boiler_C1_Run_Status*BLR_C2_Steam_Gen_1250_Leq_LBH==0)   
            
            else:
                
                m.Equation(FHRSG_C2_NG_SCFH ==0)
        
                m.Equation(BLR_C2_Steam_Gen_1250_LBH==0)   
    
    else:     
    
        if user_opt_status.loc['BLR C2','user_status'] == 0: 
     
            m.Equation(FHRSG_C2_NG_SCFH - input_df['DP_OPT_MODE_BOILER_ONLY_C2'].values[0]*Boiler_C2_Run_Status*input_df['DP_OPT_NG_FLOW_PHC_C2_HRSG_SCFH'].values[0]==0)
            
            m.Equation(BLR_C2_Steam_Gen_1250_LBH-input_df['DP_OPT_MODE_BOILER_ONLY_C2'].values[0]*Boiler_C2_Run_Status*input_df['DP_OPT_STMOL_FLOW_PHC_C2_HRSG_LBH'].values[0]==0)   
           
        else:
            
            if Boiler_C2_Run_Status == 1 :
            
                #Boiler NG C2 Linear Equation
                m.Equation((-0.0308*GT_C2_NG_Flow_SCFH+
                            212.0356*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]-
                            926.692*GT_C2_Power_MW-
                            1132.24*input_df['DP_OPT_AMB_TEMP_F'].values[0]-
                            281.838*input_df['DP_OPT_RELATIVE_HUMIDITY_PCNT'].values[0]-
                            2.8852*input_df['DP_OPT_BFW_FLOW_PHC_C2_HRSG_LBH'].values[0]-
                            709.001*input_df['DP_OPT_BFW_TEMP_PHC_C1_HRSG_F'].values[0]+
                            3.3994*BLR_C2_Steam_Gen_1250_LBH +
                            1199.433*input_df['DP_OPT_1250_STMOL_ENTHALPY_PHC_C2_HRSG_BTULB'].values[0]-
                            60064.8*input_df['DP_OPT_H2NG_RATIO_PHC_C2_HRSG'].values[0]-
                            1537375)-(FHRSG_C2_NG_SCFH)==0)
                
                # m.Equation(FHRSG_C2_NG_SCFH - input_df['DP_OPT_MODE_BOILER_ONLY_C2'].values[0]*Boiler_C2_Run_Status*FHRSG_C2_NG_Leq_SCFH==0)
        
                # m.Equation(BLR_C2_Steam_Gen_1250_LBH-input_df['DP_OPT_MODE_BOILER_ONLY_C2'].values[0]*Boiler_C2_Run_Status*BLR_C2_Steam_Gen_1250_Leq_LBH==0)   
                
            else:
                
                m.Equation(FHRSG_C2_NG_SCFH ==0)
        
                m.Equation(BLR_C2_Steam_Gen_1250_LBH==0)   

#_____________________________________________________________________________________________________________________________________________    
    
    if user_opt_status.loc['STG C3','user_status'] == 0: 
            
            m.Equation(STG_C3_Steam_Cons_1250_LBH - STG_C3_Run_Status*input_df['DP_OPT_1250STM_PHC_CONS_C3_STG_LBH'].values[0] == 0)
            
            m.Equation(STG_C3_Power_MW - STG_C3_Run_Status*input_df['DP_OPT_PWR_PHC_GEN_C3_STG_MW'].values[0] == 0)
         
        #STG C3 Linear Equation
    else :
        
        if STG_C3_Run_Status == 1:
            
            m.Equation((-2713*input_df['DP_OPT_1250_STMIL_ENTHALPY_PHC_C3_STG_BTULB'].values[0]+
                        277*input_df['DP_OPT_400_STMOL_ENTHALPY_PHC_C3_STG_BTULB'].values[0]-
                        0.6186*input_df['DP_OPT_175_STMOL_FLOW_PHC_C3_STG_LBH'].values[0]+
                        1239*input_df['DP_OPT_175_STMOL_ENTHALPY_PHC_C3_STG_BTULB'].values[0]+
                        25554*STG_C3_Power_MW+
                        2405199)-(STG_C3_Steam_Cons_1250_LBH)==0)
            
            # m.Equation(STG_C3_Steam_Cons_1250_LBH - STG_C3_Run_Status*STG_C3_Steam_Cons_1250_Leq_LBH == 0)
            
            # m.Equation(STG_C3_Power_MW - STG_C3_Run_Status*STG_C3_Power_Leq_MW == 0)
            
        else:
            
            m.Equation(STG_C3_Steam_Cons_1250_LBH == 0)
            
            m.Equation(STG_C3_Power_MW == 0)
    
#_____________________________________________________________________________________________________________________________________________    
     
    #STG R4 Linear Equation 
    
    if user_opt_status.loc['STG R4','user_status'] == 0:
        
        m.Equation(STG_R4_Power_MW - STG_R4_Run_Status*input_df['DP_OPT_PWR_RSC_GEN_R4_STG_MW'].values[0] == 0)
        
        m.Equation(STG_R4_Steam_Cons_1900_KLBH - STG_R4_Run_Status*input_df['DP_OPT_STM_RSC_GEN_R4_TOT_EXHST_KLBH'].values[0] == 0)
    
    else:
        
        if STG_R4_Run_Status ==1 :
    
            m.Equation((2.5623*input_df['DP_OPT_1900_STMIL_ENTHALPY_RSC_R4_STG_BTULB'].values[0]-
                        5.1787*input_df['DP_OPT_600_STMOL_ENTHALPY_RSC_R4_STG_BTULB'].values[0]+
                        0.3837*input_df['DP_OPT_STM_RSC_GEN_R4_IP_EXHST_KLBH'].values[0]-
                        0.5523*input_df['DP_OPT_35_STMOL_ENTHALPY_RSC_R4_STG_BTULB'].values[0]+
                        11.2399*STG_R4_Power_MW+
                        4085.923)-(STG_R4_Steam_Cons_1900_KLBH)==0)
            
            
            # m.Equation(STG_R4_Power_MW - STG_R4_Run_Status*STG_R4_Power_Leq_MW == 0)
            
            # m.Equation(STG_R4_Steam_Cons_1900_KLBH - STG_R4_Run_Status*STG_R4_Steam_Cons_1900_Leq_KLBH == 0)

        else:
            
            m.Equation(STG_R4_Power_MW  == 0)
            
            m.Equation(STG_R4_Steam_Cons_1900_KLBH == 0)

#_____________________________________________________________________________________________________________________________________________    

    if user_opt_status.loc['STG R2','user_status'] == 0:
        
        m.Equation(STG_R2_Power_MW - STG_R2_Run_Status*input_df['DP_OPT_PWR_RS_GEN_R2_STG_MW'].values[0] == 0)
        
        m.Equation(STG_R2_Steam_Cons_600_KLBH - STG_R2_Run_Status*input_df['DP_OPT_600STM_RS_CONS_R2_STG_KLBH'].values[0] == 0)
    
    #STG R2 Linear Equation 
        
    else :
        
        if STG_R2_Run_Status == 1 :
        
            m.Equation((9.3494*STG_R2_Power_MW +
                        32.6533)-(STG_R2_Steam_Cons_600_KLBH)==0)
            
            # m.Equation(STG_R2_Power_MW - STG_R2_Run_Status*STG_R2_Power_Leq_MW == 0)
            
            # m.Equation(STG_R2_Steam_Cons_600_KLBH - STG_R2_Run_Status*STG_R2_Steam_Cons_600_Leq_KLBH == 0)
 
        else :
            
            m.Equation(STG_R2_Power_MW == 0)
            
            m.Equation(STG_R2_Steam_Cons_600_KLBH== 0)
 
 
    
 #_____________________________________________________________________________________________________________________________________________    

    #STG R3 Linear Equation 
    if user_opt_status.loc['STG R3','user_status'] == 0:
        
        m.Equation(STG_R3_Power_MW - STG_R3_Run_Status*input_df['DP_OPT_PWR_RS_GEN_R3_STG_MW'].values[0] == 0)
        
        m.Equation(STG_R3_Steam_Cons_600_KLBH - STG_R3_Run_Status*input_df['DP_OPT_600STM_RS_CONS_R3_STG_KLBH'].values[0] == 0)
    
    else :
        
        if STG_R3_Run_Status == 1 :
            
            m.Equation((0.6642*input_df['DP_OPT_CONDOL_TEMP_RS_R3_STG_F'].values[0]+
                        8.7286*STG_R3_Power_MW-41.748)-(STG_R3_Steam_Cons_600_KLBH)==0)
            
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
        m.solve(disp=True) # solve
        
        print("Solution Found Successfully")
        
        opt_val =[]
        print(DC_var_bounds)
        for v in DC_var_bounds:
            # print(f"Optimized {v} is {globals()[v][0]}")
            opt_val.append(globals()[v][0])
        
        op_dict={}
        op_dict['timestamp']=[time_upto]*no_of_output_tags
        op_dict['tag']=tag_id
        op_dict['value']= opt_val
        op_df=pd.DataFrame(op_dict)
        
        reco_df = pd.read_csv('config/recommendation_tags.csv')
        
        for i,row in reco_df.iterrows() :
            
            if globals()[row['opt_1']][0]  > input_df[row['alias_1']].values[0] :
                
                x= globals()[row['opt_1']][0]
                print('hello')
            
                message = f"optimized value for {row['Equipment']} {row['comment']} i.e {row['tag_1']} is {x} {row['uom_1']} greater than actual value {input_df[row['alias_1']].values[0]} {row['uom_1']}"
                        
                recommendation_dict = [{'timestamp':time_upto,'recommendation':message}]
                recommendation_df = pd.DataFrame(recommendation_dict)
                recommendation_df.to_sql(recommendation_table, con=db_connection_2, if_exists='append', index=False)
                
            else:
                
                x= globals()[row['opt_1']][0]
                print('hello qqq')
            
                message = f"optimized value for {row['Equipment']} {row['comment']} i.e {row['tag_1']} is {x} {row['uom_1']} less than actual value {input_df[row['alias_1']].values[0]} {row['uom_1']}"
                        
                recommendation_dict = [{'timestamp':time_upto,'recommendation':message}]
                recommendation_df = pd.DataFrame(recommendation_dict)
                recommendation_df.to_sql(recommendation_table, con=db_connection_2, if_exists='append', index=False)
                
                
               
    except:
        print('Not successful')
        print(traceback.format_exc())

        act_val=[]
        for i in actual_list:
            act_val.append(input_df[i].values[0])
        
        op_dict={}
        op_dict['timestamp']=[time_upto]*no_of_output_tags
        op_dict['tag']=tag_id
        op_dict['value']= act_val
        op_df=pd.DataFrame(op_dict)
    
    return op_df
    
    
    # m.open_folder()
    
   
    
#################################### QC FILE  CODE ####################################


    bounds_without_leq =pd.read_csv('config/DC_var_without_bounds.csv')
    DC_var_bounds = bounds_without_leq['variable'].tolist()
    
    all_opt_val =[]
    for v in DC_var_bounds:
        print(f"Optimized {v} is {globals()[v][0]}")
        all_opt_val.append(globals()[v][0])
        
    output_dict= {}
    
    output_dict['variable']=DC_var_bounds
    output_dict['min']= bounds_without_leq['min'].tolist()
    output_dict['max']= bounds_without_leq['max'].tolist()
    output_dict['opt_value']=all_opt_val
    output_df = pd.DataFrame(output_dict)
    
    curr_time = "{:%Y_%m_%d_%H_%M_%S}".format(datetime.now())
    output_df.to_csv(f"output/OPT_data_{curr_time}.csv")
    
    
    # bounds_without_leq['optimized_value']=''
    
    
    for i,row in bounds_without_leq.iterrows():
        row['optimized_value'] = globals()[row['variable']][0]
        print(row['variable'],row['optimized_value'])
        
# # #############################################################################################    
    
    comparison_scripts = pd.read_csv('config/actual_and_optimized_alias.csv')
    comparison_scripts['actual value'] =''
    comparison_scripts['optimized value'] =''
        
    for i,row in comparison_scripts.iterrows():
        row['actual value']= input_df[row['actual']].values[0]
        row['optimized value'] = globals()[row['optimized']][0]
        print(row['actual value'])
        
    comparison_scripts =comparison_scripts.drop(['actual'], axis=1)
    # del comparison_scripts
    
#     curr_time = "{:%Y_%m_%d_%H_%M_%S}".format(datetime.now())
#     comparison_scripts.to_csv(f"output/Actual_Vs_OPT_data_{curr_time}.csv")
        
    
        
#     # with pd.ExcelWriter(f"Actual_Vs_OPT_data_{curr_time}.xlsx") as writer:
#     #     comparison_scripts.to_excel(writer, sheet_name="Page 1")
    
    
        
#     DC_Var_list = comparison_scripts['optimized'].tolist()
#     # Actual_val_list = comparison_scripts['actual'].tolist()
# #____________________________________________________________________________________________________________________________________________________________________________________   
   
#     output_tags=pd.read_csv('config/output_alias_map.csv')
#     output_tags =output_tags.dropna()
#     tag_id=list(output_tags['tag_id'])
#     no_of_output_tags=len(list(output_tags['tag_id']))
    
#     opt_val =[]
#     for v in DC_Var_list:
#         print(f"Optimized {v} is {globals()[v][0]}")
#         opt_val.append(globals()[v][0])
    
#     op_dict={}
#     op_dict['timestamp']=[time_upto]*no_of_output_tags
#     op_dict['tag']=tag_id
#     op_dict['value']= opt_val
#     op_df=pd.DataFrame(op_dict)
    
#     m.open_folder()
    
    
    
    # try:
    #     m.solve(disp=True)    # solve
    # except:
    #     print('Not successful')
        # from gekko.apm import get_file
        # print(m._server)
        # print(m._model_name)
        # f = get_file(m._server,m._model_name,'infeasibilities.txt')
        # f = f.decode().replace('\r','')
        # with open('infeasibilities.txt', 'w') as fl:
        #     fl.write(str(f))  
            
            
        # -2647.5*input_df['DP_OPT_1250_STMIL_ENTHALPY_PHC_C3_STG_BTULB'].values[0]+135.44*input_df['DP_OPT_400_STMOL_ENTHALPY_PHC_C3_STG_BTULB'].values[0]-0.6117*input_df['DP_OPT_175_EXT_STMOL_FLOW_PHC_C3_STG_LBH'].values[0]+1321*input_df['DP_OPT_175_STMOL_ENTHALPY_PHC_C3_STG_BTULB'].values[0]+245449.7*28.85 +2395086    
        # -119231*input_df['DP_OPT_1250_STMIL_ENTHALPY_PHC_C3_STG_BTULB'].values[0]-156311*input_df['DP_OPT_400_STMOL_ENTHALPY_PHC_C3_STG_BTULB'].values[0]-2812*input_df['DP_OPT_175_EXT_STMOL_FLOW_PHC_C3_STG_LBH'].values[0]+264047*input_df['DP_OPT_175_STMOL_ENTHALPY_PHC_C3_STG_BTULB'].values[0]+326299*28.85 +975022
           
# 0.0277*910393.46+43.0545*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]+1394.7433*70.4+151.5*input_df['DP_OPT_AIRIN_TEMP_PHC_C5_GT_F'].values[0]-102.9065*input_df['DP_OPT_AMB_TEMP_F'].values[0]+0.0658*input_df['DP_OPT_RELATIVE_HUMIDITY_PCNT'].values[0]+283.4488*input_df['DP_OPT_DAMPER_OUT_TEMP_C5_GT_F'].values[0]+0.0225*input_df['DP_OPT_175STM_PHC_GEN_C5_HRSG_LBH'].values[0]+1.5712*input_df['DP_OPT_STM_LP_PHC_GEN_C5_HRSG_LBH'].values[0]+1459.7994*input_df['DP_OPT_LPSTMOL_ENTHALPY_PHC_C5_HRSG_BTULB'].values[0]-1967459.389

# 2.5623*input_df['DP_OPT_1900_STMIL_ENTHALPY_RSC_R4_STG_BTULB'].values[0]-5.1787*input_df['DP_OPT_600_STMOL_ENTHALPY_RSC_R4_STG_BTULB'].values[0]+0.3837*input_df['DP_OPT_STM_RSC_GEN_R4_IP_EXHST_KLBH'].values[0]-0.5523*input_df['DP_OPT_35_STMOL_ENTHALPY_RSC_R4_STG_BTULB'].values[0]+11.2399*42.21+4085.923

# -450.1942*input_df['DP_OPT_NG_HV_BTU_CF'].values[0]+6477.2059*55.0353+323.0912*input_df['DP_OPT_AIROUT_TEMP_PHC_C1_GT_F'].values[0]-191.4344*input_df['DP_OPT_AMB_TEMP_F'].values[0]+22.1903*input_df['DP_OPT_RELATIVE_HUMIDITY_PCNT'].values[0]+88.8635*input_df['DP_OPT_EXHST_TEMP_PHC_C1_GT_F'].values[0]+518927.9092

# from GEKKO.apm import apm_get

# server = 'http://127.168.8.5'
# app = 'my_app'  # Replace with your app name
# file_name = 'infeasibilities.txt'

# # Use apm_get to retrieve the infeasibilities file
# apm_get(server, app, file_name)