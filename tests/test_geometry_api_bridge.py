from pathlib import Path

import pytest

from geometry_api_bridge import (
    create_component,
    get_sysmlv2_text,
    clear_components,
    load_from_sysml,
    components_from_part_world,
)


def setup_function():
    clear_components()


def test_create_root_component_and_generate_text():
    name = create_component(
        name="root",
        typeID=1,
        translation_data={"x": 0.0, "y": 0.0, "z": 0.0},
        rotation_data={"x": 0.0, "y": 0.0, "z": 0.0},
    )
    assert name == "root"

    text = get_sysmlv2_text("root", package_name="Pkg")
    assert "package Pkg {" in text
    assert "part def Component{" in text
    assert "part root :Component {" in text


def test_create_child_component_hierarchy():
    create_component(
        name="root",
        typeID=1,
        translation_data={"x": 0.0, "y": 0.0, "z": 0.0},
        rotation_data={"x": 0.0, "y": 0.0, "z": 0.0},
    )
    create_component(
        name="child",
        typeID=2,
        translation_data={"x": 1.0, "y": 2.0, "z": 3.0},
        rotation_data={"x": 0.1, "y": 0.2, "z": 0.3},
        parent_name="root",
    )

    text = get_sysmlv2_text("root")

    assert "part child: Onshape_Component, Omniverse_Component subsets children {" in text
    assert "tx=1.0;" in text
    assert "ry=0.2;" in text
    assert "typeID = 2;" in text


def test_duplicate_component_raises():
    create_component(
        name="dup",
        typeID=1,
        translation_data={"x": 0.0, "y": 0.0, "z": 0.0},
        rotation_data={"x": 0.0, "y": 0.0, "z": 0.0},
    )
    with pytest.raises(ValueError, match="already exists"):
        create_component(
            name="dup",
            typeID=1,
            translation_data={"x": 0.0, "y": 0.0, "z": 0.0},
            rotation_data={"x": 0.0, "y": 0.0, "z": 0.0},
        )


def test_missing_parent_raises():
    with pytest.raises(ValueError, match="Parent component 'missing' not found"):
        create_component(
            name="orphan",
            typeID=3,
            translation_data={"x": 0.0, "y": 0.0, "z": 0.0},
            rotation_data={"x": 0.0, "y": 0.0, "z": 0.0},
            parent_name="missing",
        )


def test_get_text_missing_root_raises():
    with pytest.raises(ValueError, match="Root component 'nope' not found"):
        get_sysmlv2_text("nope")


def _load_geometry_example_root():
    """sysmlv2_flexo_bridge equivalent of the syside test's
    `syside.load_model` + `find_partusage_by_definition` setup.

    sysmlv2_flexo_bridge (github.com/planetaryutilities/sysmlv2_flexo_bridge)
    and the sysmlv2 wheel it drives are private planetaryutilities repos;
    this repo's CI has no token to fetch them, so these two tests skip
    gracefully rather than failing when they're not installed. Run them
    locally with both installed (PYTHONPATH=src pytest ...) to actually
    exercise load_from_sysml/components_from_part_world.
    """
    pytest.importorskip("sysmlv2_flexo_bridge")
    from sysmlv2_flexo_bridge.api import (
        convert_sysml_string_textual_to_json,
        convert_json_to_sysml_textual,
        find_partusage_by_definition,
    )

    this_dir = Path(__file__).parent
    model_path = this_dir / "geometry_example.sysml"
    text = model_path.read_text()

    payload, _json_string = convert_sysml_string_textual_to_json(text)
    (_sysml_text, model), warnings = convert_json_to_sysml_textual(
        [record["payload"] for record in payload]
    )
    assert not warnings, f"unexpected warnings converting geometry_example.sysml: {warnings}"

    context = find_partusage_by_definition(
        model.document.root_node, "Component", usage_name="geometryroot"
    )
    assert context is not None, "Could not find PartUsage for geometryroot"
    return context


def test_load_from_sysml_and_regenerate_text():
    context = _load_geometry_example_root()
    root_comp, components = load_from_sysml(context)
    assert root_comp is not None
    # geometryroot is declared `:Component, Onshape_Component, Omniverse_Component`,
    # so it's the only node in this fixture with "Component" in part_definitions
    # (nexus/solari_* are typed Onshape_Component/Omniverse_Component only,
    # matching the original Syside-backed geometry_api's semantics exactly).
    assert "geometryroot" in components


def test_components_from_part_world_matches_declared_pose():
    context = _load_geometry_example_root()
    components = components_from_part_world(context)
    by_name = {c["name"]: c for c in components}

    assert "solari_inside_simple" in by_name
    inside = by_name["solari_inside_simple"]
    assert inside["tx"] == pytest.approx(0.5)
    assert inside["ty"] == pytest.approx(-0.19)
    assert inside["tz"] == pytest.approx(1.0)
