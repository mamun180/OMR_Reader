## Bugfix and Recommendation: Online License Validation

### Summary of Findings

I have analyzed the application's Python code (`license_manager.py`, `ui_registration.py`, and `ui_main.py`) and have determined that the client-side logic is correct. The application properly attempts to perform an online license verification for any license type that is not explicitly marked as `"UNLIMITED"`.

The issue you're observing—where day/count-based licenses are not being validated online—is caused by the **Google Apps Script backend**.

### Root Cause

When the application activates a new license key using the `"activate"` request, the Google Apps Script returns a JSON object representing the license. This object is then saved locally on the user's machine.

The problem is that for day-based or count-based licenses, the script is incorrectly constructing this JSON object with `"license_type": "UNLIMITED"`.

When the application restarts, `license_manager.py` reads this local license file. Seeing that the `license_type` is `"UNLIMITED"`, it correctly performs an **offline** signature check, completely skipping the required online check for day/count validity.

### How to Fix the Google Apps Script

The developer in charge of the Google Apps Script needs to modify the `doPost` function (or wherever the activation logic resides).

When handling an `"activate"` request, the script should:

1.  Look up the license key in the Google Sheet.
2.  Determine its actual type (e.g., `"DAY_LIMITED"`, `"COUNT_LIMITED"`, `"UNLIMITED"`).
3.  When generating the successful response, create a `license` JSON object that accurately reflects this type.

### Hypothetical `Code.gs` Example

Below is a hypothetical example of what the Google Apps Script `doPost` function might look like and how to correct it.

**Please note:** This is a simplified example to illustrate the necessary change. The actual script may be more complex.

```javascript
// This is a hypothetical Google Apps Script (Code.gs) file.
// The actual implementation may vary.

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const requestType = data.request_type;
    const key = data.key;

    // --- Other request types (verify, etc.) would be here ---

    if (requestType === "activate") {
      const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Licenses");
      const licenseData = findLicense(sheet, key); // A function to find the license row

      if (!licenseData) {
        return createJsonResponse({ status: "FAILED", message: "Invalid license key." });
      }

      // --- THE FIX IS HERE ---
      // The script must determine the correct license type from the spreadsheet.
      // Let's assume the spreadsheet has a 'type' column.
      const actualLicenseType = licenseData.type; // e.g., "DAY_LIMITED", "UNLIMITED"
      
      const machineHash = data.machine_hash;
      
      // Check if machine hash can be written, etc.
      // ... (logic for first-time activation vs. re-installation)

      // When building the response, use the *actual* license type.
      const licensePayloadForClient = {
        license_key: key,
        machine_hash: machineHash,
        // INCORRECT (What's likely happening now):
        // license_type: "UNLIMITED", // <-- This is the bug!

        // CORRECT:
        license_type: actualLicenseType, // <-- Use the type from the sheet
        
        // You might also include other data like expiry date for the client
        // expires_on: licenseData.expires_on 
      };

      // You would also generate and include the server_signature for UNLIMITED licenses here.
      if (actualLicenseType === "UNLIMITED") {
        // Sign the payload and add the signature.
        // const signature = sign(licensePayloadForClient);
        // licensePayloadForClient.server_signature = signature;
      }
      
      // Update the sheet (set machine hash, activation date, etc.)
      updateSheetOnActivation(sheet, licenseData.row, machineHash);

      // Return the correctly formed license object to the client
      return createJsonResponse({
        status: "SUCCESS_ACTIVATED",
        message: "Activation successful.",
        license: licensePayloadForClient
      });
    }

  } catch (err) {
    return createJsonResponse({ status: "ERROR", message: "Server error: " + err.toString() });
  }

  // Helper to return JSON
  function createJsonResponse(obj) {
    return ContentService
      .createTextOutput(JSON.stringify(obj))
      .setMimeType(ContentService.MimeType.JSON);
  }
  
  // Placeholder for your other functions
  function findLicense(sheet, key) { /* ... */ return {type: 'DAY_LIMITED', row: 2}; }
  function updateSheetOnActivation(sheet, row, hash) { /* ... */ }

}
```

### Recommendation

To resolve this bug, please forward this explanation to the developer responsible for the Google Apps Script backend and ask them to implement the change described above. The fix is entirely on the server side. No changes are needed in the Python application code.
