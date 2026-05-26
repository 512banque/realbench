package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

// These tests exercise the full HTTP surface through the same NewMux() the
// production main() wires. They must pass on the initial monolith AND on
// the refactored solution.

func doRequest(t *testing.T, srv *httptest.Server, method, path string, body any) (*http.Response, []byte) {
	t.Helper()
	var reader io.Reader
	if body != nil {
		buf, err := json.Marshal(body)
		if err != nil {
			t.Fatalf("marshal: %v", err)
		}
		reader = bytes.NewReader(buf)
	}
	req, err := http.NewRequest(method, srv.URL+path, reader)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("do: %v", err)
	}
	defer resp.Body.Close()
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatalf("read body: %v", err)
	}
	return resp, respBody
}

func TestCreateThenGet(t *testing.T) {
	srv := httptest.NewServer(NewMux())
	defer srv.Close()

	due := time.Date(2030, 1, 1, 12, 0, 0, 0, time.UTC)
	resp, body := doRequest(t, srv, http.MethodPost, "/todos", map[string]any{
		"title":  "Buy milk",
		"due_at": due,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", resp.StatusCode, body)
	}

	var created struct {
		ID    int    `json:"id"`
		Title string `json:"title"`
	}
	if err := json.Unmarshal(body, &created); err != nil {
		t.Fatalf("unmarshal: %v (body=%s)", err, body)
	}
	if created.ID <= 0 || created.Title != "Buy milk" {
		t.Fatalf("unexpected created todo: %+v", created)
	}

	resp, body = doRequest(t, srv, http.MethodGet, fmt.Sprintf("/todos/%d", created.ID), nil)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", resp.StatusCode, body)
	}

	var fetched struct {
		ID    int    `json:"id"`
		Title string `json:"title"`
	}
	if err := json.Unmarshal(body, &fetched); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if fetched.ID != created.ID || fetched.Title != "Buy milk" {
		t.Fatalf("got back wrong todo: %+v", fetched)
	}
}

func TestDelete(t *testing.T) {
	srv := httptest.NewServer(NewMux())
	defer srv.Close()

	resp, _ := doRequest(t, srv, http.MethodPost, "/todos", map[string]any{
		"title":  "Read a book",
		"due_at": time.Date(2030, 6, 1, 0, 0, 0, 0, time.UTC),
	})
	var created struct {
		ID int `json:"id"`
	}
	body, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	_ = json.Unmarshal(body, &created)
	if created.ID == 0 {
		// resp.Body was already drained by doRequest helper into the
		// returned slice; re-create the todo to get a valid id.
		resp, body := doRequest(t, srv, http.MethodPost, "/todos", map[string]any{
			"title":  "Read a book",
			"due_at": time.Date(2030, 6, 1, 0, 0, 0, 0, time.UTC),
		})
		if resp.StatusCode != http.StatusCreated {
			t.Fatalf("create failed: %s", body)
		}
		_ = json.Unmarshal(body, &created)
	}
	if created.ID == 0 {
		t.Fatal("could not create todo for delete test")
	}

	resp, body = doRequest(t, srv, http.MethodDelete, fmt.Sprintf("/todos/%d", created.ID), nil)
	if resp.StatusCode != http.StatusNoContent {
		t.Fatalf("expected 204, got %d: %s", resp.StatusCode, body)
	}

	resp, _ = doRequest(t, srv, http.MethodGet, fmt.Sprintf("/todos/%d", created.ID), nil)
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("expected 404 after delete, got %d", resp.StatusCode)
	}
}

func TestCreateValidation(t *testing.T) {
	srv := httptest.NewServer(NewMux())
	defer srv.Close()

	// empty title
	resp, _ := doRequest(t, srv, http.MethodPost, "/todos", map[string]any{
		"title":  "",
		"due_at": time.Date(2030, 1, 1, 0, 0, 0, 0, time.UTC),
	})
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected 400 for empty title, got %d", resp.StatusCode)
	}

	// missing due_at
	resp, _ = doRequest(t, srv, http.MethodPost, "/todos", map[string]any{
		"title": "no date",
	})
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected 400 for missing due_at, got %d", resp.StatusCode)
	}
}

func TestGetNotFound(t *testing.T) {
	srv := httptest.NewServer(NewMux())
	defer srv.Close()

	resp, _ := doRequest(t, srv, http.MethodGet, "/todos/9999", nil)
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("expected 404, got %d", resp.StatusCode)
	}
}
