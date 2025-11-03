import onshape_client
import requests
import base64
import numpy as np
from typing import List, Dict, Tuple
import re
import os
from pathlib import Path

from onshape_client.oas import AssembliesApi, BTModelElementParams
from onshape_client.oas.models.bt_assembly_instance_definition_params import BTAssemblyInstanceDefinitionParams
from onshape_client.oas.models.bt_assembly_transform_definition_params import BTAssemblyTransformDefinitionParams
from onshape_client.oas.models.bt_occurrence74 import BTOccurrence74
from onshape_client.oas.exceptions import ApiTypeError

from onshape_client.oas.models.bt_assembly_instance_definition_params import BTAssemblyInstanceDefinitionParams
from onshape_client.oas.models.bt_assembly_transform_definition_params import BTAssemblyTransformDefinitionParams
from onshape_client.oas.models.bt_occurrence74 import BTOccurrence74

from onshape_client import Client

from transformation_api.transformations import decompose_matrix


def _load_onshape_credentials() -> Tuple[str, str]:
    # Prefer existing environment variables if present
    access_key = os.getenv("ACCESS_KEY")
    secret_key = os.getenv("SECRET_KEY")

    def _iter_candidate_env_files():
        override = os.getenv("ONSHAPE_DOTENV")
        if override:
            yield Path(override).expanduser()

        module_path = Path(__file__).resolve()
        for parent in module_path.parents:
            yield parent / ".env"

        cwd = Path.cwd().resolve()
        for parent in (cwd, *cwd.parents):
            yield parent / ".env"

    def _apply_env_file(path: Path):
        nonlocal access_key, secret_key
        try:
            contents = path.read_text()
        except OSError:
            return

        for line in contents.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            normalized = value.strip().strip('"\'')
            key = key.strip()
            if key == "ACCESS_KEY" and not access_key:
                access_key = normalized
            elif key == "SECRET_KEY" and not secret_key:
                secret_key = normalized

    if not (access_key and secret_key):
        seen = set()
        for candidate in _iter_candidate_env_files():
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            if resolved in seen or not resolved.exists():
                continue
            seen.add(resolved)
            _apply_env_file(resolved)
            if access_key and secret_key:
                break

    if not (access_key and secret_key):
        raise RuntimeError("Missing Onshape credentials. Configure ACCESS_KEY and SECRET_KEY via environment or .env.")

    return access_key, secret_key


ACCESS_KEY, SECRET_KEY = _load_onshape_credentials()
BASE_URL_API = "https://cad.onshape.com/api/v11"
BASE_URL = "https://cad.onshape.com"


def get_onshape_client() -> Client:
    return Client(configuration={
        'base_url': BASE_URL,
        'access_key': ACCESS_KEY,
        'secret_key': SECRET_KEY,
        'debug': True
    })


def parse_onshape_url(url: str) -> Tuple[str, str, str, str]:
    """
    Parse an Onshape document URL and extract:
    - did: Document ID
    - wvm: Workspace (w), Version (v), or Microversion (m)
    - wvmid: ID of the workspace/version/microversion
    - eid: Element ID
    """
    pattern = r'/documents/([^/]+)/([wvm])/([^/]+)/e/([^/?#]+)'
    match = re.search(pattern, url)
    if not match:
        raise ValueError("URL format is invalid or not recognized")

    did, wvm, wvmid, eid = match.groups()
    return did, wvm, wvmid, eid


# Example usage on a handbrake CAD model (public):
url = "https://cad.onshape.com/documents/91f152e2325e166b5ae98f4d/w/a89e4484f3b58b05d188dde4/e/ac851a7987c86e8a7e563127"
did, wvm, wvmid, eid = parse_onshape_url(url)
print(f"did = '{did}'")
print(f"wvm = '{wvm}'")
print(f"wvmid = '{wvmid}'")
print(f"eid = '{eid}'")


def auth_headers():
    auth_string = f"{ACCESS_KEY}:{SECRET_KEY}".encode('utf-8')
    auth = base64.b64encode(auth_string).decode('utf-8')
    return {'Authorization': f'Basic {auth}'}


def get_assembly_parts_with_transforms(url: str) -> List[Dict]:
    did, wvm, wvmid, eid = parse_onshape_url(url)
    url = f"{BASE_URL_API}/assemblies/d/{did}/{wvm}/{wvmid}/e/{eid}"
    params = {
        "includeMateFeatures": True,
        "includeMateConnectors": True,
        "includeNonSolids": True
    }
    r = requests.get(url, headers=auth_headers(), params=params)
    r.raise_for_status()
    assembly = r.json()

    instances = assembly['rootAssembly']['instances'] + [
        el for sub in assembly.get('subAssemblies', []) for el in sub['instances']
    ]
    parts = {p['id']: p for p in instances if p['type'] == 'Part'}
    results = []
    for occ in assembly['rootAssembly']['occurrences']:
        path = occ['path']
        transform = np.array(occ['transform']).reshape(4, 4)

        part_info = parts.get(path[-1])
        if part_info:
            results.append({
                "id": part_info['id'],
                "name": part_info['name'],
                "transform": transform,
                "path": path
            })

    return results



def get_all_assembly_items_with_transforms(url: str) -> List[Dict]:
    did, wvm, wvmid, eid = parse_onshape_url(url)
    api_url = f"{BASE_URL_API}/assemblies/d/{did}/{wvm}/{wvmid}/e/{eid}"
    params = {
        "includeMateFeatures": True,
        "includeMateConnectors": True,
        "includeNonSolids": True
    }
    r = requests.get(api_url, headers=auth_headers(), params=params)
    r.raise_for_status()
    assembly = r.json()

    # Collect all instances from root and subassemblies
    instance_list = assembly['rootAssembly']['instances']
    for sub in assembly.get('subAssemblies', []):
        instance_list.extend(sub['instances'])

    instances = {inst['id']: inst for inst in instance_list}

    results = []

    def process_occurrences(occurrences, parent_transform=np.identity(4)):
        for occ in occurrences:
            path = occ['path']
            transform = parent_transform @ np.array(occ['transform']).reshape(4, 4)
            scale, shear, angles, translate, perspective = decompose_matrix(transform)
            inst_id = path[-1]
            inst = instances.get(inst_id)
            if inst:
                results.append({
                    "id": inst['id'],
                    "name": inst['name'],
                    "type": inst['type'],
                    "path": path,
                    "location": list(translate),
                    "rotation": list(angles)  # Euler angles in radians (x, y, z)
                })

            if 'childOccurrences' in occ:
                process_occurrences(occ['childOccurrences'], transform)

    process_occurrences(assembly['rootAssembly']['occurrences'])

    return results


def get_sysml_v2_assembly_notation(url: str, root_name: str = "test") -> str:
    items = get_all_assembly_items_with_transforms(url)

    # Index by ID for lookup and by path for hierarchy
    id_to_item = {tuple(item["path"]): item for item in items}
    children_by_parent = {}

    for path in id_to_item:
        parent_path = tuple(path[:-1])
        children_by_parent.setdefault(parent_path, []).append(path)

    def render_node(path: tuple, indent: int = 1) -> List[str]:
        item = id_to_item[path]
        indent_str = "    " * indent
        location_str = ", ".join(f"{v:.17g}" for v in item["location"])
        rotation_str = ", ".join(f"{v:.17g}" for v in item["rotation"])

        lines = [f'{indent_str}part {item["name"]}: component {{']
        lines.append(f'{indent_str}    attribute :>> ID = "{item["id"]}";')
        lines.append(f'{indent_str}    attribute :>> location = ({location_str});')
        lines.append(f'{indent_str}    attribute :>> rotation = ({rotation_str});')

        # Recurse into children
        for child_path in sorted(children_by_parent.get(path, []), key=lambda p: id_to_item[p]["name"]):
            lines.extend(render_node(child_path, indent + 1))

        lines.append(f'{indent_str}}}')
        return lines

    # Top-level lines
    lines = [f"part {root_name} {{"]

    # Root nodes: paths with no parents
    root_paths = children_by_parent.get((), [])
    for root_path in sorted(root_paths, key=lambda p: id_to_item[p]["name"]):
        lines.extend(render_node(root_path, indent=1))

    lines.append("}")

    return "\n".join(lines)



def get_subassemblies_with_transforms(did: str, wvm: str, wvmid: str, eid: str) -> List[Dict]:
    url = f"{BASE_URL_API}/assemblies/d/{did}/{wvm}/{wvmid}/e/{eid}"
    params = {
        "includeMateFeatures": True,
        "includeMateConnectors": True,
        "includeNonSolids": True
    }
    r = requests.get(url, headers=auth_headers(), params=params)
    r.raise_for_status()
    assembly = r.json()

    instances = assembly['rootAssembly']['instances'] + [
        el for sub in assembly.get('subAssemblies', []) for el in sub['instances']
    ]
    assemblies = {p['id']: p for p in instances if p['type'] == 'Assembly'}

    results = []
    for occ in assembly['rootAssembly']['occurrences']:
        path = occ['path']
        transform = np.array(occ['transform']).reshape(4, 4)

        assy_info = assemblies.get(path[-1])
        if assy_info:
            results.append({
                "id": assy_info['id'],
                "name": assy_info['name'],
                "transform": transform,
                "path": path
            })

    return results


def auth_headers():
    auth_string = f"{ACCESS_KEY}:{SECRET_KEY}".encode('utf-8')
    auth = base64.b64encode(auth_string).decode('utf-8')
    return {'Authorization': f'Basic {auth}'}


def get_workspace_by_microversion(api_client, document_id: str):
    """
    Retrieve the workspace from a document that matches a given microversion ID.

    Args:
        api_client: An instance of the configured Onshape API client.
        document_id (str): The document ID (did) to search in.
        microversion_id (str): The microversion ID to match.

    Returns:
        The workspace info dict if found, otherwise None.
    """
    # Get all workspaces for the document
    api = api_client.documents_api
    workspaces = api.get_document_workspaces(did=document_id)
    # There should only be one workspace per document as that is the branch.
    # Find the workspace with the matching microversion ID
    for ws in workspaces:
        if hasattr(ws, 'id'):
            return ws.id

    return None


def get_assembly_info(did: str, wvm: str, wvmid: str, eid: str) -> dict:
    url = f"https://cad.onshape.com/api/v11/assemblies/d/{did}/{wvm}/{wvmid}/e/{eid}"
    params = {
        "includeMateFeatures": True,
        "includeMateConnectors": True,
        "includeNonSolids": True
    }
    response = requests.get(url, headers=auth_headers(), params=params)
    response.raise_for_status()
    return response.json()


def get_last_subassembly_info(assembly_info):
    subassemblies = assembly_info.get('subAssemblies', [])
    if not subassemblies:
        return None

    last_sub = subassemblies[-1]
    element_id = last_sub.get('elementId')

    # Find the last matching name from rootAssembly.instances
    name = None
    for inst in reversed(assembly_info.get('rootAssembly', {}).get('instances', [])):
        if inst.get('elementId') == element_id:
            name = inst.get('name')
            break

    return {
        'id': element_id,
        'name': name or 'Unknown'
    }


def get_last_inserted_top_level_assembly(assembly_info):
    instances = assembly_info.get('rootAssembly', {}).get('instances', [])
    if not instances:
        return None
    last_instance = instances[-1]
    return {
        'id': last_instance.get('elementId'),
        'name': last_instance.get('name', 'Unnamed')
    }


def create_new_assembly(client: Client, document_id: str, workspace_id: str,
                        name: str) -> dict:
    """
    Creates a new Assembly tab in the specified document and workspace.

    Args:
        client (Client): Authenticated Onshape client (from onshape-client library).
        document_id (str): ID of the Onshape document.
        workspace_id (str): ID of the workspace (e.g., main workspace) where assembly will be created.
        name (str): Desired name for the new assembly.
Ï
    Returns:
        dict: Deserialized JSON response representing the new document element.
    """
    api = AssembliesApi(client.api_client)
    params = BTModelElementParams(name=name)
    try:
        element_info = api.create_assembly(document_id, workspace_id, params)
        info = element_info.to_dict()
        ws = get_workspace_by_microversion(client, document_id)
        url = f"https://cad.onshape.com/documents/{document_id}/w/{workspace_id}/e/{info['id']}"

        return url
    except Exception as e:
        print(f"Failed to create assembly '{name}': {e}")
        raise


def insert_first_assembly_from_url(client, target_url: str, source_url: str) -> list:
    return insert_assembly_from_url(client, target_url, source_url, True)


def insert_assembly_from_url(client, target_url: str, source_url: str, isFirstAssembly=False) -> list:
    target_did, target_wvm, target_wvmid, target_eid = parse_onshape_url(target_url)
    source_did, source_wvm, source_wvmid, source_eid = parse_onshape_url(source_url)

    params = BTAssemblyInstanceDefinitionParams(
        document_id=source_did,
        version_id=source_wvmid if source_wvm == 'v' else None,
        microversion_id=source_wvmid if source_wvm == 'm' else None,
        element_id=source_eid,
        is_assembly=True,
    )

    kwargs = {
        "did": target_did,
        "eid": target_eid,
        "bt_assembly_instance_definition_params": params
    }

    if target_wvm == 'w':
        kwargs["wid"] = target_wvmid
    elif target_wvm == 'v':
        kwargs["vid"] = target_wvmid
    elif target_wvm == 'm':
        kwargs["mid"] = target_wvmid
    else:
        raise ValueError(f"Unknown WVM type: {target_wvm}")

    # client.assemblies_api.create_instance(**kwargs)
    try:
        response = client.assemblies_api.create_instance(**kwargs)
        print(response)
    except onshape_client.oas.exceptions.ApiTypeError as e:
        if "received_data" in str(e):
            print("⚠️ Ignored expected API deserialization error (insert succeeded).")
        else:
            raise

    # Return last occurrence path
    assembly_info = get_assembly_info(target_did, target_wvm, target_wvmid, target_eid)
    # This gives us the name of the last assy and its ID.
    info = get_last_inserted_top_level_assembly(assembly_info)
    print(info)
    return info


def insert_assembly_from_mvid(client, target_document_id: str, target_info, source_url: str, source_wvmid: str) -> dict:
    """
    Inserts an assembly from a source URL into a target assembly defined by doc ID, element ID, and microversion ID.

    Args:
        client: Onshape client.
        target_document_id: Target document ID.
        target_element_id: Target element ID (of the assembly to insert into).
        target_mvid: Target microversion ID.
        source_url: Full Onshape URL of the source element to insert.
        source_wvmid: Version or microversion ID of the source assembly.

    Returns:
        dict: Info about the inserted subassembly (name, ID, etc.).
    """
    source_did, _, _, source_eid = parse_onshape_url(source_url)

    params = BTAssemblyInstanceDefinitionParams(
        document_id=source_did,
        microversion_id=source_wvmid,
        element_id=source_eid,
        is_assembly=True,
    )

    target_mvid = target_info['microversion_id']
    target_element_id = target_info['id']

    try:
        response = client.assemblies_api.create_instance(
            did=target_document_id,
            mid=target_mvid,
            eid=target_element_id,
            bt_assembly_instance_definition_params=params
        )
        print(response)
    except ApiTypeError as e:
        if "received_data" in str(e):
            print("⚠️ Ignored expected API deserialization error (insert likely succeeded).")
        else:
            raise

    # Get inserted subassembly info
    assembly_info = get_assembly_info(target_document_id, 'm', target_mvid, target_element_id)
    info = get_last_subassembly_info(assembly_info)
    return info


def transform_occurrence_by_url(client, target_url: str, path: list, transform: list):
    did, wvm, wvmid, eid = parse_onshape_url(target_url)
    transform = [float(x) for x in transform]  # <-- ✅ Fix here

    transform_params = BTAssemblyTransformDefinitionParams(
        is_relative=False,
        occurrences=[BTOccurrence74(path=path, parent=None)],
        transform=transform
    )

    if wvm == "w":
        client.assemblies_api.transform_occurrences(
            did=did,
            wid=wvmid,
            eid=eid,
            bt_assembly_transform_definition_params=transform_params
        )
    elif wvm == "v":
        client.assemblies_api.transform_occurrences(
            did=did,
            vid=wvmid,
            eid=eid,
            bt_assembly_transform_definition_params=transform_params
        )
    elif wvm == "m":
        client.assemblies_api.transform_occurrences(
            did=did,
            mid=wvmid,
            eid=eid,
            bt_assembly_transform_definition_params=transform_params
        )
    else:
        raise ValueError(f"Unsupported wvm: {wvm}")


def transform_by_name(client, target_url: str, name: str, transform):
    transform = np.array(transform, dtype=float)
    if transform.size == 16 and transform.ndim == 1:
        transform = transform.reshape((4, 4))
    elif transform.shape != (4, 4):
        raise ValueError("Transform must be a flat list of 16 values or a 4x4 matrix.")

    # Parse URL into document/workspace/element IDs
    did, wvm, wvmid, eid = parse_onshape_url(target_url)

    # Fetch assembly info and all parts/subassemblies
    parts = get_assembly_parts_with_transforms(target_url)
    assies = get_subassemblies_with_transforms(did, wvm, wvmid, eid)

    # Try to find target in parts or assemblies
    target = next((p for p in parts if p["name"] == name), None)
    if target is None:
        target = next((a for a in assies if a["name"] == name), None)
    if target is None:
        raise ValueError(f"Could not find part or assembly named '{name}'.")

    # Build API call
    occurrence = BTOccurrence74(path=target["path"], parent=None)
    transform_matrix = transform.astype(float).flatten().tolist()
    params = BTAssemblyTransformDefinitionParams(
        is_relative=True,
        occurrences=[occurrence],
        transform=transform_matrix
    )

    # Execute transformation
    result = client.assemblies_api.transform_occurrences(
        did=did,
        wid=wvmid,
        eid=eid,
        bt_assembly_transform_definition_params=params
    )
    print(f"Successfully transformed '{name}' with path {target['path']}")
    return result
