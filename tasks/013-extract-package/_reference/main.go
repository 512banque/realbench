package main

import (
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"time"

	"realbench/todoapp/httpapi"
	"realbench/todoapp/storage"
)

// NewMux wires the in-memory store and HTTP handlers. Kept here (top-level
// package) so main_test.go can spin up the same routing without going
// through main().
func NewMux() *http.ServeMux {
	return httpapi.NewMux(storage.NewMemoryStore())
}

func main() {
	port := resolvePort()
	addr := fmt.Sprintf(":%d", port)
	server := &http.Server{
		Addr:              addr,
		Handler:           NewMux(),
		ReadTimeout:       5 * time.Second,
		ReadHeaderTimeout: 2 * time.Second,
		WriteTimeout:      5 * time.Second,
		IdleTimeout:       30 * time.Second,
	}
	log.Printf("todo service listening on %s", addr)
	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatalf("server error: %v", err)
	}
}

func resolvePort() int {
	for _, k := range []string{"TODO_PORT", "PORT"} {
		if v := os.Getenv(k); v != "" {
			p, err := strconv.Atoi(v)
			if err != nil || p <= 0 || p > 65535 {
				log.Fatalf("invalid %s=%q", k, v)
			}
			return p
		}
	}
	return 8080
}
