# 30-Minute Review Call — Interview Preparation Guide

This guide is designed for a fresher / intern review call. It provides simple, concise, and technically sound answers to key questions about the Senna Foods Logistics Implementation.

---

## A. Explain the project in 60 seconds

> "Senna Foods sells food products to shops across India. Orders are billed in SAP. We introduced a Logistics Management System (LMS) to plan delivery trips and track fulfillment.
>
> The flow works in 6 steps:
> 1. **SAP sends daily deliveries to LMS** (CURRENT: daily CSV file, TARGET: REST API using JSON).
> 2. **LMS validates data and plans trips.**
> 3. **Transporters accept trips on the LMS portal and assign trucks/drivers.**
> 4. **Drivers see assigned trips on their Partner Mobile App.**
> 5. **Drivers deliver goods, take Proof-of-Delivery photos, and submit results via HTTPS Webhooks (even offline).**
> 6. **LMS receives webhooks and sends final item-level execution results back to SAP via REST API.**
>
> SAP remains the single system of record, and invalid data like unknown shops or missing weights are caught immediately during validation."

---

## B. Explain the architecture

> "The architecture connects four distinct systems:
> - **SAP ERP:** The main system of record for orders, products, and customer master data.
> - **LMS (Logistics Management System):** The core intelligence engine that validates data, plans routes, and tracks execution status.
> - **Transport Company Portal:** A web dashboard where logistics partners accept trips and assign trucks and drivers.
> - **Driver Partner Mobile App:** An offline-first mobile app used by drivers to record stop results and capture POD photos.
>
> Data flows sequentially: SAP -> LMS -> Transporter Portal -> Driver App -> LMS -> SAP.
> - **CURRENT PROCESS:** SAP → LMS uses daily batch **CSV files** (`SAP_delivery_sample.csv`).
> - **TARGET PROCESS:** SAP → LMS will move to **REST API** using JSON payloads.
> - **PARTNER APP:** Driver App → LMS uses **HTTPS Webhooks** with JSON payloads and `X-Signature` security."

---

## C. Explain Task 1 (Data Mapping & Flow)

> "Task 1 defines how data moves between systems:
> 1. **Hand-off Table:** Maps every transfer point—from initial SAP import to final result posting—specifying system roles, protocols (Current CSV / Target REST / Webhooks), and failure handling.
> 2. **Field Mapping:** Maps 11 key SAP fields to LMS fields. Important rules include:
>    - Preserving leading zeros for delivery numbers (`VBELN` -> `0080001234`).
>    - Stripping leading zeros for shop customer codes (`KUNNR` `0000100317` -> `100317`).
>    - Unit conversion from SAP code `CS` to LMS standard `CASE`.
>    - **Gross Weight (`BRGEW` -> `delivery_item.weight_kg`):** Mandatory field. Missing `BRGEW` (as in Delivery `0080001236`) blocks and quarantines the delivery from auto trip planning until corrected.
> 3. **System Diagram:** Visualizes the complete flow including a failure branch for unknown shop `0000100999`, which gets quarantined in an Error Queue."

---

## D. Explain Task 2 (Send Results to SAP)

> "Task 2 focuses on returning delivery results from LMS back to SAP:
> 1. **Trip Statuses:** Defines the status progression: `Planned` -> `Sent to Transporter` -> `Assigned` -> `Started` -> `Completed`.
> 2. **Delivery Result Schema:** Maps webhook fields like `event_id`, `sap_delivery_number`, `shop_code`, `result`, `loaded_qty`, `delivered_qty`, `returned_qty`, `return_reason`, and timestamps.
> 3. **Timestamp Difference:** Explains `recorded_at` (when driver saved data locally on phone) vs `sent_at` (when phone transmitted payload online).
> 4. **Item-Level Reporting:** We choose to report per-item to allow SAP to process specific inventory returns and credit notes accurately.
> 5. **6 Test Cases:** Covers full delivery, partial delivery with damaged goods, shop closed return, missing weight, unknown shop, and duplicate webhooks."

---

## E. Explain Task 3 (APIs & Webhooks)

> "Task 3 designs the communication layer:
> 1. **Master Data APIs:** REST endpoints (`POST /api/v1/shops`, `/products`, `/zones`, etc.) to onboard master data into LMS.
> 2. **Webhook Events:** Real-time push events sent specifically by the Driver Partner App (`trip.started`, `stop.result_saved`, `trip.completed`).
> 3. **Security & Deduplication:**
>    - **`X-Signature` Header:** Authenticates that the webhook request genuinely came from the authorized Partner App and was not tampered with.
>    - **`event_id` Key:** Provides idempotency to prevent duplicate event processing during network retries.
> 4. **LMS Downtime / Retries:** The app queues events locally when offline or when LMS is down, retrying with exponential backoff delays.
> 5. **Unknown Shop:** Ingestion rejects the delivery to Quarantine Error Queue and alerts the SAP team."

---

## F. Explain the Python script

> "The Python script (`bonus/process_deliveries.py`) processes the sample SAP delivery CSV file:
> 1. Reads the CSV line-by-line using Python's built-in `csv.DictReader`.
> 2. Groups rows by delivery number `VBELN` (`0080001234`, `0080001235`, etc.).
> 3. Calculates total items and sums gross weight (`BRGEW`) for each delivery.
> 4. Validates shop codes against valid LMS shop master records and checks for missing weight values.
> 5. Includes ALL deliveries in the summary output list (displaying Delivery `0080001237` - Om Provisions `[UNREGISTERED IN LMS]`).
> 6. Continues processing without crashing and prints explicit `WARNING` (for Delivery `0080001236` missing weight) and `CRITICAL ERROR` (for Shop `0000100999`) sections."

---

## G. Why did you choose these API methods?

> "We follow standard RESTful conventions:
> - **`POST`:** Used for creating new master records (shops, products, delivery locations) and posting webhook execution events.
> - `POST` ensures payload data is sent securely in the request body rather than exposed in URL query parameters."

---

## H. Why use webhooks?

> "Webhooks are event-driven. Instead of LMS polling the driver's phone every few seconds asking 'Did you finish delivery yet?', the mobile app automatically pushes data to LMS the moment the driver saves a result. This reduces server load, saves mobile battery, and updates status in real time."

---

## I. What is the difference between `X-Signature` and `event_id`?

> "- **`X-Signature` Header = Security & Authenticity:** Verifies that the webhook request genuinely came from the authorized Driver App and that data wasn't tampered with.
> - **`event_id` Field = Idempotency & Deduplication:** Ensures that if the app re-sends the same valid webhook packet due to network retries, LMS does not process duplicate delivery results."

---

## J. What happens when LMS is down?

> "If LMS is down or unreachable:
> 1. The mobile app safely saves the delivery result in local device storage.
> 2. The app retries uploading the data at increasing time intervals (exponential backoff).
> 3. Once LMS is back online, all queued events upload automatically in order without any data loss."

---

## K. Why not process an unknown shop?

> "If LMS automatically created unknown shops on the fly, it would create corrupt master records missing critical information like GPS coordinates, delivery time windows, and zone codes.
>
> Quarantining the delivery in an Error Queue ensures master data integrity. The issue is resolved properly in SAP/LMS before trip creation."

---

## L. Why item-level delivery results?

> "Because orders contain multiple SKUs. A shop might accept 10 cases of Oats but reject 4 cases of Noodles because they are damaged.
>
> Item-level reporting tells SAP *exactly* which SKU was damaged so SAP can issue a credit note for that specific item and route damaged stock to QC."

---

## M. What happens when the driver is offline?

> "The Driver Partner App is built **offline-first**:
> 1. All assigned trip data is cached locally on the phone.
> 2. When the driver saves a result, the phone captures the exact local time in `recorded_at` and stores the payload locally.
> 3. When cellular network returns, the app uploads the payload and sets `sent_at`.
>
> This allows drivers to work seamlessly in basements or rural areas."

---

## N. What are the biggest failure cases?

> "The two biggest failure cases in the sample data are:
> 1. **Missing Gross Weight (`BRGEW`) on Delivery `0080001236`:** Prevents truck volume/weight planning. Handled by quarantining delivery and issuing a warning.
> 2. **Unknown Shop Code (`0000100999` / `100999`) on Delivery `0080001237`:** Prevents stop routing and invoicing. Handled by printing in summary with `[UNREGISTERED IN LMS]`, quarantining delivery, and raising a critical error alert to the SAP team."

---

## O. What assumptions did you make?

> 1. **SAP is the Master System:** LMS reads master data and returns execution results without directly mutating SAP master tables.
> 2. **No Auto-Creation of Shops:** Unknown shops are quarantined, not auto-created.
> 3. **Item-Level Results:** Webhook payloads capture quantities per SKU line item.
> 4. **Offline Mobile Execution:** The Driver App operates offline-first, capturing local timestamps (`recorded_at`) and syncing when online (`sent_at`).
> 5. **Idempotent & Authenticated Webhooks:** Every webhook payload includes an `X-Signature` header for security and a unique `event_id` for deduplication.

---

## P. What would you recommend for future production improvements?

> "For a future production deployment, recommended architectural enhancements include:
> 1. **Automated Master Data Sync:** Scheduled background pipeline between SAP and LMS via REST APIs.
> 2. **Message Queuing & Dead-Letter Queue (DLQ):** Using an asynchronous message queue (e.g. RabbitMQ or AWS SQS) for webhook retry buffering.
> 3. **Automated Operational Alerts:** Real-time email/dashboard notifications for quarantined deliveries.
> 4. **Barcode Scanning:** Scanning SKU barcodes at delivery stops to prevent handing over wrong products."

---

## Q. Did you implement these production improvements (RabbitMQ, SQS, CDC, etc.)?

> **"No. Those are recommendations for a production version. For this assignment, I focused on the required data mapping, logistics workflow, REST API and webhook design, failure handling, testing, and the Python delivery-processing bonus."**
