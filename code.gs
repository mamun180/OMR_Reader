// --- PASTE YOUR RSA PRIVATE KEY HERE ---
// This key MUST be kept secret and should only be in this Google Apps Script.
// It must be a PKCS#8 formatted key.
const RSA_PRIVATE_KEY_PEM = `-----BEGIN PRIVATE KEY-----
MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQCYLVqeNvG0zndC
36bUWxuKIQ3XJ63JffweKFN7uDRsCuiWOF7DQRs2LPMvpzoty7Bxsou5Ekmj0pt+
g28yAnAFgxGWUVlWVnm/OqvngRJ9K3P/XGK5LDgYYuibr1+zp4lS+g9oBuFo+RZ+
xo08M5in5m/Ilca3GvaxQ80Ei6hkltHbzmPrh2m02r9LF/bjcXANkZGqG/7q2re3
Fvg43uyeulDu5AOr6MmrtQEYJ2baKE1HAll96f2t1MbsBGVpbOrgdg7xkXrMsYlR
P9gqX5UeruaXBZISN6fNbdMOMNJCtFsgxkgOENm5w8VlMhE9OBmLxU0WYUKlmv5M
IPlKcNp3AgMBAAECggEAKmghI4veKWuL0ofuvqiw8PorGDUHeenw0xqbwRNhEGat
0AbfaXwAMEWwcywfy1lCzzxZMXbGLK/pAwVvfDkvrGmNAh2jTqsEfGTGONpAI79z
MMs2+7E15J3TgmcJvU/HtebXWj7om88mFKgR/Z/HP6q4peYPHUGXU2i4fjbI81ai
HOTY5NhWzAsDd4gp1BkIpb335UwNx/puydbg6d0UvFjtOKPEpXeUvCmW5NMqS9yK
nkDqp0AbngekjB7O0M8zOOmIkMH+wLXvCrkXC59B3WKNn3EHrRKikvLnEaLt8KMm
pmMikrwAqvDuTHG+CIucIBFGQyJ/P/BDGSBGCHf6yQKBgQDGFs3ucwgI27ejjELy
aWwWDcnY/FjF+wScdilsygNELTl1D/otpL8xw/qQOSFdEoDQjDtjYjiXxzexixKm
IiRgmVCisATYEiIjFvztQbI0Gh3oILCvca2YcyhMPboAE6GmrllY/MfTWFKxhlJ2
VA//Xng/VKuoIyRuBHDci617vQKBgQDEqnQQPcLnu34zTRJsN0IFwfRp+zWhpX+/
mp2w4I2oHW6AihSHcWzfxquxnJ9NiimBilqCi9mA89eneLLoc/Tl1ow4SheVRrJV
jTqGQP8p65+gyLBRtrJLfj9jAZv1hyERlctiPIVZqKt4hj2kKIGfP6+s9fEPXd7a
RcMo40rYQwKBgGzJqV8DHa5/vGK9bSbkbs/N0sSwEbDpIqcq3aU5bIHMtHltxN+8
UqRqFPmP5prOxp/B4/u4vYvdhOCkmCFVLtU+XeJ6+K4Rh13uCgniwpOKpFIPYfl4
XPYUiFUWsUfJgEWiCr+sU7HmF8QXGMKTeBWvNCrTvVIhuqgRGEqHC0ehAoGAUwxT
5MPf+XGQkmNagz42cC3+Y37EoBU+RBArxRSeXT7IehlVH/kC6+B+gotMLjdI3b4q
CHS8DZtrFvp+OnE1GpWmMuL+4HexOTVhYG40EmTAzOnSoz8OPZj7dXipfl5o1X83
Gq3J9hmnB0dQ4nCEhFYlflmBSWbvg6bwCeUppvcCgYA2zpGlrEuHfZiS/WQBv9+n
59X5ZmPQE3Cs4RIid5kXHTaF+r6XBVF7RhSRk7FOc591cVxMW1N8MvDTvHyiIFoM
e5fBWZCR++1tYaHvEkToAE780+4FxY5+y8US3i1ftzmJZcJvCx/3SK0yjnCWP/SZ
/NRw4dFDWlrQMu8V9cxg6g==
-----END PRIVATE KEY-----
`;

/**
 * Converts an array of bytes to a hexadecimal string.
 * This is a utility function for creating the signature.
 */
function bytesToHex(bytes) {
  let hex = [];
  for (let i = 0; i < bytes.length; i++) {
    let b = bytes[i];
    if (b < 0) { b = 256 + b; }
    hex.push((b < 16 ? '0' : '') + b.toString(16));
  }
  return hex.join('');
}

/**
 * Signs a given data string using the RSA private key.
 * The signature is used for verifying the integrity of UNLIMITED licenses offline.
 */
function signData(data, privateKeyPem) {
    // The computeRsaSignature function takes the full PEM key string.
    const signatureBytes = Utilities.computeRsaSignature(Utilities.newBlob(data), privateKeyPem, Utilities.RsaAlgorithm.RSA_SHA_256);
    return bytesToHex(signatureBytes);
}

/**
 * The main function that handles POST requests from the client application.
 * It validates license keys based on the rules in the "Licenses" spreadsheet.
 */
function doPost(e) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Licenses");
    if (!sheet) {
      return createJsonResponse({ "status": "ERROR", "message": "Server configuration error: 'Licenses' sheet not found." });
    }
    
    var postData = JSON.parse(e.postData.contents);

    var licenseKey = postData.key;
    var machineHash = postData.machine_hash;
    var appName = postData.app_name;
    var requestType = postData.request_type; // "activate" or "verify"

    var range = sheet.getDataRange();
    var values = range.getValues();

    for (var i = 1; i < values.length; i++) { // Start from 1 to skip header row
      if (values[i][0] == licenseKey) { // license_key is in column A (index 0)
        
        // --- Read license details from the sheet ---
        var licenseType = values[i][1];       // license_type (UNLIMITED, DAY_BASED, COUNT_BASED) is in column B
        var value = values[i][2];             // value (days or counts) is in column C
        var storedMachineHash = values[i][3]; // machine_hash is in column D
        var status = values[i][4];            // status (e.g., "activated") is in column E
        var activationDate = values[i][5] ? new Date(values[i][5]) : null; // activation_date is in column F
        
        // --- Handle First-Time Activation ---
        if (requestType === "activate") {
          // Deny if the license is already activated on a DIFFERENT machine.
          if (status === "activated" && storedMachineHash && storedMachineHash !== machineHash) {
            return createJsonResponse({ "status": "DENIED", "message": "License already activated on another machine." });
          }
          
          // If it's a new activation or reactivation on the same machine, update details.
          const currentDate = new Date();
          sheet.getRange(i + 1, 4).setValue(machineHash); // D: machine_hash
          sheet.getRange(i + 1, 5).setValue("activated"); // E: status
          sheet.getRange(i + 1, 6).setValue(currentDate); // F: activation_date
          sheet.getRange(i + 1, 7).setValue(appName);     // G: app_name

          // --- Respond based on license type ---
          if (licenseType === "UNLIMITED") {
            // For unlimited, create and sign a license file for the client to store for offline use.
            const licensePayload = {
              "license_type": "UNLIMITED",
              "license_key": licenseKey,
              "machine_hash": machineHash,
              "activated_on": currentDate.toISOString().split('T')[0],
              "app_name": appName,
            };
            // The payload is stringified and sorted to ensure a consistent signature.
            const payloadString = JSON.stringify(licensePayload, Object.keys(licensePayload).sort());
            const signature = signData(payloadString, RSA_PRIVATE_KEY_PEM);
            
            const signedLicense = { ...licensePayload, server_signature: signature };
            return createJsonResponse({ "status": "SUCCESS_UNLIMITED", "license": signedLicense });

          } else { // DAY_BASED and COUNT_BASED
            // For DAY_BASED and COUNT_BASED, create a license object for the client.
            // This ensures the client saves a complete license file with the correct type.
            const licensePayload = {
              "license_type": licenseType, // Use the actual type from the sheet
              "license_key": licenseKey,
              "machine_hash": machineHash,
              "activated_on": currentDate.toISOString().split('T')[0],
              "app_name": appName
            };
            
            return createJsonResponse({ 
              "status": "SUCCESS_ACTIVATED", 
              "message": "License successfully activated. Online verification will be required.",
              "license": licensePayload // Return the license object
            });
          }
        }

        // --- Handle Subsequent Verifications (for online-dependent licenses) ---
        if (requestType === "verify") {
          // Verification always fails if the machine hash doesn't match the one from activation.
          if (storedMachineHash !== machineHash) {
            return createJsonResponse({ "status": "DENIED", "message": "Machine hash does not match activated machine." });
          }
          
          if (status !== "activated") {
              return createJsonResponse({ "status": "DENIED", "message": "License has not been activated." });
          }

          if (licenseType === "UNLIMITED") {
             // This case is a fallback. The client should ideally verify unlimited licenses offline after activation.
             return createJsonResponse({ "status": "APPROVED", "message": "Unlimited license is valid." });
          }

          if (licenseType === "DAY_BASED") {
            if (!activationDate) {
              return createJsonResponse({ "status": "DENIED", "message": "Invalid activation date." });
            }
            const daysAllowed = parseInt(value, 10);
            const today = new Date();
            // Calculate days elapsed since activation. Math.ceil ensures any part of a day counts.
            const daysElapsed = Math.ceil((today - activationDate) / (1000 * 60 * 60 * 24));
            
            if (daysElapsed <= daysAllowed) {
              const daysRemaining = daysAllowed - daysElapsed;
              return createJsonResponse({ "status": "APPROVED", "message": "OK. License is valid. " + daysRemaining + " day(s) remaining." });
            } else {
              return createJsonResponse({ "status": "DENIED", "message": "License has expired." });
            }
          }

          if (licenseType === "COUNT_BASED") {
            let usesRemaining = parseInt(value, 10);
            if (usesRemaining > 0) {
              sheet.getRange(i + 1, 3).setValue(usesRemaining - 1); // Decrement uses in the sheet (Column C)
              return createJsonResponse({ "status": "APPROVED", "message": "OK. Uses remaining: " + (usesRemaining - 1) });
            } else {
              return createJsonResponse({ "status": "DENIED", "message": "No uses remaining on this license." });
            }
          }
        }
        
        return createJsonResponse({ "status": "DENIED", "message": "Invalid license type '" + licenseType + "' in sheet." });
      }
    }

    return createJsonResponse({ "status": "DENIED", "message": "Invalid license key." });

  } catch (err) {
    // Definitive debugging logs
    Logger.log("--- CATCH BLOCK ENTERED ---");
    Logger.log("--- ERROR: " + err.toString() + " ---");

    // Log the detailed error for debugging, but return a generic message to the user.
    Logger.log("Server Error: " + err.toString() + "\n" + err.stack);
    return createJsonResponse({ "status": "ERROR", "message": "An error occurred on the license server." });
  }
}

/**
 * Creates a JSON response to be sent back to the client application.
 */
function createJsonResponse(data) {
  return ContentService.createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}