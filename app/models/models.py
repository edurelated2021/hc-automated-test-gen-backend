
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None

class TestCase(BaseModel):
    testCaseId: str = Field(..., alias="testCaseId")
    title: str
    description: str
    testSteps: List[str]
    expectedResults: str
    priority: str

class JiraRequest(BaseModel):
    jiraBaseUrl: str
    storyNumber: str

class FollowUpAnswers(BaseModel):
    answers: Dict[str, str]

class AdminSettings(BaseModel):
    geminiApiKey: str = ""
    jiraToken: str = ""
    maxTestCases: int = 10
    enableFollowUpQuestions: bool = True

class UserInfo(BaseModel):
    username: str
    login_time: Any

class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str
