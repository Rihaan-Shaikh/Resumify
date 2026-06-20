from pydantic import BaseModel, Field, conlist

# Pydantic model for validating the incoming resume data.
# We use Field and conlist to enforce strict requirements so empty fields are rejected.
class ResumeInput(BaseModel):
    # Must not be an empty string
    name: str = Field(..., min_length=1, description="Applicant's full name")
    
    # Must not be empty, and 'pattern' ensures it contains an '@' symbol
    email: str = Field(..., min_length=1, pattern=".*@.*", description="Applicant's email address")
    
    # Must not be empty
    phone: str = Field(..., min_length=1, description="Applicant's phone number")
    
    # Must not be empty
    linkedin: str = Field(..., min_length=1, description="LinkedIn profile URL")
    
    # Must not be empty
    skills: str = Field(..., min_length=1, description="Skills separated by commas")
    
    # conlist ensures the list contains at least 1 string item
    education: conlist(str, min_length=1) = Field(..., description="List of educational backgrounds")
    
    experience: conlist(str, min_length=1) = Field(..., description="List of technical experiences")
    
    # conlist ensures the list contains at least 1 project item
    projects: conlist(str, min_length=1) = Field(..., description="List of projects")
    
    certifications: conlist(str, min_length=1) = Field(..., description="List of certifications")
    achievements: conlist(str, min_length=1) = Field(..., description="List of achievements")
    languages: conlist(str, min_length=1) = Field(..., description="List of languages")
