# Concurrent URL Processing - Configuration Guide

## Overview

Your form filler now supports **concurrent processing** to speed up campaigns by processing multiple URLs simultaneously!

## Configuration

### Environment Variable

Set `CONCURRENT_BROWSERS` to control how many URLs are processed at once:

```bash
# Windows PowerShell
$env:CONCURRENT_BROWSERS="3"
python fastapi_backend.py

# Or add to .env file
CONCURRENT_BROWSERS=3
```

### Recommended Values

| Value | Speed | System Requirements | Best For |
|-------|-------|---------------------|----------|
| `1` | 1x (default) | Any system | Testing, debugging, low-resource systems |
| `2-3` | 2-3x faster | 4GB+ RAM | Most users, balanced speed/stability |
| `4-5` | 4-5x faster | 8GB+ RAM | Large campaigns, powerful systems |
| `6+` | 6x+ faster | 16GB+ RAM | Very large campaigns, high-end systems |

## Performance Estimates

### 1000 URLs Campaign
- **Sequential (1)**: ~8.3 hours
- **Concurrent (3)**: ~2.8 hours ⚡ **5.5 hours saved**
- **Concurrent (5)**: ~1.7 hours ⚡ **6.6 hours saved**

### 25,000 URLs Campaign
- **Sequential (1)**: ~208 hours (8.6 days)
- **Concurrent (3)**: ~69 hours (2.9 days) ⚡ **139 hours saved**
- **Concurrent (5)**: ~42 hours (1.8 days) ⚡ **166 hours saved**

## Safety Features

✅ **All timeouts preserved** - 10-second POST response wait unchanged  
✅ **Error isolation** - Failed URLs don't affect others  
✅ **Resource limits** - Semaphore prevents system overload  
✅ **Progress tracking** - Real-time updates continue  
✅ **Pause support** - Can pause mid-campaign  

## How It Works

Instead of processing URLs one-by-one:
```
URL1 → URL2 → URL3 → URL4 → URL5
```

They're processed in concurrent batches:
```
Batch 1: URL1, URL2, URL3 (all at once)
Batch 2: URL4, URL5, URL6 (all at once)
```

Each URL still gets:
- Full 10-second POST response timeout
- Complete form discovery
- Independent error handling
- Proper response capture

## Testing Recommendations

### Start Small
1. Set `CONCURRENT_BROWSERS=2`
2. Run a campaign with 10-20 URLs
3. Verify all responses captured
4. Check system resources (CPU, RAM)

### Scale Up
1. If stable, increase to `CONCURRENT_BROWSERS=3`
2. Run with 100 URLs
3. Monitor for any issues
4. Adjust based on system performance

### Production
1. Use `CONCURRENT_BROWSERS=3-5` based on your system
2. Monitor first few campaigns closely
3. Adjust if you see timeouts or crashes

## Rollback

If you experience issues:
```bash
# Set back to sequential processing
$env:CONCURRENT_BROWSERS="1"
python fastapi_backend.py
```

Or remove the environment variable entirely to use the default (1).

## Troubleshooting

**System running slow?**
- Reduce CONCURRENT_BROWSERS value
- Close other applications
- Upgrade RAM if possible

**Missing responses?**
- Check if POST_SUBMIT_WAIT_MS is still 10000
- Verify network is stable
- Try reducing concurrency

**Crashes or errors?**
- Set CONCURRENT_BROWSERS=1 temporarily
- Check error logs
- Report specific errors for help

---

**Status**: ✅ Implemented and ready to use!
