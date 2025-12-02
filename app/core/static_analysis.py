import ast
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List


class SecurityAnalyzer:
    DANGEROUS_IMPORTS = [
        "os",
        "subprocess",
        "sys",
        "shutil",
        "socket",
        "urllib",
        "requests",
        "eval",
        "exec",
        "compile",
        "open",
        "__import__",
    ]

    DANGEROUS_BUILTINS = [
        "eval",
        "exec",
        "compile",
        "open",
        "input",
        "__import__",
        "globals",
        "locals",
        "vars",
        "dir",
        "getattr",
        "setattr",
        "delattr",
    ]

    def analyze_python_code(self, code: str) -> Dict[str, Any]:
        try:
            tree = ast.parse(code)
            return {
                "is_safe": self._is_code_safe(tree),
                "violations": self._find_violations(tree),
                "imports": self._extract_imports(tree),
                "functions": self._extract_functions(tree),
            }
        except SyntaxError as e:
            return {
                "is_safe": False,
                "violations": [f"Syntax error: {str(e)}"],
                "imports": [],
                "functions": [],
            }

    def _is_code_safe(self, tree: ast.AST) -> bool:
        violations = self._find_violations(tree)
        return len(violations) == 0

    def _find_violations(self, tree: ast.AST) -> List[str]:
        violations = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in self.DANGEROUS_IMPORTS:
                        violations.append(f"Dangerous import: {alias.name}")

            elif isinstance(node, ast.ImportFrom):
                if node.module in self.DANGEROUS_IMPORTS:
                    violations.append(f"Dangerous import from: {node.module}")

            elif isinstance(node, ast.Call):
                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id in self.DANGEROUS_BUILTINS
                ):
                    violations.append(f"Dangerous builtin function: {node.func.id}")

            elif isinstance(node, ast.While) or isinstance(node, ast.For):
                if self._might_be_infinite_loop(node):
                    violations.append("Potential infinite loop detected")

        return violations

    def _extract_imports(self, tree: ast.AST) -> List[str]:
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        return imports

    def _extract_functions(self, tree: ast.AST) -> List[str]:
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append(node.name)
        return functions

    def _might_be_infinite_loop(self, node: ast.AST) -> bool:
        return False

    def analyze_nodejs_code(self, code: str) -> Dict[str, Any]:
        """
        Analyze Node.js/JavaScript code using Esprima.
        Uses subprocess to call Node.js analyzer script.
        """
        try:
            # Get path to js_analyzer.js
            current_dir = Path(__file__).parent
            analyzer_script = current_dir / "analyzers" / "js_analyzer.js"

            if not analyzer_script.exists():
                return {
                    "is_safe": False,
                    "violations": [
                        "JavaScript analyzer script not found. Please ensure js_analyzer.js is installed."
                    ],
                    "imports": [],
                    "functions": [],
                }

            # Run Node.js analyzer with subprocess
            result = subprocess.run(
                ["node", str(analyzer_script)],
                input=code,
                capture_output=True,
                text=True,
                timeout=5,  # 5 second timeout
            )

            # Parse JSON output
            try:
                analysis_result = json.loads(result.stdout)
                return analysis_result
            except json.JSONDecodeError:
                # If JSON parsing fails, check stderr
                error_msg = result.stderr if result.stderr else "Unknown error"
                return {
                    "is_safe": False,
                    "violations": [f"Analysis error: {error_msg}"],
                    "imports": [],
                    "functions": [],
                }

        except subprocess.TimeoutExpired:
            return {
                "is_safe": False,
                "violations": ["Code analysis timeout (exceeded 5 seconds)"],
                "imports": [],
                "functions": [],
            }
        except FileNotFoundError:
            return {
                "is_safe": False,
                "violations": [
                    "Node.js not found. Please ensure Node.js is installed and in PATH."
                ],
                "imports": [],
                "functions": [],
            }
        except Exception as e:
            return {
                "is_safe": False,
                "violations": [f"Unexpected error during analysis: {str(e)}"],
                "imports": [],
                "functions": [],
            }


analyzer = SecurityAnalyzer()
