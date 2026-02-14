from pydantic import BaseModel, Field

class StaffCreateIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    role: str = Field(default="Staff", max_length=100)
    work_start_time: str = "10:00"
    work_end_time: str = "20:00"

class StaffOut(BaseModel):
    id: str
    full_name: str
    role: str
    work_start_time: str
    work_end_time: str
