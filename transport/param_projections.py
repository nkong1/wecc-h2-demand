"""
This module contains data and functions for generating projections of different variables used in estimating hydrogen demand 
from the transport sector. It also contains some assumptions, stored here to keep data derived from online resources in one place.
"""


"""
The following are estimated values for the ratio of diesel and gaosline use that are from on-road transport  
the transport sector totals in 2023. They are derived from the AE02025 Reference Case Tables 39 and 36. 
The ratios were derived for 2024 and are assumed to be the same for 2023, given a lack of 2023 data.
"""
DIESEL_FROM_ONROAD_TRANSPORT = .8658
GASOLINE_FROM_ONROAD_TRANSPORT = .9899 

def get_transport_parameters(year):
    """
    Returns a list of calculated assumptions for the given year, including relative efficiencies and fuel 
    economies, as well as changes in vehicle miles traveled (VMT). These assumptions are used in the 
    transport_h2 module.
    """
    projections = [
        LD_FCEV_to_ICEV_efficiency(year),
        HD_FCEV_to_ICEV_efficiency(year),
        rel_change_LD_fuel_consumption(year), 
        rel_change_HD_fuel_consumption(year), 
        DIESEL_FROM_ONROAD_TRANSPORT, 
        GASOLINE_FROM_ONROAD_TRANSPORT
    ]
    return projections

def LD_FCEV_to_ICEV_efficiency(year):
    """
    Returns the relative efficiency of LD FCEVs to ICEVs in a given input year, using
    data derived from E3's Deep Decarbonization in a High Renewables Future paper.

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
    Returns the relative efficiency of HD FCEVs to ICEVs in a given input year.

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

def rel_change_LD_fuel_consumption(year):
    """
    Returns the relative change in gasoline fuel consumption from on-road transport from 2023 to the 
    input year. Refer to Gasoline_Use_EIA_Ref_Case.csv in the input file for more details and data
    derivation. Table 39 in the AEO2025 was used (Reference Case).
    """
    return [0, 0.044296462, 0.045407622, 0.03879188, 0.026124817, 0.009437798,
    -0.011174183, -0.036683746, -0.06214544, -0.092381316, -0.123083584,
    -0.152594123, -0.182237921, -0.213101243, -0.243269246, -0.270902176,
    -0.297043504, -0.320372834, -0.341785382, -0.362760544, -0.379842021,
    -0.396697179, -0.410141974, -0.423007724, -0.433134651, -0.444919444,
    -0.452629225, -0.458355589][year - 2023]

def rel_change_HD_fuel_consumption(year):
    """
    Returns the relative change in diesel fuel consumption from on-road transport from 2023 to the 
    input year. Refer to Diesel_Use_EIA_Ref_Case.csv in the input file for more details and data
    derivation. Table 36 in the AEO2025 was used (Reference Case).
    """
    return [0, 0.0682, 0.0726, 0.0682, 0.0586,
    0.0449, 0.0292, 0.0108, -0.0146, -0.0493,
    -0.0851, -0.1160, -0.1447, -0.1703, -0.1930,
    -0.2135, -0.2323, -0.2492, -0.2654, -0.2793,
    -0.2919, -0.3032, -0.3124, -0.3203, -0.3265,
    -0.3311, -0.3341, -0.3368][year - 2023]



"""
===========================================
The following methods are no longer currently used
===========================================
"""

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
    Reference Case was used.

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
    Energy Outlook 2025 (Reference Case).
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
    Energy Outlook 2025 (Reference Case).
    """

    hd_vmt_by_year = [
        186.77066, 187.000778, 188.452835, 190.68486, 192.556381, 194.116348,
        194.965881, 195.397522, 195.893646, 196.827133, 197.409042, 197.923721,
        198.56163, 198.940033, 199.573639, 200.202545, 200.718475, 201.372726,
        202.111191, 202.838333, 203.409256, 203.777603, 203.913666, 204.187134,
        204.440094, 204.417526, 204.473785, 205.137848
    ]

    return (hd_vmt_by_year[year - 2023] - hd_vmt_by_year[0]) / hd_vmt_by_year[0]


