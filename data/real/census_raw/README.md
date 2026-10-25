# Census 2011 raw files (drop them here)

Download from https://censusindia.gov.in (their TLS certificate does not verify from every
machine, so use a normal browser and check the file opens). Keep the original file names.

## 1. Mother tongue by state (C-16), one Excel file per state

| State | Catalog page | Expected file |
|---|---|---|
| Uttar Pradesh | https://censusindia.gov.in/nada/index.php/catalog/10224 | DDW-C16-STMT-MDDS-0900.xlsx |
| Maharashtra | https://censusindia.gov.in/nada/index.php/catalog/10212 | DDW-C16-STMT-MDDS-2700.xlsx |
| West Bengal | https://censusindia.gov.in/nada/index.php/catalog/10226 | DDW-C16-STMT-MDDS-1900.xlsx |
| Karnataka | https://censusindia.gov.in/nada/index.php/catalog/10208 | DDW-C16-STMT-MDDS-2900.xlsx |
| Tamil Nadu | https://censusindia.gov.in/nada/index.php/catalog/10222 | DDW-C16-STMT-MDDS-3300.xlsx |
| Kerala | https://censusindia.gov.in/nada/index.php/catalog/10209 | DDW-C16-STMT-MDDS-3200.xlsx |
| NCT of Delhi | https://censusindia.gov.in/nada/index.php/catalog/10201 | DDW-C16-STMT-MDDS-0700.xlsx |
| Andhra Pradesh (contains the Telangana districts; 2011 predates the split) | https://censusindia.gov.in/nada/index.php/catalog/10193 | DDW-C16-STMT-MDDS-2800.xlsx |

## 2. Households with TV, computer/laptop with internet, mobile (HL-14)

State-level files from
https://censusindia.gov.in/2011census/HLO/HL_PCA/Houselisting-housing-HLPCA.html
(one Excel file per state; same eight states as above). Keep the original names.

## 3. Primary Census Abstract (population, urban share, literacy), if you can find it

State-level PCA tables for the same eight states (Total/Rural/Urban population and literacy).

Once the files are here, tell me and I will build `scripts/import_census.py`, check the new
values against the current approximate ones, and switch the models over.
