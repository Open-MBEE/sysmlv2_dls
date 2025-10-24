from astropy.coordinates import CartesianRepresentation
from typing import List, Optional, Dict
import syside
import math
import numpy as np
# Make sure the library is importable; if needed add sys.path.append('/mnt/data')
from transformation_api.transformations import transformation_matrix, euler_from_matrix  # uses 'sxyz' by default

_components: Dict[str, "Component"] = {}

pu_geometry_pkg = '''
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
    ):
        self.name = name
        self.typeID = typeID
        self.translation = translation
        self.rotation = rotation
        self.parent = parent
        self.children: List[Component] = []

        if parent:
            parent.children.append(self)

    def to_textual(self, indent: int = 0) -> str:
        ind = " " * indent
        lines = [
            f"{ind}part {self.name} subsets children {{",
            f"{ind}    attribute :>> tx={self.translation.x};",
            f"{ind}    attribute :>> ty={self.translation.y};",
            f"{ind}    attribute :>> tz={self.translation.z};",
            f"{ind}    attribute :>> rx={self.rotation.x};",
            f"{ind}    attribute :>> ry={self.rotation.y};",
            f"{ind}    attribute :>> rz={self.rotation.z};",
            f"{ind}    attribute :>> typeID = {self.typeID};",
        ]
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

    component = Component(name, typeID, translation, rotation, parent=parent_component)
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

def walk_ownership_tree(element, level: int = 0) -> None:
    """
    Prints out all elements in a model in a tree-like format, where child
    elements appear indented under their parent elements. For example:

    Parent
      Child1
      Child2
        Grandchild

    Args:
        element: The model element to start printing from (syside.Element)
        level: How many levels to indent (increases for nested elements)
    """

    if element.try_cast(syside.AttributeUsage):
        attr = element.cast(syside.AttributeUsage)
        expression_a1 = next(iter(attr.owned_elements), None)
        if expression_a1 is not None and isinstance(expression_a1, syside.LiteralRational):
            print("  " * level, f"{attr.name} = {expression_a1.value}")
        elif expression_a1 is not None and isinstance(expression_a1, syside.LiteralInteger):
            print("  " * level, f"{attr.name} = {expression_a1.value}")
        else:
            print("  " * level, f"{attr.name}", type(expression_a1))
    elif element.name is not None:
        print("  " * level, element.name)
    # Recursively call walk_ownership_tree() for each owned element
    # (child element).
    element.owned_elements.for_each(
        lambda owned_element: walk_ownership_tree(owned_element, level + 1)
    )

def find_part_by_name(element, name: str, part_level: int = 0):
    """
    Depth-first search for a PartUsage by name.
    Prints the part hierarchy as it goes and returns the first match.
    
    Args:
        element: The model element to search from (syside.Element)
        name: The part name to find
        part_level: Current indentation level for printing
    """

    part = element.try_cast(syside.PartUsage)
    if part:
        print("  " * part_level + part.name)
        if part.name == name:
            return part
        part_level += 1  # indent children of parts

    # Iterate children in a way that allows early return
    children = getattr(element, "owned_elements", None)
    if not children:
        return None

    # Try to iterate directly; if not iterable, materialize via for_each
    try:
        iterator = iter(children)
    except TypeError:
        lst = []
        children.for_each(lambda e: lst.append(e))
        iterator = iter(lst)

    for child in iterator:
        found = find_part_by_name(child, name, part_level)
        if found is not None:
            return found

    return None

def components_from_part(root):
    """
    Walk a SysIDE PartUsage sub-tree and return a list of dicts with
    fields: name, typeID, tx, ty, tz, rx, ry, rz, parent_name, parent_typeID.
    Only nodes that have a numeric typeID are returned.
    """

    out = []

    def visit(el, parent_info=None):
        part = el.try_cast(syside.PartUsage)
        current_info = parent_info
        if part:
            vals = {}

            def collect_attr(e):
                au = e.try_cast(syside.AttributeUsage)
                if not au:
                    return
                lit = next(iter(au.owned_elements), None)
                if isinstance(lit, (syside.LiteralRational, syside.LiteralInteger)):
                    vals[au.name] = float(lit.value)

            el.owned_elements.for_each(collect_attr)

            if "typeID" in vals:
                rec = {
                    "name": part.name or "",
                    "typeID": int(vals["typeID"]),
                    "tx": vals.get("tx", 0.0),
                    "ty": vals.get("ty", 0.0),
                    "tz": vals.get("tz", 0.0),
                    "rx": vals.get("rx", 0.0),
                    "ry": vals.get("ry", 0.0),
                    "rz": vals.get("rz", 0.0),
                    "parent_name": parent_info[0] if parent_info else None,
                    "parent_typeID": parent_info[1] if parent_info else None,
                }
                out.append(rec)
                current_info = (rec["name"], rec["typeID"])

        el.owned_elements.for_each(lambda c: visit(c, current_info))

    visit(root, None)
    return out


def components_from_part_world(root, *, angles_in_degrees=False, euler_axes='sxyz'):
    """
    Traverse a PartUsage subtree and return a flat list of component dicts with:
      - local pose (tx..rz)  : relative to parent (as in the model)
      - absolute pose (abs_*) : world frame, recursively accumulated
      - nearest component ancestor (parent_name/typeID)
    Only nodes with numeric typeID are emitted as 'components'.
    """
    to_rad = (lambda a: a * math.pi / 180.0) if angles_in_degrees else (lambda a: a)
    to_deg = (lambda a: a * 180.0 / math.pi)

    # --- helpers to ensure JSON-safe, plain Python floats ---
    def _to_float(x):
        try:
            return float(x)
        except Exception:
            return x

    def _normalize(d):
        # Cast any numpy scalar/array entries to Python floats
        return {k: (_to_float(v) if not isinstance(v, (list, tuple, dict)) else v) for k, v in d.items()}


    out = []

    def visit(el, parent_state):
        """
        parent_state:
          {
            "T": 4x4 absolute/world transform of current frame,
            "comp_parent": (name, typeID) or None    # nearest emitted component ancestor
          }
        """
        if parent_state is None:
            parent_state = {
                "T": np.identity(4),
                "comp_parent": None,
            }

        part = el.try_cast(syside.PartUsage)
        next_state = dict(parent_state)

        if part:
            # Collect numeric attribute values from AttributeUsage children
            vals = {}
            def collect_attr(e):
                au = e.try_cast(syside.AttributeUsage)
                #print("au",au)
                if not au:
                    return
                attr = e.cast(syside.AttributeUsage)
                expression = next(iter(attr.owned_elements), None)
                if isinstance(expression, (syside.LiteralRational, syside.LiteralInteger)):
                    #print(f"au={au.name}, lit={type(expression)}, value={expression.value}, parent={type(e)}")
                    vals[au.name] = float(expression.value)
                elif expression is not None and isinstance(expression, syside.Expression):
                    compiler = syside.Compiler()
                    result, report = compiler.evaluate(expression)
                    vals[au.name] = float(result)
          

            owned = getattr(el, "owned_elements", None)
            if owned:
                owned.for_each(collect_attr)

            # Local pose relative to parent (defaults to zero)
            ltx = vals.get("tx", 0.0); lty = vals.get("ty", 0.0); ltz = vals.get("tz", 0.0)
            lrx = to_rad(vals.get("rx", 0.0)); lry = to_rad(vals.get("ry", 0.0)); lrz = to_rad(vals.get("rz", 0.0))

            # Build local homogeneous transform and compose: T_abs = T_parent @ T_local
            T_local = transformation_matrix((ltx, lty, ltz), (lrx, lry, lrz))  # 'sxyz' convention
            #print("T_local" , T_local)
            #print("parent_state " , parent_state["T"])
            T_abs = parent_state["T"] @ T_local
            #print("tabs", T_abs)
            # Propagate transform down regardless of whether this node becomes a 'component'
            next_state["T"] = T_abs

            if "typeID" in vals:
                type_id = int(vals["typeID"])

                # Extract absolute/world pose back to Euler+translation
                # (same axes convention as the library: 'sxyz')
                arx, ary, arz = euler_from_matrix(T_abs, axes=euler_axes)
                abs_tx, abs_ty, abs_tz = T_abs[0, 3], T_abs[1, 3], T_abs[2, 3]
                #print("abs_tx, abs_ty, abs_tz",abs_tx,abs_ty, abs_tz)
                if angles_in_degrees:
                    arx, ary, arz = to_deg(arx), to_deg(ary), to_deg(arz)

                rec = {
                    "name": part.name or "",
                    "typeID": type_id,

                    # local pose (relative to parent; unchanged from source data)
                    "tx": ltx, "ty": lty, "tz": ltz,
                    "rx": vals.get("rx", 0.0),
                    "ry": vals.get("ry", 0.0),
                    "rz": vals.get("rz", 0.0),

                    # absolute/world pose (recursively accumulated)
                    "abs_tx": abs_tx, "abs_ty": abs_ty, "abs_tz": abs_tz,
                    "abs_rx": arx,    "abs_ry": ary,    "abs_rz": arz,

                    # nearest component ancestor (same behavior as your original)
                    "parent_name": parent_state["comp_parent"][0] if parent_state["comp_parent"] else None,
                    "parent_typeID": parent_state["comp_parent"][1] if parent_state["comp_parent"] else None,
                }
                out.append(_normalize(rec))

                # This node becomes the nearest component ancestor for its descendants
                next_state["comp_parent"] = (rec["name"], rec["typeID"])

        # Recurse
        children = getattr(el, "owned_elements", None)
        if children:
            children.for_each(lambda c: visit(c, next_state))

    visit(root, None)
    return out

def _children_iter(elem):
    children = getattr(elem, "owned_elements", None)
    if not children:
        return []
    try:
        return list(children)
    except TypeError:
        out = []
        children.for_each(lambda e: out.append(e))
        return out

def _has_numeric_typeid(part_el):
    """True iff this PartUsage has an AttributeUsage named 'typeID'
    whose first owned element is a numeric literal."""
    owned = getattr(part_el, "owned_elements", None)
    if not owned:
        return False

    found = False
    def visit_attr(e):
        nonlocal found
        if found:
            return
        au = e.try_cast(syside.AttributeUsage)
        if not au or au.name != "typeID":
            return
        lit = next(iter(au.owned_elements), None)
        if isinstance(lit, (syside.LiteralInteger, syside.LiteralRational)):
            found = True

    owned.for_each(visit_attr)
    return found

def find_part_with_components(elem):
    """
    Return the FIRST/HIGHEST PartUsage whose subtree contains at least one
    PartUsage with a numeric 'typeID'. Single DFS; no transform work.
    """
    def dfs(node):
        # returns (found_topmost_partusage_or_None, subtree_has_any_component: bool)
        is_part = bool(node.try_cast(syside.PartUsage))
        here_is_component = is_part and _has_numeric_typeid(node)

        subtree_has_component = here_is_component
        child_found = None

        for ch in _children_iter(node):
            found, child_has = dfs(ch)
            # Accumulate whether *anywhere* below there is a component
            subtree_has_component = subtree_has_component or child_has or (found is not None)
            # Remember a found child (don’t overwrite first found)
            if found is not None and child_found is None:
                child_found = found

        # If THIS node is a PartUsage and its subtree (incl. itself) has any component,
        # this is the topmost qualifying node—return it.
        if is_part and subtree_has_component:
            return node, True

        # Otherwise, if a child already found its own topmost PartUsage, bubble it up.
        if child_found is not None:
            return child_found, True

        # Nothing found yet; propagate whether this subtree has any components at all.
        return None, subtree_has_component

    found, _ = dfs(elem)
    return found
