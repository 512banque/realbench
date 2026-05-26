package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
)

// ---------------------------------------------------------------------------
// Domain entity (mixed with everything else in this file: that's the smell).
// ---------------------------------------------------------------------------

type Todo struct {
	ID        int       `json:"id"`
	Title     string    `json:"title"`
	DueAt     time.Time `json:"due_at"`
	CreatedAt time.Time `json:"created_at"`
	Done      bool      `json:"done"`
}

func validateTodoTitle(title string) error {
	t := strings.TrimSpace(title)
	if t == "" {
		return errors.New("title is required")
	}
	if len(t) > 200 {
		return errors.New("title too long (max 200)")
	}
	return nil
}

func validateTodoDueAt(due time.Time) error {
	if due.IsZero() {
		return errors.New("due_at is required")
	}
	return nil
}

// ---------------------------------------------------------------------------
// In-memory storage (also in main, also mixed in).
// ---------------------------------------------------------------------------

type todoStore struct {
	mu     sync.Mutex
	nextID int
	todos  map[int]Todo
}

func newTodoStore() *todoStore {
	return &todoStore{
		nextID: 1,
		todos:  make(map[int]Todo),
	}
}

func (s *todoStore) create(t Todo) Todo {
	s.mu.Lock()
	defer s.mu.Unlock()
	t.ID = s.nextID
	s.nextID++
	t.CreatedAt = time.Now().UTC()
	s.todos[t.ID] = t
	return t
}

func (s *todoStore) get(id int) (Todo, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	t, ok := s.todos[id]
	return t, ok
}

func (s *todoStore) delete(id int) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.todos[id]; !ok {
		return false
	}
	delete(s.todos, id)
	return true
}

// ---------------------------------------------------------------------------
// HTTP layer (handlers know the store concretely, parse JSON inline,
// validate inline, write responses inline). All in main.
// ---------------------------------------------------------------------------

type createTodoRequest struct {
	Title string    `json:"title"`
	DueAt time.Time `json:"due_at"`
}

type errorResponse struct {
	Error string `json:"error"`
}

func writeJSON(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if body != nil {
		_ = json.NewEncoder(w).Encode(body)
	}
}

func parseIDFromPath(path, prefix string) (int, error) {
	rest := strings.TrimPrefix(path, prefix)
	rest = strings.TrimSuffix(rest, "/")
	if rest == "" {
		return 0, errors.New("missing id")
	}
	id, err := strconv.Atoi(rest)
	if err != nil {
		return 0, err
	}
	if id <= 0 {
		return 0, errors.New("invalid id")
	}
	return id, nil
}

func todosHandler(store *todoStore) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodPost:
			var req createTodoRequest
			if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
				writeJSON(w, http.StatusBadRequest, errorResponse{Error: "invalid JSON: " + err.Error()})
				return
			}
			if err := validateTodoTitle(req.Title); err != nil {
				writeJSON(w, http.StatusBadRequest, errorResponse{Error: err.Error()})
				return
			}
			if err := validateTodoDueAt(req.DueAt); err != nil {
				writeJSON(w, http.StatusBadRequest, errorResponse{Error: err.Error()})
				return
			}
			created := store.create(Todo{Title: strings.TrimSpace(req.Title), DueAt: req.DueAt})
			writeJSON(w, http.StatusCreated, created)
		default:
			writeJSON(w, http.StatusMethodNotAllowed, errorResponse{Error: "method not allowed"})
		}
	}
}

func todoByIDHandler(store *todoStore) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, err := parseIDFromPath(r.URL.Path, "/todos/")
		if err != nil {
			writeJSON(w, http.StatusBadRequest, errorResponse{Error: err.Error()})
			return
		}

		switch r.Method {
		case http.MethodGet:
			t, ok := store.get(id)
			if !ok {
				writeJSON(w, http.StatusNotFound, errorResponse{Error: "not found"})
				return
			}
			writeJSON(w, http.StatusOK, t)
		case http.MethodDelete:
			if !store.delete(id) {
				writeJSON(w, http.StatusNotFound, errorResponse{Error: "not found"})
				return
			}
			w.WriteHeader(http.StatusNoContent)
		default:
			writeJSON(w, http.StatusMethodNotAllowed, errorResponse{Error: "method not allowed"})
		}
	}
}

// NewMux wires the in-memory store and HTTP handlers. It is exported so the
// integration test in main_test.go can spin up the same routing without
// going through main().
func NewMux() *http.ServeMux {
	store := newTodoStore()
	mux := http.NewServeMux()
	mux.HandleFunc("/todos", todosHandler(store))
	mux.HandleFunc("/todos/", todoByIDHandler(store))
	return mux
}

// ---------------------------------------------------------------------------
// Bootstrap (also fat: parses port, builds store, wires handlers, starts
// the server, logs, all inline).
// ---------------------------------------------------------------------------

func main() {
	port := 8080
	portEnv := ""
	for _, e := range []string{"TODO_PORT", "PORT"} {
		if v := strings.TrimSpace(getEnv(e)); v != "" {
			portEnv = v
			break
		}
	}
	if portEnv != "" {
		p, err := strconv.Atoi(portEnv)
		if err != nil {
			log.Fatalf("invalid port %q: %v", portEnv, err)
		}
		if p <= 0 || p > 65535 {
			log.Fatalf("port out of range: %d", p)
		}
		port = p
	}
	addr := fmt.Sprintf(":%d", port)

	store := newTodoStore()
	log.Printf("initialized in-memory todo store with %d existing rows", len(store.todos))

	mux := http.NewServeMux()
	mux.HandleFunc("/todos", todosHandler(store))
	mux.HandleFunc("/todos/", todoByIDHandler(store))
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"ok"}`))
	})
	mux.HandleFunc("/ready", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"ready":true}`))
	})

	server := &http.Server{
		Addr:              addr,
		Handler:           mux,
		ReadTimeout:       5 * time.Second,
		ReadHeaderTimeout: 2 * time.Second,
		WriteTimeout:      5 * time.Second,
		IdleTimeout:       30 * time.Second,
	}

	log.Printf("todo service listening on %s", addr)
	log.Printf("routes: POST /todos, GET /todos/:id, DELETE /todos/:id, GET /health, GET /ready")
	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatalf("server error: %v", err)
	}
	log.Printf("server stopped")
}

// getEnv is a tiny shim around os.Getenv used by main().
func getEnv(key string) string {
	return os.Getenv(key)
}
