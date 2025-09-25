from astropy.coordinates import CartesianRepresentation
from typing import List, Optional, Dict


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