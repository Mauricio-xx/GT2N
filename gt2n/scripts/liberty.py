# SPDX-License-Identifier: BSD-3-Clause
"""Minimal Liberty reader sufficient for the GT2N generator scripts.

It parses the generic Liberty grammar (groups, simple and complex
attributes) into a tree of Group objects. Table values are kept as raw
strings; only the attributes needed for netlist/model generation are
interpreted by the callers.
"""

import re

_TOKEN = re.compile(
    r'\s*(?:'
    r'(?P<comment>/\*.*?\*/|//[^\n]*)'
    r'|(?P<string>"(?:\\.|[^"\\])*")'
    r'|(?P<punct>[{}();:,])'
    r'|(?P<cont>\\\n)'
    r'|(?P<word>[^\s{}();:,"]+)'
    r')', re.S)


class Group:
    __slots__ = ("kind", "args", "attrs", "groups")

    def __init__(self, kind, args):
        self.kind = kind
        self.args = args
        self.attrs = {}
        self.groups = []

    @property
    def name(self):
        return self.args[0] if self.args else None

    def get(self, key, default=None):
        return self.attrs.get(key, default)

    def children(self, kind):
        return [g for g in self.groups if g.kind == kind]

    def __repr__(self):
        return f"Group({self.kind}, {self.args})"


def _tokens(text):
    pos = 0
    end = len(text)
    while pos < end:
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            if text[pos:].strip() == "":
                return
            raise ValueError(f"liberty: cannot tokenize at offset {pos}: {text[pos:pos + 40]!r}")
        pos = m.end()
        if m.group("comment") or m.group("cont"):
            continue
        if m.group("string") is not None:
            yield ("str", m.group("string")[1:-1])
        elif m.group("punct") is not None:
            yield (m.group("punct"), m.group("punct"))
        else:
            yield ("word", m.group("word"))


def parse(text):
    toks = list(_tokens(text))
    i = 0

    def parse_args():
        nonlocal i
        assert toks[i][0] == "("
        i += 1
        args = []
        while toks[i][0] != ")":
            if toks[i][0] != ",":
                args.append(toks[i][1])
            i += 1
        i += 1
        return args

    def parse_body(group):
        nonlocal i
        while i < len(toks):
            kind, val = toks[i]
            if kind == "}":
                i += 1
                return
            if kind == ";":
                i += 1
                continue
            name = val
            i += 1
            if toks[i][0] == ":":
                i += 1
                value = toks[i][1]
                i += 1
                # Expressions such as `a : b + c ;` are joined verbatim.
                while i < len(toks) and toks[i][0] not in (";", "}") and not (
                        toks[i][0] == "word" and i + 1 < len(toks) and toks[i + 1][0] in (":", "(")):
                    value += " " + toks[i][1]
                    i += 1
                group.attrs[name] = value
            elif toks[i][0] == "(":
                args = parse_args()
                if i < len(toks) and toks[i][0] == "{":
                    i += 1
                    child = Group(name, args)
                    parse_body(child)
                    group.groups.append(child)
                else:
                    group.attrs.setdefault(name, args)
            else:
                raise ValueError(f"liberty: unexpected token {toks[i]} after {name}")

    root = Group("root", [])
    parse_body(root)
    libs = root.children("library")
    if not libs:
        raise ValueError("liberty: no library group found")
    return libs[0]


def read(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return parse(fh.read())


# --------------------------------------------------------------------------
# Boolean function translation (Liberty -> Verilog)
# --------------------------------------------------------------------------
_FUNC_TOKEN = re.compile(r"\s*([A-Za-z_][\w\[\]\.]*|[01]|[()!'&*|+^]|\s)")


def liberty_to_verilog(expr):
    """Translate a Liberty function string into a Verilog expression.

    Supports !, ', &, *, |, +, ^, parentheses, constants and implicit AND
    (juxtaposition / space) as defined by the Liberty specification.
    """
    toks = []
    pos = 0
    expr = expr.strip()
    while pos < len(expr):
        m = _FUNC_TOKEN.match(expr, pos)
        if not m:
            raise ValueError(f"cannot parse function {expr!r}")
        pos = m.end()
        tok = m.group(1)
        if not tok.strip():
            toks.append(" ")
        else:
            toks.append(tok)

    # Recursive descent: or := xor ('|' xor)* ; xor := and ('^' and)* ;
    # and := unary (('&'|' '|implicit) unary)* ; unary := '!' unary | atom "'"*
    toks = [t for t in toks]
    idx = 0

    def peek():
        j = idx
        while j < len(toks) and toks[j] == " ":
            j += 1
        return toks[j] if j < len(toks) else None

    def take():
        nonlocal idx
        while idx < len(toks) and toks[idx] == " ":
            idx += 1
        tok = toks[idx]
        idx += 1
        return tok

    def p_or():
        left = p_xor()
        while peek() in ("|", "+"):
            take()
            left = f"({left} | {p_xor()})"
        return left

    def p_xor():
        left = p_and()
        while peek() == "^":
            take()
            left = f"({left} ^ {p_and()})"
        return left

    def p_and():
        left = p_unary()
        while True:
            nxt = peek()
            if nxt in ("&", "*"):
                take()
                left = f"({left} & {p_unary()})"
            elif nxt is not None and (nxt == "(" or nxt == "!" or re.match(r"[A-Za-z_01]", nxt)):
                left = f"({left} & {p_unary()})"  # implicit AND
            else:
                return left

    def p_unary():
        tok = take()
        if tok == "!":
            val = f"~{p_unary()}"
        elif tok == "(":
            val = p_or()
            if take() != ")":
                raise ValueError(f"unbalanced parentheses in {expr!r}")
        elif tok in ("0", "1"):
            val = f"1'b{tok}"
        else:
            val = tok
        while peek() == "'":
            take()
            val = f"~{val}"
        return val

    result = p_or()
    if peek() is not None:
        raise ValueError(f"trailing tokens in function {expr!r}")
    return result
