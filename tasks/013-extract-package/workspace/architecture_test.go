package main

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
)

// ---------------------------------------------------------------------------
// Architecture tests: parse all .go files in the workspace and assert
// structural invariants of the refactor. These tests intentionally do NOT
// import the production code; they only read source files via go/parser
// and go/ast. They must fail on the initial monolith and pass on the
// refactored solution.
// ---------------------------------------------------------------------------

const archModulePath = "realbench/todoapp"

// workspaceRoot returns the directory containing this test file.
func workspaceRoot(t *testing.T) string {
	t.Helper()
	wd, err := os.Getwd()
	if err != nil {
		t.Fatalf("getwd: %v", err)
	}
	return wd
}

// goFilesUnder returns all non-test .go files under the workspace, excluding
// any inside vendor/ or hidden directories.
func goFilesUnder(t *testing.T, root string) []string {
	t.Helper()
	var files []string
	err := filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			name := d.Name()
			if name == "vendor" || (strings.HasPrefix(name, ".") && name != ".") {
				return filepath.SkipDir
			}
			return nil
		}
		if !strings.HasSuffix(path, ".go") {
			return nil
		}
		if strings.HasSuffix(path, "_test.go") {
			return nil
		}
		files = append(files, path)
		return nil
	})
	if err != nil {
		t.Fatalf("walk: %v", err)
	}
	sort.Strings(files)
	return files
}

// pkgPathFromFile returns the import path of the package that contains
// `file`, relative to the module root.
func pkgPathFromFile(root, modulePath, file string) string {
	rel, err := filepath.Rel(root, filepath.Dir(file))
	if err != nil {
		return ""
	}
	if rel == "." {
		return modulePath
	}
	return modulePath + "/" + filepath.ToSlash(rel)
}

// parseFile loads `path` with go/parser. Test fails on parse error.
func parseFile(t *testing.T, fset *token.FileSet, path string) *ast.File {
	t.Helper()
	f, err := parser.ParseFile(fset, path, nil, parser.ParseComments)
	if err != nil {
		t.Fatalf("parse %s: %v", path, err)
	}
	return f
}

// importsOf returns the import paths declared by `f`.
func importsOf(f *ast.File) []string {
	out := make([]string, 0, len(f.Imports))
	for _, imp := range f.Imports {
		path := strings.Trim(imp.Path.Value, `"`)
		out = append(out, path)
	}
	return out
}

// importGraph builds {pkgPath -> set of imported pkgPaths} for all non-test
// .go files under root.
func importGraph(t *testing.T, root string) map[string]map[string]struct{} {
	t.Helper()
	fset := token.NewFileSet()
	graph := map[string]map[string]struct{}{}
	for _, file := range goFilesUnder(t, root) {
		pkg := pkgPathFromFile(root, archModulePath, file)
		if _, ok := graph[pkg]; !ok {
			graph[pkg] = map[string]struct{}{}
		}
		f := parseFile(t, fset, file)
		for _, imp := range importsOf(f) {
			if strings.HasPrefix(imp, archModulePath) {
				graph[pkg][imp] = struct{}{}
			}
		}
	}
	return graph
}

// hasCycle runs a depth-first search to detect a cycle in an internal-only
// import graph (we only added internal edges to `graph`).
func hasCycle(graph map[string]map[string]struct{}) (bool, []string) {
	color := map[string]int{} // 0 unvisited, 1 visiting, 2 done
	var stack []string
	var dfs func(n string) (bool, []string)
	dfs = func(n string) (bool, []string) {
		color[n] = 1
		stack = append(stack, n)
		for next := range graph[n] {
			switch color[next] {
			case 0:
				if cyc, path := dfs(next); cyc {
					return true, path
				}
			case 1:
				// cycle: stack[i..] -> next
				for i, s := range stack {
					if s == next {
						return true, append(append([]string{}, stack[i:]...), next)
					}
				}
				return true, append(append([]string{}, stack...), next)
			}
		}
		color[n] = 2
		stack = stack[:len(stack)-1]
		return false, nil
	}
	for n := range graph {
		if color[n] == 0 {
			if cyc, path := dfs(n); cyc {
				return true, path
			}
		}
	}
	return false, nil
}

func TestNoCyclicImports(t *testing.T) {
	root := workspaceRoot(t)
	g := importGraph(t, root)
	if cyc, path := hasCycle(g); cyc {
		t.Fatalf("import cycle detected: %s", strings.Join(path, " -> "))
	}
}

func TestDomainHasNoExternalDeps(t *testing.T) {
	root := workspaceRoot(t)
	domainDir := filepath.Join(root, "domain")
	if _, err := os.Stat(domainDir); err != nil {
		t.Fatalf("expected domain/ package to exist at %s (refactor incomplete)", domainDir)
	}

	forbidden := []string{
		archModulePath + "/storage",
		archModulePath + "/httpapi",
		"net/http",
		"encoding/json",
	}

	fset := token.NewFileSet()
	files, err := filepath.Glob(filepath.Join(domainDir, "*.go"))
	if err != nil {
		t.Fatalf("glob: %v", err)
	}
	if len(files) == 0 {
		t.Fatalf("no .go files in %s", domainDir)
	}
	for _, file := range files {
		if strings.HasSuffix(file, "_test.go") {
			continue
		}
		f := parseFile(t, fset, file)
		for _, imp := range importsOf(f) {
			for _, bad := range forbidden {
				if imp == bad {
					t.Errorf("%s imports forbidden package %q", file, imp)
				}
			}
		}
	}
}

func TestHttpDependsOnDomainNotStorage(t *testing.T) {
	root := workspaceRoot(t)
	httpDir := filepath.Join(root, "httpapi")
	if _, err := os.Stat(httpDir); err != nil {
		t.Fatalf("expected httpapi/ package to exist at %s (refactor incomplete)", httpDir)
	}

	fset := token.NewFileSet()
	files, err := filepath.Glob(filepath.Join(httpDir, "*.go"))
	if err != nil {
		t.Fatalf("glob: %v", err)
	}
	if len(files) == 0 {
		t.Fatalf("no .go files in %s", httpDir)
	}

	sawDomain := false
	for _, file := range files {
		if strings.HasSuffix(file, "_test.go") {
			continue
		}
		f := parseFile(t, fset, file)
		for _, imp := range importsOf(f) {
			if imp == archModulePath+"/domain" {
				sawDomain = true
			}
			if imp == archModulePath+"/storage" {
				t.Errorf("%s imports %q directly; httpapi must depend on storage through an interface, not the concrete package", file, imp)
			}
		}
	}
	if !sawDomain {
		t.Errorf("httpapi/ does not import the domain/ package; the HTTP layer must use domain types")
	}
}

// TestMainIsThin parses main.go, finds the `main` function, and counts
// significant lines of its body. Significant lines: trimmed, non-empty,
// not starting with //, /*, *, or */. Strings and comments are skipped
// during brace matching.
func TestMainIsThin(t *testing.T) {
	root := workspaceRoot(t)
	mainFile := filepath.Join(root, "main.go")
	src, err := os.ReadFile(mainFile)
	if err != nil {
		t.Fatalf("read main.go: %v", err)
	}
	body, ok := extractFuncBody(string(src), "main")
	if !ok {
		t.Fatalf("could not locate func main() body in main.go")
	}
	n := countSignificantLines(body)
	if n > 30 {
		t.Fatalf("func main() body has %d significant lines (must be <= 30). main() must just wire packages together.\nBody:\n%s", n, body)
	}
}

// TestTodoTypeOnlyInDomain parses every non-test .go file and finds every
// type declaration named "Todo". There must be exactly one, and it must
// live in the domain/ package.
func TestTodoTypeOnlyInDomain(t *testing.T) {
	root := workspaceRoot(t)
	fset := token.NewFileSet()

	type hit struct {
		file string
		pkg  string
	}
	var hits []hit

	for _, file := range goFilesUnder(t, root) {
		f := parseFile(t, fset, file)
		ast.Inspect(f, func(n ast.Node) bool {
			ts, ok := n.(*ast.TypeSpec)
			if !ok {
				return true
			}
			if ts.Name == nil || ts.Name.Name != "Todo" {
				return true
			}
			if _, isStruct := ts.Type.(*ast.StructType); !isStruct {
				return true
			}
			hits = append(hits, hit{file: file, pkg: pkgPathFromFile(root, archModulePath, file)})
			return true
		})
	}

	if len(hits) == 0 {
		t.Fatalf("no struct named Todo found anywhere")
	}
	if len(hits) > 1 {
		var locs []string
		for _, h := range hits {
			locs = append(locs, fmt.Sprintf("%s (pkg %s)", h.file, h.pkg))
		}
		t.Fatalf("struct Todo defined in %d places, must be exactly one (in domain/):\n%s",
			len(hits), strings.Join(locs, "\n"))
	}

	if hits[0].pkg != archModulePath+"/domain" {
		t.Fatalf("struct Todo is defined in %s; it must live in the domain/ package", hits[0].pkg)
	}
}

// ---------------------------------------------------------------------------
// Mini-parser helpers (string/comment-aware brace matching, line counting).
// ---------------------------------------------------------------------------

func extractFuncBody(code, name string) (string, bool) {
	// Find `func <name>(` with no receiver: i.e. a free function. We do
	// this by matching `func\s+<name>\s*\(` and rejecting matches preceded
	// by a `)` (which would indicate a method receiver).
	i := 0
	for i < len(code) {
		j := strings.Index(code[i:], "func")
		if j < 0 {
			return "", false
		}
		j += i
		k := j + len("func")
		// must be a word boundary
		if k < len(code) && (code[k] == ' ' || code[k] == '\t') {
			// skip whitespace
			for k < len(code) && (code[k] == ' ' || code[k] == '\t') {
				k++
			}
			// expect name then "("
			if strings.HasPrefix(code[k:], name) {
				after := k + len(name)
				p := after
				for p < len(code) && (code[p] == ' ' || code[p] == '\t') {
					p++
				}
				if p < len(code) && code[p] == '(' {
					// Verify no receiver: peek back from `j` and ensure
					// the previous "(" before `j` didn't belong to a
					// receiver like `func (x T) name(`. We do that by
					// asking: was the previous non-space token a closing
					// brace `}` or newline (free function), or a `)`
					// (method receiver)?
					prev := j - 1
					for prev >= 0 && (code[prev] == ' ' || code[prev] == '\t') {
						prev--
					}
					if prev >= 0 && code[prev] == ')' {
						// looks like a method receiver scenario? actually
						// `)` before `func` is fine (end of prev block).
						// Distinguish: a method is `func (rcv T) name(` —
						// so between this `func` and the next `(`, there
						// would be a `(...)` group BEFORE the name. We
						// detect a method by checking whether the first
						// `(` we hit (right after `func`) comes BEFORE
						// the name.
					}
					// Confirm there is no `(` between `func` and the name.
					between := code[j+len("func") : k]
					if !strings.ContainsRune(between, '(') {
						// Good, this is `func name(...)`. Walk to body.
						return bodyAfter(code, p), true
					}
				}
			}
		}
		i = j + 1
	}
	return "", false
}

// bodyAfter, given position p pointing at the opening '(' of a function
// signature, finds the matching ')' end-of-signature, optional return
// types, then the opening '{' and returns the brace-matched body.
func bodyAfter(code string, p int) string {
	// Skip the signature parens.
	depth := 0
	for p < len(code) {
		ch := code[p]
		if ch == '(' {
			depth++
		} else if ch == ')' {
			depth--
			if depth == 0 {
				p++
				break
			}
		}
		p++
	}
	// Find opening '{'.
	for p < len(code) && code[p] != '{' {
		p++
	}
	if p >= len(code) {
		return ""
	}
	bodyStart := p + 1
	depth = 1
	i := bodyStart
	for i < len(code) && depth > 0 {
		ch := code[i]
		next := byte(0)
		if i+1 < len(code) {
			next = code[i+1]
		}
		if ch == '/' && next == '/' {
			for i < len(code) && code[i] != '\n' {
				i++
			}
			continue
		}
		if ch == '/' && next == '*' {
			i += 2
			for i+1 < len(code) && !(code[i] == '*' && code[i+1] == '/') {
				i++
			}
			i += 2
			continue
		}
		if ch == '\'' || ch == '"' || ch == '`' {
			quote := ch
			i++
			for i < len(code) {
				if quote != '`' && code[i] == '\\' {
					i += 2
					continue
				}
				if code[i] == quote {
					i++
					break
				}
				i++
			}
			continue
		}
		if ch == '{' {
			depth++
		} else if ch == '}' {
			depth--
			if depth == 0 {
				return code[bodyStart:i]
			}
		}
		i++
	}
	return ""
}

func countSignificantLines(body string) int {
	n := 0
	for _, line := range strings.Split(body, "\n") {
		trim := strings.TrimSpace(line)
		if trim == "" {
			continue
		}
		if strings.HasPrefix(trim, "//") || strings.HasPrefix(trim, "/*") ||
			strings.HasPrefix(trim, "*/") || strings.HasPrefix(trim, "*") {
			continue
		}
		n++
	}
	return n
}
