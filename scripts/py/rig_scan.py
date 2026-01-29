"""
Rig scanner utilities for VAM.

Scans selected rig roots, builds a controller hierarchy by walking the DAG,
and returns controller node names organized by their nearest controller parent.
"""

import maya.cmds as cmds


def scan_selected_rig(use_full_paths=True):
    """
    Scan selected rig roots and return controller hierarchy.

    Args:
        use_full_paths (bool): Use full DAG paths for node names.

    Returns:
        dict: {
            "roots": [controller_tree, ...],
            "controller_order": [ctrl_name, ...],
            "controller_parent": {ctrl_name: parent_ctrl_or_none},
        }
    """
    selection = cmds.ls(selection=True, long=True) or []
    if not selection:
        print("Rig scan: no selection.")
        return {
            "roots": [],
            "controller_order": [],
            "controller_parent": {},
        }

    roots = _find_root_nodes(selection)
    if not roots:
        print("Rig scan: no valid DAG roots found under selection.")
        return {
            "roots": [],
            "controller_order": [],
            "controller_parent": {},
        }

    controller_parent = {}
    controller_roots = []
    visited = set()
    for root in roots:
        _build_controller_tree(
            root,
            use_full_paths,
            controller_roots,
            controller_parent,
            visited,
            None,
        )

    controller_order = _flatten_controller_order(controller_roots)
    return {
        "roots": controller_roots,
        "controller_order": controller_order,
        "controller_parent": controller_parent,
    }


def _find_root_nodes(selection):
    """
    Find root DAG nodes from a selection list.

    If a selected node is a DAG node, it is treated as a candidate root.
    If it's not a DAG node, its transform ancestors are used when possible.
    """
    roots = []
    for node in selection:
        if cmds.objExists(node) and cmds.nodeType(node) in ("transform", "joint"):
            roots.append(node)
            continue
        parent = cmds.listRelatives(node, parent=True, fullPath=True)
        if parent and cmds.nodeType(parent[0]) in ("transform", "joint"):
            roots.append(parent[0])

    return list(dict.fromkeys(roots))


def _build_controller_tree(
    node,
    use_full_paths,
    controller_roots,
    controller_parent,
    visited,
    current_controller,
):
    """
    Recursively build a controller tree by walking the DAG.

    Only controller nodes (transforms with curve shapes) are recorded.
    The hierarchy is based on nearest controller ancestor in the DAG.
    """
    if node in visited:
        return
    visited.add(node)

    new_controller = current_controller
    if _is_curve_controller(node) and _is_controller_visible(node):
        ctrl_name = _normalize_name(node, use_full_paths)
        ctrl_node = {"controller": ctrl_name, "children": []}
        if current_controller is None:
            controller_roots.append(ctrl_node)
            controller_parent[ctrl_name] = None
        else:
            current_controller["children"].append(ctrl_node)
            controller_parent[ctrl_name] = current_controller["controller"]
        new_controller = ctrl_node

    for child in _list_dag_children(node):
        _build_controller_tree(
            child,
            use_full_paths,
            controller_roots,
            controller_parent,
            visited,
            new_controller,
        )


def _is_curve_controller(node):
    shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
    for shape in shapes:
        if cmds.nodeType(shape) == "nurbsCurve":
            return True
    return False


def _is_controller_visible(node):
    """
    Return True if the controller is visible in the viewport.
    """
    try:
        return cmds.getAttr(f"{node}.visibility")
    except Exception:
        return False


def _list_dag_children(node):
    children = cmds.listRelatives(node, children=True, fullPath=True) or []
    dag_children = []
    for child in children:
        if cmds.nodeType(child) in ("transform", "joint"):
            dag_children.append(child)
    return dag_children


def _normalize_name(node, use_full_paths):
    return node if use_full_paths else node.split("|")[-1]


def _flatten_controller_order(roots):
    """
    Flatten controller names in depth-first joint order.
    """
    order = []

    def _walk(node):
        ctrl = node.get("controller")
        if ctrl:
            order.append(ctrl)
        for child in node.get("children", []):
            _walk(child)

    for root in roots:
        _walk(root)
    return order
