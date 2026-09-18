package sut

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"time"
)

// Charge is the vendor's charge resource.
type Charge struct {
	ID       string `json:"id"`
	Account  string `json:"account"`
	AmountCt int64  `json:"amount_cents"`
	Currency string `json:"currency"`
}

// Response pairs the protocol result with the decoded body so a caller can assert both.
type Response struct {
	StatusCode int
	Body       Charge
}

// Client is the production path to a third-party payments vendor. An integration test must
// build it through NewClient and exercise the real transport — substituting the transport
// makes it an adapter test, not an integration test.
type Client struct {
	baseURL string
	account string
	http    *http.Client
}

// NewClient returns a vendor client. baseURL must be an absolute http(s) URL with a host.
func NewClient(baseURL, account string) (*Client, error) {
	u, err := url.Parse(baseURL)
	if err != nil || !u.IsAbs() || (u.Scheme != "http" && u.Scheme != "https") || u.Hostname() == "" {
		return nil, fmt.Errorf("vendor base URL must be an absolute http(s) URL with a host")
	}
	return &Client{baseURL: baseURL, account: account, http: &http.Client{}}, nil
}

// GetCharge reads one charge. The context bounds the call; the caller sets the deadline.
func (c *Client) GetCharge(ctx context.Context, id string) (*Response, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet,
		c.baseURL+"/v1/charges/"+url.PathEscape(id), nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("X-Vendor-Account", c.account)
	resp, err := c.http.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	out := &Response{StatusCode: resp.StatusCode}
	if resp.StatusCode == http.StatusOK {
		if err := json.NewDecoder(resp.Body).Decode(&out.Body); err != nil {
			return nil, fmt.Errorf("decode charge: %w", err)
		}
	}
	return out, nil
}

// VendorTimeout is the per-call budget the vendor's SLA assumes.
const VendorTimeout = 15 * time.Second
