#!/usr/bin/env node

const esprima = require('esprima');

/**
 * JavaScript Static Analyzer using Esprima
 * Reads JavaScript code from stdin and outputs analysis results as JSON
 */

// Configuration
const DANGEROUS_MODULES = [
  'child_process',
  'fs',
  'fs/promises',
  'net',
  'http',
  'https',
  'os',
  'cluster',
  'dgram',
  'dns',
  'readline',
  'repl',
  'tls',
  'v8',
  'vm',
  'worker_threads'
];

const DANGEROUS_GLOBALS = [
  'eval',
  'Function',
  'setTimeout',
  'setInterval',
  'setImmediate'
];

// Read code from stdin
let code = '';
process.stdin.setEncoding('utf8');

process.stdin.on('data', (chunk) => {
  code += chunk;
});

process.stdin.on('end', () => {
  analyzeCode(code);
});

/**
 * Main analysis function
 */
function analyzeCode(code) {
  let ast;

  try {
    // Try parsing as ES6 module first (supports import/export)
    try {
      ast = esprima.parseModule(code, {
        loc: true,
        range: true,
        tolerant: false
      });
    } catch (moduleError) {
      // If module parsing fails, try as script
      ast = esprima.parseScript(code, {
        loc: true,
        range: true,
        tolerant: false
      });
    }

    // Perform analysis
    const analysis = analyzeAST(ast, code);

    // Output results
    console.log(JSON.stringify(analysis, null, 2));
    process.exit(0);

  } catch (error) {
    // Syntax error caught
    const errorInfo = {
      is_safe: false,
      violations: [formatSyntaxError(error)],
      imports: [],
      functions: []
    };
    console.log(JSON.stringify(errorInfo, null, 2));
    process.exit(1);
  }
}

/**
 * Format syntax error message
 */
function formatSyntaxError(error) {
  if (error.lineNumber && error.description) {
    return `Syntax error at line ${error.lineNumber}, column ${error.column}: ${error.description}`;
  }
  return `Syntax error: ${error.message}`;
}

/**
 * Analyze AST for violations and extract metadata
 */
function analyzeAST(ast, code) {
  const violations = [];
  const imports = [];
  const functions = [];

  // Traverse AST
  traverse(ast, (node) => {
    // Check require() calls
    if (node.type === 'CallExpression' &&
        node.callee.type === 'Identifier' &&
        node.callee.name === 'require') {

      if (node.arguments.length > 0 && node.arguments[0].type === 'Literal') {
        const moduleName = node.arguments[0].value;
        imports.push(moduleName);

        if (DANGEROUS_MODULES.includes(moduleName)) {
          violations.push(`Dangerous module import: require('${moduleName}')`);
        }
      }
    }

    // Check import declarations
    if (node.type === 'ImportDeclaration') {
      const moduleName = node.source.value;
      imports.push(moduleName);

      if (DANGEROUS_MODULES.includes(moduleName)) {
        violations.push(`Dangerous module import: import from '${moduleName}'`);
      }
    }

    // Check dynamic imports
    if (node.type === 'ImportExpression') {
      if (node.source.type === 'Literal') {
        const moduleName = node.source.value;
        imports.push(moduleName);

        if (DANGEROUS_MODULES.includes(moduleName)) {
          violations.push(`Dangerous module import: import('${moduleName}')`);
        }
      }
    }

    // Check dangerous function calls
    if (node.type === 'CallExpression' &&
        node.callee.type === 'Identifier' &&
        DANGEROUS_GLOBALS.includes(node.callee.name)) {
      violations.push(`Dangerous function call: ${node.callee.name}()`);
    }

    // Check Function constructor (indirect eval)
    if (node.type === 'NewExpression' &&
        node.callee.type === 'Identifier' &&
        node.callee.name === 'Function') {
      violations.push(`Dangerous constructor: new Function()`);
    }

    // Extract function declarations
    if (node.type === 'FunctionDeclaration' && node.id) {
      functions.push(node.id.name);
    }

    // Extract function expressions assigned to variables
    if (node.type === 'VariableDeclarator' &&
        node.id.type === 'Identifier' &&
        (node.init && (node.init.type === 'FunctionExpression' ||
                       node.init.type === 'ArrowFunctionExpression'))) {
      functions.push(node.id.name);
    }

    // Check for infinite loops (basic heuristic)
    if (node.type === 'WhileStatement' || node.type === 'ForStatement') {
      if (mightBeInfiniteLoop(node)) {
        violations.push('Potential infinite loop detected');
      }
    }
  });

  return {
    is_safe: violations.length === 0,
    violations: violations,
    imports: [...new Set(imports)], // Remove duplicates
    functions: [...new Set(functions)]
  };
}

/**
 * Traverse AST recursively
 */
function traverse(node, callback) {
  if (!node || typeof node !== 'object') {
    return;
  }

  callback(node);

  for (const key in node) {
    if (node.hasOwnProperty(key)) {
      const child = node[key];

      if (Array.isArray(child)) {
        child.forEach(item => {
          if (item && typeof item === 'object') {
            traverse(item, callback);
          }
        });
      } else if (child && typeof child === 'object') {
        traverse(child, callback);
      }
    }
  }
}

/**
 * Basic heuristic to detect potential infinite loops
 */
function mightBeInfiniteLoop(node) {
  // While(true) pattern
  if (node.type === 'WhileStatement') {
    if (node.test.type === 'Literal' && node.test.value === true) {
      // Check if there's a break statement in the body
      let hasBreak = false;
      traverse(node.body, (child) => {
        if (child.type === 'BreakStatement') {
          hasBreak = true;
        }
      });
      return !hasBreak;
    }
  }

  // For(;;) pattern
  if (node.type === 'ForStatement') {
    if (!node.test || (node.test.type === 'Literal' && node.test.value === true)) {
      let hasBreak = false;
      traverse(node.body, (child) => {
        if (child.type === 'BreakStatement') {
          hasBreak = true;
        }
      });
      return !hasBreak;
    }
  }

  return false;
}
