# Capstone Home Security System - Backend API

This repository contains the central cloud backend (`backend-api`) codebase for the Smart Home Security Capstone project. The project is a real-time, WebSocket-enabled Django cloud server integrated with PostgreSQL, Redis, Firebase Cloud Messaging (FCM), and Keycloak (OAuth2/JWT).

---

## Technology Stack

* **Web Framework:** Django 5.0 & Django REST Framework (DRF)
* **Real-time Engine:** Django Channels (WebSockets ASGI)
* **Database:** PostgreSQL (for Users, Devices, Rooms, and Logs)
* **Message Broker & Channel Layer:** Redis
* **Identity Provider (IDP):** Keycloak 26.2.4 (Secure OAuth2 / JWT-based Authentication)
* **Push Notifications:** Firebase Admin SDK (FCM Multicast Push Notifications)
* **Documentation:** drf-spectacular (Swagger UI / Redoc)
* **Testing:** pytest & pytest-django

---

## Key Features

1. **OAuth2/JWT Integration:** All API endpoints are protected using Keycloak JWT Access Tokens. The custom `KeycloakJWTAuthentication` validates incoming tokens on-the-fly and maps them to Django user profiles.
2. **Dynamic Device Mapping:** The Raspberry Pi hardware panel queries the API for room and device schemas on startup to dynamically map local GPIO pins to database primary keys, eliminating hardcoded IDs.
3. **Autonomous Alarm Logic:** Danger telemetry received from local sensors (Smoke, Gas, Water Leak, Motion, Magnetic door contacts) automatically triggers the home's alarm state and sends siren commands to the Pi.
4. **WebSocket Command Router (Actuators):** Instantly routes commands like `OPEN_DOOR`, `ACTIVATE_BUZZER`, and `ALARM_STOP` from mobile applications to the corresponding Raspberry Pi over WebSockets.
5. **WebSocket Jitter (Connection Loss) Debounce:** Implements a **30-second grace period** when the Pi disconnects briefly, preventing false connection-loss alarms due to network jitter.
6. **Secure NFC Verification (IDOR Protected):** Verifies that incoming card validation requests belong to a home owned by the authenticated requesting user, preventing cross-user security bypasses.
7. **Offline Bulk Log Synchronization (Bulk Create):** Allows the Pi to buffer events locally during internet outages and upload them in bulk with their original occurrence timestamps once the connection is restored.

---

## Local Setup & Running (Docker Compose)

All dependencies (PostgreSQL, Redis, Keycloak, Django ASGI) can be launched locally with a single command using Docker Compose.

### Prerequisites
* Docker & Docker Compose (Docker Desktop for Windows/Mac)
* Git

### Execution Steps

1. **Clone the Repository and Navigate to the Directory:**
   ```bash
   git clone https://github.com/HomeSecurityBAU/backend-api.git
   cd backend-api
   ```

2. **Configure Environment Variables (`.env`):**
   Set up your `.env` file in the root directory (you can copy and customize `.env` locally).

3. **Start the Docker Services:**
   ```bash
   docker-compose up --build -d
   ```
   *This command spins up the PostgreSQL database, launches Keycloak and automatically imports the realm configuration from `realm-export.json`, runs Django database migrations, and starts the ASGI server (Daphne) on port 8000.*

4. **Accessing the Services:**
   * **Django Backend API:** `http://localhost:8000`
   * **Swagger Documentation:** `http://localhost:8000/api/docs/`
   * **Keycloak Console:** `http://localhost:8080` (Username: `admin` / Password: `admin`)
   * **Django Admin Panel:** `http://localhost:8000/admin/`

---

## Running Automated Tests

To execute the automated test suite inside the active backend container:

```bash
docker exec -it homesecurity_backend pytest
```

---

## API Endpoint Specifications

### HTTP REST API (`/api/`)

* **Homes:** `/api/homes/` (GET, POST, PUT, DELETE)
  * `POST /api/homes/{id}/set_security_mode/` -> Arms or disarms the home security system (`arm: true/false`).
  * `POST /api/homes/{id}/authenticate_entry/` -> Silences the alarm and updates security status on mobile passcode validation.
  * `GET /api/homes/{id}/dashboard/` -> Returns rooms, devices, recent event logs, and access logs in a single request.
* **Rooms:** `/api/rooms/` (GET, POST)
* **Devices:** `/api/devices/` (GET, POST)
  * `POST /api/devices/{id}/send_command/` -> Sends a direct actuator command to the Raspberry Pi over WebSockets.
* **Event Logs:** `/api/eventlogs/` (GET, POST)
  * `POST /api/eventlogs/bulk_create/` -> Uploads buffered offline event logs in bulk.
* **Access Logs:** `/api/accesslogs/` (GET, POST)
  * `POST /api/accesslogs/bulk_create/` -> Synchronizes historical offline access logs.
* **FCM Push Tokens:** `/api/fcmtokens/` (POST, DELETE)
* **Registered NFC Tags:** `/api/nfc-tags/` (GET, POST)
* **NFC Verification:** `POST /api/verify-nfc/` -> Validates incoming card UID scans from the Pi, opens the door lock, or triggers the alarm.

### WebSocket Connections (`/ws/`)

* **Mobile App Alert Stream:** `ws/alerts/<home_id>/?token=<jwt_token>`
  * Streams live sensor alerts and active alarm states to connected mobile applications.
* **Raspberry Pi Command Stream:** `ws/commands/<home_id>/?token=<jwt_token>`
  * Relays live actuator toggle commands to the Pi and monitors connection heartbeats.
