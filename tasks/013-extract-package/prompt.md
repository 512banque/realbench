The `main.go` file is a monolithic REST service: it mixes entities, in-memory
storage, JSON encoding, HTTP handlers, and bootstrap in a single package.
Refactor into three internal packages:

- `domain/`: the `Todo` struct and its validation (no external dependencies)
- `storage/`: interface + thread-safe in-memory implementation
- `httpapi/`: HTTP handlers that depend on `domain/` and a storage abstraction

`main()` should wire the pieces together and stay short. Both the functional
tests AND the architecture tests (`architecture_test.go`) must pass.
Do not modify the `*_test.go` files.
