**This model is designed to generate hydrogen demand profiles at a high spatial and temporal resolution as an input to REAM Lab's SWITCH (https://github.com/REAM-lab/switch)**

**Overview:**

Hydrogen demand is modeled for on-road transport and key hard-to-decarbonize industrial end-use sectors across 47 load zones, over the input model years. The transportation sector is broken down into light-duty and heavy-duty on-road transport, and the industrial sector is broken down into Iron & Steel, Aluminum, Cement, Refining, Chemicals, and Glass. Existing hydrogen demand from 2022 is included as a baseline.

**Key Inputs:**

Decarbonization percentages across light-duty (LD) on-road transport, heavy-duty (HD) on-road transport, and each industry can be modified for each model year. 

1) For on-road transport, this percentage is the percent decarbonization of projected fuel use (gasoline for LD, diesel for HD).
2) For industry, this percentage is the percent decarbonization of projected fuel-use for high-temperature combustion, excluding fuel used for hydrogen production. 

Note: The LD on-road transport category is defined as gasoline vehicles, and the HD on-road transport category is defined as diesel-powered vehicles.

**Key Outputs:**

For each model year, main outputs include:
1) Hourly hydrogen demand profiles for each load zone
2) A GeoPackage consisting of 5x5km squares spanning the WECC. Each square contains an attribute representing the hydrogen demand in that region. This allows for a higher spatial resolution output, used in hydrogen plant siting (https://github.com/nkong1/wecc-h2-siting).
3) Maps of hydrogen demand from on-road transport and industry.

**Methodology Flowcharts:**

**Industry**:

<img width="766" height="450" alt="Image" src="https://github.com/user-attachments/assets/727592d3-1146-4b98-9e7a-961c36ca4880" />



**On-Road Transport:**

<img width="670" height="300" alt="ld_transport_methodology drawio (1)" src="https://github.com/user-attachments/assets/2deaba2c-6cfc-4a1b-8f4a-ca84fd2dcdfb" />
