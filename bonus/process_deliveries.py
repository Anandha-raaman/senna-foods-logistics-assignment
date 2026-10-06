"""
Senna Foods Logistics Flow - SAP Delivery Processor Script
==========================================================
This script processes daily SAP delivery CSV files, groups line items into deliveries,
calculates total weights, validates master data (shop codes & item weights), and handles errors gracefully.

Author: Implementation Engineer Intern
Date: October 2026
"""

import csv
import os

# Set relative or absolute path to the SAP delivery sample CSV file
CSV_FILE_PATH = os.path.join(os.path.dirname(__file__), "..", "sample_data", "SAP_delivery_sample.csv")

# Set of valid LMS shop codes (simulating LMS Shop Master Database)
# Note: Shop '100999' / '0000100999' is intentionally omitted to simulate an unknown shop failure case.
VALID_LMS_SHOPS = {
    "100245", "100317", "100402", "100118", "100533", 
    "100274", "100650", "100381", "100712", "100159", "100826"
}


def process_sap_deliveries(file_path):
    """
    Reads SAP delivery CSV, groups line items by VBELN, validates data integrity,
    and outputs summary results along with warnings and errors.
    """
    if not os.path.exists(file_path):
        print(f"ERROR: File not found at {file_path}")
        return

    # Dictionary to hold grouped delivery records
    # Key: delivery_number (VBELN), Value: dict of delivery details & items
    deliveries = {}

    # Lists to capture validation issues
    warnings = []
    errors = []

    # Step 1: Read CSV file line by line using standard python csv library
    with open(file_path, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        
        for row in reader:
            # Extract basic fields from the CSV row
            raw_vbeln = row.get("VBELN", "").strip()
            # Standardize delivery number to 10 digits with leading zeros (e.g., '0080001235')
            vbeln = raw_vbeln.zfill(10)
            
            raw_kunnr = row.get("KUNNR", "").strip()
            # LMS shop code strips leading zeros (e.g., '0000100317' -> '100317')
            lms_shop_code = raw_kunnr.lstrip("0")
            
            shop_name = row.get("NAME1", "").strip()
            raw_weight = row.get("BRGEW", "").strip()
            
            # Step 2: Initialize delivery entry in dictionary if seeing this VBELN for the first time
            if vbeln not in deliveries:
                deliveries[vbeln] = {
                    "delivery_number": vbeln,
                    "shop_code": lms_shop_code,
                    "raw_kunnr": raw_kunnr.zfill(10),
                    "shop_name": shop_name,
                    "items_count": 0,
                    "total_weight": 0.0,
                    "has_missing_weight": False,
                    "is_unknown_shop": False
                }

            delivery = deliveries[vbeln]
            delivery["items_count"] += 1

            # Step 3: Validate Shop Master Data existence in LMS
            if lms_shop_code not in VALID_LMS_SHOPS:
                delivery["is_unknown_shop"] = True

            # Step 4: Validate and accumulate Gross Weight (BRGEW)
            if not raw_weight:
                delivery["has_missing_weight"] = True
            else:
                try:
                    weight_val = float(raw_weight)
                    delivery["total_weight"] += weight_val
                except ValueError:
                    delivery["has_missing_weight"] = True

    # Step 5: Process and print ALL delivery summaries
    print("=" * 60)
    print("      SENNA FOODS LOGISTICS - SAP DELIVERY SUMMARY REPORT      ")
    print("=" * 60)
    print()

    for vbeln, d in sorted(deliveries.items()):
        # Capture warning or error messages
        if d["has_missing_weight"]:
            warn_msg = f"WARNING:\nDelivery {d['delivery_number']} has missing weight."
            if warn_msg not in warnings:
                warnings.append(warn_msg)

        if d["is_unknown_shop"]:
            err_msg = f"ERROR:\nShop {d['raw_kunnr']} is not present in LMS."
            if err_msg not in errors:
                errors.append(err_msg)

        # Print summary for EVERY delivery (including unknown shop deliveries)
        print(f"Delivery: {d['delivery_number']}")
        if d["is_unknown_shop"]:
            print(f"Shop: {d['shop_name']} [UNREGISTERED IN LMS]")
        else:
            print(f"Shop: {d['shop_name']}")
        
        print(f"Items: {d['items_count']}")
        
        if d["has_missing_weight"]:
            print("Total Weight: INCOMPLETE (Missing weight data)")
        else:
            print(f"Total Weight: {d['total_weight']:.2f} KG")
        
        print("-" * 40)

    # Step 6: Print captured Warnings and Errors section
    if warnings:
        print("\n" + "=" * 40)
        print("         VALIDATION WARNINGS          ")
        print("=" * 40)
        for w in warnings:
            print(w)

    if errors:
        print("\n" + "=" * 40)
        print("          CRITICAL ERRORS             ")
        print("=" * 40)
        for e in errors:
            print(e)

    print("\nProcessing complete.")


if __name__ == "__main__":
    process_sap_deliveries(CSV_FILE_PATH)
