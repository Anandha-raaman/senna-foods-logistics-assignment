# Task 2 — Send Trip Results to SAP

This document details the trip status workflow, delivery result schema, JSON payload structures, decision rationale for result granularity, and end-to-end test scenarios for reporting execution results back to SAP.

---

## A. Trip Status Lifecycle Flow

The table below defines the state transitions a trip undergoes from initial creation in LMS to final completion and posting to SAP.

| Status | Next Status | What Moves It (Triggering Event) | Who / What Does It |
| :--- | :--- | :--- | :--- |
| **`Planned`** | `Sent to Transporter` | LMS routing engine completes route optimization and assigns trip to a transport partner. | **LMS System** (Automatic) |
| **`Sent to Transporter`** | `Assigned` | Transport company accepts the trip on the LMS portal and inputs driver details and truck registration. | **Transport Company Dispatcher** |
| **`Assigned`** | `Started` | Driver opens the Partner Mobile App and taps "Start Trip" at the warehouse departure gate. | **Driver Partner** (Mobile App) |
| **`Started`** | `Completed` | Driver finishes all stop deliveries, uploads all PODs, and taps "Complete Trip". | **Driver Partner** (Mobile App) |
| **`Completed`** | *(Final State)* | LMS aggregates stop results and posts delivery execution data back to SAP. | **LMS Systems Integrator** |

---

## B. Delivery Result Fields & Timestamp Rationale

### Delivery Result Schema Table

| Field | Type | Example | Description |
| :--- | :--- | :--- | :--- |
| `event_id` | `text` | `evt_01J9ZQ4K7M2X` | Unique event identifier for deduplication (idempotency key). |
| `event_type` | `text` | `stop.result_saved` | Type of event emitted by the driver application. |
| `sent_at` | `timestamp` | `2026-10-02T11:42:15+05:30` | ISO-8601 timestamp when the phone **transmitted** the payload over the network. |
| `recorded_at` | `timestamp` | `2026-10-02T11:40:03+05:30` | ISO-8601 timestamp when the driver **saved** the result locally on the phone. |
| `trip_id` | `text` | `TRP-BLR-20261002-07` | LMS unique trip tracking reference code. |
| `truck_number` | `text` | `KA-01-AB-1234` | Assigned vehicle license plate number. |
| `driver.name` | `text` | `Ravi K` | Full name of the assigned driver partner. |
| `driver.phone` | `text` | `+91-98450-00000` | Contact phone number of the driver. |
| `stop.sequence` | `integer` | `2` | Stop position in the trip route sequence. |
| `sap_delivery_number` | `text` | `0080001235` | 10-digit SAP delivery identifier. |
| `shop_code` | `text` | `0000100317` | SAP customer code (Ganesh Mart). |
| `stop.result` | `text` | `PART_DELIVERED` | Stop status (`DELIVERED`, `PART_DELIVERED`, `RETURNED`). |
| `items[].material` | `text` | `FG-3010` | SAP SKU / Product Material code. |
| `items[].loaded_qty` | `integer` | `40` | Quantity loaded onto the vehicle at warehouse. |
| `items[].delivered_qty`| `integer` | `36` | Quantity accepted and received by shop owner. |
| `items[].returned_qty` | `integer` | `4` | Quantity rejected/returned to warehouse. |
| `items[].return_reason`| `text` | `DAMAGED` | Reason code for return (`DAMAGED`, `EXPIRED`, `SHORTAGE`, `REFUSED`). |
| `pod_photo_url` | `text` | `https://partner.example.com/pod/...` | Secure URL of the Proof of Delivery photo signed by shop keeper. |
| `location.lat/lng` | `decimal` | `12.9352, 77.6245` | GPS coordinates captured at the moment of result entry. |

### Key Distinction: `recorded_at` vs. `sent_at`

* **`recorded_at` (Offline Timestamp):** The precise time the driver tapped "Save Result" inside the shop. Captured locally from the device clock even when offline in basements or dead zones.
* **`sent_at` (Online Transmission Timestamp):** The time the mobile app successfully established a network connection and uploaded the data packet to LMS.
* **Why the difference matters:** If a driver delivers goods at 11:40 AM underground with no cellular network, `recorded_at` reads `11:40:03`. When the truck drives into cellular coverage at 11:42 AM, the app uploads the queued packet, making `sent_at` read `11:42:15`. Using `recorded_at` guarantees accurate SLA measurement and delivery time verification.

---

## C. Sample Part-Delivered JSON Payload

Below is the standard JSON structure sent by the driver app when a delivery is **PART_DELIVERED** due to damaged goods (Delivery `0080001235` for Ganesh Mart).

```json
{
  "event_id": "evt_01J9ZQ4K7M2X",
  "event_type": "stop.result_saved",
  "sent_at": "2026-10-02T11:42:15+05:30",
  "trip_id": "TRP-BLR-20261002-07",
  "truck_number": "KA-01-AB-1234",
  "driver": {
    "name": "Ravi K",
    "phone": "+91-98450-00000"
  },
  "stop": {
    "sequence": 2,
    "sap_delivery_number": "0080001235",
    "shop_code": "0000100317",
    "result": "PART_DELIVERED",
    "items": [
      {
        "material": "FG-1001",
        "loaded_qty": 10,
        "delivered_qty": 10,
        "returned_qty": 0
      },
      {
        "material": "FG-3010",
        "loaded_qty": 40,
        "delivered_qty": 36,
        "returned_qty": 4,
        "return_reason": "DAMAGED"
      }
    ],
    "pod_photo_url": "https://partner.example.com/pod/TRP-BLR-20261002-07/2.jpg",
    "recorded_at": "2026-10-02T11:40:03+05:30",
    "location": {
      "lat": 12.9352,
      "lng": 77.6245
    }
  }
}
```

---

## D. Decision: Per Item vs. Per Delivery Reporting to SAP

### Choice: **PER ITEM**

### Rationale & Justification:
1. **Accurate Financial & Inventory Posting:** In SAP, billing and goods issue are maintained at the line-item level. Reporting results per item allows SAP to issue credit notes specifically for returned SKUs while billing delivered SKUs.
2. **Granular Reason Attribution:** A single delivery can have multiple line items returned for different reasons (e.g., 4 cases of `FG-3010` returned as `DAMAGED` and 2 cases of `FG-1001` returned as `EXPIRED`). A high-level delivery summary would lose this critical quality data.
3. **Automated Warehouse Restocking:** Damaged goods must be routed to scrap/QC warehouse locations, whereas undamaged returned goods go back to active stock. Item-level reporting makes automated SAP inventory posting possible.

---

## E. Six Given / When / Then Test Cases

| Test Case | Scenario | Given (Initial State) | When (Event Action) | Then (Expected System Outcome) |
| :-: | :--- | :--- | :--- | :--- |
| **1** | **Fully Delivered Order** *(Success)* | Delivery `0080001234` loaded with 24 cases `FG-1001` and 12 cases `FG-2003`. | Driver delivers all cases in full and uploads POD photo. | LMS updates status to `DELIVERED`. SAP posts 100% Goods Issue and generates full customer invoice. |
| **2** | **Partially Delivered Order** *(Success - Partial)* | Delivery `0080001235` loaded with 40 cases `FG-3010`. | Driver delivers 36 cases; 4 cases are damaged and returned. | LMS updates status to `PART_DELIVERED`. SAP posts 36 delivered, 4 returned (`DAMAGED`), and generates credit note for 4 cases. |
| **3** | **Full Return Order** *(Success - Return)* | Delivery `0080001238` routed to Lakshmi Traders. | Shop is closed; shop keeper refuses delivery. Driver marks stop returned. | LMS updates status to `RETURNED` with reason `SHOP_CLOSED`. SAP cancels Goods Issue and flags delivery for redelivery. |
| **4** | **Missing Weight Data** *(Failure 1)* | Delivery `0080001236` received from SAP with empty `BRGEW` (weight). | LMS imports the daily SAP delivery CSV. | LMS flags delivery with `WARNING`, blocks auto-routing, and quarantines it until weight is updated. |
| **5** | **Unknown Shop Code** *(Failure 2)* | Delivery `0080001237` received for customer `0000100999` (not in LMS). | LMS validates shop master records during import. | LMS raises `CRITICAL ERROR`, quarantines delivery in Error Queue, and dispatches alert to SAP Master Data team. |
| **6** | **Duplicate Webhook Event** *(Idempotency)* | Event `evt_01J9ZQ4K7M2X` already processed and stored in LMS database. | App re-sends same `event_id` due to network retry. | LMS detects existing `event_id`, ignores duplicate processing, and returns HTTP `200 OK` to prevent retry loops. |
