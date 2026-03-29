# State Portal Configurations

**CRITICAL**: These configurations drive automated LLC formation filing. Incorrect data results in failed filings, wrong charges, or compliance issues.

## Data Quality Requirements

### Before Modifying ANY Config:

1. **Verify against official source** - Only use .gov or official state SOS websites
2. **Document the source URL** in the config's `notes` field
3. **Update `lastVerified`** timestamp
4. **Run validation tests**: `pnpm --filter @paperwork-labs/filing-engine test:validate`
5. **Log changes** in `docs/KNOWLEDGE.md` with date and source

### Official Sources (Bookmark These)

| State | Official Portal | Fee Schedule |
|-------|-----------------|--------------|
| CA | https://bizfileservices.sos.ca.gov | On portal |
| TX | https://direct.sos.state.tx.us | https://www.sos.state.tx.us/corp/forms/806_boc.pdf |
| FL | https://efile.sunbiz.org | https://dos.fl.gov/sunbiz/forms/fees/ |
| DE | https://icis.corp.delaware.gov/ecorp2 | https://corp.delaware.gov/fee.shtml |
| WY | https://wyobiz.wyo.gov | https://sos.wyo.gov/Business/docs/BusinessFees.pdf |
| NY | https://www.businessexpress.ny.gov | https://dos.ny.gov/fee-schedules |
| NV | https://www.nvsilverflume.gov | https://www.nvsos.gov/businesses/commercial-recordings/forms-fees |
| IL | https://www.ilsos.gov | On portal |
| GA | https://ecorp.sos.ga.gov | https://sos.ga.gov/corporations-division |
| WA | https://ccfs.sos.wa.gov | https://apps.sos.wa.gov/corps/feescheduleexpeditedservice.aspx |

### Fee Breakdown Notes

- **CA**: $70 standard, $350 expedited (24-hour)
- **TX**: $300 (Certificate of Formation, not Articles)
- **FL**: $125 total = $100 filing + $25 RA designation
- **DE**: $90 standard, expedited tiers: $50 next-day, $100-200 same-day, $500 2-hour, $1000 1-hour
- **WY**: $100 (online processing typically same-day)
- **NY**: $200 standard, expedited: $25 (24hr), $75 (same-day), $150 (2hr)
- **NV**: $425 total = $75 Articles + $150 Initial List + $200 Business License
- **IL**: $150 standard, $250 total for 24-hour expedited
- **GA**: $100 online ($110 mail), expedited: +$100 (2-day), +$250 (same-day), +$1000 (1-hour)
- **WA**: $180 + online processing fee, expedited: +$100 (~3 days)

### State-Specific Compliance Notes

- **NY**: REQUIRES publication in 2 newspapers in county of principal office within 120 days
- **WA**: Email addresses REQUIRED for RA and Principal Office (as of Jan 2026)
- **NV**: THREE filings required together (Articles, Initial List, Business License)
- **TX**: Uses "Certificate of Formation" not "Articles of Organization"
- **DE**: Separate $300/year franchise tax (due June 1)

## Selector Verification Process

Selectors are placeholders until verified against live portals. Before production use:

1. **Manual inspection**: Open each portal in browser, inspect form elements
2. **Update selectors** with actual IDs, names, or ARIA labels found
3. **Add fallback selectors** for resilience (ID > name > aria-label > CSS class)
4. **Document changes** with portal inspection date

## Automated Validation

```bash
# Run all critical validations (fees + URLs)
pnpm --filter @paperwork-labs/filing-engine test:validate

# Run just fee accuracy tests
pnpm --filter @paperwork-labs/filing-engine test:fees

# Run just URL validation tests
pnpm --filter @paperwork-labs/filing-engine test:urls

# Run full test suite
pnpm --filter @paperwork-labs/filing-engine test
```

## Change Log Template

When updating a config, add to `docs/KNOWLEDGE.md`:

```markdown
### Portal Config Update: {STATE} ({DATE})

**Source**: {OFFICIAL_URL}
**Change**: {WHAT_CHANGED}
**Verified by**: {YOUR_NAME}
**Test command**: `pnpm --filter @paperwork-labs/filing-engine test:validate`
```

## Red Flags (Reject PR If)

- [ ] Fee changed without source documentation
- [ ] Portal URL not a .gov domain
- [ ] `lastVerified` older than 90 days
- [ ] No fallback selectors on critical fields
- [ ] Missing state-specific compliance notes (NY publication, NV triple filing, etc.)
