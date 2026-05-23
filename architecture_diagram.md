# Project Architecture Diagram (High-level)

```mermaid
flowchart LR
    U[User] -->|1. Lead Form| UI[Streamlit UI]
    U -->|2. Chat Question| UI

    UI -->|3. Save Lead| DB[(SQLite: leads.db)]
    UI -->|4. Automation workflow| AUTO[Automation Logic]
    AUTO -->|5. Generate auto reply (Gemini if enabled, else free responder)| AI[AI Responder (Gemini optional → fallback)]
    AUTO -->|6. Update lead status + chatbot reply| DB

    UI -->|7. Admin Dashboard| ADMIN[Admin/Dashboard view]

    ADMIN -->|8. Read leads| DB

    UI -->|9. Chat responses| AI
```

## Modules
- Streamlit UI (`app.py`)
- Persistence (`sqlite3` + table `leads`)
- Automation workflow (form submit triggers status update + AI preview)
- AI responder (free built-in knowledge-based responder; can be swapped with OpenAI/Gemini later)
- Admin dashboard (table + filters)

