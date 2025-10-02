import pytest

from geometry_api.geometry_api import (
    create_component,
    get_sysmlv2_text,
    clear_components,
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
    assert "part child subsets children {" in text
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


