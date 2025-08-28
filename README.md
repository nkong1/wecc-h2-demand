This model is designed to generate hydrogen demand profiles at a high spatial and temporal resolution as an input to the SWITCH-WECC capacity expansion platform (https://github.com/REAM-lab/switch)

Hydrogen demand is modeled for on-road transport and key hard-to-decarbonize industrial end-use sectors across 47 load zones, over the input model years. The transportation sector is broken down into light-duty and heavy-duty on-road transport, and the industrial sector is broken down into Iron & Steel, Aluminum, Cement, Refining, Chemicals, and Glass. Existing hydrogen demand can also be modeled.

**Inputs:**

Decarbonization percentages across light-duty (LD) on-road transport, heavy-duty (HD) on-road transport, and each industry can be modified for each model year. 

1) For on-road transport, this percentage is the percent decarbonization of projected fuel use (gasoline for LD, diesel for HD).
2) For industry, this percentage is the percent decarbonization of projected fuel-use for high-temp combustion, excluding fuel used for hydrogen production. 
3) For existing hydroegn demand, this percentage is the percent decarbonization of existing hydrogen demand, which is currently served almost entirely by steam methane reforming.

Note: The LD on-road transport category is defined as gasoline vehicles, and the HD on-road transport category is defined as diesel-powered vehicles.

**Outputs:**
For each model year, main outputs include:
1) Hourly hydrogen demand profiles for each load zone
2) A GeoPackage consisting of 5x5km squares spanning the WECC. Each square contains an attribute representing the hydrogen demand in that region. This allows for a higher spatial resolution output, used in hydrogen plant siting (https://github.com/nkong1/wecc-h2-siting).
3) Maps of hydrogen demand from on-road transport and industry.
