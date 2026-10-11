# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
Domain presets for LITHOS - generic query templates for engineering and science domains.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from lithos.query import SearchQuery, SearchProfile


# Civil Engineering Presets
CIVIL_PRESETS = {
    "soil_consolidation": SearchProfile(
        name="soil_consolidation",
        description="Soil consolidation settlement analysis",
        queries=[
            SearchQuery(original="soil consolidation settlement", boolean_query="soil consolidation settlement"),
            SearchQuery(original="consolidation test oedometer", boolean_query="consolidation test oedometer"),
            SearchQuery(original="settlement prediction clay", boolean_query="settlement prediction clay"),
            SearchQuery(original="preloading surcharge consolidation", boolean_query="preloading surcharge consolidation"),
        ],
        sources=["openalex", "crossref", "semantic_scholar", "europe_pmc", "arxiv", "doaj"],
        filters={"from_year": 2000},
    ),
    "slope_stability": SearchProfile(
        name="slope_stability",
        description="Slope stability analysis and landslide risk",
        queries=[
            SearchQuery(original="slope stability analysis", boolean_query="slope stability analysis"),
            SearchQuery(original="factor of safety slope", boolean_query="factor of safety slope"),
            SearchQuery(original="landslide risk assessment", boolean_query="landslide risk assessment"),
            SearchQuery(original="slope reinforcement soil nails", boolean_query="slope reinforcement soil nails"),
        ],
        sources=["openalex", "crossref", "semantic_scholar", "europe_pmc", "arxiv", "doaj"],
        filters={"from_year": 2000},
    ),
    "bearing_capacity": SearchProfile(
        name="bearing_capacity",
        description="Bearing capacity of shallow foundations",
        queries=[
            SearchQuery(original="bearing capacity shallow foundation", boolean_query="bearing capacity shallow foundation"),
            SearchQuery(original="Terzaghi bearing capacity", boolean_query="Terzaghi bearing capacity"),
            SearchQuery(original="Meyerhof bearing capacity", boolean_query="Meyerhof bearing capacity"),
            SearchQuery(original="plate load test bearing capacity", boolean_query="plate load test bearing capacity"),
        ],
        sources=["openalex", "crossref", "semantic_scholar", "europe_pmc", "arxiv", "doaj"],
        filters={"from_year": 2000},
    ),
    "retaining_walls": SearchProfile(
        name="retaining_walls",
        description="Retaining wall design and analysis",
        queries=[
            SearchQuery(original="retaining wall design", boolean_query="retaining wall design"),
            SearchQuery(original="earth pressure retaining wall", boolean_query="earth pressure retaining wall"),
            SearchQuery(original="MSE wall reinforced soil", boolean_query="MSE wall reinforced soil"),
            SearchQuery(original="sheet pile wall design", boolean_query="sheet pile wall design"),
        ],
        sources=["openalex", "crossref", "semantic_scholar", "europe_pmc", "arxiv", "doaj"],
        filters={"from_year": 2000},
    ),
    "ground_improvement": SearchProfile(
        name="ground_improvement",
        description="Ground improvement techniques",
        queries=[
            SearchQuery(original="ground improvement techniques", boolean_query="ground improvement techniques"),
            SearchQuery(original="dynamic compaction vibrocompaction", boolean_query="dynamic compaction vibrocompaction"),
            SearchQuery(original="stone columns ground improvement", boolean_query="stone columns ground improvement"),
            SearchQuery(original="deep soil mixing", boolean_query="deep soil mixing"),
        ],
        sources=["openalex", "crossref", "semantic_scholar", "europe_pmc", "arxiv", "doaj"],
        filters={"from_year": 2000},
    ),
}


# Geotechnical Engineering Presets
GEOTECH_PRESETS = {
    "foundation_design": SearchProfile(
        name="foundation_design",
        description="Foundation design - shallow and deep",
        queries=[
            SearchQuery(original="foundation design shallow deep", boolean_query="foundation design (shallow OR deep)"),
            SearchQuery(original="pile foundation design", boolean_query="pile foundation design"),
            SearchQuery(original="raft foundation mat foundation", boolean_query="raft foundation OR mat foundation"),
            SearchQuery(original="foundation settlement analysis", boolean_query="foundation settlement analysis"),
        ],
        sources=["openalex", "crossref", "semantic_scholar", "europe_pmc", "arxiv", "doaj"],
        filters={"from_year": 2000},
    ),
    "soil_structure_interaction": SearchProfile(
        name="soil_structure_interaction",
        description="Soil-structure interaction analysis",
        queries=[
            SearchQuery(original="soil structure interaction", boolean_query="soil structure interaction"),
            SearchQuery(original="SSI seismic analysis", boolean_query="SSI seismic analysis"),
            SearchQuery(original="pile group interaction", boolean_query="pile group interaction"),
            SearchQuery(original="foundation soil spring", boolean_query="foundation soil spring"),
        ],
        sources=["openalex", "crossref", "semantic_scholar", "europe_pmc", "arxiv", "doaj"],
        filters={"from_year": 2000},
    ),
    "geotechnical_earthquake": SearchProfile(
        name="geotechnical_earthquake",
        description="Geotechnical earthquake engineering",
        queries=[
            SearchQuery(original="earthquake-induced ground settlement", boolean_query="earthquake-induced ground settlement"),
            SearchQuery(original="seismic site response", boolean_query="seismic site response"),
            SearchQuery(original="ground motion amplification", boolean_query="ground motion amplification"),
            SearchQuery(original="seismic slope stability", boolean_query="seismic slope stability"),
        ],
        sources=["openalex", "crossref", "semantic_scholar", "europe_pmc", "arxiv", "doaj"],
        filters={"from_year": 2000},
    ),
}


# Structural Engineering Presets
STRUCTURAL_PRESETS = {
    "concrete_durability": SearchProfile(
        name="concrete_durability",
        description="Concrete durability - chloride ingress, carbonation, freeze-thaw",
        queries=[
            SearchQuery(original="concrete durability chloride", boolean_query="concrete durability chloride"),
            SearchQuery(original="chloride ingress concrete", boolean_query="chloride ingress concrete"),
            SearchQuery(original="concrete carbonation", boolean_query="concrete carbonation"),
            SearchQuery(original="freeze thaw concrete durability", boolean_query="freeze thaw concrete durability"),
        ],
        sources=["openalex", "crossref", "semantic_scholar", "europe_pmc", "arxiv", "doaj"],
        filters={"from_year": 2000},
    ),
    "reinforced_concrete": SearchProfile(
        name="reinforced_concrete",
        description="Reinforced concrete design and analysis",
        queries=[
            SearchQuery(original="reinforced concrete design", boolean_query="reinforced concrete design"),
            SearchQuery(original="RC beam column design", boolean_query="RC beam column design"),
            SearchQuery(original="shear design reinforced concrete", boolean_query="shear design reinforced concrete"),
            SearchQuery(original="deflection control concrete", boolean_query="deflection control concrete"),
        ],
        sources=["openalex", "crossref", "semantic_scholar", "europe_pmc", "arxiv", "doaj"],
        filters={"from_year": 2000},
    ),
    "steel_structures": SearchProfile(
        name="steel_structures",
        description="Steel structure design and connections",
        queries=[
            SearchQuery(original="steel structure design", boolean_query="steel structure design"),
            SearchQuery(original="steel connection design", boolean_query="steel connection design"),
            SearchQuery(original="buckling steel member", boolean_query="buckling steel member"),
            SearchQuery(original="composite steel concrete", boolean_query="composite steel concrete"),
        ],
        sources=["openalex", "crossref", "semantic_scholar", "europe_pmc", "arxiv", "doaj"],
        filters={"from_year": 2000},
    ),
    "structural_dynamics": SearchProfile(
        name="structural_dynamics",
        description="Structural dynamics and seismic analysis",
        queries=[
            SearchQuery(original="structural dynamics modal analysis", boolean_query="structural dynamics modal analysis"),
            SearchQuery(original="seismic response spectrum", boolean_query="seismic response spectrum"),
            SearchQuery(original="time history analysis structure", boolean_query="time history analysis structure"),
            SearchQuery(original="base isolation seismic", boolean_query="base isolation seismic"),
        ],
        sources=["openalex", "crossref", "semantic_scholar", "europe_pmc", "arxiv", "doaj"],
        filters={"from_year": 2000},
    ),
    "bridge_engineering": SearchProfile(
        name="bridge_engineering",
        description="Bridge design, analysis, and assessment",
        queries=[
            SearchQuery(original="bridge design analysis", boolean_query="bridge design analysis"),
            SearchQuery(original="bridge load rating", boolean_query="bridge load rating"),
            SearchQuery(original="bridge deterioration assessment", boolean_query="bridge deterioration assessment"),
            SearchQuery(original="cable stayed bridge suspension", boolean_query="cable stayed bridge OR suspension bridge"),
        ],
        sources=["openalex", "crossref", "semantic_scholar", "europe_pmc", "arxiv", "doaj"],
        filters={"from_year": 2000},
    ),
}


# Environmental Engineering Presets
ENVIRONMENTAL_PRESETS = {
    "water_treatment": SearchProfile(
        name="water_treatment",
        description="Water and wastewater treatment processes",
        queries=[
            SearchQuery(original="water treatment process", boolean_query="water treatment process"),
            SearchQuery(original="wastewater treatment plant", boolean_query="wastewater treatment plant"),
            SearchQuery(original="membrane filtration water", boolean_query="membrane filtration water"),
            SearchQuery(original="advanced oxidation process", boolean_query="advanced oxidation process"),
        ],
        sources=["openalex", "crossref", "semantic_scholar", "europe_pmc", "arxiv", "doaj"],
        filters={"from_year": 2000},
    ),
    "contaminant_transport": SearchProfile(
        name="contaminant_transport",
        description="Contaminant transport in groundwater and soil",
        queries=[
            SearchQuery(original="contaminant transport groundwater", boolean_query="contaminant transport groundwater"),
            SearchQuery(original="advection dispersion equation", boolean_query="advection dispersion equation"),
            SearchQuery(original="groundwater remediation", boolean_query="groundwater remediation"),
            SearchQuery(original="phytoremediation soil", boolean_query="phytoremediation soil"),
        ],
        sources=["openalex", "crossref", "semantic_scholar", "europe_pmc", "arxiv", "doaj"],
        filters={"from_year": 2000},
    ),
    "air_quality": SearchProfile(
        name="air_quality",
        description="Air quality modeling and pollution control",
        queries=[
            SearchQuery(original="air quality modeling", boolean_query="air quality modeling"),
            SearchQuery(original="particulate matter PM2.5", boolean_query="particulate matter PM2.5"),
            SearchQuery(original="air pollution dispersion", boolean_query="air pollution dispersion"),
            SearchQuery(original="emission control technology", boolean_query="emission control technology"),
        ],
        sources=["openalex", "crossref", "semantic_scholar", "europe_pmc", "arxiv", "doaj"],
        filters={"from_year": 2000},
    ),
    "solid_waste": SearchProfile(
        name="solid_waste",
        description="Solid waste management and landfill design",
        queries=[
            SearchQuery(original="solid waste management", boolean_query="solid waste management"),
            SearchQuery(original="landfill design leachate", boolean_query="landfill design leachate"),
            SearchQuery(original="waste to energy incineration", boolean_query="waste to energy incineration"),
            SearchQuery(original="recycling circular economy", boolean_query="recycling circular economy"),
        ],
        sources=["openalex", "crossref", "semantic_scholar", "europe_pmc", "arxiv", "doaj"],
        filters={"from_year": 2000},
    ),
}


# General Science Presets
SCIENCE_PRESETS = {
    "machine_learning_science": SearchProfile(
        name="machine_learning_science",
        description="Machine learning applications in science and engineering",
        queries=[
            SearchQuery(original="machine learning image segmentation", boolean_query="machine learning image segmentation"),
            SearchQuery(original="deep learning scientific computing", boolean_query="deep learning scientific computing"),
            SearchQuery(original="neural network physics informed", boolean_query="neural network physics informed"),
            SearchQuery(original="data science engineering applications", boolean_query="data science engineering applications"),
        ],
        sources=["openalex", "crossref", "semantic_scholar", "arxiv", "doaj"],
        filters={"from_year": 2015},
    ),
    "systematic_review_methods": SearchProfile(
        name="systematic_review_methods",
        description="Systematic review and meta-analysis methodology",
        queries=[
            SearchQuery(original="systematic review methodology", boolean_query="systematic review methodology"),
            SearchQuery(original="meta-analysis method", boolean_query="meta-analysis method"),
            SearchQuery(original="PRISMA systematic review", boolean_query="PRISMA systematic review"),
            SearchQuery(original="scoping review method", boolean_query="scoping review method"),
        ],
        sources=["openalex", "crossref", "semantic_scholar", "europe_pmc", "doaj"],
        filters={"from_year": 2010},
    ),
}


ALL_PRESETS = {
    "civil": CIVIL_PRESETS,
    "geotechnical": GEOTECH_PRESETS,
    "structural": STRUCTURAL_PRESETS,
    "environmental": ENVIRONMENTAL_PRESETS,
    "science": SCIENCE_PRESETS,
}


def get_preset(domain: str, name: str) -> Optional[SearchProfile]:
    """Get a preset by domain and name."""
    return ALL_PRESETS.get(domain, {}).get(name)


def list_presets() -> dict[str, list[str]]:
    """List all available presets."""
    return {domain: list(presets.keys()) for domain, presets in ALL_PRESETS.items()}


def get_all_profiles() -> list[SearchProfile]:
    """Get all profiles as a flat list."""
    profiles = []
    for domain_presets in ALL_PRESETS.values():
        profiles.extend(domain_presets.values())
    return profiles