# sysmlv2_geometry

## Overview
`sysmlv2_geometry` provides a public, SysML-based specification for 
sharing geometry information. The idea is that SysML serves as the platform technology that enables specifications to becomce life connections between tools and processes. 

The project currently focuses on two complementary capabilities:

1. A generic, CAD-agnostic representation of assemblies that captures
   translation, rotation, and ownership relationships between components.
2. A concrete connector that reads assembly data from Onshape and converts it
   into the common representation.

The intent is to grow this repository into a hub for multiple CAD and digital
engineering tools so that they can all feed geometry into SysML v2 models
through a single, consistent API.

## Key capabilities
- **Generic assembly structure** – The `geometry_api` package exposes endpoints
  for creating components, nesting them, and exporting the resulting hierarchy
  as SysML v2 textual notation. This makes it possible to describe assemblies
  even when the original CAD system is not available.
- **Onshape connector** – The `onshape_connector` package authenticates with the
  Onshape public API, walks assembly occurrences, and maps part poses into the
  generic structure. This is the first CAD integration, with more connectors
  planned.
- **Transformation utilities** – The `transformation_api` package bundles
  Christoph Gohlke's `transformations.py` helpers, which are used for converting
  between transformation matrices, Euler angles, and other pose formats.

## Repository layout
```
.
├── build/                  # Packaging or temporary build artifacts
├── examples/               # Sample data (e.g., SysML exports)
├── src/
│   ├── geometry_api/       # Public API for component creation & export
│   ├── onshape_connector/  # Helpers for pulling assemblies from Onshape
│   └── transformation_api/ # Math utilities for poses and transforms
├── tests/                  # Pytest suite covering API & connectors
├── requirements*.txt       # Runtime and CI dependency pins
└── pyproject.toml          # Project metadata (package name, deps, etc.)
```

## Installation
The project targets Python 3.8+ and is published under the package name
`geometry-api`. To install the package locally:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

The base dependencies include `astropy` for Cartesian representations and
`numpy` for matrix math. Some optional modules (for example, `syside` or the
Onshape client) may be required depending on which connectors you use.

## Configuring the Onshape connector
To access a workspace hosted on Onshape you will need an API key pair. The
connector searches for credentials in the `ACCESS_KEY` and `SECRET_KEY`
environment variables or inside a `.env` file placed either next to the module
or anywhere up the current working directory hierarchy. Once the credentials are
available, you can call the helper utilities in `onshape_connector` to
retrieve assembly instances, their hierarchical paths, and the transforms that
locate each component.

## Testing
The repository uses `pytest`. After installing the project along with the
additional requirements listed in `requirements.txt`, run:

```bash
pytest
```

Several tests rely on sample SysML outputs and mocked Onshape data to exercise
export and transformation logic.

## Roadmap
This repository is intended to evolve into a broad geometry interface. Planned
improvements include:

- Additional CAD connectors beyond Onshape.
- Richer metadata for components (materials, display properties, etc.).
- Higher-level orchestration scripts and examples for end-to-end workflows.

Contributions that add new tool integrations or extend the generic assembly
model are especially welcome.
