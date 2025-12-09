"""
Calculator tool for safe mathematical expression evaluation.

Uses Python's ast module to safely evaluate mathematical expressions
without allowing arbitrary code execution.

Supported operations:
- Basic arithmetic: +, -, *, /, //, %, **
- Functions: abs, round, min, max, sum
- Constants: pi, e
"""

import ast
import operator
import math
from typing import Dict, Any
from .base import BaseTool, ToolResult, ToolError


class CalculatorTool(BaseTool):
    """Safe calculator for mathematical expressions."""

    # Allowed operators
    OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    # Allowed functions
    FUNCTIONS = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "pow": pow,
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
        "exp": math.exp,
        "ceil": math.ceil,
        "floor": math.floor,
    }

    # Constants
    CONSTANTS = {
        "pi": math.pi,
        "e": math.e,
    }

    def __init__(self):
        """Initialize calculator."""
        super().__init__()
        self.name = "calculator"

    async def execute(self, expression: str) -> ToolResult:
        """
        Evaluate a mathematical expression safely.

        Args:
            expression: Math expression as string (e.g., "2 + 2", "sqrt(16)")

        Returns:
            ToolResult with calculated value or error
        """
        if not expression or not isinstance(expression, str):
            raise ToolError("Expression must be a non-empty string")

        # Clean the expression
        expression = expression.strip()

        try:
            # Parse the expression into an AST
            tree = ast.parse(expression, mode='eval')

            # Evaluate safely
            result = self._eval_node(tree.body)

            # Format result nicely
            if isinstance(result, float):
                # Round to 10 decimal places to avoid floating point artifacts
                result = round(result, 10)
                # Convert to int if it's a whole number
                if result.is_integer():
                    result = int(result)

            return ToolResult(
                success=True,
                data=result,
                metadata={
                    "expression": expression,
                    "result_type": type(result).__name__
                }
            )

        except ToolError:
            raise
        except SyntaxError as e:
            raise ToolError(f"Invalid syntax: {str(e)}")
        except (ValueError, ArithmeticError, OverflowError) as e:
            raise ToolError(f"Math error: {str(e)}")
        except Exception as e:
            raise ToolError(f"Evaluation error: {str(e)}")

    def _eval_node(self, node):
        """
        Recursively evaluate AST node safely.

        Args:
            node: AST node

        Returns:
            Evaluated value

        Raises:
            ToolError: If node type is not allowed
        """
        # Numbers
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ToolError(f"Unsupported constant type: {type(node.value)}")

        # Binary operations (+ - * / etc.)
        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in self.OPERATORS:
                raise ToolError(f"Operator {op_type.__name__} not allowed")

            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            return self.OPERATORS[op_type](left, right)

        # Unary operations (+ -)
        if isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in self.OPERATORS:
                raise ToolError(f"Operator {op_type.__name__} not allowed")

            operand = self._eval_node(node.operand)
            return self.OPERATORS[op_type](operand)

        # Function calls
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ToolError("Only named functions are allowed")

            func_name = node.func.id
            if func_name not in self.FUNCTIONS:
                raise ToolError(
                    f"Function '{func_name}' not allowed. "
                    f"Available: {', '.join(self.FUNCTIONS.keys())}"
                )

            # Evaluate arguments
            args = [self._eval_node(arg) for arg in node.args]

            # Call function
            try:
                return self.FUNCTIONS[func_name](*args)
            except (TypeError, ValueError) as e:
                raise ToolError(f"Error calling {func_name}: {str(e)}")

        # Variable/constant names
        if isinstance(node, ast.Name):
            if node.id in self.CONSTANTS:
                return self.CONSTANTS[node.id]
            raise ToolError(
                f"Variable '{node.id}' not allowed. "
                f"Available constants: {', '.join(self.CONSTANTS.keys())}"
            )

        # Unsupported node type
        raise ToolError(f"Expression type '{type(node).__name__}' not allowed")

    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get JSON schema for calculator parameters."""
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": (
                        "Mathematical expression to evaluate. "
                        "Supports: +, -, *, /, //, %, **, sqrt, sin, cos, tan, log, "
                        "abs, round, min, max, sum, pi, e"
                    ),
                }
            },
            "required": ["expression"],
        }

    def get_description(self) -> str:
        """Get human-readable description."""
        return (
            "Safely evaluates mathematical expressions. "
            "Supports arithmetic operations (+, -, *, /, **, %), "
            "common math functions (sqrt, sin, cos, log, etc.), "
            "and constants (pi, e). Cannot execute arbitrary code."
        )
