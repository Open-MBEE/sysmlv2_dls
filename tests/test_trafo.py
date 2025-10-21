import pytest

import syside
from geometry_api.transformations import transformation_matrix, euler_from_matrix

# Import your functions (adjust import to your module)
from geometry_api.geometry_api import components_from_part_world, find_part_with_components

SYSML_MODEL = r"""
package MyStructure {

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
        part rootelement :Component {
            part nx00001 subsets children {
                attribute :>> tx=1.0;
                attribute :>> ty=1.0;
                attribute :>> tz=1.0;
                attribute :>> rx=1.0;
                attribute :>> ry=1.0;
                attribute :>> rz=1.0;
                attribute :>> typeID = 0;

                part tcs00001 subsets children {
                    attribute :>> tx=1.0;
                    attribute :>> ty=1.0;
                    attribute :>> tz=1.0;
                    attribute :>> rx=1.0;
                    attribute :>> ry=1.0;
                    attribute :>> rz=1.0;
                    attribute :>> typeID = 2;
                }
            }
        }
    }
}
""".strip()


def _by_name(comps, name):
    return next(c for c in comps if c["name"] == name)


def test_components_world_pose_and_parent_links():
    model, diagnostics = syside.load_model(sysml_source=SYSML_MODEL)

    root = find_part_with_components(model.document.root_node)
    assert root is not None

    # Treat rx/ry/rz=1.0 as **radians** and use the same Euler sequence as the library
    comps = components_from_part_world(root, angles_in_degrees=False, euler_axes="sxyz")

    # We expect exactly two components: nx00001 (typeID=0) and tcs00001 (typeID=2)
    names = sorted(c["name"] for c in comps)
    assert names == ["nx00001", "tcs00001"]

    nx = _by_name(comps, "nx00001")
    tcs = _by_name(comps, "tcs00001")

    # Parent chain:
    # rootelement (no typeID; identity world)
    #  -> nx00001 (tx,ty,tz,rx,ry,rz = 1.0 each)  [component]
    #      -> tcs00001 (same local pose = 1.0 each)  [component]

    # Build expected transforms with the same helper functions
    T_nx_abs = transformation_matrix((1.0, 1.0, 1.0), (1.0, 1.0, 1.0))  # rootelement is identity
    T_tcs_abs = T_nx_abs @ transformation_matrix((1.0, 1.0, 1.0), (1.0, 1.0, 1.0))

    # Extract expected Eulers back out using the same convention
    exp_nx_rx, exp_nx_ry, exp_nx_rz = euler_from_matrix(T_nx_abs, axes="sxyz")
    exp_tcs_rx, exp_tcs_ry, exp_tcs_rz = euler_from_matrix(T_tcs_abs, axes="sxyz")

    # ---- Assertions for nx00001 ----
    assert nx["parent_name"] is None
    assert nx["parent_typeID"] is None

    assert pytest.approx(nx["abs_tx"], abs=1e-9) == T_nx_abs[0, 3]
    assert pytest.approx(nx["abs_ty"], abs=1e-9) == T_nx_abs[1, 3]
    assert pytest.approx(nx["abs_tz"], abs=1e-9) == T_nx_abs[2, 3]

    assert pytest.approx(nx["abs_rx"], rel=1e-7, abs=1e-7) == exp_nx_rx
    assert pytest.approx(nx["abs_ry"], rel=1e-7, abs=1e-7) == exp_nx_ry
    assert pytest.approx(nx["abs_rz"], rel=1e-7, abs=1e-7) == exp_nx_rz

    # ---- Assertions for tcs00001 ----
    assert tcs["parent_name"] == "nx00001"
    assert tcs["parent_typeID"] == 0

    assert pytest.approx(tcs["abs_tx"], abs=1e-9) == T_tcs_abs[0, 3]
    assert pytest.approx(tcs["abs_ty"], abs=1e-9) == T_tcs_abs[1, 3]
    assert pytest.approx(tcs["abs_tz"], abs=1e-9) == T_tcs_abs[2, 3]

    assert pytest.approx(tcs["abs_rx"], rel=1e-7, abs=1e-7) == exp_tcs_rx
    assert pytest.approx(tcs["abs_ry"], rel=1e-7, abs=1e-7) == exp_tcs_ry
    assert pytest.approx(tcs["abs_rz"], rel=1e-7, abs=1e-7) == exp_tcs_rz
