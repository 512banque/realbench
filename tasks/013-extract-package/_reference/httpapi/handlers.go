// Package httpapi exposes the REST handlers. It depends on domain/ and on
// a TodoStorage interface that consumers can satisfy with any storage
// implementation. It does NOT import storage/ directly.
package httpapi

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"strings"
	"time"

	"realbench/todoapp/domain"
)

// TodoStorage is the storage contract the HTTP layer depends on.
// Concrete implementations live in the storage/ package; the dependency
// arrow points from httpapi -> interface <- storage.
type TodoStorage interface {
	Create(t domain.Todo) domain.Todo
	Get(id int) (domain.Todo, bool)
	Delete(id int) bool
}

type createTodoRequest struct {
	Title string    `json:"title"`
	DueAt time.Time `json:"due_at"`
}

type todoResponse struct {
	ID        int       `json:"id"`
	Title     string    `json:"title"`
	DueAt     time.Time `json:"due_at"`
	CreatedAt time.Time `json:"created_at"`
	Done      bool      `json:"done"`
}

type errorResponse struct {
	Error string `json:"error"`
}

func toResponse(t domain.Todo) todoResponse {
	return todoResponse{
		ID:        t.ID,
		Title:     t.Title,
		DueAt:     t.DueAt,
		CreatedAt: t.CreatedAt,
		Done:      t.Done,
	}
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

func collectionHandler(store TodoStorage) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodPost:
			var req createTodoRequest
			if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
				writeJSON(w, http.StatusBadRequest, errorResponse{Error: "invalid JSON: " + err.Error()})
				return
			}
			if err := domain.ValidateTitle(req.Title); err != nil {
				writeJSON(w, http.StatusBadRequest, errorResponse{Error: err.Error()})
				return
			}
			if err := domain.ValidateDueAt(req.DueAt); err != nil {
				writeJSON(w, http.StatusBadRequest, errorResponse{Error: err.Error()})
				return
			}
			created := store.Create(domain.Todo{
				Title: domain.NormalizeTitle(req.Title),
				DueAt: req.DueAt,
			})
			writeJSON(w, http.StatusCreated, toResponse(created))
		default:
			writeJSON(w, http.StatusMethodNotAllowed, errorResponse{Error: "method not allowed"})
		}
	}
}

func itemHandler(store TodoStorage) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, err := parseIDFromPath(r.URL.Path, "/todos/")
		if err != nil {
			writeJSON(w, http.StatusBadRequest, errorResponse{Error: err.Error()})
			return
		}
		switch r.Method {
		case http.MethodGet:
			t, ok := store.Get(id)
			if !ok {
				writeJSON(w, http.StatusNotFound, errorResponse{Error: "not found"})
				return
			}
			writeJSON(w, http.StatusOK, toResponse(t))
		case http.MethodDelete:
			if !store.Delete(id) {
				writeJSON(w, http.StatusNotFound, errorResponse{Error: "not found"})
				return
			}
			w.WriteHeader(http.StatusNoContent)
		default:
			writeJSON(w, http.StatusMethodNotAllowed, errorResponse{Error: "method not allowed"})
		}
	}
}

// NewMux wires the HTTP routes against the provided storage.
func NewMux(store TodoStorage) *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("/todos", collectionHandler(store))
	mux.HandleFunc("/todos/", itemHandler(store))
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})
	mux.HandleFunc("/ready", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]bool{"ready": true})
	})
	return mux
}
