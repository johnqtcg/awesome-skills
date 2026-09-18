package sut

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"time"
)

// Profile is the payload returned by the user service.
type Profile struct {
	UserID      string `json:"user_id"`
	DisplayName string `json:"display_name"`
	TenantID    string `json:"tenant_id"`
}

// Response wraps the decoded body with the protocol-level result, so a caller can assert
// both layers without re-reading the HTTP response.
type Response struct {
	StatusCode int
	Body       Profile
}

// Client talks to the internal user-profile service. It is the production code path: an
// integration test must build the client through NewClient, never substitute its
// transport (that would be an adapter test — see SKILL.md §Test Taxonomy).
type Client struct {
	baseURL string
	http    *http.Client
}

// NewClient returns a client for baseURL. It validates that baseURL is an absolute
// http(s) URL so a caller cannot accidentally pass a bare host.
func NewClient(baseURL string) (*Client, error) {
	u, err := url.Parse(baseURL)
	if err != nil || !u.IsAbs() || (u.Scheme != "http" && u.Scheme != "https") || u.Hostname() == "" {
		return nil, fmt.Errorf("base URL must be an absolute http(s) URL with a host, got %q", baseURL)
	}
	return &Client{baseURL: baseURL, http: &http.Client{}}, nil
}

// GetUserProfile fetches one profile. The context bounds the call; the caller is
// responsible for setting a deadline.
func (c *Client) GetUserProfile(ctx context.Context, userID string) (*Response, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet,
		c.baseURL+"/v1/users/"+url.PathEscape(userID), nil)
	if err != nil {
		return nil, err
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	out := &Response{StatusCode: resp.StatusCode}
	if resp.StatusCode == http.StatusOK {
		if err := json.NewDecoder(resp.Body).Decode(&out.Body); err != nil {
			return nil, fmt.Errorf("decode profile: %w", err)
		}
	}
	return out, nil
}

// DialTimeout is the per-call budget this service's SLO assumes.
const DialTimeout = 15 * time.Second
