
# 📜 Changelog



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
