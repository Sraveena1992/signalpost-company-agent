import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.forensic_registry_drift import source_values, ORG

def test_official_company_address_only_from_brreg():
    d={"organisasjonsnummer":ORG,"konkurs":False,"underAvvikling":False,
       "forretningsadresse":{"adresse":["ul. Dluga 25"],"land":"Polen","poststed":"PL - 25 650 KIELCE"}}
    assert source_values(d)=={"Bankruptcy flag":False,"Liquidation flag":False,
     "Registered business address":"ul. Dluga 25, PL - 25 650 KIELCE, Polen"}
