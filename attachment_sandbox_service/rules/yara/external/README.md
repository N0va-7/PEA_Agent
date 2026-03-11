Curated external YARA rules for attachment scanning.

Selection policy:
- `reversinglabs/`: high-confidence known-malware family rules for Windows and .NET payloads commonly delivered via attachments.
- `yara_rules/maldocs/`: document exploit rules relevant to Office/RTF attachments.

Excluded on purpose:
- EML-specific rules
- broad PDF heuristic packs with high false-positive risk
- Linux-focused malware families that do not fit the email-attachment priority

Upstream sources:
- ReversingLabs: https://github.com/reversinglabs/reversinglabs-yara-rules
- Yara-Rules maldocs: https://github.com/Yara-Rules/rules/tree/master/maldocs
