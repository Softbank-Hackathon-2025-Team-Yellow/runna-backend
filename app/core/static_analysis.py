import ast
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List


class SecurityAnalyzer:
    DANGEROUS_IMPORTS = [
        "os",           # 시스템 접근
        "subprocess",
        "sys",
        "shutil",
        "socket",       # 네트워크
        "urllib",
        "requests",
        "http",
        "eval",         # 임의 코드 실행 가능한 직렬화
        "exec",
        "compile",
        "open",
        "__import__",
        "urllib3",
        "ftplib",
        "telnetlib",
        "smtplib",
        "pickle",
        "marshal",
        "shelve",
    ]

    DANGEROUS_BUILTINS = [
        "eval",         # 동적 코드 실행
        "exec",
        "compile",
        "open",         # I/O
        "input",
        "__import__",   # 동적 import
        "globals",
        "locals",
        "vars",
        "dir",
        "getattr",      # 동적 속성 접근
        "setattr",
        "delattr",
        "hasattr",
        "memoryview",
        "breakpoint",
    ]

    DANGEROUS_ATTRIBUTES = [
        "__code__",     # 내부 접근
        "__globals__",
        "__builtins__",
        "__class__",    # 클래스 계층 탐색
        "__bases__",
        "__subclasses__",
        "__dict__",
        "__module__",
        "__name__",
        "func_globals",
        "func_code",
        "gi_frame",
        "gi_code",
        "co_code",
    ]

    # Code quality limits
    MAX_FUNCTION_COMPLEXITY = 100  # Max AST nodes in a function
    MAX_NESTING_DEPTH = 5  # Max nesting depth for control structures
    MAX_FUNCTION_LENGTH = 50  # Max lines in a function

    def analyze_python_code(self, code: str) -> Dict[str, Any]:
        try:
            tree = ast.parse(code)
            violations = self._find_violations(tree)

            # Add code quality warnings (non-blocking)
            warnings = self._check_code_quality(tree)

            # Violations: 보안 위험 -> 실행 차단
            # Warnings: 코드 품질 문제 -> 실행 허용
            return {
                "is_safe": len(violations) == 0,
                "violations": violations,
                "warnings": warnings,
                "imports": self._extract_imports(tree),
                "functions": self._extract_functions(tree),
            }
        except SyntaxError as e:
            return {
                "is_safe": False,
                "violations": [f"Syntax error: {str(e)}"],
                "warnings": [],
                "imports": [],
                "functions": [],
            }

    def _is_code_safe(self, tree: ast.AST) -> bool:
        violations = self._find_violations(tree)
        return len(violations) == 0

    def _find_violations(self, tree: ast.AST) -> List[str]:
        violations = []

        for node in ast.walk(tree):
            # Check dangerous imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # Check if the base module or any part matches dangerous imports
                    module_parts = alias.name.split(".")
                    for part in module_parts:
                        if part in self.DANGEROUS_IMPORTS:
                            violations.append(f"Dangerous import: {alias.name}")
                            break

            # Check dangerous import from
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    # Check if the base module or any part matches dangerous imports
                    module_parts = node.module.split(".")
                    for part in module_parts:
                        if part in self.DANGEROUS_IMPORTS:
                            violations.append(f"Dangerous import from: {node.module}")
                            break

            # Check dangerous builtin calls
            elif isinstance(node, ast.Call):
                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id in self.DANGEROUS_BUILTINS
                ):
                    violations.append(f"Dangerous builtin function: {node.func.id}")

            # Check dangerous names (like __builtins__)
            elif isinstance(node, ast.Name):
                if node.id in self.DANGEROUS_ATTRIBUTES:
                    violations.append(f"Dangerous name reference: {node.id}")

            # Check dangerous attribute access
            elif isinstance(node, ast.Attribute):
                if node.attr in self.DANGEROUS_ATTRIBUTES:
                    violations.append(
                        f"Dangerous attribute access: {node.attr}"
                    )

            # Check subscript access to dangerous attributes (e.g., obj['__code__'])
            elif isinstance(node, ast.Subscript):
                if isinstance(node.slice, ast.Constant):
                    if node.slice.value in self.DANGEROUS_ATTRIBUTES:
                        violations.append(
                            f"Dangerous subscript access: [{node.slice.value}]"
                        )

            # Check with statements for file operations
            elif isinstance(node, ast.With):
                for item in node.items:
                    if isinstance(item.context_expr, ast.Call):
                        if (
                            isinstance(item.context_expr.func, ast.Name)
                            and item.context_expr.func.id == "open"
                        ):
                            violations.append("File access not allowed: open()")

            # Check infinite loops (basic heuristic)
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
        """
        무한 루프 감지. 명확한 케이스만 탐지
        """
        # While True without break
        if isinstance(node, ast.While):
            if isinstance(node.test, ast.Constant) and node.test.value is True:
                # Check if there's a break statement in the loop body
                has_break = False
                for child in ast.walk(node):
                    if isinstance(child, ast.Break):
                        has_break = True
                        break
                if not has_break:
                    return True

        return False

    def _check_code_quality(self, tree: ast.AST) -> List[str]:
        """
        Check code quality and return warnings (non-blocking).
        These are suggestions, not violations.
        """
        warnings = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check function complexity
                complexity_warning = self._check_function_complexity(node)
                if complexity_warning:
                    warnings.append(complexity_warning)

                # Check function length
                length_warning = self._check_function_length(node)
                if length_warning:
                    warnings.append(length_warning)

                # Check nesting depth
                depth_warning = self._check_nesting_depth(node)
                if depth_warning:
                    warnings.append(depth_warning)

        return warnings

    def _check_function_complexity(self, func_node: ast.FunctionDef) -> str:
        """
        함수 복잡도 (AST 노드 개수)
        노드가 많다 == 코드가 복잡하다 라고 가정
        """
        node_count = sum(1 for _ in ast.walk(func_node))

        if node_count > self.MAX_FUNCTION_COMPLEXITY:
            return (
                f"Function '{func_node.name}' is too complex "
                f"({node_count} nodes, max {self.MAX_FUNCTION_COMPLEXITY})"
            )
        return ""

    def _check_function_length(self, func_node: ast.FunctionDef) -> str:
        """
        함수 길이 제한
        임의로 50줄 제한
        """
        if hasattr(func_node, "end_lineno") and hasattr(func_node, "lineno"):
            length = func_node.end_lineno - func_node.lineno

            if length > self.MAX_FUNCTION_LENGTH:
                return (
                    f"Function '{func_node.name}' is too long "
                    f"({length} lines, max {self.MAX_FUNCTION_LENGTH})"
                )
        return ""

    def _check_nesting_depth(self, func_node: ast.FunctionDef) -> str:
        """
        중첩 깊이 제한
        """
        max_depth = self._calculate_max_nesting_depth(func_node.body)

        if max_depth > self.MAX_NESTING_DEPTH:
            return (
                f"Function '{func_node.name}' has too deep nesting "
                f"(depth {max_depth}, max {self.MAX_NESTING_DEPTH})"
            )
        return ""

    def _calculate_max_nesting_depth(
        self, body: List[ast.stmt], current_depth: int = 0
    ) -> int:
        """
        재귀적으로 깊이 계산
        """
        max_depth = current_depth

        for node in body:
            if isinstance(
                node,
                (
                    ast.For,
                    ast.While,
                    ast.If,
                    ast.With,
                    ast.Try,
                    ast.ExceptHandler,
                ),
            ):
                # Get the body of the control structure
                node_body = []
                if hasattr(node, "body"):
                    node_body = node.body
                if hasattr(node, "orelse") and node.orelse:
                    node_body.extend(node.orelse)

                # Recursively check nested depth
                nested_depth = self._calculate_max_nesting_depth(
                    node_body, current_depth + 1
                )
                max_depth = max(max_depth, nested_depth)

        return max_depth

    def analyze_nodejs_code(self, code: str) -> Dict[str, Any]:
        """
        Analyze Node.js/JavaScript code using Esprima.
        서브 프로세스로 Node.js 실행하여 구성.
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

            # Run Node.js analyzer with subprocess / 프로세스가 추가 생성된다.
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
