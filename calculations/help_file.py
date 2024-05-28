# -*- coding: utf-8 -*-
"""
Created on Mon Oct 16 15:39:24 2023

@author: skanojia
"""
min_max= pd.read_csv('config/min_max_input_df.csv')
    
for i,row in min_max.iterrows():
    # print(input_df[row['DP_OPT  Tag']].values[0])
    
    if (input_df[row['DP_OPT  Tag']].values[0] < row['MIN'] or input_df[row['DP_OPT  Tag']].values[0] > row['MAX']):
        
        # print(input_df[row['DP_OPT  Tag']].values[0]  + "Before")
        
        print(f"{input_df[row['DP_OPT  Tag']].values[0]} ---After ")
        
        input_df[row['DP_OPT  Tag']].values[0]= -9999
        
        # print(input_df[row['DP_OPT  Tag']].values[0]  + "After")
        print(f"{input_df[row['DP_OPT  Tag']].values[0]} ---After ")
        
        
        
        
    else :
        print(row['DP_OPT  Tag']+'in Range')
        

    
     
  
     
