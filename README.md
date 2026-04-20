# GBIF Datasets for Lakota Lands

This repository provides instructions and examples for locating, querying, and downloading biodiversity occurrence data from the [Global Biodiversity Information Facility (GBIF)](https://www.gbif.org) for species of cultural and ecological importance on or near Lakota lands and includes the Pine Ridge, Rosebud, Standing Rock, and Cheyenne River reservations.

## Overview
While GBIF does not maintain datasets explicitly titled “Lakota lands,” it contains numerous **occurrence records** for culturally relevant species, such as bison, chokecherry, prairie turnip, magpie and others within or near reservation boundaries. These data originate from herbaria, museums, community observations, and federal sources.

### Example related datasets and sources

- **[Chadron State College / High Plains Herbarium](https://www.gbif.org/dataset/97695324-8a6d-4a1c-98aa-16dbac2eb167)** – includes Pine Ridge region specimens.
- **GBIF species pages**  
  - [Prunus virginiana (Chokecherry)](https://www.gbif.org/species/3022668)  
  - [Bison bison (American Bison)](https://www.gbif.org/species/2441178)  
  - [Pediomelum esculentum (Prairie Turnip / Timpsila)](https://www.gbif.org/species/2944104)
- Fossil datasets referencing the **Lakota Formation** ([Plazi Fossil Collections](https://plazi.org)).

## Species of Focus
| Common Name | Scientific Name | GBIF Species Key |
|--------------|------------------|------------------|
| Chokecherry | *Prunus virginiana* | 3022668 |
| American Bison | *Bison bison* | 2441178 |
| Prairie Turnip (Timpsila) | *Pediomelum esculentum* | 2944104 |
| Black-billed Magpie | *Pica hudsonia* | 5229490 |
| Black-tailed Prairie Dog | *Cynomys ludovicianus* | 2437232 |
| Black-footed Ferret | *Mustela nigripes* | 5218985 |

## How to Access GBIF Occurrence Data
You can obtain occurrence data for these species within reservation boundaries using one of three approaches:
1. **Interactive filtering on the GBIF web portal**  
2. **Programmatic queries via the GBIF API**  
3. **Code-based queries with `pygbif` (Python) or `rgbif` (R)**

### Option A: Interactive GBIF Download
1. Visit [GBIF Occurrence Search](https://www.gbif.org/occurrence/search).  
2. Search for a target species (for example, *Prunus virginiana*).  
3. Apply geographic filters by typing reservation names (“Pine Ridge Indian Reservation”) **or** drawing a bounding box on the map.  
4. Click **Download** → choose `SIMPLE_CSV` format.  
5. Repeat for other species.

### Option B: Programmatic Access via Python (`pygbif`)

```python
from pygbif import species, occurrences
import pandas as pd

# Example: Prunus virginiana (Chokecherry)
res = species.name_backbone(name="Prunus virginiana")
species_key = res["usageKey"]

# Pine Ridge Reservation approximate bounding box (WKT)
geometry = "POLYGON((-103.2 42.9, -103.2 43.8, -101.0 43.8, -101.0 42.9, -103.2 42.9))"

occ = occurrences.search(
    taxonKey=species_key,
    geometry=geometry,
    hasCoordinate=True,
    limit=3000
)

df = pd.DataFrame(occ["results"])
df.to_csv("prunus_virginiana_pineridge.csv", index=False)
