

# example one

## code

```go
func (s *LayoutService) ListLayout() (layouts []*db.Layout, total int64, err error) {
    // initialize return value
    layouts = make([]*db.Layout, 0)


    // fetch layout list
    whereClause := fmt.Sprintf("uid = %v and corp_id = %v", s.uid, s.corpId)
    if err := s.orm.Model(&db.Layout{}).Where(whereClause).Order("updated_at desc").Find(&layouts).Error; err != nil {
        return nil, 0, err
    }


    // fetch layout total number
    if err := s.orm.Model(&db.Layout{}).Where(whereClause).
        Count(&total).Error; err != nil {
        return nil, 0, err
    }


    return layouts, total, nil
}
```

## AI code review output

```markdown
---                                                                                                                                         
  Review Mode                                                                                                                                 
                                                                                                                                              
  - Lite                                                                                                                                      
  - Single function (~21 lines), no concurrency, no auth flow. Small scope, low-risk surface area beyond the SQL pattern.
                                                                                                                                              
  ---
  Findings                                                                                                                                    
                                                            
  [High] SQL Injection via fmt.Sprintf in GORM Where Clause
                                                                                                                                              
  - ID: REV-001
  - Origin: uncertain (full file context unavailable)                                                                                         
  - Baseline: N/A (baseline not found)                                                                                                        
  - Principle: N/A (no constitution.md)
  - Impact: If s.uid or s.corpId are string types or ever become user-controlled, an attacker can inject arbitrary SQL. Even with integer     
  types today, the pattern is fragile — a type change silently opens an injection vector.                                                     
  - Evidence: whereClause := fmt.Sprintf("uid = %v and corp_id = %v", s.uid, s.corpId) — %v formats any type including strings without
  escaping. This bypasses GORM's built-in parameterization.                                                                                   
  - Recommendation: Use GORM's parameterized query:         
  Where("uid = ? AND corp_id = ?", s.uid, s.corpId)                                                                                           
  - Action: must-fix                                        
                                                                                                                                              
  [High] Missing Error Wrapping on Both Return Paths
                                                                                                                                              
  - ID: REV-002                                             
  - Origin: uncertain
  - Baseline: N/A                                                                                                                             
  - Principle: N/A
  - Impact: Bare return nil, 0, err loses call-site context. Callers see raw GORM/DB errors (potentially leaking table names, column names)
  with no indication which operation failed.                                                                                                  
  - Evidence: Two return nil, 0, err statements — neither wraps with fmt.Errorf. The Find error and Count error are indistinguishable to the
  caller.                                                                                                                                     
  - Recommendation:                                         
  return nil, 0, fmt.Errorf("ListLayout find: %w", err)                                                                                       
  // and                                                    
  return nil, 0, fmt.Errorf("ListLayout count: %w", err)                                                                                      
  - Action: must-fix
                                                                                                                                              
  [Medium] Missing context.Context Parameter                

  - ID: REV-003                                                                                                                               
  - Origin: uncertain
  - Baseline: N/A                                                                                                                             
  - Principle: N/A
  - Impact: GORM queries cannot be cancelled if the upstream HTTP request is cancelled (client disconnect, timeout). Long-running queries hold
   connections indefinitely.                                                                                                                  
  - Evidence: Function signature ListLayout() takes no ctx context.Context. Neither GORM call uses .WithContext(ctx).
  - Recommendation: Add ctx context.Context as the first parameter and chain .WithContext(ctx) on both GORM calls.                            
  - Action: must-fix                                                                                                                          
                                                                                                                                              
  [Medium] Query Order — Find Before Count Wastes Resources                                                                                   
                                                            
  - ID: REV-004                                                                                                                               
  - Origin: uncertain                                       
  - Baseline: N/A
  - Principle: N/A
  - Impact: The function always executes both Find (row scan + transfer) and Count. If the result set is empty (common for new users/corps),
  the Find query is wasted I/O.                                                                                                               
  - Evidence: Find at line 8 runs before Count at line 14. Per the Count-First Guard pattern (see go-database-patterns.md), reversing the
  order and returning early when total == 0 eliminates the more expensive Find for empty result sets.                                         
  - Recommendation: Execute Count first; if total == 0, return ([]*db.Layout{}, 0, nil) immediately.
  - Action: follow-up issue                                                                                                                   
                                                            
  [Medium] Shadowed Named Return err Is Never Used                                                                                            
                                                            
  - ID: REV-005                                                                                                                               
  - Origin: uncertain                                       
  - Baseline: N/A
  - Principle: N/A
  - Impact: The named return err error in the signature is shadowed by err := in both if blocks. The named return is never assigned, making it
   misleading. If a future maintainer adds a code path that does a naked return, the zero-value err (nil) will mask a real error.             
  - Evidence: Signature declares err error; both line 8 (if err := ...) and line 14 (if err := ...) use := creating new scoped variables.     
  - Recommendation: Either remove the named return err (use anonymous returns) or use = instead of := to assign to the named return variable. 
  - Action: follow-up issue                                                                                                                   
                                                                                                                                              
  ---                                                                                                                                         
  Suppressed Items                                                                                                                          
                                                                                                                                              
  None.

Risk Acceptance / SLA

┌────────────────────────────────────┬─────────────────────────────┐
│              Severity              │             SLA             │
├────────────────────────────────────┼─────────────────────────────┤
│ High (REV-001, REV-002)            │ Fix within 3 business days  │
├────────────────────────────────────┼─────────────────────────────┤
│ Medium (REV-003, REV-004, REV-005) │ Fix within 14 calendar days │
└────────────────────────────────────┴─────────────────────────────┘

  ---
Residual Risk / Testing Gaps

1. Verification gaps: All static analysis and test tools not run — code provided as screenshot only.
2. Pagination concern: Function returns all matching rows with no Limit/Offset but returns a total count, suggesting pagination intent. If
   the dataset grows, this becomes a performance/memory issue. Could not determine if pagination is handled at a higher layer.
3. Wasted allocation: make([]*db.Layout, 0) at line 3 is immediately overwritten by GORM's Find. Minor allocation waste.

  ---
Summary

0 introduced / 0 pre-existing / 5 uncertain. The SQL injection pattern (REV-001) is the highest priority fix — switch to parameterized
Where("uid = ? AND corp_id = ?", ...). Error wrapping (REV-002) and context propagation (REV-003) are close behind for production readiness.
```

# example two

## code

```go
func getBatchUser(ctx context.Context, userKeys []*UserKey) (users []*User, error) {


    userList := make([]*User, len(userKeys))


    for i, u := range userKeys {
        user, err := redis.GetGuest(ctx, u.Id)
        if err != nil {
            log.WarnContextf(ctx, "no found guest user: %v", u)
            continue
        }
        userList[i] = user
    }


    return userList, nil
}
```

## AI code review output

```markdown
 ---
  Review Mode

  - Lite
  - Single function (~18 lines), no concurrency primitives, no auth/security surface.

  ---
  Findings

  [High] Nil Pointer Dereference — Missing Nil Guard on Pointer Slice Elements

  - ID: REV-001
  - Origin: uncertain
  - Baseline: N/A (baseline not found)
  - Principle: N/A (no constitution.md)
  - Impact: userKeys is []*UserKey — any element can be nil. Accessing u.Id on a nil element panics at runtime, crashing the entire process.
  - Evidence: Parameter type is []*UserKey (pointer slice). Line 8 dereferences u.Id with no nil check. Pointer slices from DB scans, JSON
  unmarshal, or API responses commonly contain nil entries. Per go-error-and-quality.md § Pointer Slice Nil Guard, this is a confirmed defect
  pattern.
  - Recommendation:
  for i, u := range userKeys {
      if u == nil {
          continue
      }
      // ...
  }
  - Action: must-fix

  [High] Return Slice Contains Nil Holes — Downstream Panic Risk

  - ID: REV-002
  - Origin: uncertain
  - Baseline: N/A
  - Principle: N/A
  - Impact: make([]*User, len(userKeys)) pre-fills with nil. When redis.GetGuest fails, continue skips assignment, leaving userList[i] = nil.
  The caller receives a slice with nil "holes" at error indices. Any caller doing userList[i].Name panics.
  - Evidence: Line 4 allocates full-length slice (all nil). Lines 9-11: on error, continue skips line 13 (userList[i] = user). Line 17 returns
   the slice with gaps. The returned type []*User gives callers no signal about which entries are valid.
  - Recommendation: Use append-only pattern to exclude failed lookups:
  userList := make([]*User, 0, len(userKeys))
  for _, u := range userKeys {
      if u == nil {
          continue
      }
      user, err := redis.GetGuest(ctx, u.Id)
      if err != nil {
          log.WarnContextf(ctx, "guest user not found, id=%v: %v", u.Id, err)
          continue
      }
      userList = append(userList, user)
  }
  - Action: must-fix

  [Medium] N+1 Redis Calls — Individual Lookup Per Key in Loop

  - ID: REV-003
  - Origin: uncertain
  - Baseline: N/A
  - Principle: N/A
  - Impact: Each iteration makes a separate Redis round-trip. For N user keys, this is N network calls. Latency grows linearly; under high
  concurrency this saturates Redis connections.
  - Evidence: redis.GetGuest(ctx, u.Id) at line 8 inside for loop at line 7. Redis supports batch commands (MGET, pipeline) that reduce N
  round-trips to 1.
  - Recommendation: Use Redis pipeline or MGET for batch retrieval:
  users, err := redis.MGetGuests(ctx, extractIDs(userKeys))
  - Action: follow-up issue

  [Medium] Error Swallowed — Function Always Returns nil Error

  - ID: REV-004
  - Origin: uncertain
  - Baseline: N/A
  - Principle: N/A
  - Impact: All redis.GetGuest errors are logged and discarded. The function returns nil error even if every single lookup fails. Callers
  cannot distinguish "all users found" from "zero users found due to Redis outage". Per go-error-and-quality.md § Log Once Return Errors,
  intermediate layers should return errors, not swallow them.
  - Evidence: Line 10 logs the error, line 11 continue discards it. Line 17 unconditionally returns nil. A Redis connection failure silently
  returns an empty/partial result.
  - Recommendation: Either (a) return an error when all lookups fail (total failure), or (b) return a partial-result indicator:
  if len(userList) == 0 && len(userKeys) > 0 {
      return nil, fmt.Errorf("getBatchUser: all %d lookups failed", len(userKeys))
  }
  - Action: follow-up issue

  [Medium] Log Message Conflates "Not Found" With All Error Types

  - ID: REV-005
  - Origin: uncertain
  - Baseline: N/A
  - Principle: N/A
  - Impact: "no found guest user: %v" is logged for every error, but the error could be a network timeout, connection refused, serialization
  failure — not just "not found". This misdirects debugging. Additionally, logging the entire struct u with %v may leak sensitive fields.
  - Evidence: log.WarnContextf(ctx, "no found guest user: %v", u) — the err value is not included in the log message, making it impossible to
  diagnose the actual failure. The message grammatically implies "not found" but the error is unchecked.
  - Recommendation:
  log.WarnContextf(ctx, "getBatchUser: failed to get guest user id=%v: %v", u.Id, err)
  - Action: follow-up issue

  ---
  Suppressed Items

  None.

  ---

  ---
  Risk Acceptance / SLA

  ┌──────────┬───────────────────────────┬─────────────────────────────┐
  │ Severity │          Finding          │             SLA             │
  ├──────────┼───────────────────────────┼─────────────────────────────┤
  │ High     │ REV-001, REV-002          │ Fix within 3 business days  │
  ├──────────┼───────────────────────────┼─────────────────────────────┤
  │ Medium   │ REV-003, REV-004, REV-005 │ Fix within 14 calendar days │
  └──────────┴───────────────────────────┴─────────────────────────────┘

  ---
  Residual Risk / Testing Gaps

  1. Named return mismatch: Function signature declares named return users but the body uses local userList. The named return is never
  assigned — cosmetic but confusing.
  2. Index correlation lost: If callers depend on positional correspondence between userKeys[i] and userList[i] (common in batch APIs), the
  append-only fix (REV-002) breaks that contract. An alternative is to keep the indexed approach but document that nil entries indicate failed
   lookups, and ensure all callers nil-check before dereference.

  ---
  Summary

  0 introduced / 0 pre-existing / 5 uncertain. The two High findings (REV-001 nil deref on pointer slice, REV-002 nil holes in result) are
  crash-level bugs that will panic in production when any element is nil or any Redis call fails. The N+1 pattern (REV-003) is the primary
  performance concern for scaling.
```


# example three

## code

```go
func getBatchUser(ctx context.Context, userKeys []*UserKey) (users []*User, error) {


    userList := make([]*User, 0)


    var wg sync.WaitGroup
    for i, u := range userKeys {
        if u == nil {
            continue
        }
        wg.Add(1)
        // 使用 goroutine 并发加速接口
        go func() {
          defer wg.Done()
          user, err := redis.GetGuest(ctx, u.Id)
          if err != nil {
              log.WarnContextf(ctx, "no found guest user: %v", u)
              continue
          }
          userList = append(userList, user)
        }()   
    }


    return userList, nil
}
```

## AI code review output

```markdown
 ---                                                                                                                                         
  Review Mode                                                                                                                               
                                                                                                                                              
  - Standard                                                                                                                                  
  - Concurrency primitives detected (sync.WaitGroup, go func()). Multiple high-risk signals: shared state mutation from goroutines, goroutine 
  lifecycle management. Elevated from Lite.                                                                                                   
                                                                                                                                              
  ---                                                                                                                                         
  Findings                                                                                                                                  

  [High] continue Inside Goroutine — Compile Error

  - ID: REV-001                                                                                                                               
  - Origin: uncertain
  - Baseline: N/A (baseline not found)                                                                                                        
  - Principle: N/A (no constitution.md)
  - Impact: Code does not compile. continue must be inside a for loop. The goroutine body (go func() { ... }()) is a separate function scope —
   there is no enclosing for from its perspective. The compiler will reject with continue is not in a loop.                                   
  - Evidence: Line 14 opens go func() {, line 19 uses continue — no for exists between them. The outer for at line 8 is in the parent       
  function, not reachable by continue inside the closure.                                                                                     
  - Recommendation: Replace continue with return to exit the goroutine early.                                                               
  - Action: must-fix                                                                                                                          
                                                                                                                                            
  [High] Data Race on userList — Concurrent Append Without Synchronization                                                                    
                                                                                                                                            
  - ID: REV-002                                                                                                                               
  - Origin: uncertain                                                                                                                       
  - Baseline: N/A
  - Principle: N/A
  - Impact: Multiple goroutines execute userList = append(userList, user) concurrently. A slice header is 3 words (pointer, length, capacity)
  — not atomic. This is a confirmed data race: lost writes, corrupted slice, or panic. Detectable by go test -race.                           
  - Evidence: Line 21 userList = append(userList, user) runs inside goroutines spawned at line 14 with no mutex, channel, or other
  synchronization. Per go-concurrency-patterns.md § Race Conditions: "Shared slice append without lock — slice header is 3 words, not atomic."
  - Recommendation: Use a mutex-protected append, a result channel, or errgroup with a channel collector:                                   
  var mu sync.Mutex                                                                                                                           
  mu.Lock()                                                                                                                                   
  userList = append(userList, user)                                                                                                           
  mu.Unlock()                                                                                                                                 
  - Action: must-fix                                                                                                                        

  [High] Missing wg.Wait() Before Return — Goroutines Orphaned                                                                                
   
  - ID: REV-003                                                                                                                               
  - Origin: uncertain                                                                                                                       
  - Baseline: N/A
  - Principle: N/A
  - Impact: return userList, nil executes immediately without waiting for goroutines to complete. The caller receives an empty or partially
  filled slice. All goroutine work is wasted. This defeats the entire purpose of concurrent fetch.                                            
  - Evidence: wg.Add(1) at line 12, defer wg.Done() at line 15, but no wg.Wait() anywhere before return at line 26. Per
  go-concurrency-patterns.md § Goroutine Leak: "No WaitGroup.Wait() or equivalent join before program/test exit" is a red flag.               
  - Recommendation: Add wg.Wait() before the return:                                                                                        
  wg.Wait()                                                                                                                                   
  return userList, nil                                                                                                                      
  - Action: must-fix                                                                                                                          
                                                                                                                                            
  [High] Loop Variable Capture in Goroutine (pre-Go 1.22)                                                                                     
   
  - ID: REV-004                                                                                                                               
  - Origin: uncertain                                                                                                                       
  - Baseline: N/A
  - Principle: N/A
  - Impact: In Go < 1.22, u in for i, u := range userKeys is a single variable reused across iterations. All goroutines capture the same u    
  pointer — by the time they execute, u points to the last element. Every goroutine fetches the same user.                                    
  - Evidence: go func() { ... u.Id ... }() at line 14/16 references u from the range loop without rebinding or passing as a parameter. Per    
  go-concurrency-patterns.md § Loop Variable Capture: "all goroutines see the LAST value of v." Go 1.22+ fixes this with per-iteration        
  scoping, but go.mod version is unknown.                                                                                                   
  - Recommendation: Pass u as a goroutine parameter:                                                                                          
  go func(u *UserKey) {                                                                                                                     
      defer wg.Done()                                                                                                                         
      user, err := redis.GetGuest(ctx, u.Id)
      // ...                                                                                                                                  
  }(u)                                                                                                                                      
  - Action: must-fix
                                                                                                                                              
  [Medium] Unbounded Goroutine Creation — No Concurrency Limit
                                                                                                                                              
  - ID: REV-005                                                                                                                             
  - Origin: uncertain
  - Baseline: N/A
  - Principle: N/A
  - Impact: One goroutine spawned per userKey with no bound. For 10,000 keys, this creates 10,000 goroutines all hitting Redis simultaneously,
   saturating Redis connections and causing timeouts or OOM.                                                                                  
  - Evidence: go func() at line 14 inside for range at line 8 with no semaphore, worker pool, or errgroup.SetLimit(). Per                     
  go-concurrency-patterns.md § Worker Pool: "unbounded goroutine spawning — one goroutine per request" is a red flag.                         
  - Recommendation: Use errgroup with SetLimit:                                                                                             
  g, ctx := errgroup.WithContext(ctx)                                                                                                         
  g.SetLimit(10) // bound concurrent Redis calls                                                                                              
  - Action: follow-up issue                                                                                                                   
                                                                                                                                              
  [Medium] Missing Panic Recovery in Goroutines                                                                                               
                                                                                                                                            
  - ID: REV-006
  - Origin: uncertain
  - Baseline: N/A
  - Principle: N/A
  - Impact: If redis.GetGuest or any downstream code panics, the unrecovered panic crashes the entire process. Panics do not cross goroutine
  boundaries — the parent cannot catch it.                                                                                                    
  - Evidence: No defer func() { recover() }() in the goroutine body. Only defer wg.Done() exists. Per go-concurrency-patterns.md § Goroutine
  Panic Recovery: "defer wg.Done() as the only defer — if the goroutine body panics, wg.Done() runs but the panic still propagates and kills  
  the process."                                                                                                                             
  - Recommendation: Add a recover guard before wg.Done():                                                                                     
  go func(u *UserKey) {                                                                                                                     
      defer wg.Done()                                                                                                                         
      defer func() {
          if r := recover(); r != nil {                                                                                                       
              log.ErrorContextf(ctx, "panic in getBatchUser: %v\n%s", r, debug.Stack())                                                     
          }                                                                                                                                   
      }()
      // ...                                                                                                                                  
  }(u)                                                                                                                                      
  - Action: follow-up issue

  [Medium] Error Always Nil — Total Failure Indistinguishable From Success                                                                    
   
  - ID: REV-007                                                                                                                               
  - Origin: uncertain                                                                                                                       
  - Baseline: N/A                                                                                                                             
  - Principle: N/A
  - Impact: All Redis errors are logged and discarded. The function returns nil error even if every lookup fails. A Redis outage silently     
  returns an empty slice — callers cannot distinguish "no users exist" from "infrastructure failure."                                         
  - Evidence: Lines 17-19: error logged and continued (should be return). Line 26: unconditional return userList, nil. Per                    
  go-error-and-quality.md § Log Once Return Errors.                                                                                           
  - Recommendation: Use errgroup which propagates the first error, or track failure count and return an error when all lookups fail.        
  - Action: follow-up issue                                                                                                                   
                                                                                                                                            
  ---                                                                                                                                         
  Suppressed Items                                                                                                                          
                                                                                                                                              
  None.

  Risk Acceptance / SLA                                                                                                                       
                                                                                                                                              
  ┌──────────┬────────────────────────────────────┬─────────────────────────────┐
  │ Severity │              Finding               │             SLA             │                                                             
  ├──────────┼────────────────────────────────────┼─────────────────────────────┤                                                             
  │ High     │ REV-001, REV-002, REV-003, REV-004 │ Fix within 3 business days  │
  ├──────────┼────────────────────────────────────┼─────────────────────────────┤                                                             
  │ Medium   │ REV-005, REV-006, REV-007          │ Fix within 14 calendar days │                                                           
  └──────────┴────────────────────────────────────┴─────────────────────────────┘                                                             
   
  ---                                                                                                                                         
  Residual Risk / Testing Gaps                                                                                                              
                                                                                                                                              
  1. Verification gaps: -race detector not run. Given 3 confirmed concurrency defects, race testing is critical.
  2. Architectural recommendation: The entire function should be rewritten using errgroup which solves REV-001 (no continue needed), REV-002  
  (channel-based collection), REV-003 (g.Wait() returns errors), REV-005 (SetLimit), and REV-007 (error propagation) in one idiomatic pattern.
   See go-concurrency-patterns.md § Errgroup.                                                                                                 
  3. Named return mismatch: Signature declares users but body uses userList — the named return is never assigned (same cosmetic issue as      
  case-two).                                                                                                                                  
   
  ---                                                                                                                                         
  Summary                                                                                                                                   
         
  0 introduced / 0 pre-existing / 7 uncertain. This function has 4 High-severity concurrency defects including a compile error (REV-001), a
  data race (REV-002), orphaned goroutines (REV-003), and a loop variable capture bug (REV-004). The recommended fix is a full rewrite using  
  errgroup.WithContext + SetLimit, which eliminates all 7 findings in one idiomatic pattern.
```

# example four

## code

```go


var config Config


func main() {
   loadConfig("../config.yaml")
   
   StartProcess()
}


// 读取配置文件
func loadConfig(configFile string) error {


   file, err := os.Open(configFile)
   defer file.Close()
   if err != nil {
      return errors.Wrap("load config err", err)
   }
   
   // 解析配置
    err = json.Unmarshal(data, &config)
    if err != nil {
        // 记录错误日志
        fmt.Printf("Failed to parse config file: %v\n", err)
        return errors.Wrap("parse config err", err)
    }


    // 返回解析后的配置
    return nil
}
```

## AI code review output

```markdown
 Review Mode

  - Lite
  - Two functions (~35 lines), no concurrency, no auth. File I/O and error handling are the primary concern surfaces.

  ---
  Findings

  [High] defer file.Close() Before Error Check — Nil Pointer Panic

  - ID: REV-001
  - Origin: uncertain
  - Baseline: N/A (baseline not found)
  - Principle: N/A (no constitution.md)
  - Impact: If os.Open fails, file is nil. defer file.Close() at line 18 executes when the function returns via the error path at line 20,
  causing a nil pointer dereference panic that crashes the process.
  - Evidence: Line 17: file, err := os.Open(configFile). Line 18: defer file.Close() — runs unconditionally. Line 19: if err != nil — check
  happens AFTER defer is registered. Per go-error-and-quality.md and the anti-example for defer f.Close(): Close must be deferred only after
  confirming Open succeeded.
  - Recommendation:
  file, err := os.Open(configFile)
  if err != nil {
      return fmt.Errorf("load config: %w", err)
  }
  defer file.Close()
  - Action: must-fix

  [High] main() Ignores loadConfig Error — Silent Failure

  - ID: REV-002
  - Origin: uncertain
  - Baseline: N/A
  - Principle: N/A
  - Impact: loadConfig("../config.yaml") returns an error that is discarded. If config loading fails, StartProcess() at line 9 runs with
  zero-value config, causing undefined behavior, silent data corruption, or downstream crashes.
  - Evidence: Line 7: loadConfig("../config.yaml") — return value not captured. Per go-error-and-quality.md § Ignored Errors: discarding an
  error with no explicit _ is a confirmed defect. In main(), a config load failure should be fatal.
  - Recommendation:
  if err := loadConfig("../config.yaml"); err != nil {
      log.Fatalf("failed to load config: %v", err)
  }
  - Action: must-fix

  [High] Undefined Variable data — File Opened But Never Read

  - ID: REV-003
  - Origin: uncertain
  - Baseline: N/A
  - Principle: N/A
  - Impact: json.Unmarshal(data, &config) references data which is never declared or assigned. The file is opened at line 17 but its contents
  are never read. This is a compile error (undefined: data). Additionally, the file is config.yaml (YAML format) but parsed with
  json.Unmarshal — format mismatch even if data existed.
  - Evidence: No ioutil.ReadAll(file), io.ReadAll(file), or any read operation between os.Open (line 17) and json.Unmarshal (line 24). The
  variable data does not appear in any prior declaration.
  - Recommendation:
  data, err := io.ReadAll(file)
  if err != nil {
      return fmt.Errorf("read config file: %w", err)
  }
  // Use yaml.Unmarshal for .yaml files
  if err := yaml.Unmarshal(data, &config); err != nil {
      return fmt.Errorf("parse config: %w", err)
  }
  - Action: must-fix

  [Medium] Log-and-Return — Double Error Reporting

  - ID: REV-004
  - Origin: uncertain
  - Baseline: N/A
  - Principle: N/A
  - Impact: fmt.Printf("Failed to parse config file: %v\n", err) logs the error, then return errors.Wrap(...) returns it. The caller (should
  it handle the error) will log again, producing duplicate error output that clutters logs and misdirects debugging.
  - Evidence: Per go-error-and-quality.md § Log Once, Return Errors: "Logging an error AND returning it causes the same failure to appear
  multiple times in logs." Intermediate layers should wrap and return — the top-level handler (main) decides how to log.
  - Recommendation: Remove the fmt.Printf line. Let the caller decide logging.
  - Action: follow-up issue

  [Medium] Mutable Package-Level Variable — Hidden Global State

  - ID: REV-005
  - Origin: uncertain
  - Baseline: N/A
  - Principle: N/A
  - Impact: var config Config is a mutable global. Any function can read/write it, creating implicit coupling. Impossible to test loadConfig
  in parallel tests (shared state). Violates the principle of explicit dependency injection.
  - Evidence: Per go-error-and-quality.md § Mutable Package-Level Variables: "mutable global state" is a Code Quality finding. loadConfig
  silently writes to this global rather than returning the parsed config.
  - Recommendation: Return the config from loadConfig instead of mutating a global:
  func loadConfig(configFile string) (Config, error) {
      // ...
      return config, nil
  }
  - Action: follow-up issue

  ---
  Suppressed Items

  None.

  Risk Acceptance / SLA                                                                                                                       
                                                                                                                                              
  ┌──────────┬───────────────────────────┬─────────────────────────────┐
  │ Severity │          Finding          │             SLA             │                                                                      
  ├──────────┼───────────────────────────┼─────────────────────────────┤                                                                    
  │ High     │ REV-001, REV-002, REV-003 │ Fix within 3 business days  │
  ├──────────┼───────────────────────────┼─────────────────────────────┤
  │ Medium   │ REV-004, REV-005          │ Fix within 14 calendar days │                                                                      
  └──────────┴───────────────────────────┴─────────────────────────────┘                                                                      
                                                                                                                                              
  ---                                                                                                                                         
  Residual Risk / Testing Gaps                                                                                                              

  1. YAML/JSON format mismatch: config.yaml implies YAML format but json.Unmarshal is used. Even after fixing data, parsing will fail or      
  produce incorrect results. Should use gopkg.in/yaml.v3 or similar.                                                                          
  2. errors.Wrap argument order: If using github.com/pkg/errors, the signature is Wrap(err error, message string) — error first. The code     
  passes ("load config err", err) — string first. This is either a compile error (type mismatch) or a different custom errors package. Verify 
  which errors package is imported.                                                                                                         
  3. fmt.Printf for error logging: Line 27 uses fmt.Printf rather than a structured logging library. Lacks timestamps, log levels, and        
  structured context. Minor compared to the double-reporting issue (REV-004).                                                                 
  4. Relative path ../config.yaml: Works but is fragile — depends on the working directory at runtime. Consider accepting via flag or
  environment variable for production use.                                                                                                    
                                                                                                                                            
  ---                                                                                                                                         
  Summary                                                                                                                                   
         
  0 introduced / 0 pre-existing / 5 uncertain. Three High findings: nil panic from defer-before-check (REV-001), silently ignored error in
  main (REV-002), and undefined variable / missing file read (REV-003). REV-001 and REV-003 are compile/crash-level bugs. REV-002 means       
  configuration failures go undetected, allowing StartProcess() to run with zero-value config.
```