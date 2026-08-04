"""条件表达式解析器

支持的表达式语法：
- 比较: == != > < >= <=
- 逻辑: AND OR NOT (括号)
- 包含: X CONTAINS Y
- 空值: X IS NULL / X IS NOT NULL
- 正则: X MATCHES 'regex'

实现流程：
1. 变量替换：把 ${...} 替换为 Python 字面量
2. 关键字转换：AND→and, OR→or, NOT→not, CONTAINS→in（交换操作数）,
   IS NULL→is None, MATCHES→__matches__(...)
3. 用 ast.parse 解析后由 _SafeEvaluator 求值（不使用 eval()）
"""

from __future__ import annotations

import ast
import operator
import re
from typing import Any

from src.core.logger import get_logger
from src.workflow.context import WorkflowContext

logger = get_logger("workflow.condition")

# 变量引用正则
_VAR_PATTERN = re.compile(r"\$\{[^}]+\}")

# 比较运算符映射
_COMPARE_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.Gt: operator.gt,
    ast.LtE: operator.le,
    ast.GtE: operator.ge,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}

# 允许的标识符白名单
_ALLOWED_NAMES = {"True": True, "False": False, "None": None}


def evaluate_condition(expr: str, ctx: WorkflowContext) -> bool:
    """安全求值条件表达式，返回布尔结果。

    Args:
        expr: 条件表达式字符串，例如 "${mail.subject} CONTAINS '审批' AND ${classification.priority} == '紧急'"
        ctx: 流程上下文。

    Returns:
        布尔结果；表达式解析失败时返回 False，不抛异常。
    """
    if not expr or not isinstance(expr, str):
        return False
    try:
        substituted = _substitute_variables(expr, ctx)
        python_expr = _transform_operators(substituted)
        tree = ast.parse(python_expr, mode="eval")
        evaluator = _SafeEvaluator()
        result = evaluator.visit(tree)
        return bool(result)
    except Exception as exc:
        logger.warning(f"条件表达式求值失败 expr={expr!r}: {exc}")
        return False


# ----------------------------------------------------------------------
# 变量替换
# ----------------------------------------------------------------------
def _substitute_variables(expr: str, ctx: WorkflowContext) -> str:
    """把 ${...} 替换为 Python 字面量形式。"""

    def replace(match: re.Match) -> str:
        placeholder = match.group(0)
        value = ctx.get(placeholder)
        return _to_python_literal(value)

    return _VAR_PATTERN.sub(replace, expr)


def _to_python_literal(value: Any) -> str:
    """把 Python 值转为可被 ast.parse 的字符串字面量。"""
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return repr(value)
    # list/dict 等用 repr 保证可解析
    try:
        return repr(value)
    except Exception:
        return "None"


# ----------------------------------------------------------------------
# 关键字转换（基于 token 级处理，避免误伤字符串字面量）
# ----------------------------------------------------------------------
def _tokenize(expr: str) -> list[str]:
    """简单分词器：保留引号字符串、括号、运算符与标识符。"""
    tokens: list[str] = []
    i = 0
    n = len(expr)
    while i < n:
        c = expr[i]
        if c.isspace():
            i += 1
            continue
        if c in "()":
            tokens.append(c)
            i += 1
            continue
        if c in "\"'":
            quote = c
            j = i + 1
            while j < n and expr[j] != quote:
                if expr[j] == "\\" and j + 1 < n:
                    j += 2
                else:
                    j += 1
            tokens.append(expr[i : min(j + 1, n)])
            i = j + 1
            continue
        # 两字符运算符
        if expr[i : i + 2] in ("==", "!=", ">=", "<="):
            tokens.append(expr[i : i + 2])
            i += 2
            continue
        if c in "<>":
            tokens.append(c)
            i += 1
            continue
        # 标识符 / 数字 / 负号
        j = i
        while j < n and (expr[j].isalnum() or expr[j] in "._-"):
            j += 1
        if j == i:
            tokens.append(c)
            i += 1
        else:
            tokens.append(expr[i:j])
            i = j
    return tokens


def _transform_operators(expr: str) -> str:
    """把流程 DSL 关键字转换为合法 Python 表达式。"""
    tokens = _tokenize(expr)
    output: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        upper = tok.upper()
        if upper == "CONTAINS":
            lhs = output.pop() if output else "None"
            rhs = tokens[i + 1] if i + 1 < len(tokens) else "None"
            output.append(f"(({rhs}) in ({lhs}))")
            i += 2
        elif upper == "MATCHES":
            lhs = output.pop() if output else "''"
            rhs = tokens[i + 1] if i + 1 < len(tokens) else "''"
            output.append(f"__matches__(({lhs}), ({rhs}))")
            i += 2
        elif upper == "IS":
            if (
                i + 2 < len(tokens)
                and tokens[i + 1].upper() == "NOT"
                and tokens[i + 2].upper() == "NULL"
            ):
                output.append("is not")
                output.append("None")
                i += 3
            elif i + 1 < len(tokens) and tokens[i + 1].upper() == "NULL":
                output.append("is")
                output.append("None")
                i += 2
            else:
                output.append(tok)
                i += 1
        elif upper == "AND":
            output.append("and")
            i += 1
        elif upper == "OR":
            output.append("or")
            i += 1
        elif upper == "NOT":
            output.append("not")
            i += 1
        else:
            output.append(tok)
            i += 1
    return " ".join(output)


# ----------------------------------------------------------------------
# 安全 AST 求值器
# ----------------------------------------------------------------------
class _SafeEvaluator(ast.NodeVisitor):
    """白名单式 AST 求值器，禁止任何属性访问、下标、动态调用。"""

    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> Any:
        return node.value

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id in _ALLOWED_NAMES:
            return _ALLOWED_NAMES[node.id]
        raise ValueError(f"不允许的标识符: {node.id}")

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:
        if isinstance(node.op, ast.And):
            for value_node in node.values:
                if not self.visit(value_node):
                    return False
            return True
        if isinstance(node.op, ast.Or):
            for value_node in node.values:
                if self.visit(value_node):
                    return True
            return False
        raise ValueError(f"不支持的逻辑运算: {type(node.op).__name__}")

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        if isinstance(node.op, ast.Not):
            return not self.visit(node.operand)
        if isinstance(node.op, ast.USub):
            return -self.visit(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +self.visit(node.operand)
        raise ValueError(f"不支持的一元运算: {type(node.op).__name__}")

    def visit_Compare(self, node: ast.Compare) -> Any:
        left = self.visit(node.left)
        for op_node, comparator in zip(node.ops, node.comparators):
            right = self.visit(comparator)
            op_func = _COMPARE_OPS.get(type(op_node))
            if op_func is None:
                raise ValueError(f"不支持的比较运算: {type(op_node).__name__}")
            try:
                if not op_func(left, right):
                    return False
            except TypeError:
                # 类型不兼容的比较直接判为 False
                return False
            left = right
        return True

    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Name) and node.func.id == "__matches__":
            args = [self.visit(a) for a in node.args]
            if len(args) != 2:
                raise ValueError("__matches__ 需要 2 个参数")
            target, pattern = args
            if target is None:
                return False
            try:
                return re.search(str(pattern), str(target)) is not None
            except re.error as exc:
                logger.warning(f"正则表达式非法: {pattern!r}: {exc}")
                return False
        raise ValueError("仅允许调用 __matches__")

    def generic_visit(self, node: ast.AST) -> Any:
        raise ValueError(f"不支持的表达式节点: {type(node).__name__}")
