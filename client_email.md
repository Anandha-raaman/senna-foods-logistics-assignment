# Client Email to Senna Foods SAP Team

**Subject:** Action Required: Data Validation Issues in Daily SAP Delivery Feed

Dear SAP Operations Team,

During our daily LMS data validation, we identified two critical data issues in the latest SAP delivery file:

1. **Missing Gross Weight (`BRGEW`) on Delivery `0080001236`:** The total item weight is missing. Without weight data, our system cannot calculate truck capacity or allocate appropriate vehicles for delivery.
2. **Unregistered Customer/Shop (`0000100999` - Om Provisions) on Delivery `0080001237`:** This shop code does not exist in the LMS master database. Drivers cannot navigate to or execute deliveries for unmapped stores.

**Required Action:**
* Please update the gross weight (`BRGEW`) for Delivery `0080001236` in SAP.
* Please onboard customer `0000100999` into the LMS shop master database via the shop sync interface.

Once updated, please re-trigger the file sync so trip planning can proceed.

Best regards,  
**Logistics Implementation Team**  
Senna Foods Logistics Support
