"""sysmlv2-native equivalent of geometry_api, with no Syside dependency at all.

Mirrors `geometry_api`'s public API exactly (`Component`, `create_component`,
`get_sysmlv2_text`, `clear_components`, `load_from_sysml`,
`components_from_part_world`) so callers can pick between the two modules
based on which SysML v2 engine they're using — e.g.:

    if backend == "sysmlv2":
        from geometry_api_bridge import load_from_sysml, components_from_part_world
    else:
        from geometry_api.geometry_api import load_from_sysml, components_from_part_world

`Component`/`create_component`/`get_sysmlv2_text`/`clear_components` are
plain Python bookkeeping and string templating — identical to `geometry_api`'s
versions, duplicated here (rather than imported from `geometry_api`) so this
module has zero dependency on Syside, full stop.

`load_from_sysml`/`components_from_part_world` walk a
`sysmlv2_flexo_bridge` (github.com/planetaryutilities/sysmlv2_flexo_bridge)
`JsonElement` tree — the interchange-JSON equivalent of the live Syside
PartUsage/AttributeUsage AST `geometry_api`'s versions walk — using
`sysmlv2_flexo_bridge_engine.evaluate_attributes()` in place of
`syside.Compiler().evaluate()` for expression-valued attributes.
sysmlv2_flexo_bridge is imported lazily, only inside those two functions, so
this module still doesn't need it just for the bookkeeping half.
"""

from astropy.coordinates import CartesianRepresentation
from typing import List, Optional, Dict
import math
import numpy as np
from transformation_api.transformations import transformation_matrix, euler_from_matrix  # uses 'sxyz' by default

_components: Dict[str, "Component"] = {}

pu_geometry_pkg = '''

    part def Onshape_Component {
        attribute onshape_url;
    }
    part def Omniverse_Component {
        attribute ov_filepath;
    }

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
'''


class Component:
    def __init__(
        self,
        name: str,
        typeID: int,
        translation: CartesianRepresentation,
        rotation: CartesianRepresentation,
        parent: Optional["Component"] = None,
        extra_attrs: Optional[Dict] = None,
    ):
        self.name = name
        self.typeID = typeID
        self.translation = translation
        self.rotation = rotation
        self.parent = parent
        self.children: List[Component] = []
        self.extra_attrs: Dict = extra_attrs or {}

        if parent:
            parent.children.append(self)

    def to_textual(self, indent: int = 0) -> str:
        ind = " " * indent
        lines = [
            f"{ind}part {self.name}: Onshape_Component, Omniverse_Component subsets children {{",
            f"{ind}    attribute :>> tx={self.translation.x};",
            f"{ind}    attribute :>> ty={self.translation.y};",
            f"{ind}    attribute :>> tz={self.translation.z};",
            f"{ind}    attribute :>> rx={self.rotation.x};",
            f"{ind}    attribute :>> ry={self.rotation.y};",
            f"{ind}    attribute :>> rz={self.rotation.z};",
            f"{ind}    attribute :>> typeID = {self.typeID};",
        ]
        for key, val in self.extra_attrs.items():
            lines.append(f"{ind}    attribute {key} = {val!r};")
        for child in self.children:
            lines.append(child.to_textual(indent + 4))
        lines.append(f"{ind}}}")
        return "\n".join(lines)


def create_component(
    name: str,
    typeID: int,
    translation_data: Dict[str, float],
    rotation_data: Dict[str, float],
    parent_name: Optional[str] = None,
    extra_attrs: Optional[Dict] = None,
) -> str:
    """
    API endpoint to create a new geometric component and optionally attach it to a parent.
    """
    if name in _components:
        raise ValueError(f"Component with name '{name}' already exists.")

    translation = CartesianRepresentation(
        translation_data["x"], translation_data["y"], translation_data["z"]
    )
    rotation = CartesianRepresentation(
        rotation_data["x"], rotation_data["y"], rotation_data["z"]
    )

    parent_component = None
    if parent_name:
        parent_component = _components.get(parent_name)
        if not parent_component:
            raise ValueError(f"Parent component '{parent_name}' not found.")

    component = Component(name, typeID, translation, rotation, parent=parent_component, extra_attrs=extra_attrs)
    _components[name] = component
    return name


def get_sysmlv2_text(root_component_name: str, package_name: str = "MyStructure") -> str:
    """
    API endpoint to generate the SysMLv2 textual representation of the entire
    component hierarchy, starting from a specified root component.
    """
    root = _components.get(root_component_name)
    if not root:
        raise ValueError(f"Root component '{root_component_name}' not found.")

    lines = [
        f"package {package_name} {{",
        pu_geometry_pkg,
        "",
        "     part def Context {",
        f"        part {root.name} :Component {{"
    ]
    for child in root.children:
        lines.append(child.to_textual(indent=12))
    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    return "\n".join(lines)


def clear_components():
    """Clears all components from the internal store. Useful for testing or resetting."""
    _components.clear()


def _values_by_name(root) -> Dict[str, str]:
    from sysmlv2_flexo_bridge import _engine
    model = root._model
    if model.sysml_text is None:
        return {}
    return _engine.evaluate_attributes(model.sysml_text)


_LITERAL_NUMBER_TYPES = ("LiteralRational", "LiteralInteger")


def _find_first_literal(el):
    """Descend through wrapper elements (e.g. a unary operator's Feature
    operand) to find the first numeric literal, or None."""
    if el.element_type in _LITERAL_NUMBER_TYPES:
        return el
    for child in el.owned_elements:
        found = _find_first_literal(child)
        if found is not None:
            return found
    return None


def _collect_attrs(el, values_by_name: Dict[str, str]) -> Dict[str, object]:
    """Collect numeric/string attribute values under a PartUsage element (JsonElement)."""
    vals: Dict[str, object] = {}

    def _collect_attr(e):
        au = e.try_cast("AttributeUsage")
        if not au:
            return
        expression = next(iter(au.owned_elements), None)
        if expression is None:
            return
        if expression.element_type in _LITERAL_NUMBER_TYPES:
            vals[au.name] = float(expression.value)
        elif expression.element_type == "LiteralString":
            vals[au.name] = str(expression.value)
        elif expression.element_type == "OperatorExpression" and expression.data.get("operator") == "-":
            # Negative literals (e.g. `ty=-0.19;`) parse as a unary minus
            # OperatorExpression over a nested literal, not a plain literal —
            # handled directly rather than via the evaluate_attributes()
            # fallback below, which doesn't resolve this expression shape.
            literal = _find_first_literal(expression)
            if literal is not None:
                vals[au.name] = -float(literal.value)
        else:
            name = au.qualified_name or au.name
            result = values_by_name.get(name) or (
                values_by_name.get(au.name) if au.name else None
            )
            if result is not None:
                try:
                    vals[au.name] = float(result)
                except (TypeError, ValueError):
                    pass  # unresolved expression; leave attribute unset rather than storing junk

    if getattr(el, "owned_elements", None):
        el.owned_elements.for_each(_collect_attr)
    return vals


def components_from_part_world(root, *, angles_in_degrees=False, euler_axes='sxyz'):
    """
    Traverse a PartUsage subtree (a sysmlv2_flexo_bridge JsonElement — e.g.
    from sysmlv2_flexo_bridge.api.convert_json_to_sysml_textual's
    model.document.root_node) and return a flat list of component dicts with:
      - local pose (tx..rz)  : relative to parent (as in the model)
      - absolute pose (abs_*) : world frame, recursively accumulated
      - nearest component ancestor (parent_name/typeID)
    Only nodes with numeric typeID are emitted as 'components'.

    sysmlv2-native equivalent of geometry_api.components_from_part_world.
    """
    to_rad = (lambda a: a * math.pi / 180.0) if angles_in_degrees else (lambda a: a)
    to_deg = lambda a: a * 180.0 / math.pi

    def _to_float(x):
        if isinstance(x, bool):
            return x
        if isinstance(x, int):
            return x
        try:
            return float(x)
        except Exception:
            return x

    def _normalize(d):
        return {k: (_to_float(v) if not isinstance(v, (list, tuple, dict)) else v) for k, v in d.items()}

    values_by_name = _values_by_name(root)
    out = []

    def visit(el, parent_state):
        if parent_state is None:
            parent_state = {"T": np.identity(4), "comp_parent": None}

        part = el.try_cast("PartUsage")
        next_state = dict(parent_state)

        if part:
            vals = _collect_attrs(el, values_by_name)

            ltx = vals.get("tx", 0.0); lty = vals.get("ty", 0.0); ltz = vals.get("tz", 0.0)
            lrx = to_rad(vals.get("rx", 0.0)); lry = to_rad(vals.get("ry", 0.0)); lrz = to_rad(vals.get("rz", 0.0))

            T_local = transformation_matrix((ltx, lty, ltz), (lrx, lry, lrz))
            T_abs = parent_state["T"] @ T_local
            next_state["T"] = T_abs

            arx, ary, arz = euler_from_matrix(T_abs, axes=euler_axes)
            abs_tx, abs_ty, abs_tz = T_abs[0, 3], T_abs[1, 3], T_abs[2, 3]
            if angles_in_degrees:
                arx, ary, arz = to_deg(arx), to_deg(ary), to_deg(arz)

            extra = dict(vals)
            for key in ("tx", "ty", "tz", "rx", "ry", "rz", "typeID"):
                extra.pop(key, None)
            onshape_url = extra.pop("onshape_url", None)

            rec = {
                "name": part.name or "",
                "typeID": int(vals.get("typeID", 0)),
                "tx": ltx, "ty": lty, "tz": ltz,
                "rx": vals.get("rx", 0.0), "ry": vals.get("ry", 0.0), "rz": vals.get("rz", 0.0),
                "abs_tx": abs_tx, "abs_ty": abs_ty, "abs_tz": abs_tz,
                "abs_rx": arx, "abs_ry": ary, "abs_rz": arz,
                "parent_name": parent_state["comp_parent"][0] if parent_state["comp_parent"] else None,
                "parent_typeID": parent_state["comp_parent"][1] if parent_state["comp_parent"] else None,
                "onshape_url": onshape_url,
                **extra,
            }
            out.append(_normalize(rec))
            next_state["comp_parent"] = (rec["name"], rec["typeID"])

        for child in getattr(el, "owned_elements", []):
            visit(child, next_state)

    visit(root, None)
    return out


def load_from_sysml(root, clear_existing: bool = True) -> "tuple[Component | None, dict[str, Component]]":
    """
    Inverse of get_sysmlv2_text(): reads a SysMLv2 model (a
    sysmlv2_flexo_bridge JsonElement) starting at `root` and rebuilds the
    Python Component hierarchy (_components dict).

    sysmlv2-native equivalent of geometry_api.load_from_sysml.

    Args:
        root: a sysmlv2_flexo_bridge JsonElement (e.g. the Context or
            Component PartUsage).
        clear_existing: If True, clears any previous _components registry.
    Returns:
        The root Component object reconstructed from the model.
    """
    if clear_existing:
        _components.clear()

    values_by_name = _values_by_name(root)

    def visit(el, parent_component=None):
        part = el.try_cast("PartUsage")
        if part:
            vals = _collect_attrs(el, values_by_name)
            def_names = [pd.name for pd in part.part_definitions]
            has_typeid = "typeID" in vals
            has_component_def = "Component" in def_names

            if has_typeid or has_component_def:
                type_id = int(vals.get("typeID", len(_components) + 1))
                extra = dict(vals)
                extra.pop("typeID", None)
                tx = extra.pop("tx", 0.0); ty = extra.pop("ty", 0.0); tz = extra.pop("tz", 0.0)
                rx = extra.pop("rx", 0.0); ry = extra.pop("ry", 0.0); rz = extra.pop("rz", 0.0)

                this_component = Component(
                    name=part.name or f"Unnamed_{len(_components)}",
                    typeID=type_id,
                    translation=CartesianRepresentation(tx, ty, tz),
                    rotation=CartesianRepresentation(rx, ry, rz),
                    parent=parent_component,
                    extra_attrs=extra,
                )
                _components[this_component.name] = this_component
                parent_component = this_component

        for child in getattr(el, "owned_elements", []):
            visit(child, parent_component)

    visit(root, None)

    roots = [c for c in _components.values() if c.parent is None]
    return (roots[0] if roots else None), _components
