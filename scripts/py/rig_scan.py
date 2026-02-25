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
            "controller_parent": {ctrl_name: parent_ctrl_or_none},
        }
    """
    selection = cmds.ls(selection=True, long=True) or []
    if not selection:
        print("Rig scan: no selection.")
        return {
            "roots": [],
            "controller_parent": {},
        }

    roots = _find_root_nodes(selection)
    if not roots:
        print("Rig scan: no valid DAG roots found under selection.")
        return {
            "roots": [],
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

    return {
        "roots": controller_roots,
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

def scan_selected_skeleton(root_bone=None, use_full_paths=True):
    """
    Build joint hierarchy data from a root bone.

    Args:
        root_bone (str|None): Root joint/transform. If None, uses current selection.
        use_full_paths (bool): Use full DAG paths for node names.

    Returns:
        dict: {
            "root": skeleton_tree_or_none,
            "joint_parent": {joint_name: parent_joint_or_none},
        }
    """
    root_joint = root_bone
    if not root_joint:
        print("Rig scan: no valid root joint found for skeleton scan.")
        return {
            "root": None,
            "joint_parent": {},
        }

    joint_parent = {}
    root_tree = _build_skeleton_tree(
        root_joint,
        None,
        use_full_paths,
        joint_parent,
    )
    return {
        "root": root_tree,
        "joint_parent": joint_parent,
    }


def _build_skeleton_tree(joint, parent_joint, use_full_paths, joint_parent):
    """
    Recursively build a joint-only hierarchy tree.
    """
    joint_name = _normalize_name(joint, use_full_paths)
    parent_name = _normalize_name(parent_joint, use_full_paths) if parent_joint else None
    joint_parent[joint_name] = parent_name

    children = []
    child_joints = cmds.listRelatives(joint, children=True, type="joint", fullPath=True) or []
    for child in child_joints:
        children.append(
            _build_skeleton_tree(
                child,
                joint,
                use_full_paths,
                joint_parent,
            )
        )

    return {
        "joint": joint_name,
        "children": children,
    }

def update_rig_controller_hierarchy(rig_controller_hierarchy, skeleton_hierarchy):
    """
    Update controller hierarchy using joint relationships implied by constraints.

    The scanner first builds controller hierarchy from DAG parenting. This function
    augments/rewires that hierarchy when controllers are connected to skeleton joints
    through constraints (parent/point/orient/scale/etc), even across separate groups.
    """
    if not rig_controller_hierarchy or not skeleton_hierarchy:
        return rig_controller_hierarchy

    controller_parent = dict(rig_controller_hierarchy.get("controller_parent", {}))
    joint_parent = dict(skeleton_hierarchy.get("joint_parent", {}))
    if not controller_parent or not joint_parent:
        return rig_controller_hierarchy

    skeleton_uses_full_paths = any("|" in key for key in joint_parent.keys() if key)
    controller_uses_full_paths = any("|" in key for key in controller_parent.keys() if key)

    controller_joint_map = _build_controller_joint_map(
        controller_parent,
        controller_uses_full_paths,
        skeleton_uses_full_paths,
        joint_parent,
    )
    joint_to_controllers = {}
    for ctrl, joints in controller_joint_map.items():
        for joint_key in joints:
            if joint_key not in joint_parent:
                continue
            joint_to_controllers.setdefault(joint_key, set()).add(ctrl)

    # Rewire each controller to the nearest ancestor joint that also has a controller.
    for joint_key, controllers in joint_to_controllers.items():
        ancestor = joint_parent.get(joint_key)
        ancestor_controllers = None
        while ancestor:
            ancestor_controllers = joint_to_controllers.get(ancestor)
            if ancestor_controllers:
                break
            ancestor = joint_parent.get(ancestor)

        if not ancestor_controllers:
            continue

        parent_ctrl = sorted(ancestor_controllers)[0]
        for ctrl in sorted(controllers):
            if ctrl == parent_ctrl:
                continue
            if _would_create_parent_cycle(ctrl, parent_ctrl, controller_parent):
                continue
            controller_parent[ctrl] = parent_ctrl

    updated = {
        "controller_parent": controller_parent,
        "roots":_build_roots_from_parent_map(controller_parent)
    }
    return updated


def _get_connected_nodes(nodes):
    connected = []
    for node in nodes:
        descendants = cmds.listConnections(node, scn=True) or []
        pruned = [node for node in descendants if cmds.nodeType(node) not in ('objectset')]
        if pruned:
            connected.extend(pruned)
            connected.extend(_get_connected_nodes(pruned))
    return connected


def _filter_by_type(nodes, typ):
    return [node for node in nodes if cmds.nodeType(node) == typ]


def _list_constraint_nodes():
    constraint_types = [
        "parentConstraint",
        "pointConstraint",
        "orientConstraint",
        "scaleConstraint",
        "aimConstraint",
        "poleVectorConstraint",
        "geometryConstraint",
        "normalConstraint",
        "tangentConstraint",
    ]
    constraints = []
    for ctype in constraint_types:
        constraints.extend(cmds.ls(type=ctype) or [])
    return list(dict.fromkeys(constraints))


def _find_driven_joints_for_constraint(constraint):
    driven = cmds.listConnections(
        constraint,
        source=False,
        destination=True,
        type="joint",
    ) or []
    if driven:
        return list(dict.fromkeys(driven))

    transforms = set(cmds.listConnections(
        constraint,
        source=False,
        destination=True,
        type="transform",
    ) or [])
    joints = set()
    for node in transforms:
        joints.update(_collect_joints_near_transform(node))
    return list(dict.fromkeys(sorted(joints)))


def _build_controller_joint_map(
    controller_parent,
    controller_uses_full_paths,
    skeleton_uses_full_paths,
    joint_parent,
):
    """
    Precompute joints influenced by each controller via related constraints.
    """
    constraint_nodes = set(_list_constraint_nodes())
    controller_joint_map = {}
    for ctrl_key in controller_parent.keys():
        related_constraints = _find_related_constraints_for_controller(
            ctrl_key,
            controller_uses_full_paths,
            constraint_nodes,
        )
        joints = set()
        for constraint in related_constraints:
            for joint in _find_driven_joints_for_constraint(constraint):
                joint_key = _normalize_name(joint, skeleton_uses_full_paths)
                if joint_key in joint_parent:
                    joints.add(joint_key)
        controller_joint_map[ctrl_key] = joints
    import json
    # Keep sets for fast deduping in-memory, then convert for JSON preview.
    serializable_map = {
        ctrl_key: sorted(joints)
        for ctrl_key, joints in controller_joint_map.items()
    }
    with open("E:/temp/controller_joint_map.json", "w", encoding="utf-8") as f:
        json.dump(serializable_map, f, indent=2)
    return controller_joint_map


def _find_related_constraints_for_controller(ctrl_key, use_full_paths, constraint_nodes):
    """
    Find constraints connected anywhere under controller descendants.
    """
    nodes = _resolve_controller_transform_nodes(ctrl_key, use_full_paths)
    if not nodes:
        return set()

    descendants = set(nodes)
    for node in list(nodes):
        descendants.update(
            cmds.listRelatives(node, allDescendents=True, fullPath=True) or []
        )

    related = set()
    for node in descendants:
        connections = cmds.listConnections(node, source=True, destination=True) or []
        for connected in connections:
            if connected in constraint_nodes:
                related.add(connected)
                continue
            if cmds.nodeType(connected).endswith("Constraint"):
                related.add(connected)
    return related


def _resolve_controller_transform_nodes(ctrl_key, use_full_paths):
    """
    Resolve a controller key from the rig map back to transform DAG nodes.
    """
    if use_full_paths:
        if cmds.objExists(ctrl_key) and cmds.nodeType(ctrl_key) in ("transform", "joint"):
            return [ctrl_key]
        return []

    candidates = cmds.ls(ctrl_key, long=True, type="transform") or []
    resolved = []
    for node in candidates:
        if _is_curve_controller(node) and _is_controller_visible(node):
            resolved.append(node)
    return list(dict.fromkeys(resolved))


def _collect_joints_near_transform(node):
    """
    Collect joints at/under and above a driven transform when possible.
    """
    joints = set()
    if not cmds.objExists(node):
        return joints

    if cmds.nodeType(node) == "joint":
        joints.add(node)
        return joints

    for joint in cmds.listRelatives(node, allDescendents=True, type="joint", fullPath=True) or []:
        joints.add(joint)

    parent = cmds.listRelatives(node, parent=True, fullPath=True) or []
    while parent:
        parent_node = parent[0]
        if cmds.nodeType(parent_node) == "joint":
            joints.add(parent_node)
            break
        parent = cmds.listRelatives(parent_node, parent=True, fullPath=True) or []

    return joints


def _would_create_parent_cycle(child_ctrl, new_parent_ctrl, controller_parent):
    cursor = new_parent_ctrl
    while cursor:
        if cursor == child_ctrl:
            return True
        cursor = controller_parent.get(cursor)
    return False


def _build_roots_from_parent_map(controller_parent):
    all_controllers = set(controller_parent.keys())
    for parent in controller_parent.values():
        if parent:
            all_controllers.add(parent)

    children_map = {ctrl: [] for ctrl in all_controllers}
    for child, parent in controller_parent.items():
        if parent and parent in children_map:
            children_map[parent].append(child)

    def _build_node(ctrl):
        return {
            "controller": ctrl,
            "children": [_build_node(child) for child in sorted(children_map.get(ctrl, []))],
        }

    roots = []
    for ctrl in sorted(all_controllers):
        parent = controller_parent.get(ctrl)
        if not parent:
            roots.append(_build_node(ctrl))

    return roots