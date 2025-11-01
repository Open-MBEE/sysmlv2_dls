"""
Integration-style helper that maps a tiny SysMLv2 example model onto
an Onshape assembly. The test is skipped by default so it does not run
in automated pipelines; enable it by providing the required Onshape URLs
via environment variables.

Environment variables:
    ONSHAPE_TARGET_ASSEMBLY_URL   - Workspace/assembly that receives the inserts
    ONSHAPE_COMPONENT_TYPE_<id>   - Source URL for each component typeID in the model

You can also run this module directly:
    $ python -m pytest tests/test_onshape_export.py -k export --run-onshape
    or
    $ python tests/test_onshape_export.py
"""
from __future__ import annotations

import os
from typing import Dict, Iterable

import numpy as np
import pytest
import syside

from geometry_api.geometry_api import components_from_part_world, find_partusage_by_definition
from onshape_api.onshape_helper import (
    get_onshape_client,
    insert_assembly_from_url,
    transform_by_name,
)
from transformation_api.transformations import transformation_matrix

# ── Config helpers ──
TARGET_ASSEMBLY_URL = os.getenv("ONSHAPE_TARGET_ASSEMBLY_URL", "").strip()

 
def _load_root_part():
   # model, diagnostics = syside.load_model(sysml_source=SYSML_MODEL)
    (model, diagnostics) = syside.load_model(["tests/geometry_example.sysml"])

    root = None
    for document_resource in model.documents:
        with document_resource.lock() as document:
            root = find_partusage_by_definition(document.root_node, "Component", usage_name="geometryroot")
            if root:
                print("Found PartUsage:", root.name)
                break

    if root is None:
        raise AssertionError("Failed to locate a PartUsage for 'Component'.")
 
    return root


def _to_transform(component: Dict[str, float]) -> np.ndarray:
    translation = (component["abs_tx"], component["abs_ty"], component["abs_tz"])
    rotation = (component["abs_rx"], component["abs_ry"], component["abs_rz"])
    return transformation_matrix(translation, rotation)


def _export_components(
    target_url: str,
    components: Iterable[Dict[str, float]],
) -> Dict[str, Dict[str, str]]:
    client = get_onshape_client()

    inserted: Dict[str, Dict[str, str]] = {}

    for comp in components:
        source_url =  comp["onshape_url"]
        if not source_url:
            print(f"⚠️ No Onshape source URL configured ; skipping '{comp['name']}'.")
            continue

        placement = insert_assembly_from_url(client, target_url, source_url)
        transform = _to_transform(comp)
        transform_by_name(client, target_url, placement["name"], transform)

        inserted[comp["name"]] = {
            "source_url": source_url,
            "inserted_name": placement["name"],
        }
        print(f"✅ Exported '{comp['name']}' as '{placement['name']}'.")

    return inserted


@pytest.mark.integration
@pytest.mark.skipif(
    not TARGET_ASSEMBLY_URL,
    reason="Set ONSHAPE_TARGET_ASSEMBLY_URL to run the Onshape export test.",
)
def test_export_demo_model_to_onshape():

    root = _load_root_part()
    components = components_from_part_world(root, angles_in_degrees=False, euler_axes="sxyz")

    # Root element (typeID=0) is assumed to already exist as the target assembly.
    components = [c for c in components if c["parent_name"] is not None]

    inserted = _export_components(TARGET_ASSEMBLY_URL, components)
    assert inserted, "No components were exported; check your configuration."


if __name__ == "__main__":
    TARGET_ASSEMBLY_URL = "https://cad.onshape.com/documents/4a29c75993840faff03a0c45/w/64843d9e906f6a84703e03a0/e/3be269a31cfe29647647c7f3"
    if not TARGET_ASSEMBLY_URL:
        raise SystemExit("Set TARGET_ASSEMBLY_URL before running this scriptt.")

    root = _load_root_part()
    print("Loaded root part:", root.name)   
    demo_components = components_from_part_world(root, angles_in_degrees=False, euler_axes="sxyz")
    demo_components = [c for c in demo_components if c["parent_name"] is not None]
    _export_components(TARGET_ASSEMBLY_URL, demo_components)
    print("Onshape export completed to target assembly: ", TARGET_ASSEMBLY_URL)
