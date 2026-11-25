# How to Debug POST Detection

## 3 Ways to Check if POST is Working

### Method 1: Check Apache Access Logs

Your Apache logs should show the POST request when the form submits.

**Location:** Check your XAMPP Apache logs (usually `C:\xampp\apache\logs\access.log`)

**What to look for:**
```
103.201.151.153 - "POST /dummy/submit.php HTTP/1.1" 200 - "HeadlessChrome"
```

If you see this, the POST IS working! The issue is just that the tool isn't detecting it.

### Method 2: Add Logging to submit.php

Update your `submit.php` to log all requests:

```php
<?php
// submit.php
$logFile = __DIR__ . '/submissions.log';
$data = [
    'timestamp' => date('Y-m-d H:i:s'),
    'method' => $_SERVER['REQUEST_METHOD'],
    'data' => $_POST,
    'user_agent' => $_SERVER['HTTP_USER_AGENT'] ?? 'unknown'
];

file_put_contents($logFile, json_encode($data) . PHP_EOL, FILE_APPEND);

header('Content-Type: application/json');
http_response_code(200);
echo json_encode(['success' => true, 'message' => 'Form received']);
?>
```

Then check `submissions.log` to see if data was received.

### Method 3: Enable Network Logging in the Tool

The tool monitors network requests but doesn't log them by default. Let's add detailed logging.

---

## Why the Tool Might Not Detect POST

The tool looks for:
1. A network request during the 10-second window AFTER clicking submit
2. The request must be a POST with status 200/201/302
3. The URL must match certain patterns

**Common issues:**
- Form action is empty or `#` (no actual POST sent)
- Form uses JavaScript to submit (AJAX without full page load)
- POST happens but too quickly before monitoring starts
- POST goes to a different domain (CORS)

---

## Quick Test: Manual Browser Check

1. **Open the form in your browser**
   ```
   https://site23359-uw0p89.scloudsite101.com/dummy/contact.html
   ```

2. **Open Developer Tools** (F12)

3. **Go to Network tab**

4. **Fill and submit the form manually**

5. **Look for POST requests** in the Network tab:
   - Should see `submit.php` or similar
   - Status should be 200
   - Method should be POST

If you see this POST in browser DevTools but the tool doesn't detect it, then it's a tool monitoring issue.

---

## Next Steps

1. Check your Apache logs for POST requests
2. Add logging to submit.php
3. Test manually in browser DevTools
4. Share what you find and I'll help fix the detection
