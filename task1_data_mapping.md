# Task 1 — Data Mapping & Hand-off Specifications

This document outlines the complete data mapping, system hand-offs, and architecture flow for the **Senna Foods Logistics Management System (LMS)** integration with SAP ERP and partner applications.

---

## Architecture Integration Overview

To establish clear operational boundaries:

* **CURRENT PROCESS:**
  * **SAP ERP → LMS:** Daily batch **CSV file** exchange (`SAP_delivery_sample.csv`).
  * **LMS ↔ Transporters & Drivers:** Manual Excel spreadsheets and WhatsApp updates.

* **TARGET PROCESS:**
  * **SAP ERP → LMS:** Automated **REST API** using JSON payloads.
  * **PARTNER APP (Driver App → LMS):** Real-time **HTTPS Webhooks** with JSON payloads and `X-Signature` authentication.
  * **TRANSPORTER PORTAL ↔ LMS:** Web Portal / REST API interface.
  * **LMS → SAP ERP:** Automated **REST API** for returning item-level execution results.

---

## A. System Hand-off Table

The table below details every data movement step across the logistics lifecycle, including failure handling mechanisms for missing or invalid data.

| Step | Data | From | To | Method | What Happens if Data is Missing / Invalid |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Delivery Import** | Daily Delivery Orders (Header & Line Items) | SAP ERP | LMS | **CURRENT:** Daily CSV File<br>**TARGET:** Batch REST API (JSON) | LMS validates master data. Invalid deliveries (missing weight `BRGEW`, unknown shop `0000100999`) are rejected and quarantined into an Error Queue. |
| **2. Trip Dispatch** | Planned Trip Details (Stops, Deliveries, Route, SKUs) | LMS | Transport Company Portal | REST API / Web Portal | Transporter cannot accept trip until required vehicle capacity and zone constraints are satisfied. |
| **3. Driver Assignment** | Vehicle Number & Driver Details (Truck ID, Name, Phone) | Transport Company | LMS | Portal Form Submission / REST API | Trip remains in `Sent to Transporter` state. Driver cannot see trip on mobile app until assigned. |
| **4. Mobile Sync** | Assigned Trip & Stop Instructions | LMS | Driver Partner App | REST API (JSON) | Mobile app caches last available trip data locally for offline execution. |
| **5. Delivery Result Capture** | Stop Execution Result (Loaded Qty, Delivered Qty, Return Reason, POD Photo, GPS, Offline Timestamps) | Driver Partner App | LMS | **HTTPS POST Webhook** (with `X-Signature` header) | App saves result locally when offline (`recorded_at`) and retries upload when network restores (`sent_at`). |
| **6. Result Posting** | Final Execution Results & Return Adjustments | LMS | SAP ERP | REST API (JSON) | Failed posts trigger exponential backoff retries. Unresolved failures alert IT support without corrupting SAP master data. |

---

## B. Field Mapping (SAP to LMS)

Below is the mapping between SAP fields and the LMS target schema, detailing data types, mandatory flags, and transformation rules. **Gross Weight (`BRGEW`) is explicitly included because its absence triggers a mandatory validation failure.**

| # | SAP Field | LMS Field | Type | Required? | Transformation & Logic Notes |
| :-: | :--- | :--- | :--- | :-: | :--- |
| **1** | `VBELN` | `delivery_number` | `text(10)` | **Yes** | Standardized to 10 characters, preserving leading zeros (e.g., `80001234` -> `0080001234`). |
| **2** | `POSNR` | `line_number` | `integer` | **Yes** | Line item position converted to integer, stripping leading zeros (e.g., `10`, `20`). |
| **3** | `KUNNR` | `shop_code` | `text` | **Yes** | Strips leading zeros (e.g., `0000100317` -> `100317`). Used to look up Shop Master in LMS. |
| **4** | `NAME1` | `shop_name` | `text` | **Yes** | Directly mapped customer/shop name (e.g., `Ganesh Mart`). |
| **5** | `ORT01` | `city` | `text` | **Yes** | City location for delivery address (e.g., `Bengaluru`). |
| **6** | `PSTLZ` | `pin_code` | `text(6)` | **Yes** | 6-digit postal code used for zone mapping in LMS (e.g., `560076`). |
| **7** | `MATNR` | `product_code` | `text` | **Yes** | SKU / Material code (e.g., `FG-3010`). Validated against LMS Product Master. |
| **8** | `ARKTX` | `product_name` | `text` | **No** | Product description (e.g., `Instant Noodles 70g`). Additional line item context. |
| **9** | `LFIMG` | `quantity` | `integer` | **Yes** | Billed order quantity converted from string to integer. |
| **10** | `VRKME` | `unit` | `text` | **Yes** | **Unit Conversion Rule:** Converts SAP unit `CS` to LMS standard `CASE`. If `PC`, converts to `PIECE`. |
| **11** | `BRGEW` | `delivery_item.weight_kg` | `decimal` | **Yes** | **Gross Weight:** Weight of the line item in kg. **Missing `BRGEW` blocks/quarantines the delivery from auto trip planning.** |

### Additional LMS-Calculated & Master Fields (Not in SAP File)
* **`total_weight_kg` (`decimal`):** Sum of line item gross weights (`BRGEW`) computed during LMS ingestion.
* **`status` (`text`):** Managed by LMS workflow (starts as `NEW` upon import).
* **`latitude` / `longitude` (`decimal`):** Sourced from LMS Shop Master pin location for driver navigation.
* **`delivery_window` (`text`):** Operational hours captured in LMS (e.g., `09:00-18:00`).

---

## C. Handling Missing-Weight Failure Case (`BRGEW`)

The sample dataset intentionally includes Delivery `0080001236` with a missing `BRGEW` value.

### Validation & Quarantine Rule for Missing Weight:
1. **Validation Detection:** During ingestion, the LMS validation module checks if `BRGEW` is populated for every line item.
2. **Block Trip Planning:** If `BRGEW` is missing or invalid, the delivery **must not silently continue into trip planning**, as the system cannot calculate total vehicle payload weight or verify truck capacity constraints.
3. **Quarantine & Logging:** LMS flags the delivery with a validation warning, logs the error (`WARNING: Delivery 0080001236 has missing weight data`), and moves the delivery to the **LMS Delivery Quarantine Queue**.
4. **Resolution Required:** The delivery remains blocked until the gross weight is updated in SAP or corrected in master data, after which the delivery is released for trip routing.

---

## D. System Flow Diagram & Failure Branch

### Architecture Diagram

![Logistics Flow Architecture](file:///f:/My%20projects/senna_foods_assignment/diagram/logistics_flow.png)

```
[ SAP ERP (System of Record) ]
             │
             │ CURRENT: Daily CSV | TARGET: REST API (JSON)
             ▼
   [ LMS Ingestion Engine ] ──(Validation Fails: Unknown Shop 100999 / Missing Weight)──► [ QUARANTINE ERROR QUEUE ]
             │                                                                                  │
             │ (Validation Passes)                                                              ▼
             ▼                                                                       (Alert SAP & Master Data Team)
 [ Transport Company Portal ]
             │
             │ Assigns Truck & Driver
             ▼
   [ Driver Partner App ] ──(Executes Stop / Offline Mode)
             │
             │ HTTPS POST Webhook (X-Signature + event_id, recorded_at, sent_at)
             ▼
   [ LMS Results Engine ]
             │
             │ Item-Level Delivery Results REST API
             ▼
      [ SAP ERP ] (Goods Issue Updated & Returns Processed)
```

### Explanation of the Unknown Shop Failure Branch (`0000100999`)
1. **SAP Sends Delivery Order:** SAP transmits a delivery for customer code `0000100999` (Om Provisions).
2. **LMS Master Data Validation:** During ingestion, the LMS cross-references `0000100999` against its Shop Master DB.
3. **Validation Failure (Shop Not Found):** The shop does not exist in LMS. Automatically creating unverified shops is blocked to protect data integrity.
4. **Quarantine & Error Queue:** The delivery is rejected from normal trip planning and moved to the **LMS Delivery Quarantine Queue**.
5. **Alert & Resolution:** An automated notification is dispatched to the SAP and Master Data teams. Trip creation remains blocked until the shop is registered in LMS or corrected in SAP.
