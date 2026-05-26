// Package domain holds the core entities and business invariants. It has
// no dependencies on HTTP, on storage implementations, or on encoding.
package domain

import (
	"errors"
	"strings"
	"time"
)

// Todo is the single source of truth for the entity type.
type Todo struct {
	ID        int
	Title     string
	DueAt     time.Time
	CreatedAt time.Time
	Done      bool
}

// ValidateTitle returns nil iff the title is non-empty after trimming and
// no longer than 200 characters.
func ValidateTitle(title string) error {
	t := strings.TrimSpace(title)
	if t == "" {
		return errors.New("title is required")
	}
	if len(t) > 200 {
		return errors.New("title too long (max 200)")
	}
	return nil
}

// ValidateDueAt returns nil iff the due date is set.
func ValidateDueAt(due time.Time) error {
	if due.IsZero() {
		return errors.New("due_at is required")
	}
	return nil
}

// NormalizeTitle is the canonical title transform applied before storage.
func NormalizeTitle(title string) string { return strings.TrimSpace(title) }
