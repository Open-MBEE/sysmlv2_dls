from astropy.coordinates import CartesianRepresentation
from typing import List, Optional, Dict
import syside

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
        if expression_a1 is not None and isinstance(expression_a1, syside.LiteralInteger):
            print("  " * level, f"{attr.name} = {expression_a1.value}")
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

def _children_list(elem):
    children = getattr(elem, "owned_elements", None)
    if not children:
        return []
    try:
        return list(children)
    except TypeError:
        lst = []
        children.for_each(lambda e: lst.append(e))
        return lst
    
def find_part_with_components(elem):
    part = elem.try_cast(syside.PartUsage)
    if part:
        comps_try = components_from_part(part)
        if comps_try:
            return part
    for ch in _children_list(elem):
        found = find_part_with_components(ch)
        if found:
            return found
    return None
