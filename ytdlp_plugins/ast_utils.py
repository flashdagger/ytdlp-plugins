import ast
from contextlib import suppress
from importlib import import_module
from inspect import getsourcelines, getsourcefile
from typing import Dict, Any, List


# from yt_dlp.extractor.youtube import YoutubeIE


def dict_info(node: ast.Dict) -> Dict[str, Any]:
    info = {}
    for key, value in zip(node.keys, node.values):
        with suppress(AssertionError):
            assert isinstance(key, ast.Constant)
            info[key.value] = value.value if isinstance(value, ast.Constant) else value

    return info


def dict_lines(node: ast.Dict) -> Dict[str, int]:
    info = {}
    for key, value in zip(node.keys, node.values):
        with suppress(AssertionError):
            assert isinstance(key, ast.Constant)
            info[key.value] = value.lineno

    return info


def list_info(node: ast.List, **defaults) -> List[Dict[str, Any]]:
    data = []
    for child in ast.iter_child_nodes(node):
        info: Dict[str, Any] = {}
        if isinstance(child, ast.Dict):
            info["lineno"] = child.lineno
            const_info = dict_info(child)
            for key, default in defaults.items():
                value = const_info.get(key, default)
                if isinstance(value, ast.List):
                    _defaults = default if isinstance(default, dict) else {}
                    value = list_info(value, **_defaults)
                info[key] = value
            info_dict = const_info.get("info_dict")
            if isinstance(info_dict, ast.Dict):
                info["info_dict"] = dict_lines(info_dict)
            data.append(info)
    return data


def unlazyify(cls: type) -> type:
    with suppress(AttributeError, ImportError):
        actual_module = getattr(cls, "_module")
        module = import_module(actual_module)
        cls = getattr(module, cls.__name__)
    return cls


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


def get_test_lineno(cls: type, index: int, onlymatching=False) -> Dict[str, Any]:
    cls = unlazyify(cls)
    source_file = getsourcefile(cls)
    assert isinstance(source_file, str)
    source_lines, line_number = getsourcelines(cls)
    ast_obj = ast.parse("".join(source_lines))
    ast.increment_lineno(ast_obj, n=line_number - 1)

    test_node = find_assignment(ast_obj.body[0], lambda name: name.startswith("_TEST"))
    if not isinstance(test_node, ast.List):
        return {"file": source_file, "lineno": line_number}

    data = list_info(test_node, only_matching=False, playlist=None)

    data = [item for item in data if item.get("only_matching", False) is onlymatching]
    if index >= len(data):
        index = len(data) - 1
    item = data[index]
    item["file"] = source_file
    return item
