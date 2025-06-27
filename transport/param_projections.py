"""
This module contain data and functions for generating projections of different variables used in estimating hydrogen demand 
from the transport sector.
"""

def get_transport_parameters(year):
    """
    Returns a list of calculated assumptions for the given year, including relative efficiencies and fuel 
    economies, as well as changes in vehicle miles traveled (VMT). These outputs are used in the 
    transport_h2 module.
    """
    projections = [
        LD_FCEV_to_ICEV_efficiency(year),
        HD_FCEV_to_ICEV_efficiency(year),
        rel_change_LDV_mpg(year),
        rel_change_HDV_mpg(year),
        rel_change_LD_VMT(year),
        rel_change_HD_VMT(year)
    ]

    print(projections)

    return projections


def LD_FCEV_to_ICEV_efficiency(year):
    """
    This function returns the relative efficiency of LD FCEVs to ICEVs in a given input year and uses
    data from E3's Deep Decarbonization in a High Renewables Future paper 

    https://www.ethree.com/wp-content/uploads/2018/06/Deep_Decarbonization_in_a_High_Renewables_Future_CEC-500-2018-012-1.pdf

    Data is taken from the 'LDV costs and efficiencies' on Page B-7. To get the fuel efficiency in
    mpg or mpge of light duty ICEVs and FCEVs in 2020 and 2050, we took the average of the fuel 
    efficiency of the corresponding truck and auto in the chosen year, following the methodology used in 
    the CEC Roadmap for the Deployment and Buildout of Renewable Hydrogen Report. The relative 
    efficiencies in 2020 and 2050 are estimated, then linearly connected to model years in between.
    """

    LD_ICEV_mpg_2020 = (33 + 23) / 2
    LD_ICEV_mpg_2050 = (40 + 30) / 2

    LD_FCEV_mpge_2020 = (83 + 60) / 2
    LD_FCEV_mpge_2050 = (138 + 95) / 2

    rel_efficiency_2020 = LD_FCEV_mpge_2020 / LD_ICEV_mpg_2020
    rel_efficiency_2050 = LD_FCEV_mpge_2050 / LD_ICEV_mpg_2050

    lin_projection = lambda yr: (rel_efficiency_2050 - rel_efficiency_2020) / 30 * (yr - 2020) \
        + rel_efficiency_2020
    
    return lin_projection(year)



def HD_FCEV_to_ICEV_efficiency(year):
    """
    This function returns the relative efficiency of HD FCEVs to ICEVs in a given input year.

    A similar methodology is used in this function as the previous. Data from the 'HDV Costs and 
    Efficiencies' table on Page B-10 is directly taken to get the fuel efficiency of Reference HD 
    Diesel ICEVs and HDV FCEVs in 2020 and 2050, with no averaging needed. A line is again used
    to model relative efficiencies for years in between.
    """

    HD_ICEV_mpg_2020 = 7.6
    HD_ICEV_mpg_2050 = 7.7

    HD_FCEV_mpge_2020 = 8.5
    HD_FCEV_mpge_2050 = 11.2

    rel_efficiency_2020 = HD_FCEV_mpge_2020 / HD_ICEV_mpg_2020
    rel_efficiency_2050 = HD_FCEV_mpge_2050 / HD_ICEV_mpg_2050

    lin_projection = lambda yr: (rel_efficiency_2050 - rel_efficiency_2020) / 30 * (yr - 2020) \
        + rel_efficiency_2020
    
    return lin_projection(year)



def rel_change_LDV_mpg(year):
    """
    Returns the relative change in LDV mpg from 2023 to the input year (in decimal format).
    A line of best fit was fitted to data on the Average Fuel Efficiency of U.S. Light Duty 
    Vehicles from 2000 to 2023 and is used here to project LDV fuel efficiency for future years. 

    https://www.bts.gov/content/average-fuel-efficiency-us-light-duty-vehicles
    """
    MPG_2023 = 22.6

    projected_mpg = 0.1352 * (year - 2000) + 19.731

    return (projected_mpg - MPG_2023) / MPG_2023



def rel_change_HDV_mpg(year):
    """
    Returns the relative change in HDV mpg from 2023 to the input year (in decimal format).
    Data for Diesel HDV fuel efficiency is taken directly from Table 49 of the EIA Annual Energy Outlook 2025.
    The list contains the projected fuel efficiency for every year from 2023 to 2050, in order by index. The 
    AEO2023 Reference Case was used.

    https://www.eia.gov/outlooks/aeo/data/browser/#/?id=58-AEO2025&region=0-0&cases=aeo2023ref&start=2023&end=2050&f=A&linechart=aeo2023ref-d020623a.6-58-AEO2025~&map=&ctype=linechart&sourcekey=0

    """

    heavy_fuel_efficiency_by_year = [
    6.259011, 6.360165, 6.470843, 6.589664, 6.714928, 6.836287, 6.954601,
    7.068473, 7.178148, 7.282597, 7.3777, 7.462639, 7.53763, 7.603401,
    7.660309, 7.708639, 7.750559, 7.787107, 7.819769, 7.846699, 7.869397,
    7.88855, 7.905129, 7.92081, 7.935941, 7.950862, 7.966321, 7.982552]

    return (heavy_fuel_efficiency_by_year[year - 2023] - heavy_fuel_efficiency_by_year[0]) \
        / heavy_fuel_efficiency_by_year[0]



def rel_change_LD_VMT(year):
    """
    Returns the relative change in LD VMT from 2023 to the input year (in decimal format).
    Data for projected LD VMT from 2023 to 2050 was taken directly from Table 41 of the EIA Annual 
    Energy Outlook 2025. The AEO2023 Reference Case was used.
    """

    ld_vmt_by_year = [
        2540.002441, 2549.398193, 2547.35083, 2552.27832, 2560.690674,
        2564.727295, 2560.838867, 2550.160156, 2538.888184, 2524.38623,
        2513.166504, 2504.722168, 2494.232422, 2480.870605, 2469.888672,
        2461.147461, 2452.884766, 2447.28125, 2444.361572, 2443.996338,
        2444.437988, 2447.431152, 2453.515381, 2463.175537, 2475.763184,
        2489.99292, 2505.494385, 2524.001465
    ]

    return (ld_vmt_by_year[year - 2023] - ld_vmt_by_year[0]) / ld_vmt_by_year[0]



def rel_change_HD_VMT(year):
    """
    Returns the relative change in HD VMT from 2023 to the input year (in decimal format).
    Data for projected HD VMT from 2023 to 2050 was taken directly from Table 49 of the EIA Annual 
    Energy Outlook 2025. The AEO2023 Reference Case was used.
    """

    hd_vmt_by_year = [
        186.77066, 187.000778, 188.452835, 190.68486, 192.556381, 194.116348,
        194.965881, 195.397522, 195.893646, 196.827133, 197.409042, 197.923721,
        198.56163, 198.940033, 199.573639, 200.202545, 200.718475, 201.372726,
        202.111191, 202.838333, 203.409256, 203.777603, 203.913666, 204.187134,
        204.440094, 204.417526, 204.473785, 205.137848
    ]

    return (hd_vmt_by_year[year - 2023] - hd_vmt_by_year[0]) / hd_vmt_by_year[0]


