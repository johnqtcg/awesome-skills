package sut

import (
	"encoding/json"
	"net/http"
)

// HealthResponse is what the service reports about itself.
type HealthResponse struct {
	Status string `json:"status"`
}

// HealthHandler is THIS service's own HTTP handler — first-party code, served by the same
// binary under test. There is no third-party vendor anywhere in this path: no vendor client,
// no external account, no sandbox host, nothing billable.
func HealthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(HealthResponse{Status: "ok"})
}
