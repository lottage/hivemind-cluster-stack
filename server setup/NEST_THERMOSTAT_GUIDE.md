# Google Nest Thermostat Integration Guide for Home Assistant

**Target Home Assistant Instance**: `http://192.168.1.82:8123`  
**Purpose**: Connect your Google Nest Thermostat into Home Assistant with zero auth barriers, enabling local control, automations, and AI companion delegation.

---

## 1. Identify Your Nest Thermostat Model

Before proceeding, check which Nest Thermostat model you have:

| Model | Visual Identifier | Recommended Path | Setup Complexity |
| :--- | :--- | :--- | :--- |
| **Nest Thermostat (2020)** | Smooth mirror display with touch groove on the right edge | **Path A: Matter (Local)** | 2 minutes (Zero fees, no cloud console) |
| **Nest Learning (4th Gen, 2024)** | Large edge-to-edge crystal display with rotating ring | **Path A: Matter (Local)** | 2 minutes (Zero fees, no cloud console) |
| **Nest Learning (3rd Gen)** | High-res color screen with metallic rotating ring | **Path B: Google SDM API** | ~10 minutes (Burner Gmail OAuth) |
| **Nest Thermostat E** | Frosted white display that blends into wall | **Path B: Google SDM API** | ~10 minutes (Burner Gmail OAuth) |

---

## Path A: Local Matter Protocol (Recommended if 2020 or 4th Gen)

If your Nest Thermostat is the 2020 model or 4th Gen, **it speaks Matter directly**. It pairs locally to Home Assistant without touching the Google Cloud Console or paying any fees.

### Steps:
1. Open the **Google Home** app on your phone (logged into your burner Gmail or primary account where the thermostat is paired).
2. Tap your **Thermostat** -> tap the **Settings (gear icon)** in the top right.
3. Scroll down and tap **Linked Matter apps & services**.
4. Tap **Link apps & services** -> **Matter setup code** (or **Pair with Matter**).
5. The Google Home app will generate an **11-digit or 21-digit numeric pairing code** (and a QR code) with a 3-minute validity timer. Copy or write down the numeric code.
6. Open Home Assistant (`http://192.168.1.82:8123`):
   - Go to **Settings** -> **Devices & Services**.
   - Tap **Add Integration** (bottom right) -> Search for **Matter (experimental / official)**.
   - If Matter Server is not yet installed, Home Assistant will prompt you to install the Matter Server add-on; approve it.
   - Choose **Commission a device** -> Select **Use setup code**.
   - Paste the numeric code from Step 5.
7. Home Assistant will discover the Nest Thermostat over your Wi-Fi network and generate the entity `climate.<thermostat_name>`.
8. Done! You have 100% local, instantaneous control.

---

## Path B: Google Smart Device Management (SDM) API (3rd Gen & E)

For the 3rd Gen Learning Thermostat or Nest Thermostat E, communication must route through Google's Smart Device Management (SDM) API. The common issue users encounter is **OAuth consent blocked / 403 access_denied**. Following the exact sequence below using your **burner Gmail** completely avoids these traps.

### Why the Burner Gmail Solves the Issue:
- Regular personal accounts tied to Google Family groups or Google Workspace domains enforce strict OAuth 2.0 app restrictions.
- A clean, standalone burner Gmail has no parent organization policies and allows self-authorization of "Testing" OAuth apps without Google verification.

---

### Step 1: Add Burner Gmail as a Home Member in Google Home
1. In the **Google Home app** on your phone:
   - Tap **Settings** -> **Household / Members**.
   - Tap **Invite person** -> enter your **burner Gmail address**.
   - Accept the invitation from the burner Gmail inbox.
2. Verify that when you log into Google Home with the burner Gmail, you can see and control the Nest Thermostat.

---

### Step 2: Google Cloud Console Setup (Using Burner Gmail)
1. In your browser (use an Incognito window or separate profile logged strictly into the **burner Gmail**), navigate to:
   **https://console.cloud.google.com/**
2. In the top bar, click the project dropdown and click **New Project**:
   - Project Name: `HomeAssistant-Nest`
   - Organization: `No organization`
   - Click **Create**.
3. Enable the Smart Device Management API:
   - Go to **APIs & Services** -> **Library**.
   - Search for `Smart Device Management API`.
   - Click on it and click **Enable**.

---

### Step 3: Configure the OAuth Consent Screen (Crucial Step)
1. In Cloud Console, go to **APIs & Services** -> **OAuth consent screen**:
   - Select **External** and click **Create**.
   - App Name: `Home Assistant`
   - User support email: `Your burner Gmail address`
   - Developer contact email: `Your burner Gmail address`
   - Click **Save and Continue**.
2. **Scopes**:
   - Click **Add or Remove Scopes**.
   - Filter or search for `smartdevicemanagement.googleapis.com`.
   - Check all scopes under Smart Device Management.
   - Click **Update** -> **Save and Continue**.
3. **Test Users (Prevents 403 access_denied!)**:
   - Click **Add Users**.
   - Enter your **burner Gmail address**.
   - Click **Save and Continue**, then **Back to Dashboard**.
   - *Note: Leave Publishing status as "Testing". Do NOT submit for verification.*

---

### Step 4: Create OAuth 2.0 Credentials
1. Go to **APIs & Services** -> **Credentials**.
2. Click **+ Create Credentials** -> **OAuth client ID**:
   - Application type: **Web application**
   - Name: `Home Assistant Web OAuth`
   - Authorized redirect URIs: Click **+ Add URI** and enter:
     `https://my.home-assistant.io/redirect/oauth`
   - Click **Create**.
3. A popup will display your **Client ID** and **Client Secret**. Copy both to a secure note.

---

### Step 5: Register on Google Device Access Console ($5 One-time Fee)
1. In the same burner Gmail session, navigate to:
   **https://console.nest.google.com/device-access**
2. Accept the Terms of Service and pay the one-time $5 developer registration fee.
3. Click **Create project**:
   - Project name: `Home Assistant`
   - OAuth client ID: Paste the **Client ID** you copied from Step 4.
   - Enable Events: Toggle **Enable**.
   - Click **Create project**.
4. On the project details page, copy the **Project ID** (a UUID string like `d490c21a-6379-4d8e-9082-xxxxxxxxxxxx`).

---

### Step 6: Configure Home Assistant (192.168.1.82:8123)
1. Open Home Assistant: `http://192.168.1.82:8123`
2. Go to **Settings** -> **Devices & Services** -> **Add Integration**.
3. Search for **Google Nest**.
4. When prompted for authentication method:
   - Select **Web auth** (or "OAuth").
   - Enter your **Project ID** (from Device Access Console).
   - Enter your **Client ID** and **Client Secret** (from Cloud Console).
5. Home Assistant will provide a link to sign in with Google:
   - Click the link.
   - Make sure you select the **burner Gmail account**.
   - You may see a warning screen: *"Google hasn’t verified this app"*. Click **Advanced** -> **Go to Home Assistant (unsafe)**.
   - Select the Home / Structure and check the boxes next to your Nest Thermostat.
   - Click **Allow**.
6. Google will redirect to `my.home-assistant.io`, which hands the authorization code back to your local Home Assistant instance.
7. Home Assistant will confirm: **Device added successfully!**

---

## 2. Verification & Exposed Entities

Once paired, Home Assistant will expose:
- `climate.<name>`: Target temperature, HVAC modes (heat/cool/off/eco), current temperature.
- `sensor.<name>_temperature`: Ambient temperature sensor.
- `sensor.<name>_humidity`: Ambient relative humidity.

### Test via Home Assistant Developer Tools:
1. Go to `http://192.168.1.82:8123/developer-tools/service`
2. Select Service: `climate.set_temperature`
3. Target: Pick your Nest Thermostat entity.
4. Temperature: `72`
5. Click **Call Service**. The thermostat display should update immediately.

---

## 3. Delegation to AI Companion

With Home Assistant integrated, you can delegate thermostat and ambient comfort tasks directly to your local cluster models:
- Say: *"Set thermostat to 72"* or *"Turn on Eco mode"*
- The **3B Worker** parses the intent into:
  ```json
  {
    "domain": "climate",
    "service": "set_temperature",
    "service_data": {
      "entity_id": "climate.nest_thermostat",
      "temperature": 72
    }
  }
  ```
- The FastMCP bridge calls `POST http://192.168.1.82:8123/api/services/climate/set_temperature`
- The result is immediately reflected in EasyDash and your home.
