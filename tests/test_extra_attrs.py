"""Coverage for the `extra_attrs` round-trip added to geometry_api.

Exercises the new code paths:
- Component.__init__ / Component.to_textual emitting extra attributes
- create_component passing extra_attrs through
- components_from_part / components_from_part_world spreading extras into the record
- load_from_sysml restoring extras onto the Component
"""
import pytest
import syside
from flexo_syside_lib.core import find_partusage_by_definition

from geometry_api.geometry_api import (
    create_component,
    get_sysmlv2_text,
    clear_components,
    load_from_sysml,
    components_from_part,
    components_from_part_world,
)

# A model whose power unit carries two extra (non-standard) numeric attributes.
EXTRA_MODEL = r"""
package ExtraStructure {

    part def Component{
        attribute tx;
        attribute ty;
        attribute tz;

        attribute rx;
        attribute ry;
        attribute rz;

        attribute typeID;
        part children: Component[0..*];
    }

    part def Context {
        part geometryroot : Component {
            part pwr00001 subsets children {
                attribute :>> tx=1.0;
                attribute :>> ty=2.0;
                attribute :>> tz=3.0;
                attribute :>> rx=0.0;
                attribute :>> ry=0.0;
                attribute :>> rz=0.0;
                attribute :>> typeID = 0;
                attribute alpha = 0.785;
                attribute beta = 0.5;
            }
        }
    }
}
""".strip()


def setup_function():
    clear_components()


def _geometryroot(model_text):
    model, _ = syside.load_model(sysml_source=model_text)
    for doc_res in model.documents:
        with doc_res.lock() as doc:
            root = find_partusage_by_definition(doc.root_node, "Component", usage_name="geometryroot")
            if root:
                return root
    raise AssertionError("geometryroot PartUsage not found")


def test_extra_attrs_emitted_in_generated_text():
    create_component(
        name="root",
        typeID=1,
        translation_data={"x": 0.0, "y": 0.0, "z": 0.0},
        rotation_data={"x": 0.0, "y": 0.0, "z": 0.0},
    )
    create_component(
        name="pwr",
        typeID=0,
        translation_data={"x": 1.0, "y": 2.0, "z": 3.0},
        rotation_data={"x": 0.0, "y": 0.0, "z": 0.0},
        parent_name="root",
        extra_attrs={"alpha": 0.785, "beta": 0.5},
    )
    text = get_sysmlv2_text("root")
    assert "attribute alpha = 0.785;" in text
    assert "attribute beta = 0.5;" in text


def test_no_extra_attrs_emits_nothing_extra():
    # Component without extras must not gain stray attribute lines.
    create_component(
        name="root",
        typeID=1,
        translation_data={"x": 0.0, "y": 0.0, "z": 0.0},
        rotation_data={"x": 0.0, "y": 0.0, "z": 0.0},
    )
    text = get_sysmlv2_text("root")
    assert "attribute alpha" not in text


def test_components_from_part_includes_extra():
    comps = components_from_part(_geometryroot(EXTRA_MODEL))
    pwr = next(c for c in comps if c["name"] == "pwr00001")
    assert pwr["typeID"] == 0
    assert pwr["tx"] == pytest.approx(1.0)
    assert pwr["alpha"] == pytest.approx(0.785)
    assert pwr["beta"] == pytest.approx(0.5)


def test_components_from_part_world_includes_extra():
    comps = components_from_part_world(_geometryroot(EXTRA_MODEL), angles_in_degrees=False)
    pwr = next(c for c in comps if c["name"] == "pwr00001")
    assert pwr["alpha"] == pytest.approx(0.785)
    assert pwr["beta"] == pytest.approx(0.5)
    # standard pose keys are handled explicitly, not duplicated via **extra
    assert pwr["tx"] == pytest.approx(1.0)


def test_load_from_sysml_restores_extra_attrs():
    _root, comps = load_from_sysml(_geometryroot(EXTRA_MODEL))
    assert "pwr00001" in comps
    pwr = comps["pwr00001"]
    assert pwr.extra_attrs.get("alpha") == pytest.approx(0.785)
    assert pwr.extra_attrs.get("beta") == pytest.approx(0.5)
    # pose/typeID are consumed into the Component, not left in extra_attrs
    assert "typeID" not in pwr.extra_attrs
    assert "tx" not in pwr.extra_attrs
