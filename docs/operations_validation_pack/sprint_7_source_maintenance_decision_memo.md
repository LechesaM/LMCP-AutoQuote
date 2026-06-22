# Sprint 7 Source Maintenance Decision Memo

The dominant issue is stale or wrong URLs. The HTTP failure summary shows 88 HTTP 404s, which is the largest failure bucket.

This is not a qualification, governance, audit, or submission-flow issue.

Do not add more sources until the 404 and redirect groups are cleaned.
Do not quarantine sources from one automated result alone.

## Summary Counts

| Action | Count |
| --- | ---: |
| fix_404_url | 0 |
| resolve_redirect | 0 |
| investigate_redirect_loop | 0 |
| investigate_auth | 0 |
| manual_probe_unknown | 235 |
| keep_retry | 0 |
| promote | 1 |

## Recommended Actions

- `fix_404_url`: search/update procurement URL or confirm source is dead; quarantine only after manual confirmation.
- `resolve_redirect`: follow the final URL and update the source if the destination is a valid procurement page.
- `investigate_redirect_loop`: try browser headers/session or a corrected endpoint.
- `investigate_auth`: check whether the public procurement page exists or if the portal requires login.
- `manual_probe_unknown`: test with browser or GET before deciding.
- `keep_retry`: keep enabled, lower priority, and retry later.
- `promote`: keep as a reference producer and monitor as a benchmark source.

## Top 404 Cleanup Candidates

_No sources._

## Redirect Sources

_No sources._

## Redirect Loop Sources

_No sources._

## Authentication Sources

_No sources._

## Unknown HTTP Sources

| Source | Category | URL | Observed Status | Priority | Recommended Next Step |
| --- | --- | --- | --- | ---: | --- |
| Airports Company South Africa | soe | https://www.airports.co.za/ | dns_failed | 5 | Test with browser or GET before deciding. |
| Airports Company South Africa - Archive | soe | https://www.airports.co.za/business/supply-chain-management/current-and-future-tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| Airports Company South Africa - Awards | soe | https://www.airports.co.za/business/supply-chain-management/current-and-future-tenders | duplicate_url | 5 | Test with browser or GET before deciding. |
| Airports Company South Africa - Bidboard | soe | https://www.airports.co.za/business/supply-chain-management/current-and-future-tenders | duplicate_url | 5 | Test with browser or GET before deciding. |
| Airports Company South Africa - Contracts | soe | https://www.airports.co.za/business/supply-chain-management/current-and-future-tenders | duplicate_url | 5 | Test with browser or GET before deciding. |
| Airports Company South Africa - Current Tenders | soe | https://www.airports.co.za/business/supply-chain-management/current-and-future-tenders | duplicate_url | 5 | Test with browser or GET before deciding. |
| Airports Company South Africa - Documents | soe | https://www.airports.co.za/documents | dns_failed | 5 | Test with browser or GET before deciding. |
| Airports Company South Africa - Downloads | soe | https://www.airports.co.za/business/supply-chain-management/current-and-future-tenders | duplicate_url | 5 | Test with browser or GET before deciding. |
| Airports Company South Africa - Notices | soe | https://www.airports.co.za/business/supply-chain-management/current-and-future-tenders | duplicate_url | 5 | Test with browser or GET before deciding. |
| Airports Company South Africa - Opportunities | soe | https://www.airports.co.za/business/supply-chain-management/current-and-future-tenders | duplicate_url | 5 | Test with browser or GET before deciding. |
| Airports Company South Africa - Procurement | soe | https://www.airports.co.za/business/supply-chain-management/current-and-future-tenders | duplicate_url | 5 | Test with browser or GET before deciding. |
| Airports Company South Africa - Procurement Tenders | soe | https://www.airports.co.za/business/supply-chain-management/current-and-future-tenders | duplicate_url | 5 | Test with browser or GET before deciding. |
| Airports Company South Africa - Quote | soe | https://www.airports.co.za/business/supply-chain-management/current-and-future-tenders | duplicate_url | 5 | Test with browser or GET before deciding. |
| Airports Company South Africa - Rfq | soe | https://www.airports.co.za/business/supply-chain-management/current-and-future-tenders | duplicate_url | 5 | Test with browser or GET before deciding. |
| Airports Company South Africa - Supplier Portal | soe | https://www.airports.co.za/business/supply-chain-management/current-and-future-tenders | duplicate_url | 5 | Test with browser or GET before deciding. |
| Airports Company South Africa - Tenders | soe | https://www.airports.co.za/business/supply-chain-management/current-and-future-tenders | duplicate_url | 5 | Test with browser or GET before deciding. |
| Bloem Water | public_entity | https://www.bloemwater.co.za/ | dns_failed | 5 | Test with browser or GET before deciding. |
| Bloem Water - Archive | public_entity | https://vaalcentralwater.co.za/advertised-tenders/ | dns_failed | 5 | Test with browser or GET before deciding. |
| Bloem Water - Awards | public_entity | https://vaalcentralwater.co.za/advertised-tenders/ | duplicate_url | 5 | Test with browser or GET before deciding. |
| Bloem Water - Bidboard | public_entity | https://vaalcentralwater.co.za/advertised-tenders/ | duplicate_url | 5 | Test with browser or GET before deciding. |
| Bloem Water - Contracts | public_entity | https://vaalcentralwater.co.za/advertised-tenders/ | duplicate_url | 5 | Test with browser or GET before deciding. |
| Bloem Water - Current Tenders | public_entity | https://vaalcentralwater.co.za/advertised-tenders/ | duplicate_url | 5 | Test with browser or GET before deciding. |
| Bloem Water - Documents | public_entity | https://vaalcentralwater.co.za/advertised-tenders/ | duplicate_url | 5 | Test with browser or GET before deciding. |
| Bloem Water - Downloads | public_entity | https://vaalcentralwater.co.za/advertised-tenders/ | duplicate_url | 5 | Test with browser or GET before deciding. |
| Bloem Water - Notices | public_entity | https://vaalcentralwater.co.za/advertised-tenders/ | duplicate_url | 5 | Test with browser or GET before deciding. |
| Bloem Water - Opportunities | public_entity | https://vaalcentralwater.co.za/advertised-tenders/ | duplicate_url | 5 | Test with browser or GET before deciding. |
| Bloem Water - Procurement | public_entity | https://vaalcentralwater.co.za/advertised-tenders/ | duplicate_url | 5 | Test with browser or GET before deciding. |
| Bloem Water - Procurement Tenders | public_entity | https://vaalcentralwater.co.za/advertised-tenders/ | duplicate_url | 5 | Test with browser or GET before deciding. |
| Bloem Water - Quote | public_entity | https://vaalcentralwater.co.za/request-for-quotations/ | dns_failed | 5 | Test with browser or GET before deciding. |
| Bloem Water - Rfq | public_entity | https://vaalcentralwater.co.za/request-for-quotations/ | duplicate_url | 5 | Test with browser or GET before deciding. |
| Bloem Water - Supplier Portal | public_entity | https://vaalcentralwater.co.za/request-for-quotations/ | duplicate_url | 5 | Test with browser or GET before deciding. |
| Bloem Water - Tenders | public_entity | https://vaalcentralwater.co.za/advertised-tenders/ | duplicate_url | 5 | Test with browser or GET before deciding. |
| CSD | aggregator | https://secure.csd.gov.za/ | dns_failed | 5 | Test with browser or GET before deciding. |
| CSD - Archive | aggregator | https://secure.csd.gov.za/archive | dns_failed | 5 | Test with browser or GET before deciding. |
| CSD - Awards | aggregator | https://secure.csd.gov.za/awards | dns_failed | 5 | Test with browser or GET before deciding. |
| CSD - Bidboard | aggregator | https://secure.csd.gov.za/bidboard | dns_failed | 5 | Test with browser or GET before deciding. |
| CSD - Contracts | aggregator | https://secure.csd.gov.za/contracts | dns_failed | 5 | Test with browser or GET before deciding. |
| CSD - Current Tenders | aggregator | https://secure.csd.gov.za/tenders/current | dns_failed | 5 | Test with browser or GET before deciding. |
| CSD - Documents | aggregator | https://secure.csd.gov.za/documents | dns_failed | 5 | Test with browser or GET before deciding. |
| CSD - Downloads | aggregator | https://secure.csd.gov.za/downloads | dns_failed | 5 | Test with browser or GET before deciding. |
| CSD - Notices | aggregator | https://secure.csd.gov.za/notices | dns_failed | 5 | Test with browser or GET before deciding. |
| CSD - Opportunities | aggregator | https://secure.csd.gov.za/opportunities | dns_failed | 5 | Test with browser or GET before deciding. |
| CSD - Procurement | aggregator | https://secure.csd.gov.za/procurement | dns_failed | 5 | Test with browser or GET before deciding. |
| CSD - Procurement Tenders | aggregator | https://secure.csd.gov.za/procurement/tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| CSD - Quote | aggregator | https://secure.csd.gov.za/quote | dns_failed | 5 | Test with browser or GET before deciding. |
| CSD - Rfq | aggregator | https://secure.csd.gov.za/rfq | dns_failed | 5 | Test with browser or GET before deciding. |
| CSD - Supplier Portal | aggregator | https://secure.csd.gov.za/supplier-portal | dns_failed | 5 | Test with browser or GET before deciding. |
| CSD - Tenders | aggregator | https://secure.csd.gov.za/tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| DBSA | public_entity | https://www.dbsa.org/ | dns_failed | 5 | Test with browser or GET before deciding. |
| DBSA - Archive | public_entity | https://www.dbsa.org/procurement | dns_failed | 5 | Test with browser or GET before deciding. |
| DBSA - Awards | public_entity | https://www.dbsa.org/awarded-and-cancelled-tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| DBSA - Bidboard | public_entity | https://www.dbsa.org/procurement | duplicate_url | 5 | Test with browser or GET before deciding. |
| DBSA - Contracts | public_entity | https://www.dbsa.org/procurement | duplicate_url | 5 | Test with browser or GET before deciding. |
| DBSA - Current Tenders | public_entity | https://www.dbsa.org/procurement | duplicate_url | 5 | Test with browser or GET before deciding. |
| DBSA - Documents | public_entity | https://www.dbsa.org/procurement | duplicate_url | 5 | Test with browser or GET before deciding. |
| DBSA - Downloads | public_entity | https://www.dbsa.org/procurement | duplicate_url | 5 | Test with browser or GET before deciding. |
| DBSA - Notices | public_entity | https://www.dbsa.org/procurement | duplicate_url | 5 | Test with browser or GET before deciding. |
| DBSA - Opportunities | public_entity | https://www.dbsa.org/procurement | duplicate_url | 5 | Test with browser or GET before deciding. |
| DBSA - Procurement | public_entity | https://www.dbsa.org/procurement | duplicate_url | 5 | Test with browser or GET before deciding. |
| DBSA - Procurement Tenders | public_entity | https://www.dbsa.org/procurement | duplicate_url | 5 | Test with browser or GET before deciding. |
| DBSA - Quote | public_entity | https://www.dbsa.org/procurement | duplicate_url | 5 | Test with browser or GET before deciding. |
| DBSA - Rfq | public_entity | https://www.dbsa.org/rfq | dns_failed | 5 | Test with browser or GET before deciding. |
| DBSA - Supplier Portal | public_entity | https://www.dbsa.org/supplier-portal | dns_failed | 5 | Test with browser or GET before deciding. |
| DBSA - Tenders | public_entity | https://www.dbsa.org/tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| Denel | soe | https://www.denel.co.za/ | dns_failed | 5 | Test with browser or GET before deciding. |
| Denel - Archive | soe | https://www.denel.co.za/archive | dns_failed | 5 | Test with browser or GET before deciding. |
| Denel - Awards | soe | https://www.denel.co.za/awards | dns_failed | 5 | Test with browser or GET before deciding. |
| Denel - Bidboard | soe | https://www.denel.co.za/bidboard | dns_failed | 5 | Test with browser or GET before deciding. |
| Denel - Contracts | soe | https://www.denel.co.za/contracts | dns_failed | 5 | Test with browser or GET before deciding. |
| Denel - Current Tenders | soe | https://www.denel.co.za/tenders/current | dns_failed | 5 | Test with browser or GET before deciding. |
| Denel - Documents | soe | https://www.denel.co.za/documents | dns_failed | 5 | Test with browser or GET before deciding. |
| Denel - Downloads | soe | https://www.denel.co.za/downloads | dns_failed | 5 | Test with browser or GET before deciding. |
| Denel - Notices | soe | https://www.denel.co.za/notices | dns_failed | 5 | Test with browser or GET before deciding. |
| Denel - Opportunities | soe | https://www.denel.co.za/opportunities | dns_failed | 5 | Test with browser or GET before deciding. |
| Denel - Procurement | soe | https://www.denel.co.za/procurement | dns_failed | 5 | Test with browser or GET before deciding. |
| Denel - Procurement Tenders | soe | https://www.denel.co.za/procurement/tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| Denel - Quote | soe | https://www.denel.co.za/quote | dns_failed | 5 | Test with browser or GET before deciding. |
| Denel - Rfq | soe | https://www.denel.co.za/rfq | dns_failed | 5 | Test with browser or GET before deciding. |
| Denel - Supplier Portal | soe | https://www.denel.co.za/supplier-portal | dns_failed | 5 | Test with browser or GET before deciding. |
| Denel - Tenders | soe | https://www.denel.co.za/tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| Eskom | soe | https://www.eskom.co.za/ | dns_failed | 5 | Test with browser or GET before deciding. |
| Eskom - Archive | soe | https://www.eskom.co.za/archive | dns_failed | 5 | Test with browser or GET before deciding. |
| Eskom - Awards | soe | https://www.eskom.co.za/awards | dns_failed | 5 | Test with browser or GET before deciding. |
| Eskom - Bidboard | soe | https://www.eskom.co.za/bidboard | dns_failed | 5 | Test with browser or GET before deciding. |
| Eskom - Contracts | soe | https://www.eskom.co.za/contracts | dns_failed | 5 | Test with browser or GET before deciding. |
| Eskom - Current Tenders | soe | https://www.eskom.co.za/tenders/current | dns_failed | 5 | Test with browser or GET before deciding. |
| Eskom - Documents | soe | https://www.eskom.co.za/documents | dns_failed | 5 | Test with browser or GET before deciding. |
| Eskom - Downloads | soe | https://www.eskom.co.za/downloads | dns_failed | 5 | Test with browser or GET before deciding. |
| Eskom - Notices | soe | https://www.eskom.co.za/notices | dns_failed | 5 | Test with browser or GET before deciding. |
| Eskom - Opportunities | soe | https://www.eskom.co.za/opportunities | dns_failed | 5 | Test with browser or GET before deciding. |
| Eskom - Procurement | soe | https://www.eskom.co.za/procurement | dns_failed | 5 | Test with browser or GET before deciding. |
| Eskom - Procurement Tenders | soe | https://www.eskom.co.za/procurement/tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| Eskom - Quote | soe | https://www.eskom.co.za/quote | dns_failed | 5 | Test with browser or GET before deciding. |
| Eskom - Rfq | soe | https://www.eskom.co.za/rfq | dns_failed | 5 | Test with browser or GET before deciding. |
| Eskom - Supplier Portal | soe | https://www.eskom.co.za/supplier-portal | dns_failed | 5 | Test with browser or GET before deciding. |
| Eskom - Tenders | soe | https://www.eskom.co.za/tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| Lepelle Northern Water | public_entity | https://www.lnw.co.za/ | dns_failed | 5 | Test with browser or GET before deciding. |
| Lepelle Northern Water - Archive | public_entity | https://www.lnw.co.za/archive | dns_failed | 5 | Test with browser or GET before deciding. |
| Lepelle Northern Water - Awards | public_entity | https://www.lnw.co.za/awards | dns_failed | 5 | Test with browser or GET before deciding. |
| Lepelle Northern Water - Bidboard | public_entity | https://www.lnw.co.za/bidboard | dns_failed | 5 | Test with browser or GET before deciding. |
| Lepelle Northern Water - Contracts | public_entity | https://www.lnw.co.za/contracts | dns_failed | 5 | Test with browser or GET before deciding. |
| Lepelle Northern Water - Current Tenders | public_entity | https://www.lnw.co.za/tenders/current | dns_failed | 5 | Test with browser or GET before deciding. |
| Lepelle Northern Water - Documents | public_entity | https://www.lnw.co.za/documents | dns_failed | 5 | Test with browser or GET before deciding. |
| Lepelle Northern Water - Downloads | public_entity | https://www.lnw.co.za/downloads | dns_failed | 5 | Test with browser or GET before deciding. |
| Lepelle Northern Water - Notices | public_entity | https://www.lnw.co.za/notices | dns_failed | 5 | Test with browser or GET before deciding. |
| Lepelle Northern Water - Opportunities | public_entity | https://www.lnw.co.za/opportunities | dns_failed | 5 | Test with browser or GET before deciding. |
| Lepelle Northern Water - Procurement | public_entity | https://www.lnw.co.za/procurement | dns_failed | 5 | Test with browser or GET before deciding. |
| Lepelle Northern Water - Procurement Tenders | public_entity | https://www.lnw.co.za/procurement/tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| Lepelle Northern Water - Quote | public_entity | https://www.lnw.co.za/quote | dns_failed | 5 | Test with browser or GET before deciding. |
| Lepelle Northern Water - Rfq | public_entity | https://www.lnw.co.za/rfq | dns_failed | 5 | Test with browser or GET before deciding. |
| Lepelle Northern Water - Supplier Portal | public_entity | https://www.lnw.co.za/supplier-portal | dns_failed | 5 | Test with browser or GET before deciding. |
| Lepelle Northern Water - Tenders | public_entity | https://www.lnw.co.za/tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| Magalies Water | public_entity | https://www.magalieswater.co.za/ | dns_failed | 5 | Test with browser or GET before deciding. |
| Magalies Water - Archive | public_entity | https://www.magalieswater.co.za/archive | dns_failed | 5 | Test with browser or GET before deciding. |
| Magalies Water - Awards | public_entity | https://www.magalieswater.co.za/awards | dns_failed | 5 | Test with browser or GET before deciding. |
| Magalies Water - Bidboard | public_entity | https://www.magalieswater.co.za/bidboard | dns_failed | 5 | Test with browser or GET before deciding. |
| Magalies Water - Contracts | public_entity | https://www.magalieswater.co.za/contracts | dns_failed | 5 | Test with browser or GET before deciding. |
| Magalies Water - Current Tenders | public_entity | https://www.magalieswater.co.za/tenders/current | dns_failed | 5 | Test with browser or GET before deciding. |
| Magalies Water - Documents | public_entity | https://www.magalieswater.co.za/documents | dns_failed | 5 | Test with browser or GET before deciding. |
| Magalies Water - Downloads | public_entity | https://www.magalieswater.co.za/downloads | dns_failed | 5 | Test with browser or GET before deciding. |
| Magalies Water - Notices | public_entity | https://www.magalieswater.co.za/notices | dns_failed | 5 | Test with browser or GET before deciding. |
| Magalies Water - Opportunities | public_entity | https://www.magalieswater.co.za/opportunities | dns_failed | 5 | Test with browser or GET before deciding. |
| Magalies Water - Procurement | public_entity | https://www.magalieswater.co.za/procurement | dns_failed | 5 | Test with browser or GET before deciding. |
| Magalies Water - Procurement Tenders | public_entity | https://www.magalieswater.co.za/procurement/tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| Magalies Water - Quote | public_entity | https://www.magalieswater.co.za/quote | dns_failed | 5 | Test with browser or GET before deciding. |
| Magalies Water - Rfq | public_entity | https://www.magalieswater.co.za/rfq | dns_failed | 5 | Test with browser or GET before deciding. |
| Magalies Water - Supplier Portal | public_entity | https://www.magalieswater.co.za/supplier-portal | dns_failed | 5 | Test with browser or GET before deciding. |
| Magalies Water - Tenders | public_entity | https://www.magalieswater.co.za/tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| National Treasury eTenders - Archive | aggregator | https://www.etenders.gov.za/archive | dns_failed | 5 | Test with browser or GET before deciding. |
| National Treasury eTenders - Awards | aggregator | https://www.etenders.gov.za/awards | dns_failed | 5 | Test with browser or GET before deciding. |
| National Treasury eTenders - Bidboard | aggregator | https://www.etenders.gov.za/bidboard | dns_failed | 5 | Test with browser or GET before deciding. |
| National Treasury eTenders - Contracts | aggregator | https://www.etenders.gov.za/contracts | dns_failed | 5 | Test with browser or GET before deciding. |
| National Treasury eTenders - Current Tenders | aggregator | https://www.etenders.gov.za/tenders/current | dns_failed | 5 | Test with browser or GET before deciding. |
| National Treasury eTenders - Documents | aggregator | https://www.etenders.gov.za/documents | dns_failed | 5 | Test with browser or GET before deciding. |
| National Treasury eTenders - Downloads | aggregator | https://www.etenders.gov.za/downloads | dns_failed | 5 | Test with browser or GET before deciding. |
| National Treasury eTenders - Notices | aggregator | https://www.etenders.gov.za/notices | dns_failed | 5 | Test with browser or GET before deciding. |
| National Treasury eTenders - Opportunities | aggregator | https://www.etenders.gov.za/opportunities | dns_failed | 5 | Test with browser or GET before deciding. |
| National Treasury eTenders - Procurement | aggregator | https://www.etenders.gov.za/procurement | dns_failed | 5 | Test with browser or GET before deciding. |
| National Treasury eTenders - Procurement Tenders | aggregator | https://www.etenders.gov.za/procurement/tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| National Treasury eTenders - Quote | aggregator | https://www.etenders.gov.za/quote | dns_failed | 5 | Test with browser or GET before deciding. |
| National Treasury eTenders - Rfq | aggregator | https://www.etenders.gov.za/rfq | dns_failed | 5 | Test with browser or GET before deciding. |
| National Treasury eTenders - Supplier Portal | aggregator | https://www.etenders.gov.za/supplier-portal | dns_failed | 5 | Test with browser or GET before deciding. |
| National Treasury eTenders - Tenders | aggregator | https://www.etenders.gov.za/tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| NECSA | soe | https://www.necsa.co.za/ | dns_failed | 5 | Test with browser or GET before deciding. |
| NECSA - Archive | soe | https://www.necsa.co.za/archive | dns_failed | 5 | Test with browser or GET before deciding. |
| NECSA - Awards | soe | https://www.necsa.co.za/awards | dns_failed | 5 | Test with browser or GET before deciding. |
| NECSA - Bidboard | soe | https://www.necsa.co.za/bidboard | dns_failed | 5 | Test with browser or GET before deciding. |
| NECSA - Contracts | soe | https://www.necsa.co.za/contracts | dns_failed | 5 | Test with browser or GET before deciding. |
| NECSA - Current Tenders | soe | https://www.necsa.co.za/tenders/current | dns_failed | 5 | Test with browser or GET before deciding. |
| NECSA - Documents | soe | https://www.necsa.co.za/documents | dns_failed | 5 | Test with browser or GET before deciding. |
| NECSA - Downloads | soe | https://www.necsa.co.za/downloads | dns_failed | 5 | Test with browser or GET before deciding. |
| NECSA - Notices | soe | https://www.necsa.co.za/notices | dns_failed | 5 | Test with browser or GET before deciding. |
| NECSA - Opportunities | soe | https://www.necsa.co.za/opportunities | dns_failed | 5 | Test with browser or GET before deciding. |
| NECSA - Procurement | soe | https://www.necsa.co.za/procurement | dns_failed | 5 | Test with browser or GET before deciding. |
| NECSA - Procurement Tenders | soe | https://www.necsa.co.za/procurement/tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| NECSA - Quote | soe | https://www.necsa.co.za/quote | dns_failed | 5 | Test with browser or GET before deciding. |
| NECSA - Rfq | soe | https://www.necsa.co.za/rfq | dns_failed | 5 | Test with browser or GET before deciding. |
| NECSA - Supplier Portal | soe | https://www.necsa.co.za/supplier-portal | dns_failed | 5 | Test with browser or GET before deciding. |
| NECSA - Tenders | soe | https://www.necsa.co.za/tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| PRASA | soe | https://www.prasa.com/ | dns_failed | 5 | Test with browser or GET before deciding. |
| PRASA - Archive | soe | https://www.prasa.com/archive | dns_failed | 5 | Test with browser or GET before deciding. |
| PRASA - Awards | soe | https://www.prasa.com/awards | dns_failed | 5 | Test with browser or GET before deciding. |
| PRASA - Bidboard | soe | https://www.prasa.com/bidboard | dns_failed | 5 | Test with browser or GET before deciding. |
| PRASA - Contracts | soe | https://www.prasa.com/contracts | dns_failed | 5 | Test with browser or GET before deciding. |
| PRASA - Current Tenders | soe | https://www.prasa.com/tenders/current | dns_failed | 5 | Test with browser or GET before deciding. |
| PRASA - Documents | soe | https://www.prasa.com/documents | dns_failed | 5 | Test with browser or GET before deciding. |
| PRASA - Downloads | soe | https://www.prasa.com/downloads | dns_failed | 5 | Test with browser or GET before deciding. |
| PRASA - Notices | soe | https://www.prasa.com/notices | dns_failed | 5 | Test with browser or GET before deciding. |
| PRASA - Opportunities | soe | https://www.prasa.com/opportunities | dns_failed | 5 | Test with browser or GET before deciding. |
| PRASA - Procurement | soe | https://www.prasa.com/procurement | dns_failed | 5 | Test with browser or GET before deciding. |
| PRASA - Procurement Tenders | soe | https://www.prasa.com/procurement/tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| PRASA - Quote | soe | https://www.prasa.com/quote | dns_failed | 5 | Test with browser or GET before deciding. |
| PRASA - Rfq | soe | https://www.prasa.com/rfq | dns_failed | 5 | Test with browser or GET before deciding. |
| PRASA - Supplier Portal | soe | https://www.prasa.com/supplier-portal | dns_failed | 5 | Test with browser or GET before deciding. |
| PRASA - Tenders | soe | https://www.prasa.com/tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| Rand Water | public_entity | https://www.randwater.co.za/ | dns_failed | 5 | Test with browser or GET before deciding. |
| Rand Water - Archive | public_entity | https://www.randwater.co.za/archive | dns_failed | 5 | Test with browser or GET before deciding. |
| Rand Water - Awards | public_entity | https://www.randwater.co.za/awards | dns_failed | 5 | Test with browser or GET before deciding. |
| Rand Water - Bidboard | public_entity | https://www.randwater.co.za/bidboard | dns_failed | 5 | Test with browser or GET before deciding. |
| Rand Water - Contracts | public_entity | https://www.randwater.co.za/contracts | dns_failed | 5 | Test with browser or GET before deciding. |
| Rand Water - Current Tenders | public_entity | https://www.randwater.co.za/tenders/current | dns_failed | 5 | Test with browser or GET before deciding. |
| Rand Water - Documents | public_entity | https://www.randwater.co.za/documents | dns_failed | 5 | Test with browser or GET before deciding. |
| Rand Water - Downloads | public_entity | https://www.randwater.co.za/downloads | dns_failed | 5 | Test with browser or GET before deciding. |
| Rand Water - Notices | public_entity | https://www.randwater.co.za/notices | dns_failed | 5 | Test with browser or GET before deciding. |
| Rand Water - Opportunities | public_entity | https://www.randwater.co.za/opportunities | dns_failed | 5 | Test with browser or GET before deciding. |
| Rand Water - Procurement | public_entity | https://www.randwater.co.za/procurement | dns_failed | 5 | Test with browser or GET before deciding. |
| Rand Water - Procurement Tenders | public_entity | https://www.randwater.co.za/procurement/tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| SAA | soe | https://www.flysaa.com/ | dns_failed | 5 | Test with browser or GET before deciding. |
| SAA - Archive | soe | https://www.flysaa.com/archive | dns_failed | 5 | Test with browser or GET before deciding. |
| SAA - Awards | soe | https://www.flysaa.com/awards | dns_failed | 5 | Test with browser or GET before deciding. |
| SAA - Bidboard | soe | https://www.flysaa.com/bidboard | dns_failed | 5 | Test with browser or GET before deciding. |
| SAA - Contracts | soe | https://www.flysaa.com/contracts | dns_failed | 5 | Test with browser or GET before deciding. |
| SAA - Current Tenders | soe | https://www.flysaa.com/tenders/current | dns_failed | 5 | Test with browser or GET before deciding. |
| SAA - Documents | soe | https://www.flysaa.com/documents | dns_failed | 5 | Test with browser or GET before deciding. |
| SAA - Downloads | soe | https://www.flysaa.com/downloads | dns_failed | 5 | Test with browser or GET before deciding. |
| SAA - Notices | soe | https://www.flysaa.com/notices | dns_failed | 5 | Test with browser or GET before deciding. |
| SAA - Opportunities | soe | https://www.flysaa.com/opportunities | dns_failed | 5 | Test with browser or GET before deciding. |
| SAA - Procurement | soe | https://www.flysaa.com/procurement | dns_failed | 5 | Test with browser or GET before deciding. |
| SAA - Procurement Tenders | soe | https://www.flysaa.com/procurement/tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| SAA - Quote | soe | https://www.flysaa.com/quote | dns_failed | 5 | Test with browser or GET before deciding. |
| SAA - Rfq | soe | https://www.flysaa.com/rfq | dns_failed | 5 | Test with browser or GET before deciding. |
| SAA - Supplier Portal | soe | https://www.flysaa.com/supplier-portal | dns_failed | 5 | Test with browser or GET before deciding. |
| SAA - Tenders | soe | https://www.flysaa.com/tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| SANRAL | soe | https://www.nra.co.za/ | dns_failed | 5 | Test with browser or GET before deciding. |
| SANRAL - Archive | soe | https://www.nra.co.za/archive | dns_failed | 5 | Test with browser or GET before deciding. |
| SANRAL - Awards | soe | https://www.nra.co.za/awards | dns_failed | 5 | Test with browser or GET before deciding. |
| SANRAL - Bidboard | soe | https://www.nra.co.za/bidboard | dns_failed | 5 | Test with browser or GET before deciding. |
| SANRAL - Contracts | soe | https://www.nra.co.za/contracts | dns_failed | 5 | Test with browser or GET before deciding. |
| SANRAL - Current Tenders | soe | https://www.nra.co.za/tenders/current | dns_failed | 5 | Test with browser or GET before deciding. |
| SANRAL - Documents | soe | https://www.nra.co.za/documents | dns_failed | 5 | Test with browser or GET before deciding. |
| SANRAL - Downloads | soe | https://www.nra.co.za/downloads | dns_failed | 5 | Test with browser or GET before deciding. |
| SANRAL - Notices | soe | https://www.nra.co.za/notices | dns_failed | 5 | Test with browser or GET before deciding. |
| SANRAL - Opportunities | soe | https://www.nra.co.za/opportunities | dns_failed | 5 | Test with browser or GET before deciding. |
| SANRAL - Procurement | soe | https://www.nra.co.za/procurement | dns_failed | 5 | Test with browser or GET before deciding. |
| SANRAL - Procurement Tenders | soe | https://www.nra.co.za/procurement/tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| SANRAL - Quote | soe | https://www.nra.co.za/quote | dns_failed | 5 | Test with browser or GET before deciding. |
| SANRAL - Rfq | soe | https://www.nra.co.za/rfq | dns_failed | 5 | Test with browser or GET before deciding. |
| SANRAL - Supplier Portal | soe | https://www.nra.co.za/supplier-portal | dns_failed | 5 | Test with browser or GET before deciding. |
| SANRAL - Tenders | soe | https://www.nra.co.za/tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| Transnet | soe | https://www.transnet.net/ | dns_failed | 5 | Test with browser or GET before deciding. |
| Transnet - Archive | soe | https://www.transnet.net/archive | dns_failed | 5 | Test with browser or GET before deciding. |
| Transnet - Awards | soe | https://www.transnet.net/awards | dns_failed | 5 | Test with browser or GET before deciding. |
| Transnet - Bidboard | soe | https://www.transnet.net/bidboard | dns_failed | 5 | Test with browser or GET before deciding. |
| Transnet - Contracts | soe | https://www.transnet.net/contracts | dns_failed | 5 | Test with browser or GET before deciding. |
| Transnet - Current Tenders | soe | https://www.transnet.net/tenders/current | dns_failed | 5 | Test with browser or GET before deciding. |
| Transnet - Documents | soe | https://www.transnet.net/documents | dns_failed | 5 | Test with browser or GET before deciding. |
| Transnet - Downloads | soe | https://www.transnet.net/downloads | dns_failed | 5 | Test with browser or GET before deciding. |
| Transnet - Notices | soe | https://www.transnet.net/notices | dns_failed | 5 | Test with browser or GET before deciding. |
| Transnet - Opportunities | soe | https://www.transnet.net/opportunities | dns_failed | 5 | Test with browser or GET before deciding. |
| Transnet - Procurement | soe | https://www.transnet.net/procurement | dns_failed | 5 | Test with browser or GET before deciding. |
| Transnet - Procurement Tenders | soe | https://www.transnet.net/procurement/tenders | dns_failed | 5 | Test with browser or GET before deciding. |
| Transnet - Quote | soe | https://www.transnet.net/quote | dns_failed | 5 | Test with browser or GET before deciding. |
| Transnet - Rfq | soe | https://www.transnet.net/rfq | dns_failed | 5 | Test with browser or GET before deciding. |
| Transnet - Supplier Portal | soe | https://www.transnet.net/supplier-portal | dns_failed | 5 | Test with browser or GET before deciding. |
| Transnet - Tenders | soe | https://www.transnet.net/tenders | dns_failed | 5 | Test with browser or GET before deciding. |

## Retry Sources

_No sources._

## Promote Sources

| Source | Category | URL | Observed Status | Priority | Recommended Next Step |
| --- | --- | --- | --- | ---: | --- |
| National Treasury eTenders | aggregator | https://www.etenders.gov.za/ | dns_failed | 7 | Keep as a reference producer and monitor as a benchmark source. |

No source was disabled by this action list.
