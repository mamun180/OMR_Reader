/**
 * Combined Google Apps Script License API
 * Supports RSA signing for offline verification (UNLIMITED)
 * and online verification for DAY_BASED and COUNT_BASED licenses.
 */

const SHEET_NAME = "Licenses";

// --- PRIVATE KEY FOR RSA SIGNING ---
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

function doPost(e) {
  try {
    const postData = JSON.parse(e.postData.contents);
    const licenseKey = postData.key;
    const machineHash = postData.machine_hash;
    const appName = postData.app_name;
    const requestType = postData.request_type; // "activate", "verify"

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getSheetByName(SHEET_NAME);
    
    if (!sheet) {
      return createJsonResponse({ "status": "ERROR", "message": "Sheet '" + SHEET_NAME + "' not found" });
    }

    const range = sheet.getDataRange();
    const values = range.getValues();

    // Find row with license key
    let rowIdx = -1;
    for (let i = 1; i < values.length; i++) {
      if (values[i][0] == licenseKey) {
        rowIdx = i + 1;
        break;
      }
    }

    if (rowIdx === -1) {
      return createJsonResponse({ "status": "DENIED", "message": "Invalid license key." });
    }

    const rowData = values[rowIdx - 1];
    const licenseType = rowData[1];       // B: license_type (UNLIMITED, DAY_BASED, etc)
    const licenseValue = rowData[2];      // C: value (days/counts)
    const storedHash = rowData[3];        // D: machine_hash
    const status = rowData[4];            // E: status
    const activationDate = rowData[5] ? new Date(rowData[5]) : null; // F: activation_date

    if (requestType === "activate") {
      // Logic for re-installation on same machine
      if (status === "activated" && storedHash && storedHash !== machineHash) {
        return createJsonResponse({ 
          "status": "DENIED", 
          "message": "License already bound to another machine." 
        });
      }

      // Update the sheet with activation details
      const currentDate = new Date();
      sheet.getRange(rowIdx, 4).setValue(machineHash); // D: machine_hash
      sheet.getRange(rowIdx, 5).setValue("activated"); // E: status
      sheet.getRange(rowIdx, 6).setValue(currentDate); // F: activation_date
      sheet.getRange(rowIdx, 7).setValue(appName);     // G: app_name

      // Prepare response payload
      const licensePayload = {
        "license_type": licenseType,
        "license_key": licenseKey,
        "machine_hash": machineHash,
        "activated_on": currentDate.toISOString().split('T')[0],
        "app_name": appName
      };

      if (licenseType === "UNLIMITED") {
        const payloadString = JSON.stringify(licensePayload, Object.keys(licensePayload).sort());
        const signature = signData(payloadString, RSA_PRIVATE_KEY_PEM);
        const signedLicense = { ...licensePayload, server_signature: signature };
        return createJsonResponse({ "status": "SUCCESS_UNLIMITED", "license": signedLicense });
      } else {
        return createJsonResponse({ 
          "status": "SUCCESS_ACTIVATED", 
          "message": "Activation successful.",
          "license": licensePayload
        });
      }
    }

    if (requestType === "verify") {
       if (status !== "activated" || storedHash !== machineHash) {
         return createJsonResponse({ "status": "DENIED", "message": "Verification failed. Invalid machine or status." });
       }

       if (licenseType === "UNLIMITED") {
         return createJsonResponse({ "status": "APPROVED", "message": "License is valid." });
       }

       if (licenseType === "DAY_BASED") {
         const daysAllowed = parseInt(licenseValue, 10);
         const daysElapsed = Math.ceil((new Date() - activationDate) / (1000 * 60 * 60 * 24));
         if (daysElapsed <= daysAllowed) {
           return createJsonResponse({ "status": "APPROVED", "message": "OK. " + (daysAllowed - daysElapsed) + " days remaining." });
         } else {
           return createJsonResponse({ "status": "DENIED", "message": "License expired." });
         }
       }

       if (licenseType === "COUNT_BASED") {
         const remaining = parseInt(licenseValue, 10);
         if (remaining > 0) {
           return createJsonResponse({ "status": "APPROVED", "message": "OK. Scans remaining: " + remaining, "remaining": remaining });
         } else {
           return createJsonResponse({ "status": "DENIED", "message": "No scan credits remaining." });
         }
       }
    }

    if (requestType === "use_scans") {
      if (status !== "activated" || storedHash !== machineHash) {
        return createJsonResponse({ "status": "DENIED", "message": "Invalid machine or activation status." });
      }
      if (licenseType === "COUNT_BASED") {
        const used = Math.max(1, parseInt(postData.count || 1, 10));
        const remaining = parseInt(licenseValue, 10);
        const newRemaining = Math.max(0, remaining - used);
        sheet.getRange(rowIdx, 3).setValue(newRemaining);
        return createJsonResponse({ "status": "OK", "remaining": newRemaining });
      }
      // UNLIMITED / DAY_BASED — scans are unrestricted
      return createJsonResponse({ "status": "OK", "remaining": -1 });
    }

    return createJsonResponse({ "status": "ERROR", "message": "Invalid request type." });

  } catch (err) {
    return createJsonResponse({ "status": "ERROR", "message": err.toString() });
  }
}

function signData(data, privateKeyPem) {
    // Ensure the key is a clean string and handle potential whitespace/newline issues
    const cleanKey = privateKeyPem.trim();
    const signatureBytes = Utilities.computeRsaSignature(
        Utilities.RsaAlgorithm.RSA_SHA_256, 
        data, 
        cleanKey
    );
    return Utilities.base64Encode(signatureBytes);
}

function createJsonResponse(data) {
  return ContentService.createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
