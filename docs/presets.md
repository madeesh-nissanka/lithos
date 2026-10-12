# Domain Presets

LITHOS includes curated search presets for common engineering and science topics.
Presets are generic textbook-level queries and can be used as starting points.

## Available Presets

### Civil Engineering
- `soil_consolidation` - Soil consolidation settlement
- `slope_stability` - Slope stability analysis
- `bearing_capacity` - Bearing capacity of shallow foundations
- `retaining_walls` - Retaining wall design
- `ground_improvement` - Ground improvement techniques

### Geotechnical Engineering
- `foundation_design` - Foundation design
- `soil_structure_interaction` - Soil-structure interaction
- `geotechnical_earthquake` - Geotechnical earthquake engineering

### Structural Engineering
- `concrete_durability` - Concrete durability and chloride ingress
- `reinforced_concrete` - Reinforced concrete design
- `steel_structures` - Steel structures
- `structural_dynamics` - Structural dynamics
- `bridge_engineering` - Bridge engineering

### Environmental Engineering
- `water_treatment` - Water treatment processes
- `contaminant_transport` - Contaminant transport
- `air_quality` - Air quality modeling
- `solid_waste` - Solid waste management

### General Science
- `machine_learning_science` - Machine learning in science
- `systematic_review_methods` - Systematic review methodology

## Using Presets

### CLI

```bash
# List all presets
lithos presets

# List as JSON
lithos presets --json

# Emit a preset as a profile JSON
lithos presets --domain civil --name soil_consolidation -o profile.json

# Search using the profile
lithos search --profile profile.json --out results/
```

### Python API

```python
import lithos

# List all presets
print(lithos.list_presets())
# {'civil': ['soil_consolidation', 'slope_stability', ...], ...}

# Get a specific preset
profile = lithos.get_preset("civil", "soil_consolidation")

# Access queries
for query in profile.queries:
    print(query.boolean_query)

# Use in search
lithos.init_adapters({})
for query in profile.queries:
    for adapter in lithos.get_enabled_adapters():
        result = adapter.search(query, limit=100)
        # process result.records
```

## Preset Structure

Each preset is a `SearchProfile` with:
- `domain` - Domain category
- `name` - Preset name
- `description` - Human-readable description
- `queries` - List of `SearchQuery` objects with:
  - `original` - Original query string
  - `boolean_query` - Boolean query for search
  - `synonyms` - Synonym expansions
  - `source_translations` - Per-source query translations
  - `filters` - Year/type/open-access filters

## Custom Presets

Create your own presets by writing a JSON file matching the `SearchProfile`
structure, or build one programmatically:

```python
from lithos import SearchProfile, SearchQuery

profile = SearchProfile(
    domain="custom",
    name="my_topic",
    description="My custom topic",
    queries=[
        SearchQuery(
            original="my search terms",
            boolean_query="my search terms",
            filters={"from_year": 2015}
        )
    ]
)

# Save
profile.save(Path("my_preset.json"))

# Load
loaded = SearchProfile.load(Path("my_preset.json"))
```