// Debugging script to check campaign functionality
// Open analytics.html and paste this in the browser console

console.log("=".repeat(50));
console.log("CAMPAIGN DEBUGGING SCRIPT");
console.log("=".repeat(50));

// 1. Check if backend is accessible
console.log("\n1. Testing backend connection...");
fetch('http://127.0.0.1:8000/api/campaigns')
    .then(r => {
        console.log("✓ Backend responded with status:", r.status);
        return r.json();
    })
    .then(data => {
        console.log("✓ Campaigns data:", data);
        if (data.items && data.items.length > 0) {
            console.log("✓ Found", data.items.length, "campaigns");
            console.log("First campaign:", data.items[0]);
        } else {
            console.log("⚠ No campaigns found");
        }
    })
    .catch(err => console.error("✗ Backend error:", err));

// 2. Check if functions are defined
console.log("\n2. Checking if functions exist...");
console.log("campaignRestart:", typeof window.campaignRestart);
console.log("campaignPause:", typeof window.campaignPause);
console.log("loadCampaigns:", typeof window.loadCampaigns);

// 3. Test starting a campaign (replace ID with your campaign ID)
console.log("\n3. To test starting a campaign, run this in console:");
console.log("  campaignRestart(YOUR_CAMPAIGN_ID_HERE)");
console.log("\nExample: campaignRestart(1)");

console.log("\n" + "=".repeat(50));
