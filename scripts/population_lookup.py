"""
Population lookup for the 7 NHS England commissioning regions.

NHS England's 7 regions don't map 1:1 onto ONS's 9 official regions of England.
Two NHS regions are each a combination of two ONS regions:

    NHS "Midlands"                = ONS West Midlands + ONS East Midlands
    NHS "North East and Yorkshire" = ONS North East + ONS Yorkshire and The Humber

The other five NHS regions map directly onto a single ONS region.

SOURCE: ONS mid-year population estimates (2021 Census-based figures, as
published by ONS or citing on ONS data). These are the values in use as of
this project's setup (August 2026).

TODO: swap in ONS mid-2023 or mid-2024 regional estimates if you want the
most current figures — the ONS "Population estimates for England and Wales"
release page publishes these tables directly:
https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationestimates
Only the numbers below need updating; nothing else in the pipeline changes.
"""

# ONS 9 official regions of England
ONS_REGION_POPULATION = {
    "North East": 2_646_772,
    "North West": 7_422_295,
    "Yorkshire and The Humber": 5_481_431,
    "East Midlands": 4_880_094,
    "West Midlands": 5_954_240,
    "East of England": 6_348_096,
    "London": 8_796_628,
    "South East": 9_294_023,
    "South West": 5_712_840,
}

# Mapping from NHS England's 7 regions (as used in the CSVs) to the ONS
# region(s) that make it up
NHS_REGION_TO_ONS_REGIONS = {
    "Midlands": ["West Midlands", "East Midlands"],
    "North East and Yorkshire": ["North East", "Yorkshire and The Humber"],
    "North West": ["North West"],
    "East of England": ["East of England"],
    "South East": ["South East"],
    "South West": ["South West"],
    "London": ["London"],
}


def get_nhs_region_population() -> dict:
    """Returns {nhs_region_name: population} for the 7 NHS England regions."""
    return {
        nhs_region: sum(ONS_REGION_POPULATION[ons_region] for ons_region in ons_regions)
        for nhs_region, ons_regions in NHS_REGION_TO_ONS_REGIONS.items()
    }


if __name__ == "__main__":
    pops = get_nhs_region_population()
    for region, pop in pops.items():
        print(f"{region}: {pop:,}")
