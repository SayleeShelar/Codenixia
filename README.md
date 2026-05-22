# AI-Powered Business Automation Assistant (Streamlit)

This is a practical assessment project implementing:
- AI Assistant / Chatbot (with a free/no-key fallback)
- Lead Capture System (form)
- Data Storage (SQLite)
- Automation Workflow (on form submit + chatbot)
- Admin/Dashboard view

## Features
- `/` Lead form + Chatbot
- `/admin` Admin dashboard (leads table)
- Stores submissions in `data/leads.db`

## Tech Stack
- Python
- Streamlit
- SQLite

## Run Locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deployment (recommended)
- **Streamlit Community Cloud**: connect GitHub repo, set entry `app.py`
- For public deployment, ensure the environment can write to a persistent volume if needed (SQLite works best when backed by platform storage).

## Notes about “free AI”
This project includes a **fallback AI responder** that works without an API key. If you later add an LLM API key, you can replace the responder module.

## Demo checklist (5–7 minutes)
1. Open app, show Lead Capture form
2. Submit a sample lead; show it appears in Admin page
3. Show chatbot answering a business/course query
4. Show automation behavior (auto acknowledgment / auto response)
5. Briefly explain architecture + modules

