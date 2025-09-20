
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import json
import logging
from datetime import datetime, timedelta
import uuid

from app.services.auth_service import AuthService
from app.services.pdf_service import PDFService
from app.services.jira_service import JiraService
from app.services.llm_service import LLMService
from app.models.models import (
    LoginRequest, LoginResponse, TestCase, JiraRequest,
    FollowUpAnswers, AdminSettings, UserInfo, LogEntry
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Healthcare Test Case Generator", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Services
auth_service = AuthService()
pdf_service = PDFService()
jira_service = JiraService()
llm_service = LLMService()

# In-memory storage for demo (replace with database in production)
user_sessions = {}
follow_up_contexts = {}
system_logs = []
admin_settings = {
    "geminiApiKey": "",
    "jiraToken": "",
    "maxTestCases": 10,
    "enableFollowUpQuestions": True
}

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    if token not in user_sessions:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_sessions[token]

def log_activity(level: str, message: str):
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level,
        "message": message
    }
    system_logs.append(log_entry)
    logger.info(f"{level}: {message}")

@app.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    try:
        if auth_service.authenticate(request.username, request.password):
            token = str(uuid.uuid4())
            user_sessions[token] = {
                "username": request.username,
                "login_time": datetime.now()
            }
            log_activity("INFO", f"User {request.username} logged in successfully")
            return LoginResponse(success=True, token=token)
        else:
            log_activity("WARN", f"Failed login attempt for user {request.username}")
            raise HTTPException(status_code=401, detail="Invalid credentials")
    except Exception as e:
        log_activity("ERROR", f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")

@app.post("/testcases/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    try:
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        # Save uploaded file
        file_path = f"uploads/{file.filename}"
        os.makedirs("uploads", exist_ok=True)
        
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Extract text from PDF
        extracted_text = pdf_service.extract_text(file_path)
        log_activity("INFO", f"PDF text extracted for file: {file.filename}")
        
        # Generate test cases with LLM
        result = await llm_service.generate_test_cases(
            extracted_text, 
            admin_settings["maxTestCases"],
            admin_settings["enableFollowUpQuestions"]
        )
        
        if result.get("followUpQuestions"):
            # Store context for follow-up
            context_id = str(uuid.uuid4())
            follow_up_contexts[context_id] = {
                "original_text": extracted_text,
                "questions": result["followUpQuestions"],
                "user": current_user["username"]
            }
            return {
                "followUpQuestions": result["followUpQuestions"],
                "contextId": context_id
            }
        else:
            log_activity("INFO", f"Generated {len(result['testCases'])} test cases from PDF")
            return {"testCases": result["testCases"]}
            
    except Exception as e:
        log_activity("ERROR", f"File upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")

@app.post("/testcases/jira")
async def fetch_jira_story(
    request: JiraRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        # Fetch story from Jira
        story_data = jira_service.fetch_story(
            request.jiraBaseUrl, 
            request.storyNumber,
            admin_settings["jiraToken"]
        )
        log_activity("INFO", f"Jira story {request.storyNumber} fetched successfully")
        
        # Generate test cases with LLM
        result = await llm_service.generate_test_cases(
            story_data,
            admin_settings["maxTestCases"],
            admin_settings["enableFollowUpQuestions"]
        )
        
        if result.get("followUpQuestions"):
            # Store context for follow-up
            context_id = str(uuid.uuid4())
            follow_up_contexts[context_id] = {
                "original_text": story_data,
                "questions": result["followUpQuestions"],
                "user": current_user["username"]
            }
            return {
                "followUpQuestions": result["followUpQuestions"],
                "contextId": context_id
            }
        else:
            log_activity("INFO", f"Generated {len(result['testCases'])} test cases from Jira story")
            return {"testCases": result["testCases"]}
            
    except Exception as e:
        log_activity("ERROR", f"Jira fetch error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch Jira story: {str(e)}")

@app.post("/testcases/answers")
async def submit_answers(
    request: FollowUpAnswers,
    current_user: dict = Depends(get_current_user)
):
    try:
        # Find the context (simplified - in production, pass contextId)
        context = None
        for ctx_id, ctx_data in follow_up_contexts.items():
            if ctx_data["user"] == current_user["username"]:
                context = ctx_data
                break
        
        if not context:
            raise HTTPException(status_code=404, detail="Context not found")
        
        # Generate refined test cases
        result = await llm_service.generate_refined_test_cases(
            context["original_text"],
            context["questions"],
            request.answers,
            admin_settings["maxTestCases"]
        )
        
        log_activity("INFO", f"Generated refined test cases with user answers")
        return {"testCases": result["testCases"]}
        
    except Exception as e:
        log_activity("ERROR", f"Answer submission error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process answers: {str(e)}")

@app.get("/admin/users")
async def get_users(current_user: dict = Depends(get_current_user)):
    # Mock user data
    users = [
        {
            "username": "admin",
            "role": "Administrator",
            "lastLogin": "2024-01-15 10:30:00",
            "status": "active"
        }
    ]
    return users

@app.get("/admin/logs")
async def get_logs(current_user: dict = Depends(get_current_user)):
    return system_logs[-100:]  # Return last 100 logs

@app.get("/admin/settings")
async def get_settings(current_user: dict = Depends(get_current_user)):
    return admin_settings

@app.put("/admin/settings")
async def update_settings(
    settings: AdminSettings,
    current_user: dict = Depends(get_current_user)
):
    global admin_settings
    admin_settings.update(settings.dict())
    log_activity("INFO", f"Admin settings updated by {current_user['username']}")
    return {"success": True}

@app.delete("/admin/logs")
async def clear_logs(current_user: dict = Depends(get_current_user)):
    global system_logs
    system_logs.clear()
    log_activity("INFO", f"System logs cleared by {current_user['username']}")
    return {"success": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
