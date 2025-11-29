import ast
import re
from typing import List, Dict, Any


class SecurityAnalyzer:
    DANGEROUS_IMPORTS = [
        "os", "subprocess", "sys", "shutil", "socket", "urllib", "requests",
        "eval", "exec", "compile", "open", "__import__"
    ]
    
    DANGEROUS_BUILTINS = [
        "eval", "exec", "compile", "open", "input", "__import__",
        "globals", "locals", "vars", "dir", "getattr", "setattr", "delattr"
    ]

    def analyze_python_code(self, code: str) -> Dict[str, Any]:
        try:
            tree = ast.parse(code)
            return {
                "is_safe": self._is_code_safe(tree),
                "violations": self._find_violations(tree),
                "imports": self._extract_imports(tree),
                "functions": self._extract_functions(tree)
            }
        except SyntaxError as e:
            return {
                "is_safe": False,
                "violations": [f"Syntax error: {str(e)}"],
                "imports": [],
                "functions": []
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
                if isinstance(node.func, ast.Name) and node.func.id in self.DANGEROUS_BUILTINS:
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
        violations = []
        
        dangerous_patterns = [
            r"require\s*\(\s*['\"]child_process['\"]\s*\)",
            r"require\s*\(\s*['\"]fs['\"]\s*\)",
            r"require\s*\(\s*['\"]os['\"]\s*\)",
            r"eval\s*\(",
            r"Function\s*\(",
            r"setTimeout\s*\(",
            r"setInterval\s*\(",
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, code):
                violations.append(f"Dangerous pattern detected: {pattern}")
        
        return {
            "is_safe": len(violations) == 0,
            "violations": violations,
            "imports": self._extract_nodejs_imports(code),
            "functions": self._extract_nodejs_functions(code)
        }

    def _extract_nodejs_imports(self, code: str) -> List[str]:
        imports = []
        require_pattern = r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"
        import_pattern = r"import\s+.*?from\s+['\"]([^'\"]+)['\"]"
        
        for match in re.finditer(require_pattern, code):
            imports.append(match.group(1))
        
        for match in re.finditer(import_pattern, code):
            imports.append(match.group(1))
        
        return imports

    def _extract_nodejs_functions(self, code: str) -> List[str]:
        functions = []
        function_pattern = r"function\s+(\w+)\s*\("
        arrow_function_pattern = r"const\s+(\w+)\s*=\s*\([^)]*\)\s*=>"
        
        for match in re.finditer(function_pattern, code):
            functions.append(match.group(1))
        
        for match in re.finditer(arrow_function_pattern, code):
            functions.append(match.group(1))
        
        return functions


analyzer = SecurityAnalyzer()