package sut

import (
	"context"
	"fmt"
)

// Level is a tier record as stored by the repository, lowest rank first.
type Level struct {
	ID   string
	Name string
	Rank int
}

// LevelView is the caller-facing projection of a Level.
type LevelView struct {
	ID          string
	Name        string
	NextLevelID string
}

// LevelRepo loads the configured levels in ascending rank order.
type LevelRepo interface {
	List(ctx context.Context) ([]Level, error)
}

// LevelService projects repository levels into the caller-facing chain.
type LevelService struct {
	repo LevelRepo
}

// NewLevelService wires a LevelService to its repository.
func NewLevelService(repo LevelRepo) *LevelService {
	return &LevelService{repo: repo}
}

// ListLevels returns one LevelView per repository Level, preserving order and count.
//
// Every level links to its successor. The terminal level's NextLevelID is empty, which
// is how a caller detects the top of the chain — so an empty NextLevelID anywhere else
// would be read as "this is the top".
//
// On a repository failure it returns a nil slice and a wrapped error.
// The error wraps the repository's error with %w, so errors.Is still matches at the
// caller; and the result is nil, never a partial list alongside an error.
//
// Note what is deliberately NOT promised: the shape of the successful empty result. A
// caller must not depend on it being non-nil.
func (s *LevelService) ListLevels(ctx context.Context) ([]LevelView, error) {
	levels, err := s.repo.List(ctx)
	if err != nil {
		return nil, fmt.Errorf("list levels: %w", err)
	}
	out := make([]LevelView, 0, len(levels))
	for i := 0; i < len(levels); i++ {
		v := LevelView{ID: levels[i].ID, Name: levels[i].Name}
		if i+1 < len(levels) {
			v.NextLevelID = levels[i+1].ID
		}
		out = append(out, v)
	}
	return out, nil
}
