# Task 3 — APIs, Webhooks & System Reliability

This document specifies the REST API design for Master Data onboarding, Webhook event definitions for mobile execution, security signature verification, and failure handling procedures for duplicate requests, system downtime, and master data mismatches.

---

## Architecture Integration Overview

* **CURRENT PROCESS:** SAP ERP → LMS uses daily batch **CSV file** exchange (`SAP_delivery_sample.csv`).
* **TARGET PROCESS:** SAP ERP → LMS will move to **REST API** using JSON payloads.
* **PARTNER APP:** Driver/Partner App → LMS uses **HTTPS Webhooks** with JSON payloads and `X-Signature` security header.

---

## A. Master Data REST APIs

Below is the lightweight REST API specification for synchronizing master data between SAP, internal management consoles, and LMS.

| Master Entity | Method | Endpoint | Main Required Fields | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **1. Shop** | `POST` | `/api/v1/shops` | `shop_code`, `shop_name`, `city`, `pin_code`, `address` | Onboards retail customer shop master records from SAP into LMS. |
| **2. Delivery Location** | `POST` | `/api/v1/delivery-locations` | `shop_code`, `latitude`, `longitude`, `delivery_window` | Sets precise GPS map coordinates and daily receiving hours for a shop. |
| **3. Zone** | `POST` | `/api/v1/zones` | `zone_code`, `zone_name`, `city`, `pin_codes` | Groups clusters of postal codes/shops for optimized trip routing. |
| **4. Truck Type** | `POST` | `/api/v1/truck-types` | `truck_type_code`, `name`, `max_weight_kg`, `max_volume_m3` | Defines vehicle capacity constraints used by the LMS trip planning engine. |
| **5. Transport Company** | `POST` | `/api/v1/transport-companies` | `transporter_code`, `name`, `contact_email`, `phone` | Registers transport partners and grants access to the Transporter Web Portal. |
| **6. Freight Rate** | `POST` | `/api/v1/freight-rates` | `transporter_code`, `zone_code`, `truck_type_code`, `rate_amount` | Configures trip contract pricing based on vehicle type and delivery zone. |
| **7. Product** | `POST` | `/api/v1/products` | `product_code`, `product_name`, `unit`, `weight_kg_per_unit` | Onboards food item SKU master details including unit weights from SAP. |

---

## B. Webhook Events (Driver Partner App -> LMS)

Webhooks allow the Driver Partner App to push real-time event updates to LMS as deliveries are performed in the field.

| Event Name | Sender System | When Sent | Main Payload Data |
| :--- | :--- | :--- | :--- |
| **1. `trip.started`** | **Driver Partner App** | Driver taps "Start Trip" at warehouse gate. | `event_id`, `trip_id`, `truck_number`, `driver`, `start_time`, `start_location` |
| **2. `stop.result_saved`** | **Driver Partner App** | Driver records delivery/return result at a shop stop. | `event_id`, `trip_id`, `sap_delivery_number`, `shop_code`, `result`, `items[]`, `pod_photo_url`, `recorded_at`, `sent_at`, `location` |
| **3. `trip.completed`** | **Driver Partner App** | Driver completes all assigned stops and finishes trip. | `event_id`, `trip_id`, `completion_time`, `total_stops`, `successful_stops` |

*(Note: Trip dispatching and driver allocation events, such as `trip.assigned`, occur on the **Transporter Web Portal**, not on the Driver Partner App).*

---

## C. Security & Authentication: `X-Signature` Header

### What is `X-Signature`?
The assignment specifies that when the Partner App sends a webhook as an HTTPS POST request, it includes an **`X-Signature`** HTTP header.

### How `X-Signature` Works:
1. **Partner App Sends HTTPS POST:** The driver app transmits the JSON webhook request containing the `X-Signature` header in the HTTP request headers.
2. **LMS Signature Verification:** Before processing the body payload, LMS computes the expected cryptographic signature using a shared secret key and compares it against `X-Signature`.
3. **Invalid Signature:** If the signature does not match, LMS **rejects the webhook** immediately with HTTP `401 Unauthorized`.
4. **Valid Signature:** If the signature matches, LMS proceeds to inspect and process the payload.

### IMPORTANT: `X-Signature` vs. `event_id`

* **`X-Signature` Header = Authenticity & Integrity Security:** Verifies that the webhook genuinely originated from the authorized Partner App and was not altered in transit.
* **`event_id` Field = Idempotency & Duplicate Handling:** Used to detect if the same valid event packet is received multiple times due to network retries.

---

## D. Three Technical Short Answers

### 1. What happens if the same event arrives twice?

* **Mechanism:** **Idempotency Keying via `event_id`**.
* **Step-by-Step Logic:**
  1. LMS receives the HTTPS POST webhook request and verifies `X-Signature`.
  2. LMS extracts and reads the `event_id` field from the sample webhook payload (e.g., `"event_id": "evt_01J9ZQ4K7M2X"`).
  3. LMS queries its database index to check whether this `event_id` has already been processed.
  4. **If already processed:** LMS **does not process the business action again** (preventing duplicate inventory deduction or double credit notes).
  5. LMS **returns a successful response (HTTP 200 OK)** immediately so the sending app knows the message was safely recorded and stops retrying.

### 2. What happens if LMS is down when an event is sent?

* **Mechanism:** **Offline Caching & Exponential Backoff Retries**.
* **Step-by-Step Logic:**
  1. **Event Safeguard:** If LMS is temporarily unavailable, the delivery event is not lost. The Partner App saves the recorded payload safely in local phone storage.
  2. **Sender Retries:** The Partner App automatically attempts to re-send the queued event at increasing retry delays (exponential backoff).
  3. **Error Queue Fallback:** After repeated failures over a long period, the event moves to an offline sync error log / dead-letter mechanism for manual investigation.
  4. **Recovery & Sync:** Once LMS becomes available again, the Partner App transmits all queued events sequentially.
  5. **Duplicate Protection:** Using `event_id` ensures that if a retried packet was actually received by LMS right before going offline, duplicate processing is prevented.

### 3. What happens if SAP sends a delivery for a shop LMS doesn't have?

* **Mechanism:** **Ingestion Validation & Quarantine Error Queue**.
* **Step-by-Step Logic:**
  1. **Validate Shop Code:** During daily delivery ingestion, LMS extracts `KUNNR` / `shop_code` (e.g., `0000100999`) and checks it against the LMS Shop Master table.
  2. **Reject & Quarantine:** If `shop_code` is missing from LMS, LMS **rejects the delivery** and routes it to the **LMS Delivery Quarantine Queue**.
  3. **Log & Alert:** LMS logs the explicit validation error (`ERROR: Shop 0000100999 is not present in LMS`) and alerts the SAP/Master Data team.
  4. **No Auto-Creation:** LMS does *not* automatically create unverified shop records to avoid creating corrupt or dummy master records lacking GPS coordinates and zone mappings.
  5. **Resolution:** After the SAP team creates the shop in LMS via `/api/v1/shops`, the quarantined delivery is re-processed and released for trip routing.
