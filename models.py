from pydantic import BaseModel, EmailStr, Field
from typing import Literal

Role = Literal["student", "developer"]
ProjectType = Literal["web", "mobile", "both"]
ThemePreference = str

class ProjectApplication(BaseModel):
    developer_email: EmailStr
    status: Literal["pending", "approved"]

class ProjectAttachment(BaseModel):
    id: int
    file_name: str
    file_url: str
    mime_type: str | None = None
    size_bytes: int

class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    role: Role

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role
    name: str
    email: EmailStr

class UserPublic(BaseModel):
    name: str
    email: EmailStr
    role: Role

class ProjectCreateRequest(BaseModel):
    project_type: ProjectType
    title: str = Field(min_length=3, max_length=140)
    description: str = Field(min_length=10, max_length=5000)
    budget: float = Field(gt=0)

class ProjectUpdateRequest(BaseModel):
    project_type: ProjectType
    title: str = Field(min_length=3, max_length=140)
    description: str = Field(min_length=10, max_length=5000)
    budget: float = Field(gt=0)

class ProjectResponse(BaseModel):
    id: str
    project_type: ProjectType
    title: str
    description: str
    budget: float
    owner_email: EmailStr
    approved_developer_email: EmailStr | None = None
    applications: list[ProjectApplication] = []
    attachments: list[ProjectAttachment] = []
    created_at: str

class ProjectApproveRequest(BaseModel):
    developer_email: EmailStr

class WalletTransactionResponse(BaseModel):
    id: str
    title: str
    amount: float
    type: Literal["credit", "debit"]
    date: str

class WalletResponse(BaseModel):
    balance: float
    transactions: list[WalletTransactionResponse]

class WalletWithdrawRequest(BaseModel):
    amount: float = Field(gt=0)

class ThemePreferenceResponse(BaseModel):
    theme: ThemePreference
    primary_color: str
    theme_color: str
    secondary_color: str
    brand_name: str
    brand_logo: str

class ThemePreferenceUpdateRequest(BaseModel):
    theme: ThemePreference
    primary_color: str
    secondary_color: str
    brand_name: str
    brand_logo: str
