from multiprocessing import context
from annotated_types import doc
import pytest
import syside
from geometry_api.geometry_api import (
    create_component,
    get_sysmlv2_text,
    clear_components,
    load_from_sysml,
    find_partusage_by_definition,
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

from pathlib import Path
 

def test_load_from_sysml_and_regenerate_text():
    this_dir = Path(__file__).parent
    model_path = this_dir / "geometry_example.sysml"
    print(f"Looking for model file at: {model_path.resolve()}")
    model, _ = syside.load_model([str(model_path)])
    model, _ = syside.load_model([str(model_path)])

    # Get the first document root for traversal
    context = None
    for doc_res in model.documents:
        with doc_res.lock() as doc:
            context = find_partusage_by_definition(doc.root_node, "Component", usage_name="geometryroot")
            if context:
                break

    assert context is not None, "Could not find PartUsage for geometryroot"
    print("Loading from SysMLv2 model...")
    root_comp = load_from_sysml(context)

    print(root_comp.to_textual())
#test_load_from_sysml_and_regenerate_text()


