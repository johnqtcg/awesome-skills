package review

import "sync"

// Store is a concurrency-safe string cache.
type Store struct {
	mu    sync.RWMutex
	items map[string]string
}

func NewStore() *Store {
	return &Store{items: make(map[string]string)}
}

func (s *Store) Get(key string) (string, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	v, ok := s.items[key]
	return v, ok
}
