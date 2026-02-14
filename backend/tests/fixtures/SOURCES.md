# Fixture Provenance

- 5-minute and 30-minute fixture structures are aligned to AEMO MDFF NEM12/NEM13 v2.7 sample record shapes (Appendix H.9 and H.1):
  https://www.aemo.com.au/-/media/files/electricity/nem/retail_and_metering/market_settlement_and_transfer_solutions/2025/mdff-specification-nem12-nem13-v27.pdf?rev=9d9baf6940594142a691f75b13433779&sc_lang=en
- 15-minute fixture structure is aligned to AEMO NEM12/NEM13 file testing guidance (scenario-based interval changes):
  https://www.aemo.com.au/-/media/files/electricity/nem/retail_and_metering/metering-procedures/2017/nem12-and-nem13-file-testing.pdf?rev=83be0855c2434eff8def34b801602c54&sc_lang=en

Notes:
- Values are synthetic for deterministic test assertions.
- Record types and interval counts per day are real-format compatible: 5m=288, 15m=96, 30m=48.
