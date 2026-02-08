# expensify-os

**Status**: active
**Last Updated**: 2026-02-08
**Progress**: Core architecture built, plugins in development

## Current Focus

Automated expense management CLI — fetches invoices from multiple sources (Anthropic, OpenAI, Vodafone), downloads PDF receipts, submits to Expensify via Integration API. Designed for monthly n8n scheduling.

## Completed

- [x] Plugin architecture with registry pattern
- [x] Expensify Integration API client with rate limiting
- [x] Playwright browser automation for invoice downloads
- [x] 1Password integration for all credentials
- [x] CLI with Click (run, validate, plugins commands)
- [x] Dry-run mode
- [x] Config updated to correct 1Password vault references

## Pending

- [ ] Complete and test Anthropic plugin end-to-end
- [ ] Complete and test OpenAI plugin end-to-end
- [ ] Complete and test Vodafone plugin end-to-end
- [ ] n8n workflow for monthly scheduling with Slack notifications
- [ ] First real monthly expense submission

## Blockers

None.

## Notes

- Uses uv as package manager (Python 3.13+)
- 1Password vault references updated today
