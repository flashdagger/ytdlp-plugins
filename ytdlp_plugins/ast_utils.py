import ast
import builtins
from contextlib import suppress
from inspect import getsourcelines, getsourcefile, getmro
from typing import Dict, Any, List, Tuple

from .utils import unlazify

_CACHE: Dict[type, Tuple[str, List[Dict[str, Any]]]] = {}

AST_TYPE_MAP = {
    ast.Constant: lambda obj: obj.value,
    ast.NameConstant: lambda obj: obj.value,
    ast.Str: lambda obj: obj.s,
    ast.Num: lambda obj: obj.n,
    type(None): lambda obj: obj,  # for type completion
}


def dict_info(node: ast.Dict, **defaults) -> Dict[str, Any]:
    line_info = {"_self": node.lineno}
    info = {"_lineno": line_info}
    for key, value in zip(node.keys, node.values):
        key_cls, value_cls = type(key), type(value)
        key_value = AST_TYPE_MAP[key_cls](key) if key_cls in AST_TYPE_MAP else key

        if value_cls in AST_TYPE_MAP:
            actual_value = AST_TYPE_MAP[value_cls](value)
        elif isinstance(value, ast.Dict):
            _defaults = defaults.get(key_value, {})
            actual_value = dict_info(value, **_defaults)
        elif isinstance(value, ast.List):
            actual_value = list_info(value, **defaults)
        elif isinstance(value, ast.Name):
            actual_value = getattr(builtins, value.id, value.id)
        else:
            actual_value = value
        line_info[key_value] = value.lineno
        info[key_value] = actual_value

    return info


def list_info(node: ast.List, **defaults) -> List[Dict[str, Any]]:
    data = []
    for child in ast.iter_child_nodes(node):
        if not isinstance(child, ast.Dict):
            continue
        info = dict_info(child, **defaults)
        data.append(info)
    return data


def find_assignment(node, name_predicate):
    for child in ast.iter_child_nodes(node):
        with suppress(AssertionError):
            assert isinstance(child, ast.Assign)
            left_expr = child.targets[0]
            assert isinstance(left_expr, ast.Name)
            name = left_expr.id
            assert name_predicate(name)
            return child.value
    return None


def get_line_infos(test_cls: type) -> Tuple[str, List[Dict[str, Any]]]:
    test_attributes = {"_TESTS", "_TEST"}
    cls = unlazify(test_cls)
    for cls in getmro(cls):
        if not test_attributes & set(cls.__dict__.keys()):
            continue
        source_lines, line_number = getsourcelines(cls)
        ast_obj = ast.parse("".join(source_lines))
        ast.increment_lineno(ast_obj, n=line_number - 1)
        test_node = find_assignment(
            ast_obj.body[0], lambda name: name in test_attributes
        )
        break
    else:
        test_node = None
        line_number = 0

    source_file = str(getsourcefile(cls))

    if isinstance(test_node, ast.List):
        data = list_info(test_node)
    elif isinstance(test_node, ast.Dict):
        data = [dict_info(test_node)]
    else:
        data = [{"_file": source_file, "_lineno": {"_self": line_number}}]

    return source_file, data


def get_test_lineno(cls: type, index: int) -> Dict[str, Any]:
    if cls in _CACHE:
        source_filename, line_infos = _CACHE[cls]
    else:
        source_filename, line_infos = get_line_infos(cls)
        _CACHE[cls] = source_filename, line_infos

    if index >= len(line_infos):
        index = len(line_infos) - 1

    info = line_infos[index]
    info["_file"] = source_filename

    return info
