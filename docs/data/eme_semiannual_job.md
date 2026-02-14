# EME Semiannual Refresh Job

## Endpoint
`POST /api/energy-plans/fetch-eme-all-retailers`

Use this endpoint to:
- parse retailer names from EME dropdown HTML
- fetch detailed plans for resolved retailer slugs
- persist plan catalog to `retail_plans.json`
- optionally refresh DB catalogs

## Recommended cadence
- every 6 months
- EventBridge cron: `cron(0 2 1 1,7 ? *)`

## Example payload
```json
{
  "dropdown_html": "<ul>...retailer list html...</ul>",
  "source_url": "https://www.energymadeeasy.gov.au/plans/electricity/current-energy-company",
  "page_size": 20,
  "max_plans_per_retailer": 100,
  "fuel_type": "ELECTRICITY",
  "timeout_seconds": 30,
  "persist_to_retail_catalog": true,
  "refresh_db_after_persist": true
}
```

## Notes
- The CDR `x-v` header is mandatory for source API calls.
- Some retailer names may not map directly to CDR base-URI slugs.
- Response includes `resolved_retailers` and `unresolved_retailers` to support follow-up mapping maintenance.
