# CHANGELOG


## v0.1.0 (2025-12-06)

### Chores

* chore: Update the GitHub Actions workflow to utilize a personal access token for authentication. (#10)

* chore: enable zero version support in semantic release configuration

* chore: update semantic release configuration for versioning and commit parser

* chore: update GitHub Actions workflow to use PAT_TOKEN for authentication ([`772b281`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/772b281f7f703fe178395cf2ce514bf6c9bec6f2))

* chore: adjust the commit parser to use the Angular style. (#9)

* chore: enable zero version support in semantic release configuration

* chore: update semantic release configuration for versioning and commit parser ([`1ca8991`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/1ca89917923734de76f1ae12f1ef93243009ec35))

* chore: enable zero version support in semantic release configuration ([`64426d4`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/64426d4981262b7421badb51aa8ec1af12cc0e98))

* chore: configure python-semantic-release with pyproject version (#7) ([`aaf52fe`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/aaf52fe4284ac343299eb37068e2aa7e9c271828))

### Features

* feat(ci): introduce semantic-release with conventional commits and automated versioning (#5) ([`6ce4f03`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/6ce4f03e8cc9c52c5a715828ba8f78a0e28f5443))

### Refactoring

* refactor(kta_mrp): move reports to new module & update import paths (#3)

* feat: Add kta_mrp module definition and update modules.txt

* feat(refactor): Add new reports for production planning and purchasing

- Implemented Production Start Week Report to analyze production schedules based on sales orders and stock levels.
- Created Recommended Purchase Orders report to suggest purchase orders based on material requirements and supplier details.
- Developed Shipment Week report to track shipments and delivery schedules for customers.
- Introduced Work Order Planning report to visualize work order requirements against production capacity.
- Added necessary JavaScript and JSON files for frontend integration of the new reports.
- Included helper functions for fetching item groups and calculating stock balances.

* feat(refactor): Add custom weekly production field to item doctype

* feat(refactor): Update module references from erpnextkta to kta_mrp in reports and JSON configurations

* feat(refactor): Update module reference from erpnextkta to kta_mrp in item.json

* feat(refactor): Format item.json for improved readability and maintainability

* feat(refactor): Update report metadata and indices for consistency in kta_mrp module

* feat(refactor): Update module import paths in capacity_planning_report for consistency ([`bc03ceb`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/bc03ceb55385f5468c57b7ac4731ed4eea533efe))

### Unknown

* feat:Add CI workflow with testing setup and update version_variables format (#6)

* fix(ci): update version_variables format for semantic-release

* feat(ci): add GitHub Actions workflow for CI with testing setup ([`e6aee0a`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/e6aee0aff1a956d2d3b41c476f51617258ef9ecb))

* Hotfix/stock entry dialog (#2) ([`7e701b0`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/7e701b0ceea18fd81b829c2b90992b892ae3164d))

* Main mrp changes (#1)

* Default supplier and item name columns added to Material requirement report

* Fields are added to all stages

---------

Co-authored-by: alpkanoz <ozturk.alpkan@gmail.com> ([`55155c4`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/55155c4bd30d6b2e08b4136ffbd6d8168da0e734))

* production start week formula correction ([`8360365`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/8360365709f9440a5f6a30c7cb127cb381865436))

* Mandatory fields are added. ([`df99951`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/df99951b4d226ceeed55625cbf7721f2c0e49c82))

* Adding field of non_conformance in erpnextkta app ([`caffa39`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/caffa39c771d4fa45d8274b3b3edd8097c01138a))

* Calisma karti autoname fix ([`ff4716b`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/ff4716bcf1420bd16d541b9650fb7f188eeaf9d6))

* Calisma Karti filters, naming rule changes ([`5fb502b`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/5fb502b2f428c63732b03585aa07978fbf2091bf))

* Calisma Karti custom fields ([`09af41a`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/09af41a4e43d8b26ea4ea6ecf1e67a8db4be0758))

* Merge branch 'master' of 10.41.253.168:kta/erpnextkta ([`3fb024f`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/3fb024f989d970bcde09e98df79769f252aae1b2))

* troubleshooting AI changes ([`61ecdb5`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/61ecdb5692ebe77ca0bd81b2bdb40c0a668cd3e5))

* Purchase order moq override, Calisma karti update ([`99ff9d3`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/99ff9d37bcc8656fd1418742c49b6028fc735166))

* troubleshooting AI changes ([`080ec91`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/080ec91db1004f4f7f133380f12b6c3b0ad9d02d))

* troubleshooting AI changes ([`ad3a8ba`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/ad3a8bab94ea23a7e7d3a977dd1b5eff3e5557f6))

* troubleshooting AI changes ([`388fd44`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/388fd44332db634f0ffd24d464c44ca02077a8f4))

* Merge remote-tracking branch 'master/master' ([`099dd11`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/099dd11ee282727461250a9ea46c9db942af89bd))

* supply_on: evaluate sales orders after processing; add evaluation endpoint ([`836a3d7`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/836a3d7c41f119b1486098ce413d70ada133e59c))

* troubleshooting AI changes ([`8694dfd`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/8694dfdcdd5e31e1a4e267dcfeae7c171ab118e2))

* troubleshooting AI changes ([`def2e56`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/def2e56b117a7b0616deaeb7e51a075f9b7dbc7e))

* Merge remote-tracking branch 'upstream/master' ([`7ace4c1`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/7ace4c1cbbb7bf8b793be10a92e122856b8ccff8))

* Update process_supply_on method to find customer through Address doctype links child table using custom_eski_kod field ([`d5b0634`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/d5b063450a261ef7de4e6b6d7ff4f3ed51733bbe))

* troubleshooting AI changes ([`4d5222b`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/4d5222bd0143f30dd64bf0501310fd45067b9270))

* refactoring api.py ([`4dc3c9e`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/4dc3c9e662acbbae6fc38fbbd08789a53bf9094a))

* özel alanlar ([`1ec3706`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/1ec3706d966dcb399f204e7b21ed3593f70857e2))

* özel alanlar ([`54ca64b`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/54ca64b2fc8a4c6ab9fc437b350320c9dc7920c8))

* özel alanlar ([`121300f`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/121300f965707d8eb8aca3a3b79c0177781b9f8c))

* özel alanlar ([`73b4200`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/73b4200adfb766b07a5ed3a5aeac0b1ae000fad7))

* özel alanlar ([`a96a209`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/a96a2095fcb9169992ac9a61ae5ab244e2754a2d))

* özel alanlar ([`7a2e67a`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/7a2e67ae8df374b1ffa2ef3554a5d5dfc26438e5))

* özel alanlar ([`27cf599`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/27cf5993c6bf55a2669319b84ba886d5e6496c9c))

* Merge branch 'master' of 10.41.253.168:kta/erpnextkta ([`c45b899`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/c45b899974ca195ac57cf0e78c054ba243f9f0af))

* özel alanlar ([`432e43b`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/432e43b7701214913778378e793106e0f506a7d7))

* özel alanlar ([`dfe9793`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/dfe97932cef2392071501f4e97b04b8c3541d756))

* material planning report fieldname change ([`7eec484`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/7eec4841bdb7f29729905ee96966009a409a40c5))

* hata giderme ([`cfe0ab4`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/cfe0ab4e6a2228be3b1ea4c855bcd29d49b18188))

* Merge remote-tracking branch 'origin/temp-saving-my-changes'

# Conflicts:
#	erpnextkta/api.py ([`ae7c76c`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/ae7c76c3c8281f595fad7a6dfc5162ca5f51b681))

* api.py guncellenmesi ([`207c016`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/207c0163d2d535372853b59fd5f2a40b2c18f826))

* Merge remote-tracking branch 'origin/temp-saving-my-changes'

# Conflicts:
#	erpnextkta/api.py ([`f7b653d`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/f7b653d5d67ecb946547a011f2550fb5819beb25))

* alpkan calisma karti + mrp ([`cd032c0`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/cd032c006d655c2eed71b0db941e2ae8e6cfd939))

* özel alanlar ([`ee603f5`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/ee603f5e7134cf669b4df7b36f376764ca58cee6))

* özel alanlar ([`e499641`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/e499641bb8910fe7838e14ce77bee54ca9724539))

* özel alanlar ([`424ddde`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/424ddde8ab7ab1a10377df76864ee0af5b0b1ad7))

* özel alanlar ([`303954e`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/303954e8ec1983a4f4ba04eaec443ecc8786fb17))

* özel alanlar ([`fe5bc37`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/fe5bc379e7b07a22524d8c9af85a01c77e04409b))

* özel alanlar ([`15eb602`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/15eb602446cafb198362f830855fecf8dad54881))

* özel alanlar ([`1519a0b`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/1519a0bce539ac0280c0f1565e18c0a29e2654e8))

* özel alanlar ([`338ca9d`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/338ca9d09413a004373a25301dfa30ba51155570))

* özel alanlar ([`84188a9`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/84188a99ef74e1f9a40265c9c83a52382aa1a950))

* özel alanlar ([`955df1f`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/955df1f876b278d9a2e985754d049323e45c63c8))

* özel alanlar ([`ef3f467`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/ef3f467f980bab506c25e82a58418bfb1e1969a9))

* özel alanlar ([`00ce27d`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/00ce27d8d917902d173d7836540579af6b211b7b))

* özel alanlar ([`9f4b17c`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/9f4b17c19dd6ac402d4d70c489faef0f072b7374))

* özel alanlar ([`b1ee8c2`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/b1ee8c223ee6d6500bba23cd1ace9cd778a741be))

* özel alanlar ([`90a9bf8`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/90a9bf8d66a5762ed53e3928e71b325887a2f413))

* özel alanlar ([`e3206a0`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/e3206a088bbbec58dd594e577a4ad6bdcdd4c322))

* özel alanlar ([`f9d65fa`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/f9d65fa2aa217b56638e44e50a6a4166be9696d6))

* özel alanlar ([`52b8981`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/52b8981255215de38d87eecfec16c3e6fc503497))

* özel alanlar ([`d630bb0`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/d630bb03ba38a2446955f5779b857c2e38eed42f))

* özel alanlar ([`d273f5f`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/d273f5f4cb668828478137750f7dd47263660875))

* özel alanlar ([`23ee570`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/23ee570d305a717f19514d909ee681f6520468ff))

* özel alanlar ([`ea61c31`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/ea61c3139fe312c31317688fce5a0366276f7ede))

* özel alanlar ([`2e6aa26`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/2e6aa26ec761afbef055b1e59746b363e2360231))

* özel alanlar ([`5f150e0`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/5f150e07584ee79847f3212a6c1cfe301f1eb7ba))

* özel alanlar ([`8b279e0`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/8b279e06883a4816df86a1d249aee77cf2ff88d3))

* özel alanlar ([`ab04067`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/ab04067022cca0222fe7ed54f6bad39d29fea036))

* özel alanlar ([`c4ac0ff`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/c4ac0ff2c01966aa3393e2b04740e9e920f13faa))

* özel alanlar ([`409e346`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/409e346c1905b67c503740711792b6fa840e87b2))

* özel alanlar ([`b62916b`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/b62916b455dc4b01ec24bf8621978be74bc64975))

* özel alanlar ([`6923ef5`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/6923ef58a9b274109b60e65cd20707c24ccd9329))

* özel alanlar ([`e279077`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/e2790777de2b27b4d027a5ef34300e1981d658e6))

* özel alanlar ([`c0eac8e`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/c0eac8eb7763395d15d07b85c945f71d1ba5118c))

* özel alanlar ([`b5b767d`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/b5b767d743a3f115c8be4bcd07a2015e1c5ea9ee))

* özel alanlar ([`ec604bf`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/ec604bf45e16da9116d506c7ae9a4476508faf4f))

* özel alanlar ([`cfd312f`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/cfd312fbd6b8de283e12b07208732b1eceaf9511))

* özel alanlar ([`b64fe87`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/b64fe87db696eb9609481e50df8a7b621237db1b))

* özel alanlar ([`92ff052`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/92ff05232c4344719be5aeb2122f682dbab33c46))

* özel alanlar ([`f94c07d`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/f94c07d6810443e566470be8cca970c229961a32))

* özel alanlar ([`808cc5f`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/808cc5feb87098ca87c069eba75ac0217abe463f))

* özel alanlar ([`1805437`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/1805437ed1aa0dc71d485f47f773f99ecc6a02b0))

* özel alanlar ([`ee5e9e7`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/ee5e9e7168e1cf42ca5b50b3d781cd9774d37a84))

* özel alanlar ([`3296977`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/3296977deb83b1c7b5a59f37b6f8736d106134fd))

* özel alanlar ([`9c042d7`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/9c042d7699110b22de88a3e1a1662e7b5185ef78))

* özel alanlar ([`9ae6b96`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/9ae6b9613733eddc3ea951deec6938308bfdf765))

* özel alanlar ([`6fb611f`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/6fb611fbaab414986b4057807a96e5450c8ada23))

* özel alanlar ([`a8d5f80`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/a8d5f808926ce9a5dbcc9b831a6cd29eac625617))

* özel alanlar ([`85efd43`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/85efd43c5cfb96710113df267712f2fdfa4c8059))

* özel alanlar ([`494d140`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/494d14034fcd35afffbc61cfa9aecf6ca37b52a7))

* özel alanlar ([`c899744`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/c899744faa59ba300fdfd9f0a67f666b6bb6ad1c))

* özel alanlar ([`e4cf5a2`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/e4cf5a25b20adae53bc3b44d3b43208cb515eaa2))

* özel alanlar ([`3b762f8`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/3b762f8624a9ec2c2c13f7053e2fc6ec175d043d))

* özel alanlar ([`4d21196`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/4d2119630f47627fc696add86015629d507715f7))

* özel alanlar ([`0753e00`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/0753e00d9191a915784848273343befc392a053c))

* özel alanlar ([`cf27a2f`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/cf27a2f90a83541639cc6ec76e55855251c1fd78))

* özel alanlar ([`ceeb17b`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/ceeb17b519760cd31fd702293babd34eb9fe71de))

* özel alanlar ([`19b4f2f`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/19b4f2fffe5353bd07fa5187777ab558c1ccd561))

* özel alanlar ([`eda6d67`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/eda6d6778ff66db718c11b4bea7fbdcd2458893f))

* özel alanlar ([`9339f92`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/9339f9263d161b2f3dd8c44167091d1ee7701801))

* özel alanlar ([`04fe735`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/04fe735f2b659fd8634187961b991e0721dba173))

* özel alanlar ([`55c27ba`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/55c27bafe70ee49212efe2300f09cf285ac78e12))

* özel alanlar ([`125f424`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/125f4248251811267359f262227de1551807d91c))

* özel alanlar ([`f40dddd`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/f40dddd28db6fc485a498a8e540701b688b50f37))

* özel alanlar ([`44f1dd7`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/44f1dd7f4dc0879068aa57903e3b09eed47d5a5e))

* özel alanlar ([`5506576`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/55065764b1f2ed07cfb2728e6109a35b1ec18ac3))

* özel alanlar ([`4c45709`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/4c45709886b0445bc3bda063ba04c1b2ba785c01))

* özel alanlar ([`372371e`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/372371e664598c5b782d924f9a4368cf98db24b6))

* özel alanlar ([`12ab855`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/12ab8556f037ff8d77ba5d557080e93f58eab5df))

* özel alanlar ([`66be88b`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/66be88b1bfaa083f5720224a730453cd52463dfa))

* özel alanlar ([`329445d`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/329445dfa2b1d3e0fb33cb5e41fda4d60a5ad9ac))

* özel alanlar ([`8f30fa9`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/8f30fa9418109a3c157f100a1981a81b35ed6ec9))

* özel alanlar ([`2e9de00`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/2e9de005ac39060ba1726cbe39ea7c709e7a6bb5))

* özel alanlar ([`d5ee2f7`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/d5ee2f7dd65033b6699049b2140bb7036370bc8f))

* özel alanlar ([`7365d6f`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/7365d6fae1664fe68e097b8efe45dd35dbb1e97c))

* özel alanlar ([`db08013`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/db080137d717ebc413e6f626a735b20abdfbec4a))

* özel alanlar ([`20f9820`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/20f98202f3c7ca58f877e1f02072a2b6e880f79c))

* özel alanlar ([`f4872d6`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/f4872d6ba8a2ddbcbb3961aeba276b0b9056614b))

* özel alanlar ([`b52d0f9`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/b52d0f9f47065fa4e457c30ba54554c03f2bf747))

* özel alanlar ([`19ff6a1`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/19ff6a1ae7835660795c5bc24764000ffe22c2aa))

* özel alanlar ([`0e8293a`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/0e8293a153f1a53dd8a7134c81949d53ef2e0d13))

* özel alanlar ([`2ad30f2`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/2ad30f2b1c7b1e65e2850b26dda90822b55a2590))

* özel alanlar ([`71acc60`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/71acc60cc1b6ada9bd2feaff3335a9dc55459ce6))

* özel alanlar ([`775f467`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/775f467f792f85186a338c04338e8f5db01274ad))

* özel alanlar ([`1c3f404`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/1c3f4041b89a3469ac4e83ef73fe8d7d400f09b5))

* özel alanlar ([`c0b1856`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/c0b1856d693841ec04ac7826136c245329ae42ea))

* özel alanlar ([`18827f4`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/18827f46e12dabf10bfbdfa317fa9e35eda389cb))

* özel alanlar ([`cc1debd`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/cc1debd5e40aca2be1bb270b4ca326113126ed86))

* özel alanlar ([`e5fbe7c`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/e5fbe7c622b38d500690c049ba2d1243c5630538))

* özel alanlar ([`21bbe13`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/21bbe136dafbef05114b82330f6ea2c848c19301))

* özel alanlar ([`b710265`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/b7102658655e949db93aa41109599ec7a3b64011))

* özel alanlar ([`04c8fd9`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/04c8fd985aff30d1f2fc9c4a1922d446eacc40fc))

* özel alanlar ([`17916ba`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/17916badfacc71d47c9e10f0f4508392dc407005))

* Merge remote-tracking branch 'upstream/master' ([`a17e0b3`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/a17e0b31bd6c51fdec0d8025a1e02c89bb62caab))

* özel alanlar ([`c05ea96`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/c05ea969a5aaaa904be1a35e7f086a7735101a87))

* kta machine capability study for quailty ([`5b10956`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/5b109560aa19d8b8ae522bd315a52a7cfa942fb1))

* özel alanlar ([`3a7fa6e`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/3a7fa6e235d90116064aa5381f9506e6e59d2c44))

* özel alanlar ([`9597cb0`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/9597cb0cf539738af947cccc27b96084e4cd95f4))

* özel alanlar ([`6b79546`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/6b795469ba97ab5d99d4b5eaaa37552256f994ab))

* özel alanlar ([`c875cef`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/c875cef1f9375d34ac10d00525a8dfe467062263))

* özel alanlar ([`e1d28ff`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/e1d28ff42cd895737c09c8b8a97bd94da34a62ad))

* özel alanlar ([`7e19f5f`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/7e19f5f483f6a92dd348515a84337c8ef82e7e98))

* özel alanlar ([`b2db353`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/b2db35304fe93dad2f4c064ec6f2ac2a3a333cee))

* özel alanlar ([`2bd8b69`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/2bd8b692736a205a79c07faaf64f2dd3370f6591))

* özel alanlar ([`2903aa3`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/2903aa31452923e74194dfb1575d9f2d433ac74b))

* özel alanlar ([`9408f54`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/9408f54e33fbe6a0e69c864f8226a174f19f3eb5))

* özel alanlar ([`af55c28`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/af55c2874db567623ba6510240b1334252cc9056))

* özel alanlar ([`26c7d70`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/26c7d705ca3be5f8e745a3b12870c8ff11406b7f))

* özel alanlar ([`03af7ff`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/03af7ff33c074269e132350d338c42e47f389cd5))

* özel alanlar ([`24ec081`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/24ec08137c185141128f8240ea3e29e1fc019d7c))

* GKK ve etiketler düzenleniyor. ([`64f612c`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/64f612cafe8403ea351409381b1196cf4bedc2dd))

* GKK ve etiketler düzenleniyor. ([`ad257ef`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/ad257effd1dd0a125b038d0c0f1d0d144670231f))

* GKK ve etiketler düzenleniyor. ([`68d088a`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/68d088a60ee887c42e93aaa2a55f3bc4e18096cc))

* GKK ve etiketler düzenleniyor. ([`f2b879e`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/f2b879e81ab78da85ce41cdacc283005f80e1287))

* GKK ve etiketler düzenleniyor. ([`3e2289c`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/3e2289c084e9611c0603a09459023bbba076da23))

* GKK ve etiketler düzenleniyor. ([`43c974c`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/43c974c717a2f6148c740ed64d40679b161b8ef5))

* GKK ve etiketler düzenleniyor. ([`9bf189e`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/9bf189e9543e50246aad0e7a794819ce940fde56))

* GKK ve etiketler düzenleniyor. ([`d795054`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/d79505495a41278be07e001628066115e36d3585))

* GKK ve etiketler düzenleniyor. ([`b9ac195`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/b9ac1956a241e0c8176b14df21c34e89e983635f))

* GKK ve etiketler düzenleniyor. ([`f3fe24c`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/f3fe24ce6a162d6a31d9dfe2e716ada07f293927))

* Canlıdaki değişiklikler aktarılıyor ([`52cd29a`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/52cd29a70f0df80a8b6e8190f71aeadc6ac4f2f4))

* Canlıdaki değişiklikler aktarılıyor ([`1765470`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/1765470342485846169502e8e908dd08f7359864))

* Canlıdaki değişiklikler aktarılıyor ([`c0ad0d6`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/c0ad0d623d468e6f970b59f26c82c61bae919150))

* Canlıdaki değişiklikler aktarılıyor ([`3346b0c`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/3346b0c697bfabc8821c69a11d000aa233bc1ece))

* Canlıdaki değişiklikler aktarılıyor ([`1806835`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/1806835da8107b6a14ec97524afdb3f3da5ec265))

* Canlıdaki değişiklikler aktarılıyor ([`0a00cff`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/0a00cff46a5aa07b9d0dedd04ae171c973ce73a1))

* Canlıdaki değişiklikler aktarılıyor ([`71892df`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/71892dfbeceecc1c4c7c9fd3f25cf87b697c4261))

* Canlıdaki değişiklikler aktarılıyor ([`4671595`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/4671595d1a131d4249ab154a207dc16c64f340e2))

* Canlıdaki değişiklikler aktarılıyor ([`c1fa5af`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/c1fa5afef1a7b9f4bcfeda58b1042152f82378a5))

* Canlıdaki değişiklikler aktarılıyor ([`8d528d9`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/8d528d9daa8205733babc691c63d286848cc5869))

* Canlıdaki değişiklikler aktarılıyor ([`017a445`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/017a445a79a0504a93ece59a0e606f15a92c7e65))

* Canlıdaki değişiklikler aktarılıyor ([`3216669`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/321666973d0e5502374cf1d7e9f360aff3867ad8))

* Zebra Printer setup and label count corrected ([`3bb9564`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/3bb9564ad8ce1025ce6c1672701357f146340cd2))

* Zebra Printer setup and label count corrected ([`5ea4ef2`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/5ea4ef26100ca47cdbe0fd2e7eaabaab67038022))

* Zebra Printer setup and label count corrected ([`4c9c071`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/4c9c07173aaee3828faafa670651536d58db93af))

* BOM to Item set custom index ([`ee34408`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/ee344081e85d38fa6db6cb5bcee1150cd9425b25))

* BOM to Item set custom index ([`5c7c70f`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/5c7c70f442b68ea9403cc8d739e50b758a3d7ba6))

* BOM to Item set custom index ([`ab6c7ac`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/ab6c7ac90ee83b5ffbbc06f9ff9021e8ec8b326e))

* zebra ([`ed91d48`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/ed91d481ce666e7ab1dcb6932aadfca4eede2901))

* Kta data update, send data to printer, zebra formatter ([`141561b`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/141561b1d954694efb66272bdfc16282143c4c2d))

* Kta data update, send data to printer, zebra formatter ([`1409e29`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/1409e29a319c592a12a22fa72268a2167f97294c))

* db commit ([`e341f54`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/e341f54f6b12fa22dda29b540659b4a251c91b31))

* refactor ([`158b99f`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/158b99f63ab19dfb25089b1de450c620b80dfa20))

* 8D form update ([`5acce39`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/5acce39e8d2648999b16b8065d6b15ae5b624b81))

* 8D form update ([`9426cd3`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/9426cd365edfe40cb762c3cb4e615c69de30699d))

* 8D form updates ([`3c0991b`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/3c0991ba16fdf52bd877e48bca519a7e8567904e))

* 8d ([`29fcef2`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/29fcef260bec705ff5bcb5b83c05d742d1892d21))

* 8d ([`56f345d`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/56f345d693db51294b40ccbd5c064c647d7a121a))

* Merge remote-tracking branch 'origin/master' ([`b8469a9`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/b8469a939355a9afff5a5f7cb8bb08ed341f9e92))

* new codes ([`b21b58c`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/b21b58c3e7b01d08a44a2207d5efd1a5dac2820d))

* son güncellemeler ([`6ccb5b6`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/6ccb5b612c58bfe42d507c0072a8213e2315e353))

* all Purchase Receipt ([`328bd4a`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/328bd4ae7b89aebf66dab1eb80550008d6aaed5c))

* all changes ([`fff27e0`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/fff27e0a7b0b0094bd0d784104453f3bb1af12a0))

* all changes ([`3bf449b`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/3bf449bac56db808abb73d6523e484828e2a6e71))

* d1 takım üyeleri ([`13e9604`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/13e96041d90dbffe4999d13f158d707aabffc1c7))

* antrepo beyannamesi ([`7a7a784`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/7a7a784a3cdc0a264497728d32d821a63a6244d3))

* antrepo beyannamesi ([`ba6b6aa`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/ba6b6aa458e07870fd1485e3f9de7ebc98a891e9))

* antrepo beyannamesi ([`6dee280`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/6dee28073bd0c7d056a69b8667ad4a35c7e7bbf0))

* antrepo beyannamesi ([`0a3d69e`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/0a3d69e50b4d74a3db274663cba1e1351af0ff75))

* antrepo beyannamesi ([`2ec81da`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/2ec81da294e5eb1987f308ee8142c44beb6f67fa))

* antrepo beyannamesi ([`5575a69`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/5575a692620b5c2d87e795628e82d6b60042533d))

* antrepo beyannamesi ([`b4d9370`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/b4d9370a5d5ec0b45065dd7f9e06681b435af1d7))

* antrepo beyannamesi ([`7b9a13a`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/7b9a13a669d9783a509401f16d77b180c50017fc))

* antrepo beyannamesi ([`cf88f87`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/cf88f87b8cae88c62e8f759d71a6a33820cfc61c))

* antrepo beyannamesi ([`1b18e75`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/1b18e75f59157ebb607e6a3685a340c750608228))

* antrepo beyannamesi ([`16c1726`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/16c1726a0717c46e5b9a430cd554b575e934e4f8))

* antrepo beyannamesi ([`29c6469`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/29c64694dd4f929792b7abdfd557c39f7a8757ec))

* antrepo beyannamesi ([`91c0995`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/91c0995401542910ef71cf35e18495388b3c7a37))

* antrepo beyannamesi ([`91ef606`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/91ef606724c41b652799e47a8aad365f12f4e22d))

* antrepo beyannamesi ([`13a7e99`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/13a7e994fc5e3d2f346ae897d3cdfb444b781a2a))

* antrepo beyannamesi ([`f011130`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/f011130d921be182bf5df7c0aedf5ed0c6391623))

* antrepo beyannamesi ([`9a7dd03`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/9a7dd0303f6cdb7979f0a081e0e2c6525d47f570))

* Purchase receipt debug ([`c81a6a4`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/c81a6a49cd90839c05599f68ce3a1e1188978959))

* Purchase Receipt overriding ([`c4f66fe`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/c4f66fe3403d370ccee38534c7572188e94356fe))

* Purchase Receipt overriding ([`9db5411`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/9db5411389ca59eb86e16f4991a67c6793df3333))

* Customer Income Account assignment ([`25e6300`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/25e6300dbebed86031db59d2a18f4b5df1e421f0))

* Customer Income Account ([`de95777`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/de95777d89bed165a6a45c5306d0bca9156b4789))

* Customer Income Account ([`a0e1ee7`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/a0e1ee70b2fef9fffc430d120cce7f67b0042512))

* 8D updates ([`b22cabf`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/b22cabf291dd057d1230981652fe779e682ca77c))

* 8D updates ([`d176efe`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/d176efe782fdb70c31a9e5164d25e13b00116448))

* customizations on 8D ([`35fc225`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/35fc225c8c06284ae9446220db90753c603373a2))

* 3D modified ([`4d1a4e9`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/4d1a4e97d3a59fe900664e0439a84fac30eb069e))

* customizations on 8D ([`b75e533`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/b75e53306bd8b40c2877c4c3cc003b1a0a778daf))

* Client Script ([`8e60764`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/8e60764930b05287e76cf84ccf89c1929b2f692e))

* adding workspace ([`fae5524`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/fae55242a543c3775fefcf7e58f2941a6c867ba0))

* new workspace ([`33a81bb`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/33a81bb7762a2a246310f78c32b4a539dfbfb24f))

* remote changes applied ([`197a79c`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/197a79c126d699b14c1986bc2c8e12554320c782))

* eski kod alanları eklendi ([`a35dd74`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/a35dd74a9d6fe5f411b5fd7085f35f427a36f382))

* custom changes uploaded ([`0b9e824`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/0b9e82483998a8c4cfa9c31ba869830f430f9d4a))

* asset_category fixture immature ([`094d959`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/094d9591721903ae6563d84f0604001bb5b3e9b3))

* Purchase Receipt ([`5f0ddf5`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/5f0ddf5b4b84698789d4d74c2a8bac82bb103673))

* Purchase Receipt ([`984b5ac`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/984b5accb70544e53de68f548c13310fa19771a3))

* Purchase Receipt ([`e22f9fa`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/e22f9fa86f40215baa34998f738e1048d28807de))

* Purchase Receipt ([`4a07cc3`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/4a07cc3fe0feaad37847de2aaa4b7648a65d065d))

* Purchase Receipt ([`62997b1`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/62997b1c1135af1ac4c2742c448261f61b7463dd))

* Purchase Receipt ([`93d7453`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/93d745326b2b4ce7d87cea7e8e09eff19974ce59))

* D1 takım üyeleri ([`574a2fb`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/574a2fb9b28cba70ebff01ac45091e4ddbe949f7))

* D1 takım üyeleri ([`581de28`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/581de28943da3c6d8679037dd5f00089cdd21ddd))

* D1 takım üyeleri ([`aca5ecf`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/aca5ecf7fae8d334bcdfd336223c93a9d37a27cd))

* D1 takım üyeleri ([`ef0368b`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/ef0368ba278ee22e7355224dffe5a10b5887a939))

* Antrepo Beyanname No ([`7223d2d`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/7223d2d477432652056d9c987fd23166d71ffae4))

* Antrepo Beyanname No ([`afe5cf6`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/afe5cf6eb70367b423a63732f5c883ddb62ab4ab))

* Antrepo Beyanname No ([`ef27945`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/ef279456ac6f22955fe942cea9b6adf0968748bb))

* Antrepo Beyanname No ([`0e7c634`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/0e7c6344bac6e3e0c05251502031493ace2b97e5))

* Antrepo Beyanname No ([`1c4fbc1`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/1c4fbc168f44a41e7bdf310b91a5bb84b1525b66))

* Antrepo Beyanname No ([`91b9ea6`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/91b9ea6dffb0fc095be8e0f9b2f94fab0ad72212))

* Antrepo Beyanname No ([`d53dad6`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/d53dad6518c07308bebacad2150906249fd2f6b2))

* Antrepo Beyanname No ([`fa167d4`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/fa167d4f16766d152b11acae92e254b33f89a0d3))

* Antrepo Beyanname No ([`44b5d7a`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/44b5d7ac82bf4c1aac78b2a75077c36edfd093c0))

* Antrepo Beyanname No ([`0ed6809`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/0ed68094d7628beb677085ee2a29d4920ab2b98b))

* Antrepo Beyanname No ([`7bb2619`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/7bb2619d473f30ee596353738710011c9c48193d))

* Antrepo Beyanname No ([`33c6931`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/33c6931f4aa5ede90ca41dd27d5a3008ae960e2e))

* Antrepo Beyanname No ([`d8d80ba`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/d8d80baf6e0120635198e124ab1c4b868c25b021))

* Antrepo Beyanname No ([`05c744e`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/05c744e2334042d6a0b24c495ae83a37769ec405))

* Antrepo Beyanname No ([`09409d8`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/09409d849581f6a13364d5a765bc655207f69bdc))

* Antrepo Beyanname No ([`8139fb2`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/8139fb23f0ce100e45bdbccb2b1f874f682d405d))

* Antrepo Beyanname No ([`60e8d89`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/60e8d8985eb8ed9396c7c27fca73ee887ab7db89))

* Antrepo Beyanname No ([`d2f2501`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/d2f2501f063b7ace5ece566d2897ba5ab7c99c9b))

* Antrepo Beyanname No ([`dbd48cd`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/dbd48cd15e9e3f68f1888a060d777e8eea0b4023))

* Antrepo Beyanname No ([`7663774`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/7663774088ac15d609d56696bdbaef73f0434cc4))

* Antrepo Beyanname No ([`6f538a7`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/6f538a70aae2e7bf58e0b05b0647c0883b1fa158))

* Purchase Receipt overriding ([`c311c0e`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/c311c0eb4bd4a88b468f42d6c65adb94e85c42fd))

* Purchase Receipt overriding ([`71aba48`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/71aba4887a6162fc2ce7b5fc6c3e881f3963ef86))

* Delivery Note localization ([`fa81170`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/fa81170cb30a7cf38842c3ddf44e2eb265908090))

* Delivery Note localization ([`c5c1781`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/c5c1781fcf3aa6977fcd5c0b65880e3bb30cf808))

* Added Income Account to party account ([`af2e552`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/af2e55212392600f4247c69093f9035551b593f5))

* Added Income Account to party account ([`52f741e`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/52f741e3e8494b6db7751c43e60081a6daae4348))

* Added Income Account to party account ([`2f5561f`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/2f5561f8c2bee3d9921051ad8c6d45c448dfb8b7))

* Added Income Account to party account ([`0562755`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/0562755681270128e45e1bb031f15e3d7b5e38dd))

* Added Income Account to party account ([`bfd236b`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/bfd236bef2d8a7b107f1fb25b92eb74f33b6c8f3))

* Added Income Account to party account ([`d60b624`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/d60b624ce2f7e4d3badab2c5fb517d40e4cfd5ec))

* added role profiles ([`b519af2`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/b519af27e1bd42ba94b8754d5aab3262e2c7079f))

* added role profiles ([`7cfc14a`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/7cfc14afd84371407e0866bffc6211774b28e1c7))

* Item updates for Terminal and Kablo ([`3c12361`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/3c12361c0d96cb1797c3b170ba7eca6936535499))

* 8D form updates ([`4963a6d`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/4963a6d9e065b6d585e0511811b885a77a134965))

* 8D form updates ([`585f073`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/585f07318d360863cd6c36c91cb501c1914d49f7))

* 8D form updates ([`3941c56`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/3941c56f3d55be4df0cd475a8c20c185264977d5))

* Quality Feedback sum Client Script added ([`8e76a94`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/8e76a9424a1b885b7567638a79f740a83f33cd6a))

* Quality Feedback sum Client Script added ([`db1ed82`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/db1ed82e667408d7659b5de732ad1d83ff1af55d))

* Quality Feedback sum Client Script added ([`b3e01e2`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/b3e01e21d509abf9fee863fda7cf0e15e977aaa8))

* Quality Feedback sum Client Script added ([`4f43c72`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/4f43c72373d0081e2ab26aa2cfb34c3d82a04275))

* KTA Kalite Workspace ([`386884f`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/386884f4274b347e5db9ae6d7906ee1e2d324d49))

* KTA Kalite Workspace ([`7588b9a`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/7588b9aef509e90438be75e660fe1f4f85d2c354))

* Property setters reset ([`eef9f70`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/eef9f701c6fbb3bc5c810b8cb518d860fb5f8450))

* Property setters reset ([`dffd44d`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/dffd44d13bb15f53b9e4b15e2821f34391d5fbba))

* Property setters reset ([`e854980`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/e854980fd2b715c97bb3b99b0ab62594b75c5059))

* Property setters reset ([`08b02c4`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/08b02c4f70c9e82875688cbc767e751b2f076cd9))

* Property setters reset ([`945b704`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/945b704eb8c66bec444673c260ef1c33ca6c6fa9))

* BOM Ürünü özelleştirmeleri ([`1b55734`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/1b55734d5a3ab096c3ab0796c67f7a47baeefe75))

* BOM Ürünü özelleştirmeleri ([`dbf148d`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/dbf148dabc1fe4db07711d469db55f456b97caaf))

* BOM Ürünü özelleştirmeleri ([`fd1d101`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/fd1d101ffa99b72c5c7eff9f75289c4ce249135c))

* operasyon grubu ([`c34e200`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/c34e200f251fd463ffddfd688c13d0a79f5f5c92))

* operasyon grubu ([`c85926b`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/c85926b9f373073c6d6b29a7e4e51d11aa9200d8))

* operasyon grubu ([`fc12681`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/fc126819536f6601c5342571dc9fc67542b2c83e))

* operasyon grubu ([`3e92de7`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/3e92de7814f5f3d1f5ae8be95651177793881fea))

* operasyon grubu ([`3c0f218`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/3c0f218bc909ce8fc0bb9e27ce083e4ef7e1c4c4))

* operasyon grubu ([`d9e031f`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/d9e031f3b85505d219c7c6a5db7b979594969efc))

* operasyon grubu ([`22c152a`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/22c152a2591b6c41b8ac4c88657b4a379ea8d1d5))

* Kalite Geribildirim Değerlendirmesine tarih eklendi ([`2453c5c`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/2453c5c28b83ada5198cc1b0fe85b1f17ae0c86e))

* Kalite Geribildirimine Değerlendirme toplamı eklendi ([`77f6689`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/77f6689f04d0d2d2d010ee1260bc4b039830c16f))

* Kalite Kontrolü Barkod Kontrol alanı Barkoda döndürüldü ([`9b4883f`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/9b4883f6964986b2708cd932543192b98875e9aa))

* Purchase Receipt üzerine workflow_state eklendi ([`bab9290`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/bab92903f77edc078a0a7232950b1bd0f05bb98e))

* İthalat kısa malzeme açıklamaları ([`314594c`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/314594c1254bff76f23d6b91aec029f423b8a8f6))

* 8D formu düzenlendi ([`30e8764`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/30e8764c95d464b8023e4588795c949753c8c63f))

* 8D formu düzenlendi ([`276d323`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/276d323f9aa8896cdba6df3b3178e7762622c80c))

* 8D formu düzenlendi ([`0d189ad`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/0d189ad539fe801a6553d15855f2d0dda94aa229))

* 8D formu düzenlendi ([`6b21d2d`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/6b21d2d21e280e929c10a614e7c6b1d15f534db1))

* 8D formu düzenlendi ([`48d3d96`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/48d3d96fc42d20a8312d2a647d54c25f87d8b6cf))

* Merge remote-tracking branch 'origin/master' ([`8a2f708`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/8a2f708bec85c236b2a57f3f3a727b11f16c1b52))

* Merge remote-tracking branch 'origin/master'

# Conflicts:
#	erpnextkta/erpnextkta/custom/purchase_receipt.json ([`bdcb63b`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/bdcb63b030c035022fad2bede25d55701c5838b3))

* Doğru Doctype Link yapıldı (Gümrük Müdürlükleri) ([`04cc705`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/04cc705743ab2d313656c8655be009bc44e43ea6))

* İthalat tab'ine alanlar eklendi ([`2cdbe36`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/2cdbe36a863e701358cad44885689a80e134b3a7))

* varlık kategorisi fixture added ([`d0de407`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/d0de4075e07df9caf5b4d4fc38604d36eeb0645b))

* varlık kategorisi fixture added ([`aa7b0c1`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/aa7b0c118eaea82adeaf970ddba929dafb3319ce))

* Satış Sipariş Kalemi'nde Müşteri İndeksi Allow on Submit kaldırıldı ([`1d799f4`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/1d799f4b76e44f3971bb64f340aae01c46512252))

* Sanal veri tiplerin düzenlendi ([`8e32ca9`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/8e32ca9e59150aa242fd388d05f51c037f323495))

* Sanal veri tiplerin düzenlendi ([`f6ea7fb`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/f6ea7fb11b6149052f15a0c31f65ee5bf40ef8c0))

* Malzeme Kalemine KalemineÜrün ağacına Malzeme Grubu eklendi
Gümrük Müdürlükleri ve Bölge Müdürlükleri eklendi ([`cd924d9`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/cd924d9f5f9b059de1bb4bb8cf05ce39e5cf55d0))

* Malzeme Kalemine Kalemine BOM Müşteri Indeksi eklendi ([`e70c8a6`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/e70c8a6dabe2a709a661de6a083447ace0280024))

* Satış Siparişi Kalemine BOM Müşteri Indeksi eklendi ([`cd56183`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/cd56183cbf44acbf95b33a1947bee74423437fa0))

* Ölçü Metodu fixture yapıldı ([`8ab3948`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/8ab394868797bdcd8f98acbdcd2006b163c14846))

* Antrepo alanı açıldı ([`9cca2f6`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/9cca2f6b212b302a0a9a196e6fefadc9655a90c5))

* İthalat kontrol değerinin varsayılanı 0'a eşitlendi ([`3b7d32e`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/3b7d32e38005c5a47d4eacd641770a4f8223d0a3))

* İthalat kontrol değerinin varsayılanı 0'a eşitlendi ([`2900077`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/290007764f0c20572a1038fd66e8f74f4e148256))

* Satınalma İrsaliyesine ithalat ve etiketleme geliştirmelerine ait iş akışı tanımlanıyor ([`943e04f`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/943e04f15b34d38784e9a12322b096e3f569ae13))

* Satınalma İrsaliyesine ithalat ve etiketleme geliştirmelerine ait iş akışı tanımlanıyor ([`db9e081`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/db9e0816acc206cf2538d701d9755191f6cbaf7a))

* Satınalma İrsaliyesine ithalat ve etiketleme geliştirmelerine ait iş akışı tanımlanıyor ([`a6bb104`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/a6bb104480748c9c7b4bcd193eb70ee4d4435c85))

* Kalite 8D formu eklendi ([`a5d64ae`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/a5d64aec998c0ee6815b71ef57d14150a6ddf41b))

* Kalite Kontrolüne Borkod Kontrolü alanı eklendı ([`8481510`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/8481510dc5e9c604411e562b1e444493d301666f))

* Ürün Kalite Kontrol Parametreleri ek alanı Ölçü Metodu eklendi ([`e64044e`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/e64044e65878ce5399d9cc572d2a60b8c669b4c5))

* kalite için Ölçü Metodu DocType tanımlandı ([`069bfd3`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/069bfd3329ee2b165382f94ec9177bd373a90671))

* Ürün Müşteri Detayı üzerinde Referans Açıklaması alanı açıldı, Ürün Tedarikçisi üzerinde Tedarikçi Parça Açıklaması alanı açıldı ([`98950fa`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/98950fa0514aa2fdc480c3a2f0b26698279d0540))

* Ürün Ağacı üzerinde Müşteri İndeksi alanı açıldı ([`5912667`](https://github.com/KTA-Endustri-Sistemleri/erpnextkta/commit/59126676afcf2e5666bf2533ce2a5e7b6f7aa5cd))
