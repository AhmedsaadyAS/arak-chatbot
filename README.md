# 🤖 Arak AI Chatbot

An intelligent assistant for the **Arak School Admin System**, designed to handle academic queries, student performance tracking, and administrative tasks using Natural Language Processing (NLP).

## 🚀 Overview

The Arak Chatbot is a FastAPI-based microservice that integrates with the main Arak Backend (ASP.NET Core). It uses an intent classification pipeline to understand user requests and provides automated responses for:
- **Attendance Tracking:** Querying daily and historical attendance by class or student.
- **Academic Performance:** Retrieving student grades and calculating averages.
- **Schedules:** Fetching class timetables and teacher assignments.

## 🛠 Tech Stack

- **Framework:** FastAPI (Python 3.9+)
- **NLP:** Custom Intent Classifier (Pipeline-based)
- **API Client:** Httpx (Async HTTP requests)
- **Authentication:** JWT (Bearer Token)
- **Integration:** Integrated with Arak Dashboard (React) and Arak Backend (.NET 9)

## 📁 Project Structure

```text
arak-chatbot/
├── api/                # FastAPI routers and auth middleware
├── data/               # Intent training data and JSON configs
├── models/             # Trained models and classification logic
├── pipeline/           # Data processing and intent classification
├── scripts/            # Utility scripts (token generation, etc.)
├── tests/              # Pytest suite
└── main.py             # Application entry point
```

## ⚙️ Configuration

1. **Environment Variables:**
   Create a `.env` file in the root directory:
   ```env
   ARAK_API_URL=http://localhost:5000/api
   JWT_SECRET_KEY=your_secret_key
   ```

2. **Installation:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Running the Service:**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8001 --reload
   ```

## 🧪 API Endpoints

- `POST /api/chat`: The main entry point for chatbot queries.
  - **Request:** `{ "message": "درجات الطالب 5", "token": "..." }`
  - **Response:** `{ "reply": "...", "intent": "student_grade", "entities": {...} }`

## 🤝 Integration with Arak System

This chatbot is designed to be called by the **Arak Admin Dashboard**. It authenticates using the same JWT tokens issued by the main backend, ensuring secure access to student data based on user roles (Admin, Teacher, Parent).

## 📝 License

Part of the Arak School Management Suite. Created by Ahmed Saady.
