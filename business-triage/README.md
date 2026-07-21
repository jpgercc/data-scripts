# Business triage

n8n workflow to automatically classify and process emails using Gemini, Gmail, Telegram, and Google Sheets

<img width="1287" height="842" alt="Image" src="https://github.com/user-attachments/assets/8698ce55-0475-4b36-9e3b-ac70bdfcef2b" />

## Fluxo
``` txt
[ Get Messages ] (Filter unread messages in the 'n8n' label)
➔ ​​[ Sort ] (Sort by date: oldest first)
➔ ​​[ AI API Classify ] (Initial triage via Gemini 2.5)
➔ ​​[ L1 Output Gatekeeper ] (Check Pipe '|' Regex)
│
├── L1 TRUE (Correct format) ➔ [ Switch / Router ]
│                                  ├── urgent ➔ [ Telegram Urgent ] ➔ [ Label n8n-done ]
│                                  ├── unknown ➔ [ Label n8n-unknow ]
│                                  ├── commercial ➔ [ Google Sheets ] ➔ [ Label n8n-done ]
│                                  ├── support ➔ [ AI Draft Generator ] ➔ [ Create Draft ] ➔ [ Label n8n-done ]
│                                  └── FALLBACK ➔ [ Telegram Fallback ] ➔ [ Label n8n-fallback ] ➔ [ Stop Error ]
│
└── L1 FALSE (Invalid format)
        ➔ ​​[ Fallback AI Model ] (Second attempt with Gemini 3.5)
        ➔ ​​[ L2 Output Gatekeeper ] (Validate if text is an accepted category)
        │
        ├── L2 TRUE ➔ (Connect back to the same [ Switch / Router ])
        │
        └── L2 FALSE ➔ [ Telegram Error ] ➔ [ Label n8n-fallback ]
```

<img width="1504" height="737" alt="Image" src="https://github.com/user-attachments/assets/b591df60-061d-4f5e-826b-6fab1654dff0" />

## What it does

- Reads new Gmail messages.
- Categorizes each email as `urgent`, `commercial`, `support`, or `unknown`.
- Sends a Telegram alert for urgent cases.
- Logs commercial leads in a spreadsheet.
- Generates a draft response for support cases.
- Marks processed emails with Gmail labels.

## Setup

1. Import the `.json` file into n8n.
2. Reconfigure/link the credentials in your instance.