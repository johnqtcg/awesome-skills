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

// Warm pre-populates the cache for the given keys.
// PLANTED DEFECT (concurrency): goroutines write s.items without holding s.mu.
func (s *Store) Warm(keys []string) {
	var wg sync.WaitGroup
	for _, k := range keys {
		wg.Add(1)
		go func(key string) {
			defer wg.Done()
			s.items[key] = compute(key)
		}(k)
	}
	wg.Wait()
}

func compute(key string) string {
	return key + "-warmed"
}
