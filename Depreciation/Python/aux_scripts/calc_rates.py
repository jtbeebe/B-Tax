"""
Calculate Depreciation Rates (calc_rates):
-------------------------------------------------------------------------------
Last updated: 4/29/2016.

This module provides functions for calculating economic and tax depreciation
rates. All of the data is processed into NAICS trees by other modules, and
taken in as input of these functions. 
"""
# Packages:
import os.path
import numpy as np
import pandas as pd
import xlrd
import ipdb
# Directories:
_CUR_DIR = os.path.dirname(__file__)
_MAIN_DIR = os.path.dirname(_CUR_DIR)
_DATA_DIR = os.path.join(_MAIN_DIR, 'data')
_NAICS_CODE_PATH = os.path.abspath(_DATA_DIR + "//NAICS_Codes.csv")
_DEPR_DIR = os.path.join(_DATA_DIR, 'depreciation_rates')
# Importing custom modules:
import naics_processing as naics
import constants as cst
# Full file paths:
_ECON_DEPR_IN_PATH = os.path.join(_DEPR_DIR, "Economic Depreciation Rates.csv")
_TAX_DEPR_IN_PATH = os.path.join(_DEPR_DIR, "BEA_IRS_Crosswalk.csv")

def calc_depr_rates(asset_tree, inv_tree, land_tree):
    #opens the file containing depreciation rates by asset type:
    depr_econ = pd.read_csv(_ECON_DEPR_IN_PATH)
    depr_econ = depr_econ.fillna(0)
    #stores the economic depreciation rates in a 1xN matrix
    econ_rates = np.array(depr_econ['Economic Depreciation Rate'])
    #creates a dataframe that is returned at the end of the function with a list of all corp and non-corp industry averages
    econ_depr = pd.DataFrame(index = np.arange(0,2210), columns = ('NAICS', 'Corp', 'Non-Corp'))
    #retrieves the naics code
    naics_codes = pd.read_csv(_NAICS_CODE_PATH)
    #sets the first column of the dataframe with the naics values
    econ_depr['NAICS'] = naics_codes
    types = ['Corp', 'Non-Corp']
    #Runs for the corporate assets and for non-corporate assets
    for i in types:        
        depr_list = []
        #Iterates over every industry in the tree     
        for j in xrange(0, 2210):
            #retrieves the fixed asset values for each industry
            asset_row = np.array(asset_tree.enum_inds[j].data.dfs[i])[0]
            #calculates the depreciation for each asset in that industry
            depr_row = np.multiply(asset_row, econ_rates)
            #takes the weighted average of depreciation
            avg_depr = np.sum(depr_row) / np.sum(asset_row)
            #stores the weighted average in a list
            depr_list.append(avg_depr)
        #stores the depreciation rate list in the dataframe 
        econ_depr[i] = depr_list

    return econ_depr

def calc_tax_depr_rates(asset_tree, inv_tree, land_tree):
    #
    tax_data = pd.read_csv(_TAX_DEPR_IN_PATH).fillna(0)
    tax_assets = tax_data["Asset Type"]
    # Real Interest Rate:
    r = .05  
    #
    tax_mthds = {"GDS 200%": 2.0, "GDS 150%": 1.5, "GDS SL": 1.0, "ADS SL": 1.0}
    tax_cols = {'Asset','Tax_Depreciation_Rate'}
    tax_rates = pd.DataFrame(np.zeros((len(tax_assets),len(tax_cols))), columns = tax_cols)
    tax_rates['Asset'] = tax_assets

    # Compute the tax depreciation rates:
    for i in xrange(0, len(tax_assets)):
        tax_method = tax_data['Method'][i]
        tax_system = tax_data['System'][i]
        tax_life = tax_data[tax_system][i]
        tax_b = tax_mthds[tax_method]
        tax_beta = tax_b / tax_life
        if(tax_method == 'GDS 200%' or tax_method == 'GDS 150%'):
            tax_star = tax_life * (1 - (1/tax_b))
            tax_z = (((tax_beta/(tax_beta+r))* (1-np.exp(-1*(tax_beta+r)*tax_star))) 
                      + ((np.exp(-1*tax_beta*tax_star)/((tax_life-tax_star)*r))* (np.exp(-1*r*tax_star)-np.exp(-1*r*tax_life))))
            tax_rates.iloc[i,0] = r/((1/tax_z)-1)
        else:
            tax_z = ((1-np.exp(-1*r*tax_life)) / (r*tax_life))
            tax_rates.iloc[i,0] = (tax_z * r) / (1 + r - tax_z)
    #
    types = ["All", "Corp", "Non-Corp"]
    # Initialize tax depreciation rates tree:
    depr_tree = naics.generate_tree()
    depr_tree.append_all(df_nm="Tax", df_cols=types)
    #
    asset_list = asset_tree.enum_inds[0].data.dfs['Corp'].columns
    asset_list = asset_list.values.tolist() 
    for i in types:        
        #Iterates over every industry in the tree       
        for j in xrange(0, len(depr_tree.enum_inds)):
            asset_depreciation = 0
            total_depreciation = 0
            #grabs the assets for the industry
            asset_df = asset_tree.enum_inds[j].data.dfs[i]
            #Iterates over each asset in the industry
            for k in xrange(0, len(asset_list)):   
                #calculates the sum of all the depreciation in the industry, multiplying the amount of each asset by its corresponding depreciation rate
                asset_depreciation += (asset_df.iloc[0,k] * tax_rates['Tax_Depreciation_Rate'][k])
            
            #calculates the total capital stock in the industry
            tot_assets = sum(asset_tree.enum_inds[j].data.dfs[i].iloc[0,:])
            tot_inv = inv_tree.enum_inds[j].data.dfs["Inventories"][i][0]
            tot_land = land_tree.enum_inds[j].data.dfs["Land"][i][0]
            total_capital_stock = tot_assets + tot_inv + tot_land
            if(total_capital_stock != 0):
                #calculates the weighted average depreciation rate for assets only (can be changed to include inventories and land)
                depr_tree.enum_inds[j].data.dfs['Tax'][i].iloc[0] = asset_depreciation / tot_assets
            else:
                depr_tree.enum_inds[j].data.dfs['Tax'][i].iloc[0] = 0
                    
    return depr_tree
