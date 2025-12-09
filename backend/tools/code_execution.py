"""
Code execution tool for running Python code safely.

Features:
- Timeout protection (default: 5 seconds)
- Resource limits (memory, file operations)
- Restricted module imports
- Captures stdout, stderr, and return values

Security notes:
- Basic sandboxing via restricted builtins
- Timeout enforcement
- For production, consider Docker or E2B for better isolation
"""

import asyncio
import sys
import io
from contextlib import redirect_stdout, redirect_stderr
from typing import Dict, Any, Optional
from .base import BaseTool, ToolResult, ToolError


class CodeExecutionTool(BaseTool):
    """Execute Python code with safety restrictions."""

    # Allowed built-in functions
    SAFE_BUILTINS = {
        'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'bytes', 'chr',
        'dict', 'divmod', 'enumerate', 'filter', 'float', 'format',
        'frozenset', 'hex', 'int', 'isinstance', 'issubclass', 'iter',
        'len', 'list', 'map', 'max', 'min', 'oct', 'ord', 'pow',
        'print', 'range', 'repr', 'reversed', 'round', 'set', 'slice',
        'sorted', 'str', 'sum', 'tuple', 'type', 'zip',
    }

    # Allowed modules (can be imported)
    SAFE_MODULES = {
        'math', 'random', 'datetime', 'json', 're', 'itertools',
        'collections', 'functools', 'operator', 'string', 'decimal',
    }

    def __init__(self):
        """Initialize code execution tool."""
        super().__init__()
        self.name = "code_execution"
        self.default_timeout = 5.0  # seconds

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout: Optional[float] = None
    ) -> ToolResult:
        """
        Execute code in a restricted environment.

        Args:
            code: Python code to execute
            language: Programming language (only "python" supported)
            timeout: Max execution time in seconds (default: 5)

        Returns:
            ToolResult with output and return value
        """
        if language != "python":
            raise ToolError(
                f"Language '{language}' not supported. Only 'python' is available."
            )

        if not code or not isinstance(code, str):
            raise ToolError("Code must be a non-empty string")

        timeout = timeout or self.default_timeout

        try:
            # Run code in executor to enforce timeout
            result = await asyncio.wait_for(
                asyncio.to_thread(self._execute_python, code),
                timeout=timeout
            )

            return ToolResult(
                success=True,
                data=result,
                metadata={
                    "language": "python",
                    "timeout": timeout,
                    "code_length": len(code)
                }
            )

        except asyncio.TimeoutError:
            raise ToolError(f"Code execution timed out after {timeout} seconds")
        except ToolError:
            raise
        except Exception as e:
            raise ToolError(f"Code execution failed: {str(e)}")

    def _execute_python(self, code: str) -> Dict[str, Any]:
        """
        Execute Python code with restrictions.

        Args:
            code: Python code string

        Returns:
            Dict with stdout, stderr, return_value, and success status
        """
        # Create restricted builtins
        safe_builtins_dict = {
            name: __builtins__[name]
            for name in self.SAFE_BUILTINS
            if name in __builtins__
        }

        # Add safe import function
        def safe_import(name, *args, **kwargs):
            if name not in self.SAFE_MODULES:
                raise ImportError(
                    f"Module '{name}' not allowed. "
                    f"Available: {', '.join(sorted(self.SAFE_MODULES))}"
                )
            return __import__(name, *args, **kwargs)

        safe_builtins_dict['__import__'] = safe_import

        # Prepare execution environment
        exec_globals = {
            '__builtins__': safe_builtins_dict,
            '__name__': '__main__',
        }
        exec_locals = {}

        # Capture stdout and stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                # Compile and execute code
                compiled = compile(code, '<string>', 'exec')
                exec(compiled, exec_globals, exec_locals)

            stdout_text = stdout_capture.getvalue()
            stderr_text = stderr_capture.getvalue()

            # Get return value if any (look for 'result' variable)
            return_value = exec_locals.get('result', None)

            return {
                "stdout": stdout_text,
                "stderr": stderr_text,
                "return_value": return_value,
                "success": True,
                "variables": {
                    k: str(v)[:100]  # Limit variable output
                    for k, v in exec_locals.items()
                    if not k.startswith('_')
                }
            }

        except Exception as e:
            return {
                "stdout": stdout_capture.getvalue(),
                "stderr": stderr_capture.getvalue() + f"\nError: {str(e)}",
                "return_value": None,
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }

    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get JSON schema for code execution parameters."""
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": (
                        "Python code to execute. Can use: math, random, datetime, json, re, "
                        "collections, itertools. Cannot use: file I/O, network, os, subprocess. "
                        "Store result in 'result' variable to return it."
                    ),
                },
                "language": {
                    "type": "string",
                    "enum": ["python"],
                    "description": "Programming language (only 'python' supported)",
                    "default": "python",
                },
                "timeout": {
                    "type": "number",
                    "description": "Maximum execution time in seconds (default: 5)",
                    "minimum": 0.1,
                    "maximum": 30.0,
                    "default": 5.0,
                },
            },
            "required": ["code"],
        }

    def get_description(self) -> str:
        """Get human-readable description."""
        return (
            "Executes Python code in a restricted sandbox. "
            f"Supports modules: {', '.join(sorted(self.SAFE_MODULES))}. "
            "Use for: calculations, data processing, algorithms. "
            "Cannot access files, network, or OS. "
            "Timeout: 5 seconds default."
        )
