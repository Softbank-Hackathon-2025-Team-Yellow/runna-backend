import pytest

from app.core.static_analysis import analyzer


class TestJavaScriptAnalysis:
    """Test JavaScript static analysis with Esprima"""

    def test_valid_javascript_code(self):
        """Test that valid JavaScript code passes analysis"""
        code = """
function handler(event) {
    return {
        statusCode: 200,
        body: JSON.stringify({ message: "Hello World" })
    };
}
"""
        result = analyzer.analyze_nodejs_code(code)

        assert result["is_safe"] is True
        assert len(result["violations"]) == 0
        assert "handler" in result["functions"]

    def test_javascript_syntax_error(self):
        """Test that syntax errors are caught"""
        code = """
function handler(event {  // Missing closing parenthesis
    return { message: "Hello" };
}
"""
        result = analyzer.analyze_nodejs_code(code)

        assert result["is_safe"] is False
        assert len(result["violations"]) > 0
        assert "Syntax error" in result["violations"][0]

    def test_dangerous_require_fs(self):
        """Test that dangerous fs module is detected"""
        code = """
const fs = require('fs');

function handler(event) {
    const data = fs.readFileSync('/etc/passwd', 'utf8');
    return { data: data };
}
"""
        result = analyzer.analyze_nodejs_code(code)

        assert result["is_safe"] is False
        assert any("fs" in v for v in result["violations"])
        assert "fs" in result["imports"]

    def test_dangerous_require_child_process(self):
        """Test that dangerous child_process module is detected"""
        code = """
const { exec } = require('child_process');

function handler(event) {
    exec('ls -la', (error, stdout, stderr) => {
        console.log(stdout);
    });
}
"""
        result = analyzer.analyze_nodejs_code(code)

        assert result["is_safe"] is False
        assert any("child_process" in v for v in result["violations"])
        assert "child_process" in result["imports"]

    def test_dangerous_eval_function(self):
        """Test that eval() is detected"""
        code = """
function handler(event) {
    const result = eval(event.code);
    return { result: result };
}
"""
        result = analyzer.analyze_nodejs_code(code)

        assert result["is_safe"] is False
        assert any("eval" in v.lower() for v in result["violations"])

    def test_dangerous_function_constructor(self):
        """Test that Function constructor is detected"""
        code = """
function handler(event) {
    const fn = new Function('return 1 + 1');
    return { result: fn() };
}
"""
        result = analyzer.analyze_nodejs_code(code)

        assert result["is_safe"] is False
        assert any("Function" in v for v in result["violations"])

    def test_dangerous_settimeout(self):
        """Test that setTimeout is detected"""
        code = """
function handler(event) {
    setTimeout(() => {
        console.log('Delayed');
    }, 1000);
    return { message: "Timer set" };
}
"""
        result = analyzer.analyze_nodejs_code(code)

        assert result["is_safe"] is False
        assert any("setTimeout" in v for v in result["violations"])

    def test_es6_import_syntax(self):
        """Test ES6 import detection"""
        code = """
import http from 'http';

export function handler(event) {
    return { message: "Hello" };
}
"""
        result = analyzer.analyze_nodejs_code(code)

        assert result["is_safe"] is False
        assert any("http" in v for v in result["violations"])
        assert "http" in result["imports"]

    def test_arrow_function_detection(self):
        """Test that arrow functions are detected"""
        code = """
const handler = (event) => {
    return { message: "Hello from arrow function" };
};
"""
        result = analyzer.analyze_nodejs_code(code)

        assert result["is_safe"] is True
        assert "handler" in result["functions"]

    def test_safe_imports(self):
        """Test that safe module imports are allowed"""
        code = """
const lodash = require('lodash');
const moment = require('moment');

function handler(event) {
    const now = moment();
    const data = lodash.map([1, 2, 3], n => n * 2);
    return { time: now, data: data };
}
"""
        result = analyzer.analyze_nodejs_code(code)

        assert result["is_safe"] is True
        assert "lodash" in result["imports"]
        assert "moment" in result["imports"]

    def test_infinite_loop_detection(self):
        """Test that infinite loops are detected"""
        code = """
function handler(event) {
    while (true) {
        console.log('Infinite loop');
    }
    return { message: "This never returns" };
}
"""
        result = analyzer.analyze_nodejs_code(code)

        assert result["is_safe"] is False
        assert any("infinite loop" in v.lower() for v in result["violations"])

    def test_for_loop_without_break(self):
        """Test infinite for loop detection"""
        code = """
function handler(event) {
    for (;;) {
        console.log('Forever');
    }
}
"""
        result = analyzer.analyze_nodejs_code(code)

        assert result["is_safe"] is False
        assert any("infinite loop" in v.lower() for v in result["violations"])

    def test_empty_code(self):
        """Test empty code handling"""
        code = ""
        result = analyzer.analyze_nodejs_code(code)

        # Empty code is technically valid but has no functions
        assert result["is_safe"] is True
        assert len(result["functions"]) == 0


class TestPythonAnalysis:
    """Test Python static analysis"""

    def test_valid_python_code(self):
        """Test that valid Python code passes analysis"""
        code = """
def handler(event):
    return {"message": "Hello World"}
"""
        result = analyzer.analyze_python_code(code)

        assert result["is_safe"] is True
        assert len(result["violations"]) == 0
        assert "handler" in result["functions"]

    def test_python_syntax_error(self):
        """Test that Python syntax errors are caught"""
        code = """
def handler(event)  # Missing colon
    return {"message": "Hello"}
"""
        result = analyzer.analyze_python_code(code)

        assert result["is_safe"] is False
        assert len(result["violations"]) > 0
        assert "Syntax error" in result["violations"][0]

    def test_dangerous_import_os(self):
        """Test that dangerous os module is detected"""
        code = """
import os

def handler(event):
    result = os.system('ls')
    return {"result": result}
"""
        result = analyzer.analyze_python_code(code)

        assert result["is_safe"] is False
        assert any("os" in v for v in result["violations"])
        assert "os" in result["imports"]

    def test_dangerous_import_subprocess(self):
        """Test that dangerous subprocess module is detected"""
        code = """
import subprocess

def handler(event):
    result = subprocess.run(['ls', '-la'], capture_output=True)
    return {"output": result.stdout}
"""
        result = analyzer.analyze_python_code(code)

        assert result["is_safe"] is False
        assert any("subprocess" in v for v in result["violations"])
        assert "subprocess" in result["imports"]

    def test_dangerous_eval_builtin(self):
        """Test that eval() builtin is detected"""
        code = """
def handler(event):
    result = eval(event['code'])
    return {"result": result}
"""
        result = analyzer.analyze_python_code(code)

        assert result["is_safe"] is False
        assert any("eval" in v.lower() for v in result["violations"])

    def test_dangerous_exec_builtin(self):
        """Test that exec() builtin is detected"""
        code = """
def handler(event):
    exec(event['code'])
    return {"message": "Code executed"}
"""
        result = analyzer.analyze_python_code(code)

        assert result["is_safe"] is False
        assert any("exec" in v.lower() for v in result["violations"])

    def test_dangerous_open_builtin(self):
        """Test that open() builtin is detected"""
        code = """
def handler(event):
    with open('/etc/passwd', 'r') as f:
        data = f.read()
    return {"data": data}
"""
        result = analyzer.analyze_python_code(code)

        assert result["is_safe"] is False
        assert any("open" in v.lower() for v in result["violations"])

    def test_safe_imports(self):
        """Test that safe imports are allowed"""
        code = """
import json
import datetime

def handler(event):
    now = datetime.datetime.now()
    return json.dumps({"time": str(now)})
"""
        result = analyzer.analyze_python_code(code)

        assert result["is_safe"] is True
        assert "json" in result["imports"]
        assert "datetime" in result["imports"]

    def test_multiple_functions(self):
        """Test multiple function detection"""
        code = """
def helper():
    return "Helper"

def handler(event):
    msg = helper()
    return {"message": msg}
"""
        result = analyzer.analyze_python_code(code)

        assert result["is_safe"] is True
        assert "helper" in result["functions"]
        assert "handler" in result["functions"]
