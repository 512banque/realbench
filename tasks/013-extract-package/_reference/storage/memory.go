// Package storage provides persistence for domain entities. It depends on
// domain/ but knows nothing about HTTP or transport encoding.
package storage

import (
	"sync"
	"time"

	"realbench/todoapp/domain"
)

// MemoryStore is a thread-safe in-memory implementation backing the
// httpapi's TodoStorage interface.
type MemoryStore struct {
	mu     sync.Mutex
	nextID int
	todos  map[int]domain.Todo
}

func NewMemoryStore() *MemoryStore {
	return &MemoryStore{
		nextID: 1,
		todos:  make(map[int]domain.Todo),
	}
}

// Create persists a new todo, assigning ID and CreatedAt.
func (s *MemoryStore) Create(t domain.Todo) domain.Todo {
	s.mu.Lock()
	defer s.mu.Unlock()
	t.ID = s.nextID
	s.nextID++
	t.CreatedAt = time.Now().UTC()
	s.todos[t.ID] = t
	return t
}

func (s *MemoryStore) Get(id int) (domain.Todo, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	t, ok := s.todos[id]
	return t, ok
}

func (s *MemoryStore) Delete(id int) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.todos[id]; !ok {
		return false
	}
	delete(s.todos, id)
	return true
}
