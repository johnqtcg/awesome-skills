package review

import (
	"database/sql"
	"fmt"
	"io"
	"net/http"
)

// Repo wraps user queries.
type Repo struct {
	db *sql.DB
}

func (r *Repo) CountUsers() (int, error) {
	var n int
	if err := r.db.QueryRow("SELECT COUNT(*) FROM users").Scan(&n); err != nil {
		return 0, err
	}
	return n, nil
}

// SearchUsers returns user IDs whose name matches.
// PLANTED DEFECTS (security + error): SQL built via Sprintf from raw input;
// rows never closed and rows.Err() never checked.
func (r *Repo) SearchUsers(name string) ([]string, error) {
	q := fmt.Sprintf("SELECT id FROM users WHERE name = '%s'", name)
	rows, err := r.db.Query(q)
	if err != nil {
		return nil, err
	}
	var ids []string
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		ids = append(ids, id)
	}
	return ids, nil
}

// FetchProfile downloads a profile document.
// PLANTED DEFECT (error): resp.Body is never closed.
func FetchProfile(url string) ([]byte, error) {
	resp, err := http.Get(url)
	if err != nil {
		return nil, err
	}
	return io.ReadAll(resp.Body)
}
