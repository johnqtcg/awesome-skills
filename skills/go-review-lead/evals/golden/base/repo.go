package review

import "database/sql"

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
