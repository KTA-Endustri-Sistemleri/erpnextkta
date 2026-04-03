
# 📜 Changelog



## 🚀 v1.4.0 (2026-04-03)





  

    
    
    

### 🔧 Features

    
      
      
        
- add MRP Analysis report to visualize material consumption by customer group and stock levels
      
      
    

  

  

    
    
    

### 🔧 Refactoring

    
      
      
        
- **kta_calisma_karti**: move is_work_order_within_tolerance to helpers and update Work Order status validation logic
      
      
    

  


---


## 🚀 v1.3.0 (2026-04-01)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- **kta_calisma_karti**: move patches to v1_2_0 and add net duration correction patch
      
      
    
      
      
        
- **kta_calisma_karti**: calculate net duration based on shift capacity minus pauses
      
      
    
      
      
        
- **kta_calisma_karti_ui**: restore missing 'Devam Et' button by fixing showResume variable destructing in App.vue and strictly mapping paused state from backend durum
      
      
    
      
      
        
- **kta_calisma_karti**: make quality_inspection field editable by authorities (permlevel 1) instead of read_only
      
      
    
      
      
        
- **kta_calisma_karti**: shift boundary time causing 430min limit bypass
      
      
    

  

  

    
    
    

### 🔧 Documentation

    
      
      
        
- **memory-bank**: update progress, active context and patterns for duration logic overhaul
      
      
    
      
      
        
- correct the rule regarding card start and finish logic based on qc and sub-operations
      
      
    
      
      
        
- add comprehensive settings parameters to the user guide
      
      
    
      
      
        
- update readme and user guide with dynamic admin roles configuration
      
      
    
      
      
        
- **memory-bank**: update security audit patterns and progress
      
      
    
      
      
        
- **memory-bank**: progress file updated
      
      
    
      
      
        
- **memory-bank**: update memory-bank files
      
      
    

  

  

    
    
    

### 🔧 Features

    
      
      
        
- **kta_calisma_karti_ui**: add loading indicator to quality toggle buttons
      
      
    
      
      
        
- **ui**: prevent vue state leakage and restrict action buttons by status and configured admin roles
      
      
    
      
      
        
- **kta_calisma_karti**: implement pessimistic locking and dynamic admin roles configuration
      
      
    

  


---


## 🚀 v1.2.0 (2026-03-31)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- **kta_calisma_karti**: kta-dashboard-metrics
      
      
    
      
      
        
- **kta_calisma_karti**: enable MultiSelectList and update dashboard charts with 1-day filter and improved data processing
      
      
    

  

  

    
    
    

### 🔧 Features

    
      
      
        
- **kta_calisma_karti**: add daily completed work card count number card to dashboard
      
      
    

  


---


## 🚀 v1.1.0 (2026-03-30)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- **kta_calisma_karti**: quality debounce and auto close function
      
      
    
      
      
        
- **permissions**: uom permission added to calisma karti yoneticisi and calisma karti kullanicisi
      
      
    
      
      
        
- **permissions**: KTA Calisma Karti Settings permission added to calisma karti yoneticisi and calisma karti kullanicisi
      
      
    
      
      
        
- **tasks**: prevent premature auto-close of cards during shift transition
      
      
    
      
      
        
- **permissions**: calisma karti submit, delete permission added to calisma karti yoneticisi and calisma karti kullanicisi
      
      
    
      
      
        
- **permissions**: add if_owner permission to KTA Çalışma Kartı Kullanıcısı role in setup.py
      
      
    
      
      
        
- **permissions**: add read-only permission for KTA Çalışma Kartı Kullanıcısı role
      
      
    
      
      
        
- **permissions**: remove redundant permission entry and clean up attributes for Calisma Karti role
      
      
    

  

  

    
    
    

### 🔧 Features

    
      
      
        
- implement configurable throttled real-time updates with pending notification UI for list and detail views
      
      
    

  


---


## 🚀 v1.0.0 (2026-03-29)





  

    
    
    

### 🔧 Features

    
      
      
        
- modernize UI/UX and migrate to Draft-First architecture
      
      
    

  


---


## 🚀 v0.20.1 (2026-03-29)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- purchase receipt rate update
      
      
    
      
      
        
- posting_date değişikliğinde frontend kur/fiyat zincirini engelle
      
      
    
      
      
        
- override controller cscript method, not just form handler
      
      
    

  


---


## 🚀 v0.20.0 (2026-03-12)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- stock balance svd correction
      
      
    
      
      
        
- correct stock_value_difference for foreign currency PRs and add SLE balance fix script
      
      
    

  

  

    
    
    

### 🔧 Features

    
      
      
        
- Add item rate deviation validation for Purchase Receipts and remove the stock value difference fix script.
      
      
    

  


---


## 🚀 v0.19.0 (2026-03-05)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- **batch-split**: allow batch splitting on Return Purchase Receipts by checking outward batch entries
      
      
    
      
      
        
- **quality-inspection**: prevent zebra printer errors from rolling back batch splitting
      
      
    

  

  

    
    
    

### 🔧 Features

    
      
      
        
- Implement reliable incoming rate determination and ensure accurate batch quantity updates during bundle processing.
      
      
    

  

  

    
    
    

### 🔧 Unknown

    
      
      
- fix:batch labels (#108)
      
    

  


---


## 🚀 v0.18.0 (2026-03-04)





  

    
    
    

### 🔧 Features

    
      
      
        
- Implement reliable incoming rate determination and ensure accurate batch quantity updates during bundle processing.
      
      
    

  

  

    
    
    

### 🔧 Unknown

    
      
      
- hotfix: Gümrüksüz exchange rate logic, batch split incoming_rate fix, return validation fix (#106)

- Add 'Gümrüksüz' checkbox to Purchase Receipt İthalat tab
- When checked, use for_buying exchange rate based on posting_date
- Fix zero incoming_rate in split batch entries (api.py)
- Fix batch validation error for Purchase Receipt returns (serial_batch_bundle_doc.py)
      
    

  


---


## 🚀 v0.17.1 (2026-02-24)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- **kta-calisma-karti**: define customer_group param to prevent NameError
      
      
    

  


---


## 🚀 v0.17.0 (2026-02-23)





  

    
    
    

### 🔧 Features

    
      
      
        
- **kta-calisma-karti**: add customer group filter and load-more pagination
      
      
    

  


---


## 🚀 v0.16.0 (2026-02-22)





  

    
    
    

### 🔧 Chores

    
      
      
        
- deleted unwanted files
      
      
    

  

  

    
    
    

### 🔧 Features

    
      
      
        
- Enhance QC workflow by adding 'Reddedildi' status and updating related logic
      
      
    
      
      
        
- Implement real-time updates for Calisma Karti with Socket.IO integration
      
      
    
      
      
        
- Implement real-time updates for QC in Calisma Karti with Socket.IO integration
      
      
    
      
      
        
- Implement real-time updates for Create Calisma Karti with Socket.IO integration
      
      
    

  

  

    
    
    

### 🔧 Unknown

    
      
      
- feat/calisma-karti-realtime-events (#103)
      
    

  


---


## 🚀 v0.15.0 (2026-02-19)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- Install setuptools in the CI tests workflow.
      
      
    
      
      
        
- Pin setuptools to a version less than 71 in the CI workflow.
      
      
    
      
      
        
- Install setuptools in the CI tests workflow.
      
      
    
      
      
        
- Pin setuptools to a version less than 71 in the CI workflow.
      
      
    
      
      
        
- so sync rule
      
      
    
      
      
        
- Adjust deleted sales order item handling to only consider delivered quantity and remove duplicate sync job functions.
      
      
    
      
      
        
- Install setuptools in the CI tests workflow.
      
      
    
      
      
        
- Pin setuptools to a version less than 71 in the CI workflow.
      
      
    
      
      
        
- so sync rule
      
      
    
      
      
        
- Adjust deleted sales order item handling to only consider delivered quantity and remove duplicate sync job functions.
      
      
    
      
      
        
- **kta-calisma-karti**: 'item_code' added to listview
      
      
    
      
      
        
- Install setuptools in the CI tests workflow.
      
      
    
      
      
        
- Pin setuptools to a version less than 71 in the CI workflow.
      
      
    
      
      
        
- so sync rule
      
      
    
      
      
        
- Adjust deleted sales order item handling to only consider delivered quantity and remove duplicate sync job functions.
      
      
    
      
      
        
- **kta-calisma-karti**: 'item_code' added to listview
      
      
    

  

  

    
    
    

### 🔧 Build system

    
      
      
        
- Add `setuptools` to `install_requires`.
      
      
    
      
      
        
- Add `setuptools` to `install_requires`.
      
      
    
      
      
        
- Add `setuptools` to `install_requires`.
      
      
    
      
      
        
- Add `setuptools` to `install_requires`.
      
      
    

  

  

    
    
    

### 🔧 Chores

    
      
      
        
- update project dependencies and build configuration.
      
      
    
      
      
        
- update project dependencies and build configuration.
      
      
    
      
      
        
- update project dependencies and build configuration.
      
      
    
      
      
        
- update project dependencies and build configuration.
      
      
    

  

  

    
    
    

### 🔧 Continuous integration

    
      
      
        
- Move setuptools installation after bench setup requirements in tests workflow.
      
      
    
      
      
        
- force reinstall setuptools in GitHub Actions workflow.
      
      
    
      
      
        
- Move setuptools installation after bench setup requirements in tests workflow.
      
      
    
      
      
        
- force reinstall setuptools in GitHub Actions workflow.
      
      
    
      
      
        
- Move setuptools installation after bench setup requirements in tests workflow.
      
      
    
      
      
        
- force reinstall setuptools in GitHub Actions workflow.
      
      
    
      
      
        
- Move setuptools installation after bench setup requirements in tests workflow.
      
      
    
      
      
        
- force reinstall setuptools in GitHub Actions workflow.
      
      
    

  

  

    
    
    

### 🔧 Features

    
      
      
        
- Staging to main
      
      
    
      
      
        
- **kta-calisma-karti**: new calisma karti user interface and improvements
      
      
    
      
      
        
- sample order rule
      
      
    
      
      
        
- **kta-calisma-karti**: new calisma karti user interface and improvements
      
      
    
      
      
        
- Adjust Sales Order field visibility and defaults, and simplify Delivery Note by removing custom logic and changing its base class.
      
      
    
      
      
        
- **kta-calisma-karti**: new calisma karti user interface and improvements
      
      
    
      
      
        
- sample order rule
      
      
    
      
      
        
- **kta-calisma-karti**: new calisma karti user interface and improvements
      
      
    
      
      
        
- Adjust Sales Order field visibility and defaults, and simplify Delivery Note by removing custom logic and changing its base class.
      
      
    
      
      
        
- Force close Sales Orders when deleted items have billed amounts exceeding delivered quantities.
      
      
    
      
      
        
- Add a custom buying setting and client script to automatically set Purchase Order currency based on the selected price list.
      
      
    
      
      
        
- **kta-calisma-karti**: new calisma karti user interface and improvements
      
      
    
      
      
        
- sample order rule
      
      
    
      
      
        
- **kta-calisma-karti**: new calisma karti user interface and improvements
      
      
    
      
      
        
- Adjust Sales Order field visibility and defaults, and simplify Delivery Note by removing custom logic and changing its base class.
      
      
    
      
      
        
- Force close Sales Orders when deleted items have billed amounts exceeding delivered quantities.
      
      
    
      
      
        
- Add a custom buying setting and client script to automatically set Purchase Order currency based on the selected price list.
      
      
    
      
      
        
- **kta-calisma-karti**: new calisma karti user interface and improvements
      
      
    
      
      
        
- sample order rule
      
      
    
      
      
        
- **kta-calisma-karti**: new calisma karti user interface and improvements
      
      
    
      
      
        
- Adjust Sales Order field visibility and defaults, and simplify Delivery Note by removing custom logic and changing its base class.
      
      
    
      
      
        
- Force close Sales Orders when deleted items have billed amounts exceeding delivered quantities.
      
      
    
      
      
        
- Add a custom buying setting and client script to automatically set Purchase Order currency based on the selected price list.
      
      
    
      
      
        
- Filter stock calculations in material requirement and production start week reports by 'Kullanılabilir Stok' warehouse type and update stock balance date to current day.
      
      
    

  

  

    
    
    

### 🔧 Refactoring

    
      
      
        
- **kta-calisma-karti**: minor bug fix and logic improvments
      
      
    
      
      
        
- **kta-calisma-karti**: minor bug fix and logic improvments
      
      
    
      
      
        
- **kta-calisma-karti**: minor bug fix and logic improvments
      
      
    
      
      
        
- **kta-calisma-karti**: minor bug fix and logic improvments
      
      
    

  


---


## 🚀 v0.14.0 (2026-02-19)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- Install setuptools in the CI tests workflow.
      
      
    
      
      
        
- Pin setuptools to a version less than 71 in the CI workflow.
      
      
    
      
      
        
- Install setuptools in the CI tests workflow.
      
      
    
      
      
        
- Pin setuptools to a version less than 71 in the CI workflow.
      
      
    
      
      
        
- so sync rule
      
      
    
      
      
        
- Adjust deleted sales order item handling to only consider delivered quantity and remove duplicate sync job functions.
      
      
    
      
      
        
- Install setuptools in the CI tests workflow.
      
      
    
      
      
        
- Pin setuptools to a version less than 71 in the CI workflow.
      
      
    
      
      
        
- so sync rule
      
      
    
      
      
        
- Adjust deleted sales order item handling to only consider delivered quantity and remove duplicate sync job functions.
      
      
    
      
      
        
- **kta-calisma-karti**: 'item_code' added to listview
      
      
    

  

  

    
    
    

### 🔧 Build system

    
      
      
        
- Add `setuptools` to `install_requires`.
      
      
    
      
      
        
- Add `setuptools` to `install_requires`.
      
      
    
      
      
        
- Add `setuptools` to `install_requires`.
      
      
    

  

  

    
    
    

### 🔧 Chores

    
      
      
        
- update project dependencies and build configuration.
      
      
    
      
      
        
- update project dependencies and build configuration.
      
      
    
      
      
        
- update project dependencies and build configuration.
      
      
    

  

  

    
    
    

### 🔧 Continuous integration

    
      
      
        
- Move setuptools installation after bench setup requirements in tests workflow.
      
      
    
      
      
        
- force reinstall setuptools in GitHub Actions workflow.
      
      
    
      
      
        
- Move setuptools installation after bench setup requirements in tests workflow.
      
      
    
      
      
        
- force reinstall setuptools in GitHub Actions workflow.
      
      
    
      
      
        
- Move setuptools installation after bench setup requirements in tests workflow.
      
      
    
      
      
        
- force reinstall setuptools in GitHub Actions workflow.
      
      
    

  

  

    
    
    

### 🔧 Features

    
      
      
        
- Add a custom buying setting and client script to automatically set Purchase Order currency based on the selected price list
      
      
    
      
      
        
- **kta-calisma-karti**: new calisma karti user interface and improvements
      
      
    
      
      
        
- sample order rule
      
      
    
      
      
        
- **kta-calisma-karti**: new calisma karti user interface and improvements
      
      
    
      
      
        
- Adjust Sales Order field visibility and defaults, and simplify Delivery Note by removing custom logic and changing its base class.
      
      
    
      
      
        
- **kta-calisma-karti**: new calisma karti user interface and improvements
      
      
    
      
      
        
- sample order rule
      
      
    
      
      
        
- **kta-calisma-karti**: new calisma karti user interface and improvements
      
      
    
      
      
        
- Adjust Sales Order field visibility and defaults, and simplify Delivery Note by removing custom logic and changing its base class.
      
      
    
      
      
        
- Force close Sales Orders when deleted items have billed amounts exceeding delivered quantities.
      
      
    
      
      
        
- Add a custom buying setting and client script to automatically set Purchase Order currency based on the selected price list.
      
      
    
      
      
        
- **kta-calisma-karti**: new calisma karti user interface and improvements
      
      
    
      
      
        
- sample order rule
      
      
    
      
      
        
- **kta-calisma-karti**: new calisma karti user interface and improvements
      
      
    
      
      
        
- Adjust Sales Order field visibility and defaults, and simplify Delivery Note by removing custom logic and changing its base class.
      
      
    
      
      
        
- Force close Sales Orders when deleted items have billed amounts exceeding delivered quantities.
      
      
    
      
      
        
- Add a custom buying setting and client script to automatically set Purchase Order currency based on the selected price list.
      
      
    

  

  

    
    
    

### 🔧 Refactoring

    
      
      
        
- **kta-calisma-karti**: minor bug fix and logic improvments
      
      
    
      
      
        
- **kta-calisma-karti**: minor bug fix and logic improvments
      
      
    
      
      
        
- **kta-calisma-karti**: minor bug fix and logic improvments
      
      
    

  


---


## 🚀 v0.13.0 (2026-02-13)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- **kta-calisma-karti**: if operator error fixed
      
      
    
      
      
        
- **kta-calisma-karti**: calisma-karti-roles-logic
      
      
    
      
      
        
- **kta-calisma-karti**: The 'is_quality_user' check has been added to "get_my_calisma_karti" and "get_calisma_karti_detail" so that users with the Quality Role can view work cards.
      
      
    
      
      
        
- Install setuptools in the CI tests workflow.
      
      
    
      
      
        
- Pin setuptools to a version less than 71 in the CI workflow.
      
      
    
      
      
        
- skip update_rates_logic for return delivery notes during validation.
      
      
    

  

  

    
    
    

### 🔧 Build system

    
      
      
        
- Add `setuptools` to `install_requires`.
      
      
    

  

  

    
    
    

### 🔧 Chores

    
      
      
        
- **kta-calisma-karti**: deleted unwanted files
      
      
    
      
      
        
- update project dependencies and build configuration.
      
      
    

  

  

    
    
    

### 🔧 Continuous integration

    
      
      
        
- Move setuptools installation after bench setup requirements in tests workflow.
      
      
    
      
      
        
- force reinstall setuptools in GitHub Actions workflow.
      
      
    
      
      
        
- add conventional commits check workflow
      
      
    
      
      
        
- add conventional commits check workflow
      
      
    

  

  

    
    
    

### 🔧 Features

    
      
      
        
- **kta-calisma-karti**: sorting added to calisma karti list view
      
      
    
      
      
        
- sample order rule and calisma karti ui logic enhancements
      
      
    
      
      
        
- **kta-calisma-karti**: new calisma karti user interface and improvements
      
      
    
      
      
        
- sample order rule
      
      
    
      
      
        
- **kta-calisma-karti**: new calisma karti user interface and improvements
      
      
    
      
      
        
- Adjust Sales Order field visibility and defaults, and simplify Delivery Note by removing custom logic and changing its base class.
      
      
    

  

  

    
    
    

### 🔧 Refactoring

    
      
      
        
- **kta-calisma-karti**: minor bug fix and logic improvments
      
      
    

  

  

    
    
    

### 🔧 Unknown

    
      
      
- double rate error fixed
      
    

  


---


## 🚀 v0.12.0 (2026-01-24)





  

    
    
    

### 🔧 Features

    
      
      
        
- **frappe-ui**: :building_construction: frappe-ui integration added
      
      
    

  


---


## 🚀 v0.11.2 (2026-01-22)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- Ithalat fixed
      
      
    

  


---


## 🚀 v0.11.1 (2026-01-20)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- sales invoice double rate error
      
      
    

  

  

    
    
    

### 🔧 Refactoring

    
      
      
        
- stock entry get items from calisma karti added to doctype js. removed from global
      
      
    

  


---


## 🚀 v0.11.0 (2026-01-15)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- purchase receipt item prices date fix
      
      
    
      
      
        
- multiple receipt bill bug fix
      
      
    
      
      
        
- delivery note price list rate currency fix
      
      
    

  

  

    
    
    

### 🔧 Chores

    
      
      
        
- remove temporary test files
      
      
    

  

  

    
    
    

### 🔧 Features

    
      
      
        
- overrides for DN and PR exchange rate
      
      
    

  

  

    
    
    

### 🔧 Refactoring

    
      
      
        
- item price date adjusted
      
      
    
      
      
        
- adjusted exchange rate date
      
      
    

  

  

    
    
    

### 🔧 Unknown

    
      
      
- epic: dn pr price sync (#51)
      
    

  


---


## 🚀 v0.10.1 (2026-01-14)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- manufacture stock entry
      
      
    
      
      
        
- partial work order closing problem
      
      
    

  


---


## 🚀 v0.10.0 (2026-01-13)





  

    
    
    

### 🔧 Features

    
      
      
        
- invoice due date
      
      
    

  


---


## 🚀 v0.9.0 (2026-01-12)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- batch sut creation method monkey patching conversion to class overrides
      
      
    
      
      
        
- batch sut creation method monkey patching conversion to class overrides
      
      
    
      
      
        
- use_serial_batch_number field default value "0"
      
      
    

  

  

    
    
    

### 🔧 Features

    
      
      
        
- implement custom barcode routing and templates for print formats
      
      
    
      
      
        
- enhance serial and batch bundle handling with automatic name generation and background job synchronization for sales orders
      
      
    
      
      
        
- enhance batch processing and bundle name generation in KTA modules
      
      
    
      
      
        
- enhance batch handling in KTAPurchaseReceipt with automatic batch creation and improved submission logic
      
      
    
      
      
        
- improve batch splitting logic in KTAPurchaseReceipt with enhanced flag management and error handling
      
      
    
      
      
        
- implement custom naming logic for Serial and Batch Bundle to reuse SUT prefix from Purchase Receipts
      
      
    
      
      
        
- implement KTAStockEntry override to support manufacturing batch splitting in stock ledger updates
      
      
    
      
      
        
- implement custom barcode routing and templates for print formats
      
      
    
      
      
        
- enhance serial and batch bundle handling with automatic name generation and background job synchronization for sales orders
      
      
    
      
      
        
- enhance batch processing and bundle name generation in KTA modules
      
      
    
      
      
        
- enhance batch handling in KTAPurchaseReceipt with automatic batch creation and improved submission logic
      
      
    
      
      
        
- improve batch splitting logic in KTAPurchaseReceipt with enhanced flag management and error handling
      
      
    
      
      
        
- implement KTAStockEntry override to support manufacturing batch splitting in stock ledger updates
      
      
    
      
      
        
- implement custom naming logic for Serial and Batch Bundle to reuse SUT prefix from Purchase Receipts
      
      
    
      
      
        
- implement batch handling and validation for manufacturing processes
      
      
    
      
      
        
- enhance serial and batch bundle handling with automatic name generation and background job synchronization for sales orders
      
      
    
      
      
        
- enhance batch processing and bundle name generation in KTA modules
      
      
    
      
      
        
- enhance batch handling in KTAPurchaseReceipt with automatic batch creation and improved submission logic
      
      
    
      
      
        
- improve batch splitting logic in KTAPurchaseReceipt with enhanced flag management and error handling
      
      
    
      
      
        
- implement custom naming logic for Serial and Batch Bundle to reuse SUT prefix from Purchase Receipts
      
      
    
      
      
        
- implement KTAStockEntry override to support manufacturing batch splitting in stock ledger updates
      
      
    
      
      
        
- enhance serial and batch bundle handling with automatic name generation and background job synchronization for sales orders
      
      
    
      
      
        
- enhance batch processing and bundle name generation in KTA modules
      
      
    
      
      
        
- enhance batch handling in KTAPurchaseReceipt with automatic batch creation and improved submission logic
      
      
    
      
      
        
- improve batch splitting logic in KTAPurchaseReceipt with enhanced flag management and error handling
      
      
    
      
      
        
- implement custom naming logic for Serial and Batch Bundle to reuse SUT prefix from Purchase Receipts
      
      
    
      
      
        
- implement KTAStockEntry override to support manufacturing batch splitting in stock ledger updates
      
      
    
      
      
        
- implement batch handling and validation for manufacturing processes
      
      
    

  

  

    
    
    

### 🔧 Refactoring

    
      
      
        
- batch sut creation code cleanup
      
      
    
      
      
        
- remove before_insert event for Serial and Batch Bundle in Stock Entry validation
      
      
    

  


---


## 🚀 v0.8.3 (2026-01-08)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- batch_sut_creation
      
      
    

  

  

    
    
    

### 🔧 Unknown

    
      
      
- Fix/batch_sut_creation (#41)
      
    
      
      
- Feat:batch sut creation (#40)
      
    

  


---


## 🚀 v0.8.2 (2025-12-17)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- update method path for stock reconciliation job creation
      
      
    

  


---


## 🚀 v0.8.1 (2025-12-17)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- **kta_stock**: implement background job for bulk stock reconciliation document creation
      
      
    

  

  

    
    
    

### 🔧 Unknown

    
      
      
- fix/stock-reco-bulk-fix (#38)
      
    

  


---


## 🚀 v0.8.0 (2025-12-17)





  

    
    
    

### 🔧 Features

    
      
      
        
- **kta_stock**: added kta_stock & enhance Stock Reconciliation Dashboard with date filtering and validation
      
      
    
      
      
        
- **kta_stock**: add kta_stock module and related files
      
      
    
      
      
        
- **kta_stock**: add Stock Reconciliation Dashboard page and related files
      
      
    
      
      
        
- **kta_stock**: implement Stock Reconciliation dashboard event handlers and API
      
      
    
      
      
        
- **kta_stock**: add server-side access control for Stock Reconciliation Dashboard
      
      
    
      
      
        
- **kta_stock**: add Stock Reconciliation Dashboard components and ui setup
      
      
    
      
      
        
- **kta_stock**: add validation for stock entry and draft stock reconciliation locks
      
      
    
      
      
        
- **kta_stock**: enhance Stock Reconciliation Dashboard with date filtering and validation
      
      
    

  

  

    
    
    

### 🔧 Refactoring

    
      
      
        
- **kta_stock**: clean up code structure and improve readability in App.vue
      
      
    

  


---


## 🚀 v0.7.1 (2025-12-15)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- :bug: implement background job for sales order synchronization
      
      
    
      
      
        
- enhance sales order synchronization with queued status handling and logging
      
      
    
      
      
        
- update sales order sync log creation and status handling
      
      
    
      
      
        
- handle validation errors for deleted sales orders in sync log
      
      
    
      
      
        
- :bug: implement background job for sales order synchronization
      
      
    
      
      
        
- enhance sales order synchronization with queued status handling and logging
      
      
    
      
      
        
- update sales order sync log creation and status handling
      
      
    
      
      
        
- handle validation errors for deleted sales orders in sync log
      
      
    

  

  

    
    
    

### 🔧 Unknown

    
      
      
- # 🔀 fix: sales order update bug fix (#36)
      
    

  


---


## 🚀 v0.7.0 (2025-12-13)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- **labeler**: restructure file patterns for improved clarity in labeler configuration
      
      
    

  

  

    
    
    

### 🔧 Chores

    
      
      
        
- add GitHub issue/PR templates and workflow automations
      
      
    

  

  

    
    
    

### 🔧 Continuous integration

    
      
      
        
- add auto-assign reviewers and auto-label workflows
      
      
    

  

  

    
    
    

### 🔧 Documentation

    
      
      
        
- add issue and PR templates
      
      
    

  

  

    
    
    

### 🔧 Features

    
      
      
        
- **stock-reconciliation**: bulk create stock reconciliations by warehouse group
      
      
    
      
      
        
- **stock-reconciliation**: add UI action to bulk create reconciliations
      
      
    
      
      
        
- **stock-reconciliation**: simplify item removal logic to retain all rows on submit
      
      
    

  

  

    
    
    

### 🔧 Refactoring

    
      
      
        
- rename keys in labeler configuration for clarity
      
      
    

  

  

    
    
    

### 🔧 Unknown

    
      
      
- Feat: bulk stock reconciliation by warehouse group (#34)
      
    

  


---


## 🚀 v0.6.2 (2025-12-11)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- Add KTA SO Sync Detail DocType and related functionality
      
      
    
      
      
        
- Correct module name in KTA SO Sync Detail and improve error logging in KTA SO Sync Log
      
      
    
      
      
        
- Enhance sales order sync process with improved logging and optional customer filter
      
      
    
      
      
        
- Optimize sales order update process with batch processing and improved logging
      
      
    
      
      
        
- Improve error handling and logging during sales order sync log insertion
      
      
    
      
      
        
- Refactor sales order sync logic for improved customer and item handling
      
      
    
      
      
        
- Refactor sales order update comparison logic for improved previous record retrieval
      
      
    
      
      
        
- Add KTA SO Sync Detail DocType and related functionality
      
      
    
      
      
        
- Correct module name in KTA SO Sync Detail and improve error logging in KTA SO Sync Log
      
      
    
      
      
        
- Enhance sales order sync process with improved logging and optional customer filter
      
      
    
      
      
        
- Optimize sales order update process with batch processing and improved logging
      
      
    
      
      
        
- Improve error handling and logging during sales order sync log insertion
      
      
    
      
      
        
- Refactor sales order sync logic for improved customer and item handling
      
      
    
      
      
        
- Refactor sales order update comparison logic for improved previous record retrieval
      
      
    

  

  

    
    
    

### 🔧 Unknown

    
      
      
- Add KTA SO Sync Detail DocType and enhance sales order sync functionality (#28)
      
    

  


---


## 🚀 v0.6.1 (2025-12-11)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- **stock-reconciliation**: renamed api folder api to rest-api and fixed js endpoint
      
      
    

  


---


## 🚀 v0.6.0 (2025-12-10)





  

    
    
    

### 🔧 Features

    
      
      
        
- stabilize Stock Reconciliation items for physical count workflow
      
      
    
      
      
        
- **stock-reconciliation**: keep all items while document is draft
      
      
    
      
      
        
- **stock-reconciliation**: add static items API based on current bin stock
      
      
    
      
      
        
- **stock-reconciliation**: use custom static items API in fetch dialog
      
      
    

  


---


## 🚀 v0.5.0 (2025-12-08)





  

    
    
    

### 🔧 Features

    
      
      
        
- Add GitHub Pages documentation configuration and layout
      
      
    
      
      
        
- Add configuration for GitHub Pages documentation
      
      
    
      
      
        
- Add initial documentation layout and styles for erpnextkta for github pages
      
      
    
      
      
        
- Add GitHub Pages gem configuration to Gemfile
      
      
    
      
      
        
- Add *.lock files to .gitignore
      
      
    

  


---


## 🚀 v0.4.0 (2025-12-08)





  

    
    
    

### 🔧 Chores

    
      
      
        
- Remove unused KTA Supply On, KTA Supply On Head, and KTA Supply On Step doctype files and their associated scripts and configurations to clean up the codebase.
      
      
    

  

  

    
    
    

### 🔧 Features

    
      
      
        
- Add KTA Sales Order Update module
      
      
    
      
      
        
- Remove unused KTA Supply On Entry and KTA Supply On Evaluation doctypes
      
      
    
      
      
        
- Add kta_sales module definition and update modules list
      
      
    
      
      
        
- Import additional modules for enhanced sales order synchronization functionality
      
      
    
      
      
        
- Initialize kta_sales module with empty __init__.py file
      
      
    
      
      
        
- Create __init__.py file for kta_sales module
      
      
    

  

  

    
    
    

### 🔧 Refactoring

    
      
      
        
- KTASalesOrderUpdateEntry class
      
      
    

  


---


## 🚀 v0.3.5 (2025-12-07)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- update release notes and changelog templates for improved commit description handling
      
      
    
      
      
        
- update python-semantic-release version constraint to allow 10.x
      
      
    
      
      
        
- update semantic release configuration for version variables
      
      
    
      
      
        
- change commit parser from 'angular' to 'conventional'
      
      
    
      
      
        
- Update README.md with detailed user and developer sections
      
      
    

  

  

    
    
    

### 🔧 Chores

    
      
      
        
- revert app version to 0.3.4
      
      
    
      
      
        
- Update version to 0.3.4 and add changelog templates
      
      
    
      
      
        
- update version to 0.3.4 in project files
      
      
    
      
      
        
- add semantic release changelog templates
      
      
    

  

  

    
    
    

### 🔧 Unknown

    
      
      
- Fix: changelog release templates

* Refactor: changelog template for better clarity

* Refactor: release notes template for clarity
      
    

  


---


## 🚀 v0.3.4 (2025-12-07)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- stabilize Vue header teleport and unify step component UI
      
      
    
      
      
        
- stabilize page header by creating dedicated teleport target
      
      
    

  

  

    
    
    

### 🔧 Code style

    
      
      
        
- unify UI styles across StepJobCard and StepOperation components
      
      
    

  

  

    
    
    

### 🔧 Refactoring

    
      
      
        
- move teleport target to .kta-ck-header for reliability
      
      
    

  


---


## 🚀 v0.3.3 (2025-12-07)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- Remove redundant test execution steps from CI workflow
      
      
    

  


---


## 🚀 v0.3.2 (2025-12-07)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- Add additional apps to CI workflow for testing
      
      
    

  


---


## 🚀 v0.3.1 (2025-12-07)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- Add KTA Customer Group DocType with initial structure
      
      
    

  


---


## 🚀 v0.3.0 (2025-12-06)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- **calisma_karti**: correct method path for callIslemYap function
      
      
    
      
      
        
- **calisma_karti**: correct page reference and bundle import for KTA Calisma Karti
      
      
    
      
      
        
- **api**: rename parameter in get_job_card_by_barcode function for clarity and add operator department tag handling in create_calisma_karti
      
      
    
      
      
        
- **ui**: correct page show event handler and improve header content clearing in Vue app
      
      
    
      
      
        
- **calisma_karti**: update module reference to kta_calisma_karti in custom field
      
      
    

  

  

    
    
    

### 🔧 Chores

    
      
      
        
- update .gitignore to include additional files and directories
      
      
    
      
      
        
- title default changed to null
      
      
    
      
      
        
- code readability and cleanliness
      
      
    
      
      
        
- renamed page and js files
      
      
    
      
      
        
- renamed folder kta_calisma_karti to kta-calisma-karti
      
      
    
      
      
        
- page folder name revert kta_calisma_karti
      
      
    
      
      
        
- **fix**: revert page files to kta_calisma_karti
      
      
    
      
      
        
- **operasyon_duruslari**: moved DocType and JSON configuration for kta_calisma_karti module
      
      
    
      
      
        
- **kta_operasyon_grubu**: moved KTA Operasyon Grubu DocType and related files for kta_calisma_karti module
      
      
    
      
      
        
- **hooks**: remove unused custom field filter for Calisma Karti
      
      
    
      
      
        
- **calisma_karti**: remove custom field JSON configuration for Calisma Karti
      
      
    

  

  

    
    
    

### 🔧 Features

    
      
      
        
- Add KTA Calisma Karti module with Vue integration
      
      
    
      
      
        
- **kta_calisma_karti**: add new module definition and update modules list
      
      
    
      
      
        
- **calisma_karti**: implement Calisma Karti doctype with custom fields and functionality
      
      
    
      
      
        
- **calisma_karti_hurda**: add Calisma Karti Hurda doctype with fields and functionality
      
      
    
      
      
        
- **kta_calisma_karti_operasyonlari**: add KTA Calisma Karti Operasyonlari doctype with fields and functionality
      
      
    
      
      
        
- **calisma_karti**: add __init__.py files for kta_calisma_karti and doctype modules
      
      
    
      
      
        
- **calisma_karti**: add initial Vue components for Calisma Karti
      
      
    
      
      
        
- **calisma_karti**: add initial files for KTA Calisma Karti page and Vue integration
      
      
    
      
      
        
- **calisma_karti**: implement multi-step form for Calisma Karti with Vue components
      
      
    
      
      
        
- **calisma_karti**: add API functions for retrieving and creating Calisma Karti documents
      
      
    
      
      
        
- **app/ui/ux**: added loading helper, card re-creation wizard, ui/ux improvments
      
      
    
      
      
        
- add StepJobCardSearch component for job card barcode input
      
      
    
      
      
        
- **ui/ux**: enhance StepIndicator component with mobile compact view and improved step tracking
      
      
    
      
      
        
- **api**: add early validation for Job Card retrieval by barcode
      
      
    
      
      
        
- **api**: update Job Card retrieval to include early Work Order validation
      
      
    
      
      
        
- **workspace**: add hızlı tarama workspace configuration with initial content and structure
      
      
    
      
      
        
- **calisma_karti**: add custom field for İş Emri in Calisma Karti
      
      
    

  

  

    
    
    

### 🔧 Refactoring

    
      
      
        
- **calisma_karti**: add custom fields and property setters for Calisma Karti
      
      
    
      
      
        
- **calisma_karti**: optimize page load and Vue integration for Calisma Karti
      
      
    
      
      
        
- **hooks**: clean up commented code and improve readability
      
      
    
      
      
        
- **api**: update field names and improve error handling in create_calisma_karti
      
      
    
      
      
        
- **components**: clean up code and improve readability in StepOperation and StepUser components
      
      
    
      
      
        
- **App**: implement dynamic step descriptions and integrate StepIndicator component
      
      
    
      
      
        
- **ui/ux**: StepWorkstation flag added
      
      
    
      
      
        
- **ui/ux**: added user search and ui improvments
      
      
    
      
      
        
- **ui/ux**: StepJobCard ui/ux improvments
      
      
    
      
      
        
- **ui/ux**: ui/ux behaviors improved
      
      
    
      
      
        
- **calisma_karti**: clean up page load logic and remove redundant Vue mount
      
      
    

  


---


## 🚀 v0.2.2 (2025-12-06)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- Specify Frappe branch version during bench initialization
      
      
    

  


---


## 🚀 v0.2.1 (2025-12-06)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- Update app retrieval to specify branch for erpnext for ci
      
      
    
      
      
        
- **ci**: Enhance CI workflow to install erpnext and setup test site
      
      
    

  

  

    
    
    

### 🔧 Chores

    
      
      
        
- update author email in setup.py and remove unused test.txt file
      
      
    

  

  

    
    
    

### 🔧 Unknown

    
      
      
- fix(ci):Update CI workflow and author email, remove unused file
      
    

  


---


## 🚀 v0.2.0 (2025-12-06)





  

    
    
    

### 🔧 Features

    
      
      
        
- **work-order**: Automatically update Work Order status when Job Card starts
      
      
    
      
      
        
- **hooks**: wire Job Card update event to custom Work Order status handler
      
      
    

  


---


## 🚀 v0.1.0 (2025-12-06)





  

    
    
    

### 🔧 Bug fixes

    
      
      
        
- **ci**: update version_variables format for semantic-release
      
      
    

  

  

    
    
    

### 🔧 Chores

    
      
      
        
- Update the GitHub Actions workflow to utilize a personal access token for authentication.
      
      
    
      
      
        
- enable zero version support in semantic release configuration
      
      
    
      
      
        
- update semantic release configuration for versioning and commit parser
      
      
    
      
      
        
- update GitHub Actions workflow to use PAT_TOKEN for authentication
      
      
    
      
      
        
- adjust the commit parser to use the Angular style.
      
      
    
      
      
        
- enable zero version support in semantic release configuration
      
      
    
      
      
        
- update semantic release configuration for versioning and commit parser
      
      
    
      
      
        
- enable zero version support in semantic release configuration
      
      
    
      
      
        
- configure python-semantic-release with pyproject version
      
      
    

  

  

    
    
    

### 🔧 Features

    
      
      
        
- **ci**: add GitHub Actions workflow for CI with testing setup
      
      
    
      
      
        
- **ci**: introduce semantic-release with conventional commits and automated versioning
      
      
    
      
      
        
- Add kta_mrp module definition and update modules.txt
      
      
    
      
      
        
- **refactor**: Add new reports for production planning and purchasing
      
      
    
      
      
        
- **refactor**: Add custom weekly production field to item doctype
      
      
    
      
      
        
- **refactor**: Update module references from erpnextkta to kta_mrp in reports and JSON configurations
      
      
    
      
      
        
- **refactor**: Update module reference from erpnextkta to kta_mrp in item.json
      
      
    
      
      
        
- **refactor**: Format item.json for improved readability and maintainability
      
      
    
      
      
        
- **refactor**: Update report metadata and indices for consistency in kta_mrp module
      
      
    
      
      
        
- **refactor**: Update module import paths in capacity_planning_report for consistency
      
      
    

  

  

    
    
    

### 🔧 Refactoring

    
      
      
        
- **kta_mrp**: move reports to new module & update import paths
      
      
    

  

  

    
    
    

### 🔧 Unknown

    
      
      
- feat:Add CI workflow with testing setup and update version_variables format (#6)
      
    
      
      
- Hotfix/stock entry dialog (#2)
      
    
      
      
- Main mrp changes (#1)

* Default supplier and item name columns added to Material requirement report

* Fields are added to all stages

---------

Co-authored-by: alpkanoz <ozturk.alpkan@gmail.com>
      
    
      
      
- production start week formula correction
      
    
      
      
- Mandatory fields are added.
      
    
      
      
- Adding field of non_conformance in erpnextkta app
      
    
      
      
- Calisma karti autoname fix
      
    
      
      
- Calisma Karti filters, naming rule changes
      
    
      
      
- Calisma Karti custom fields
      
    
      
      
- troubleshooting AI changes
      
    
      
      
- Purchase order moq override, Calisma karti update
      
    
      
      
- troubleshooting AI changes
      
    
      
      
- troubleshooting AI changes
      
    
      
      
- troubleshooting AI changes
      
    
      
      
- supply_on: evaluate sales orders after processing; add evaluation endpoint
      
    
      
      
- troubleshooting AI changes
      
    
      
      
- troubleshooting AI changes
      
    
      
      
- Update process_supply_on method to find customer through Address doctype links child table using custom_eski_kod field
      
    
      
      
- troubleshooting AI changes
      
    
      
      
- refactoring api.py
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- material planning report fieldname change
      
    
      
      
- hata giderme
      
    
      
      
- alpkan calisma karti + mrp
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- kta machine capability study for quailty
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- özel alanlar
      
    
      
      
- GKK ve etiketler düzenleniyor.
      
    
      
      
- GKK ve etiketler düzenleniyor.
      
    
      
      
- GKK ve etiketler düzenleniyor.
      
    
      
      
- GKK ve etiketler düzenleniyor.
      
    
      
      
- GKK ve etiketler düzenleniyor.
      
    
      
      
- GKK ve etiketler düzenleniyor.
      
    
      
      
- GKK ve etiketler düzenleniyor.
      
    
      
      
- GKK ve etiketler düzenleniyor.
      
    
      
      
- GKK ve etiketler düzenleniyor.
      
    
      
      
- GKK ve etiketler düzenleniyor.
      
    
      
      
- Canlıdaki değişiklikler aktarılıyor
      
    
      
      
- Canlıdaki değişiklikler aktarılıyor
      
    
      
      
- Canlıdaki değişiklikler aktarılıyor
      
    
      
      
- Canlıdaki değişiklikler aktarılıyor
      
    
      
      
- Canlıdaki değişiklikler aktarılıyor
      
    
      
      
- Canlıdaki değişiklikler aktarılıyor
      
    
      
      
- Canlıdaki değişiklikler aktarılıyor
      
    
      
      
- Canlıdaki değişiklikler aktarılıyor
      
    
      
      
- Canlıdaki değişiklikler aktarılıyor
      
    
      
      
- Canlıdaki değişiklikler aktarılıyor
      
    
      
      
- Canlıdaki değişiklikler aktarılıyor
      
    
      
      
- Canlıdaki değişiklikler aktarılıyor
      
    
      
      
- Zebra Printer setup and label count corrected
      
    
      
      
- Zebra Printer setup and label count corrected
      
    
      
      
- Zebra Printer setup and label count corrected
      
    
      
      
- BOM to Item set custom index
      
    
      
      
- BOM to Item set custom index
      
    
      
      
- BOM to Item set custom index
      
    
      
      
- zebra
      
    
      
      
- Kta data update, send data to printer, zebra formatter
      
    
      
      
- Kta data update, send data to printer, zebra formatter
      
    
      
      
- db commit
      
    
      
      
- refactor
      
    
      
      
- 8D form update
      
    
      
      
- 8D form update
      
    
      
      
- 8D form updates
      
    
      
      
- 8d
      
    
      
      
- 8d
      
    
      
      
- new codes
      
    
      
      
- son güncellemeler
      
    
      
      
- all Purchase Receipt
      
    
      
      
- all changes
      
    
      
      
- all changes
      
    
      
      
- d1 takım üyeleri
      
    
      
      
- antrepo beyannamesi
      
    
      
      
- antrepo beyannamesi
      
    
      
      
- antrepo beyannamesi
      
    
      
      
- antrepo beyannamesi
      
    
      
      
- antrepo beyannamesi
      
    
      
      
- antrepo beyannamesi
      
    
      
      
- antrepo beyannamesi
      
    
      
      
- antrepo beyannamesi
      
    
      
      
- antrepo beyannamesi
      
    
      
      
- antrepo beyannamesi
      
    
      
      
- antrepo beyannamesi
      
    
      
      
- antrepo beyannamesi
      
    
      
      
- antrepo beyannamesi
      
    
      
      
- antrepo beyannamesi
      
    
      
      
- antrepo beyannamesi
      
    
      
      
- antrepo beyannamesi
      
    
      
      
- antrepo beyannamesi
      
    
      
      
- Purchase receipt debug
      
    
      
      
- Purchase Receipt overriding
      
    
      
      
- Purchase Receipt overriding
      
    
      
      
- Customer Income Account assignment
      
    
      
      
- Customer Income Account
      
    
      
      
- Customer Income Account
      
    
      
      
- 8D updates
      
    
      
      
- 8D updates
      
    
      
      
- customizations on 8D
      
    
      
      
- 3D modified
      
    
      
      
- customizations on 8D
      
    
      
      
- Client Script
      
    
      
      
- adding workspace
      
    
      
      
- new workspace
      
    
      
      
- remote changes applied
      
    
      
      
- eski kod alanları eklendi
      
    
      
      
- custom changes uploaded
      
    
      
      
- asset_category fixture immature
      
    
      
      
- Purchase Receipt
      
    
      
      
- Purchase Receipt
      
    
      
      
- Purchase Receipt
      
    
      
      
- Purchase Receipt
      
    
      
      
- Purchase Receipt
      
    
      
      
- Purchase Receipt
      
    
      
      
- D1 takım üyeleri
      
    
      
      
- D1 takım üyeleri
      
    
      
      
- D1 takım üyeleri
      
    
      
      
- D1 takım üyeleri
      
    
      
      
- Antrepo Beyanname No
      
    
      
      
- Antrepo Beyanname No
      
    
      
      
- Antrepo Beyanname No
      
    
      
      
- Antrepo Beyanname No
      
    
      
      
- Antrepo Beyanname No
      
    
      
      
- Antrepo Beyanname No
      
    
      
      
- Antrepo Beyanname No
      
    
      
      
- Antrepo Beyanname No
      
    
      
      
- Antrepo Beyanname No
      
    
      
      
- Antrepo Beyanname No
      
    
      
      
- Antrepo Beyanname No
      
    
      
      
- Antrepo Beyanname No
      
    
      
      
- Antrepo Beyanname No
      
    
      
      
- Antrepo Beyanname No
      
    
      
      
- Antrepo Beyanname No
      
    
      
      
- Antrepo Beyanname No
      
    
      
      
- Antrepo Beyanname No
      
    
      
      
- Antrepo Beyanname No
      
    
      
      
- Antrepo Beyanname No
      
    
      
      
- Antrepo Beyanname No
      
    
      
      
- Antrepo Beyanname No
      
    
      
      
- Purchase Receipt overriding
      
    
      
      
- Purchase Receipt overriding
      
    
      
      
- Delivery Note localization
      
    
      
      
- Delivery Note localization
      
    
      
      
- Added Income Account to party account
      
    
      
      
- Added Income Account to party account
      
    
      
      
- Added Income Account to party account
      
    
      
      
- Added Income Account to party account
      
    
      
      
- Added Income Account to party account
      
    
      
      
- Added Income Account to party account
      
    
      
      
- added role profiles
      
    
      
      
- added role profiles
      
    
      
      
- Item updates for Terminal and Kablo
      
    
      
      
- 8D form updates
      
    
      
      
- 8D form updates
      
    
      
      
- 8D form updates
      
    
      
      
- Quality Feedback sum Client Script added
      
    
      
      
- Quality Feedback sum Client Script added
      
    
      
      
- Quality Feedback sum Client Script added
      
    
      
      
- Quality Feedback sum Client Script added
      
    
      
      
- KTA Kalite Workspace
      
    
      
      
- KTA Kalite Workspace
      
    
      
      
- Property setters reset
      
    
      
      
- Property setters reset
      
    
      
      
- Property setters reset
      
    
      
      
- Property setters reset
      
    
      
      
- Property setters reset
      
    
      
      
- BOM Ürünü özelleştirmeleri
      
    
      
      
- BOM Ürünü özelleştirmeleri
      
    
      
      
- BOM Ürünü özelleştirmeleri
      
    
      
      
- operasyon grubu
      
    
      
      
- operasyon grubu
      
    
      
      
- operasyon grubu
      
    
      
      
- operasyon grubu
      
    
      
      
- operasyon grubu
      
    
      
      
- operasyon grubu
      
    
      
      
- operasyon grubu
      
    
      
      
- Kalite Geribildirim Değerlendirmesine tarih eklendi
      
    
      
      
- Kalite Geribildirimine Değerlendirme toplamı eklendi
      
    
      
      
- Kalite Kontrolü Barkod Kontrol alanı Barkoda döndürüldü
      
    
      
      
- Purchase Receipt üzerine workflow_state eklendi
      
    
      
      
- İthalat kısa malzeme açıklamaları
      
    
      
      
- 8D formu düzenlendi
      
    
      
      
- 8D formu düzenlendi
      
    
      
      
- 8D formu düzenlendi
      
    
      
      
- 8D formu düzenlendi
      
    
      
      
- 8D formu düzenlendi
      
    
      
      
- Doğru Doctype Link yapıldı (Gümrük Müdürlükleri)
      
    
      
      
- İthalat tab'ine alanlar eklendi
      
    
      
      
- varlık kategorisi fixture added
      
    
      
      
- varlık kategorisi fixture added
      
    
      
      
- Satış Sipariş Kalemi'nde Müşteri İndeksi Allow on Submit kaldırıldı
      
    
      
      
- Sanal veri tiplerin düzenlendi
      
    
      
      
- Sanal veri tiplerin düzenlendi
      
    
      
      
- Malzeme Kalemine KalemineÜrün ağacına Malzeme Grubu eklendi
Gümrük Müdürlükleri ve Bölge Müdürlükleri eklendi
      
    
      
      
- Malzeme Kalemine Kalemine BOM Müşteri Indeksi eklendi
      
    
      
      
- Satış Siparişi Kalemine BOM Müşteri Indeksi eklendi
      
    
      
      
- Ölçü Metodu fixture yapıldı
      
    
      
      
- Antrepo alanı açıldı
      
    
      
      
- İthalat kontrol değerinin varsayılanı 0'a eşitlendi
      
    
      
      
- İthalat kontrol değerinin varsayılanı 0'a eşitlendi
      
    
      
      
- Satınalma İrsaliyesine ithalat ve etiketleme geliştirmelerine ait iş akışı tanımlanıyor
      
    
      
      
- Satınalma İrsaliyesine ithalat ve etiketleme geliştirmelerine ait iş akışı tanımlanıyor
      
    
      
      
- Satınalma İrsaliyesine ithalat ve etiketleme geliştirmelerine ait iş akışı tanımlanıyor
      
    
      
      
- Kalite 8D formu eklendi
      
    
      
      
- Kalite Kontrolüne Borkod Kontrolü alanı eklendı
      
    
      
      
- Ürün Kalite Kontrol Parametreleri ek alanı Ölçü Metodu eklendi
      
    
      
      
- kalite için Ölçü Metodu DocType tanımlandı
      
    
      
      
- Ürün Müşteri Detayı üzerinde Referans Açıklaması alanı açıldı, Ürün Tedarikçisi üzerinde Tedarikçi Parça Açıklaması alanı açıldı
      
    
      
      
- Ürün Ağacı üzerinde Müşteri İndeksi alanı açıldı
      
    

  


---
