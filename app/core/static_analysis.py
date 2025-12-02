import ast
from typing import Any, Dict, List

try:
    import esprima
    ESPRIMA_AVAILABLE = True
except ImportError:
    ESPRIMA_AVAILABLE = False


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

    # JavaScript dangerous modules
    DANGEROUS_JS_MODULES = [
        "child_process",
        "fs",
        "fs/promises",
        "net",
        "http",
        "https",
        "os",
        "cluster",
        "dgram",
        "dns",
        "readline",
        "repl",
        "tls",
        "v8",
        "vm",
        "worker_threads",
    ]

    # JavaScript dangerous globals
    DANGEROUS_JS_GLOBALS = [
        "eval",
        "Function",
        "setTimeout",
        "setInterval",
        "setImmediate",
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
        Analyze Node.js/JavaScript code using Python esprima.
        """
        if not ESPRIMA_AVAILABLE:
            return {
                "is_safe": False,
                "violations": [
                    "JavaScript analysis unavailable (esprima not installed)"
                ],
                "imports": [],
                "functions": [],
            }

        try:
            # Try parsing as ES6 module first (supports import/export)
            try:
                ast_tree = esprima.parseModule(code, {"loc": True, "range": True})
            except esprima.Error:
                # If module parsing fails, try as script
                ast_tree = esprima.parseScript(code, {"loc": True, "range": True})

            # Convert AST to dictionary for easier traversal
            ast_dict = ast_tree.toDict()

            # Perform analysis
            violations = []
            imports = []
            functions = []

            self._traverse_js_ast(ast_dict, violations, imports, functions)

            return {
                "is_safe": len(violations) == 0,
                "violations": violations,
                "imports": list(set(imports)),  # Remove duplicates
                "functions": list(set(functions)),
            }

        except esprima.Error as e:
            # Syntax error
            error_message = f"Syntax error: {str(e)}"
            if hasattr(e, "lineNumber") and hasattr(e, "description"):
                error_message = (
                    f"Syntax error at line {e.lineNumber}, "
                    f"column {e.column}: {e.description}"
                )

            return {
                "is_safe": False,
                "violations": [error_message],
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

    def _traverse_js_ast(
        self,
        node: Any,
        violations: List[str],
        imports: List[str],
        functions: List[str],
    ) -> None:
        """
        Recursively traverse JavaScript AST and collect violations.
        """
        if not node or not isinstance(node, dict):
            return

        node_type = node.get("type")

        # Check require() calls
        if node_type == "CallExpression":
            callee = node.get("callee", {})
            if callee.get("type") == "Identifier" and callee.get("name") == "require":
                arguments = node.get("arguments", [])
                if arguments and arguments[0].get("type") == "Literal":
                    module_name = arguments[0].get("value")
                    imports.append(module_name)
                    if module_name in self.DANGEROUS_JS_MODULES:
                        violations.append(
                            f"Dangerous module import: require('{module_name}')"
                        )

            # Check dangerous function calls
            if callee.get("type") == "Identifier":
                func_name = callee.get("name")
                if func_name in self.DANGEROUS_JS_GLOBALS:
                    violations.append(f"Dangerous function call: {func_name}()")

        # Check import declarations
        elif node_type == "ImportDeclaration":
            source = node.get("source", {})
            module_name = source.get("value")
            if module_name:
                imports.append(module_name)
                if module_name in self.DANGEROUS_JS_MODULES:
                    violations.append(
                        f"Dangerous module import: import from '{module_name}'"
                    )

        # Check dynamic imports
        elif node_type == "ImportExpression":
            source = node.get("source", {})
            if source.get("type") == "Literal":
                module_name = source.get("value")
                if module_name:
                    imports.append(module_name)
                    if module_name in self.DANGEROUS_JS_MODULES:
                        violations.append(
                            f"Dangerous module import: import('{module_name}')"
                        )

        # Check Function constructor (indirect eval)
        elif node_type == "NewExpression":
            callee = node.get("callee", {})
            if callee.get("type") == "Identifier" and callee.get("name") == "Function":
                violations.append("Dangerous constructor: new Function()")

        # Extract function declarations
        elif node_type == "FunctionDeclaration":
            func_id = node.get("id")
            if func_id and func_id.get("name"):
                functions.append(func_id["name"])

        # Extract function expressions assigned to variables
        elif node_type == "VariableDeclarator":
            var_id = node.get("id", {})
            init = node.get("init", {})
            if (
                var_id.get("type") == "Identifier"
                and init.get("type") in ["FunctionExpression", "ArrowFunctionExpression"]
            ):
                functions.append(var_id["name"])

        # Check for infinite loops
        elif node_type in ["WhileStatement", "ForStatement"]:
            if self._js_might_be_infinite_loop(node):
                violations.append("Potential infinite loop detected")

        # Recursively traverse child nodes
        for key, value in node.items():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        self._traverse_js_ast(item, violations, imports, functions)
            elif isinstance(value, dict):
                self._traverse_js_ast(value, violations, imports, functions)

    def _js_might_be_infinite_loop(self, node: Dict[str, Any]) -> bool:
        """
        Basic heuristic to detect potential infinite loops in JavaScript.
        """
        node_type = node.get("type")

        # While(true) pattern
        if node_type == "WhileStatement":
            test = node.get("test", {})
            if test.get("type") == "Literal" and test.get("value") is True:
                # Check if there's a break statement in the body
                has_break = self._js_has_break_statement(node.get("body"))
                return not has_break

        # For(;;) pattern
        if node_type == "ForStatement":
            test = node.get("test")
            if test is None or (
                test.get("type") == "Literal" and test.get("value") is True
            ):
                has_break = self._js_has_break_statement(node.get("body"))
                return not has_break

        return False

    def _js_has_break_statement(self, node: Any) -> bool:
        """
        Check if a JavaScript AST node contains a break statement.
        """
        if not node or not isinstance(node, dict):
            return False

        if node.get("type") == "BreakStatement":
            return True

        # Recursively check child nodes
        for key, value in node.items():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and self._js_has_break_statement(item):
                        return True
            elif isinstance(value, dict) and self._js_has_break_statement(value):
                return True

        return False


analyzer = SecurityAnalyzer()
