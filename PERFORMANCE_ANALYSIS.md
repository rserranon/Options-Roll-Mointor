# Performance Analysis & Optimization Guide

## Executive Summary

Your application has **significant performance bottlenecks** in market data retrieval, with a single position analysis taking **140-145 seconds** without caching. The main issues are:

1. **Sequential API calls with long waits** (~3.4s per option quote)
2. **Sampling too many strikes** (up to 40 strikes per position)
3. **Inefficient retry logic** with progressive waits (2s → 4s)
4. **No concurrent request processing**

**Good news**: You already have a caching system in place that can help significantly!

---

## Performance Bottlenecks Identified

### 1. **portfolio.py - Position Retrieval** (CRITICAL)
**Time per position: 2-9 seconds**

```python
# Current implementation (lines 38-70)
for attempt in range(retry_attempts):
    ticker = ib.reqMktData(contract, '106', False, False)
    wait_time = 2.0 + (attempt * 1.0)  # 2s, 3s, 4s
    ib.sleep(wait_time)
    wait_for_greeks(ticker, timeout=4.0)  # Additional 4s wait
    # ...
```

**Issues:**
- Progressive waits: 2s → 3s → 4s = **9s total** per retry cycle
- `wait_for_greeks()` adds another **4s timeout**
- **Total worst case: 13s per position** just to get current data

**Impact:** With 3 positions = 39 seconds just for initial data retrieval

---

### 2. **options_finder.py - Strike Sampling** (CRITICAL)
**Time per position: 60-136 seconds**

```python
# Current implementation (lines 110-138)
if len(band) <= 40:
    sample = band  # Could be 40 strikes!
else:
    sample = band[::2][:40]  # Still 40 strikes

for k in sample:
    opt_data = get_option_quote(ib, symbol, expiry, k, right=right)
    # Each quote: 0.4s sleep + 3.0s Greeks wait = 3.4s
```

**Issues:**
- Samples **up to 40 strikes** per expiry
- Each strike takes **3.4s** (sleep + Greeks wait)
- **No early exit** - checks ALL 40 strikes even after finding good options
- **Total: 40 × 3.4s = 136 seconds per position**

**Your own documentation says:**
> "Optimized to 12-15 strikes average (3-4× faster)"

But code samples **40 strikes**, not 12-15!

---

### 3. **market_data.py - Sequential Requests** (HIGH)
**Time per request: 3.4 seconds**

```python
# get_option_quote (lines 98-99)
ib.sleep(0.4)
wait_for_greeks(tk, timeout=timeout)  # Default 2.5s, can be 3.0s
```

**Issues:**
- Every option quote waits **0.4s + 2.5-3.0s = 3.4s**
- No parallelization - all requests are sequential
- Cache helps but only after first run

---

### 4. **wait_for_greeks() - Polling Loop** (MEDIUM)
**Time per call: 0-3 seconds**

```python
# lines 45-61
def wait_for_greeks(tk: Ticker, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if tk.modelGreeks and tk.modelGreeks.delta is not None:
            return True
        time.sleep(0.12)  # Poll every 120ms
    return False
```

**Issues:**
- Fixed **0.12s** sleep between polls (too conservative)
- Always waits full timeout if Greeks unavailable
- Could use event-based approach instead of polling

---

## Time Breakdown Per Position

### Without Cache (First Run):
```
1. Get current position data:         2-9s    (portfolio.py retries)
2. Get stock price:                    0.8s    (market_data.py)
3. Get same strike quote:              3.4s    (market_data.py)
4. Find strikes by delta:             60-136s  (options_finder.py)
   - Sample 20-40 strikes × 3.4s each
   ----------------------------------------
   TOTAL:                             66-149s per position
```

### With Cache (Subsequent Runs):
```
1. Get current position data:         2-9s    (portfolio.py - not cached)
2. Get stock price:                    0.8s    (not cached)
3. Get same strike quote:              0.01s   (CACHED!)
4. Find strikes by delta:              0.01s   (CACHED!)
   ----------------------------------------
   TOTAL:                             3-10s per position
```

**Cache is crucial** but only helps on subsequent runs!

---

## Optimization Strategies

### Priority 1: REDUCE STRIKE SAMPLING (Immediate Impact)

**Problem:** Sampling 40 strikes takes 136 seconds

**Solution:** Implement true early exit and reduce sample size

```python
# In options_finder.py - find_strikes_by_delta()
# BEFORE (lines 110-138):
if len(band) <= 40:
    sample = band
else:
    sample = band[::2][:40]

for k in sample:
    opt_data = get_option_quote(ib, symbol, expiry, k, right=right)
    if opt_data and opt_data['delta'] is not None:
        options.append(opt_data)

# AFTER (RECOMMENDED):
if len(band) <= 15:
    sample = band
else:
    # Evenly sample max 15 strikes
    step = len(band) / 15
    sample = [band[int(i * step)] for i in range(15)]

options = []
good_options_count = 0
target_good_options = 8  # Stop after finding 8 near target

for k in sample:
    opt_data = get_option_quote(ib, symbol, expiry, k, right=right)
    if opt_data and opt_data['delta'] is not None:
        options.append(opt_data)
        
        # Early exit if we found enough good options
        if abs(abs(opt_data['delta']) - abs(target_delta)) <= 0.05:
            good_options_count += 1
            if good_options_count >= target_good_options:
                break
```

**Impact:** 
- Worst case: 15 × 3.4s = **51 seconds** (vs 136s = **62% faster**)
- Average case: 8-10 × 3.4s = **27-34 seconds** (vs 60s = **50% faster**)

---

### Priority 2: PARALLEL API REQUESTS (High Impact)

**Problem:** All API calls are sequential

**Solution:** Use asyncio or threading for parallel requests

```python
# In options_finder.py - find_strikes_by_delta()
# Use concurrent requests for strike sampling

from concurrent.futures import ThreadPoolExecutor, as_completed

def get_strike_data_parallel(ib, symbol, expiry, strikes, right='C', max_workers=5):
    """Fetch quotes for multiple strikes in parallel."""
    results = []
    
    def fetch_quote(strike):
        return get_option_quote(ib, symbol, expiry, strike, right=right)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_strike = {
            executor.submit(fetch_quote, k): k for k in strikes
        }
        
        for future in as_completed(future_to_strike):
            opt_data = future.result()
            if opt_data and opt_data['delta'] is not None:
                results.append(opt_data)
    
    return results

# Usage in find_strikes_by_delta():
options = get_strike_data_parallel(ib, symbol, next_expiry, sample[:15], right)
```

**Impact:**
- 15 strikes in parallel (5 workers): **15s** (vs 51s = **70% faster**)
- Combined with early exit: **10-15s** (vs 60-136s = **85% faster**)

**⚠️ Caution:** IB API has rate limits. Test with max_workers=3-5 to avoid throttling.

---

### Priority 3: OPTIMIZE WAIT TIMES (Medium Impact)

#### 3A. Reduce portfolio.py retry waits

```python
# In portfolio.py - get_current_positions()
# BEFORE (lines 42-44):
wait_time = 2.0 + (attempt * 1.0)  # 2s, 3s, 4s
ib.sleep(wait_time)
wait_for_greeks(ticker, timeout=4.0)

# AFTER (RECOMMENDED):
# Use shorter, smarter waits
if attempt == 0:
    wait_time = 1.5  # First attempt: quick check
else:
    wait_time = 2.0  # Subsequent: give more time

ib.sleep(wait_time)
wait_for_greeks(ticker, timeout=2.5)  # Reduce from 4.0s
```

**Impact:** 
- First attempt: 1.5s + 2.5s = **4s** (vs 6s = **33% faster**)
- Total retries: 4s + 4.5s + 4.5s = **13s** (vs 18s = **28% faster**)

#### 3B. Adaptive polling in wait_for_greeks()

```python
# In market_data.py - wait_for_greeks()
# BEFORE (line 60):
time.sleep(0.12)

# AFTER (RECOMMENDED):
# Start with faster polling, then slow down
elapsed = time.time() - (end - timeout)
if elapsed < 0.5:
    time.sleep(0.05)  # Fast polling first 500ms
elif elapsed < 1.5:
    time.sleep(0.10)  # Medium polling next 1s
else:
    time.sleep(0.20)  # Slower polling if taking long
```

**Impact:** Greeks often available quickly - **saves 200-500ms per request**

---

### Priority 4: SMARTER CACHING (Medium Impact)

#### 4A. Cache stock prices

```python
# In market_data.py - add stock price caching
def get_stock_price(ib, symbol, use_cache=True, cache_ttl=30):
    """Get current stock price with caching."""
    if use_cache:
        cache = get_cache(ttl_seconds=cache_ttl)
        cached = cache.get(symbol, 'STOCK', 0, 'STOCK')
        if cached:
            return cached.get('price')
    
    # Existing stock price logic...
    price = safe_mark(stkt)
    
    if use_cache and price:
        cache.put(symbol, 'STOCK', 0, 'STOCK', {'price': price})
    
    return price
```

**Impact:** Saves **0.8s per position** on subsequent checks

#### 4B. Increase cache TTL during market hours

```python
# In roll_monitor.py or roll_monitor_live.py
# Use longer cache TTL during active monitoring
cache_ttl = 300 if continuous_mode else 60  # 5 min vs 1 min
```

**Impact:** More cache hits over time, especially with live monitor

---

### Priority 5: REDUCE RETRY ATTEMPTS (Low Risk)

```python
# In portfolio.py - get_current_positions()
# BEFORE (line 8):
def get_current_positions(ib, retry_attempts=3, initial_wait=1.0):

# AFTER (RECOMMENDED):
def get_current_positions(ib, retry_attempts=2, initial_wait=1.0):
```

**Impact:** Removes 4s third retry, saves **4-5s per position with issues**

---

## Recommended Implementation Plan

### Phase 1: Quick Wins (1-2 hours)
1. ✅ **Reduce strike sampling to 15** (from 40)
2. ✅ **Add early exit logic** (stop after 8 good options)
3. ✅ **Reduce retry attempts to 2** (from 3)
4. ✅ **Shorten wait times** in portfolio.py

**Expected improvement: 50-60% faster**

### Phase 2: Medium Effort (4-6 hours)
5. ✅ **Implement parallel strike fetching** (ThreadPoolExecutor)
6. ✅ **Add stock price caching**
7. ✅ **Optimize wait_for_greeks() polling**

**Expected improvement: 70-80% faster**

### Phase 3: Advanced (8-12 hours)
8. ⚠️ **Consider event-based Greeks updates** (IB callbacks instead of polling)
9. ⚠️ **Pre-warm cache** on startup
10. ⚠️ **Batch multiple positions** if possible

**Expected improvement: 85-90% faster**

---

## Performance Testing Recommendations

### Add timing instrumentation:

```python
import time

def profile_function(func):
    """Decorator to profile function execution time."""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        print(f"[PERF] {func.__name__}: {elapsed:.2f}s")
        return result
    return wrapper

# Usage:
@profile_function
def find_strikes_by_delta(ib, symbol, expiry, target_delta, spot, current_strike, right='C'):
    # ... existing code
```

### Add cache statistics reporting:

```python
# At end of each monitoring cycle
cache = get_cache()
stats = cache.get_stats()
print(f"\n[CACHE] Hits: {stats['hits']}, Misses: {stats['misses']}, "
      f"Hit Rate: {stats['hit_rate']:.1f}%, Size: {stats['cache_size']}")
```

---

## Configuration Recommendations

### For Live Monitor (frequent checks):
```python
--interval 60              # Check every minute
cache_ttl = 300           # 5-minute cache
max_workers = 5           # More parallel requests
max_strikes = 12          # Fewer strikes per check
```

### For Classic Monitor (detailed analysis):
```python
--interval 300            # Check every 5 minutes
cache_ttl = 120          # 2-minute cache
max_workers = 3          # Conservative parallelization
max_strikes = 15         # More thorough sampling
```

---

## Risk Assessment

### Low Risk Changes:
- ✅ Reduce strike sampling from 40 to 15
- ✅ Add early exit after 8 good options
- ✅ Reduce retry attempts from 3 to 2
- ✅ Cache stock prices

### Medium Risk Changes:
- ⚠️ Parallel API requests (test rate limits)
- ⚠️ Shorten wait times (may reduce data quality)
- ⚠️ Adaptive polling (test on slow connections)

### High Risk Changes:
- ⚠️ Event-based Greeks (major refactor)
- ⚠️ Remove retry logic (may cause failures)
- ⚠️ Aggressive caching (stale data risk)

---

## Expected Results

### Current Performance:
```
Single position analysis:  140-145s (no cache)
Single position analysis:   3-10s  (with cache)
3 positions first run:     420-435s (7+ minutes!)
3 positions cached:          9-30s
```

### After Phase 1 Optimizations:
```
Single position analysis:   60-70s  (no cache) - 50% improvement
Single position analysis:    3-10s  (with cache)
3 positions first run:     180-210s (3-3.5 minutes) - 50% improvement
3 positions cached:          9-30s
```

### After Phase 2 Optimizations:
```
Single position analysis:   20-30s  (no cache) - 80% improvement
Single position analysis:    2-5s   (with cache)
3 positions first run:      60-90s  (1-1.5 minutes) - 80% improvement
3 positions cached:          6-15s
```

---

## Monitoring & Validation

### Add performance metrics:
1. Track average time per position
2. Monitor cache hit rate
3. Log slow operations (>5s)
4. Alert on API throttling

### Validate data quality:
1. Compare results before/after optimization
2. Verify all Greeks are populated
3. Check for missing strikes
4. Ensure roll recommendations are consistent

---

## Conclusion

Your main bottleneck is **strike sampling taking 60-136 seconds** per position. The code samples **40 strikes sequentially** when it should sample **12-15 with early exit**.

**Quick Fix (30 minutes):**
Change line 111 in `options_finder.py`:
```python
# From:
if len(band) <= 40:
# To:
if len(band) <= 12:
```

And change line 117:
```python
# From:
sample = band[::2][:40]
# To:
sample = [band[int(i * len(band) / 12)] for i in range(12)]
```

Add early exit at line 127:
```python
good_options_count = 0
for k in sample:
    opt_data = get_option_quote(ib, symbol, expiry, k, right=right)
    if opt_data and opt_data['delta'] is not None:
        options.append(opt_data)
        if abs(abs(opt_data['delta']) - abs(target_delta)) <= 0.05:
            good_options_count += 1
            if good_options_count >= 8:
                break
```

**This alone will give you 50-60% performance improvement!**

For maximum performance, implement parallel requests (Phase 2) for **80% improvement overall**.
