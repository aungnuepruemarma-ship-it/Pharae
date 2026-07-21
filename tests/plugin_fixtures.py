"""Fixture plugin entrypoints for the plugin-system tests."""

CALLS = []


def _calc_handler(task, ctx):
    CALLS.append(("calc.local", task.id))
    return {"sum": sum(task.payload.get("numbers", [])), "by": "calc.local"}


def _calc_a_handler(task, ctx):
    CALLS.append(("calc.a", task.id))
    return {"by": "calc.a"}


def _calc_b_handler(task, ctx):
    CALLS.append(("calc.b", task.id))
    return {"by": "calc.b"}


def setup_calc():
    return {"calc.local": _calc_handler}


def setup_calc_v2():
    return {"calc.local": _calc_handler, "calc.stats": _calc_a_handler}


def setup_a():
    return {"calc.a": _calc_a_handler}


def setup_b():
    return {"calc.b": _calc_b_handler}


def setup_broken():
    raise RuntimeError("plugin exploded during setup")


def setup_wrong_keys():
    return {"not.the.capability": _calc_handler}


def setup_not_a_dict():
    return ["not", "a", "dict"]
