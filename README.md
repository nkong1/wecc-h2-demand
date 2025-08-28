# WECC H2 Demand Model

This model generates hourly hydrogen demand profiles from on-road transport and various industrial end-use sectors across 47 load zones in SWITCH-WECC (excluding 2 load zones in Canada and one in Mexico), over the input model years. The transportation sector is broken down into light-duty and heavy-duty on-road transport, and the industrial sector is broken down into key hard-to-decarbonize industries: Iron & Steel, Aluminum, Cement, Refining, Chemicals, and Glass. Existing hydrogen demand can also be modeled (the modeling of the individual industrial sectors does not include existing hydrogen demand).

Decarbonization percentages across LD on-road transport, HD on-road transport, and each industry can be modified for each model year. 

For on-road transport, this percentage is the percentage of fuel (gasoline for LD, diesel for HD) decarbonization.

For industry, this percentage is the percent decarbonization of fuel used for high-temp combustion, excluding fuel used for hydrogen production. 

For existing hydroegn demand, this percentage is the percent decarbonization of existing hydrogen demand (existing hydrogen demand in the WECC is served almost entirely from natural gas SMRs).

Note: LD on-road transport is defined as gasoline vehicles, and HD on-road transport is defined as diesel-powered vehicles.
