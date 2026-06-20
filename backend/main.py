from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from schemas import ResumeInput
from model import analyze_project, rewrite_bullet_logic

# Initialize the FastAPI application
app = FastAPI(
    title="AI Resume Builder API",
    description="A beginner friendly FastAPI backend for an AI Resume Builder."
)

# Add CORS so the JS frontend can fetch from this API without browser blocks
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom exception handler to return very clear error messages when Pydantic validation fails
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    If the frontend sends an empty name or empty project list, Pydantic throws an error.
    This handler catches those errors and formats them cleanly for the user.
    """
    errors = exc.errors()
    
    # Extract readable error messages
    error_messages = []
    for err in errors:
        # err["loc"] looks like ('body', 'email')
        field_name = err["loc"][-1]
        error_messages.append(f"Validation failed for '{field_name}': {err['msg']}")
        
    return JSONResponse(
        status_code=422,
        content={
            "message": "Validation Error",
            "details": error_messages
        }
    )

# Create an API endpoint for receiving the resume data via HTTP POST
@app.post("/resume")
def submit_resume(resume_data: ResumeInput):
    """
    Endpoint: POST /resume
    
    FastAPI takes the JSON payload and uses our strict 'ResumeInput' schema.
    If any field is missing or empty, the custom exception handler above takes over!
    If valid, the code perfectly reaches this success block.
    """
    
    # We return a JSON response confirming successful validation exactly as requested
    return {
        "message": "Resume data validated and received successfully!",
        "received_data": resume_data.model_dump()
    }

# Create an API endpoint for analyzing project descriptions using AI
@app.post("/analyze")
def analyze_resume(resume_data: ResumeInput):
    """
    Endpoint: POST /analyze
    
    Accepts the validated resume JSON and runs each project description
    through our resume-quality scoring engine to return a Resume Analysis Dashboard response!
    """
    import re
    from model import ACTION_VERBS, METRIC_KEYWORDS, TECH_KEYWORDS
    
    analysis_results = []
    
    # Loop through all the provided projects
    for project in resume_data.projects:
        # Get quality analysis, score, strength, confidence, and coaching suggestions
        result = analyze_project(project)
        analysis_results.append(result)
        
    # Calculate base score as the average of the quality scores of all projects
    if analysis_results:
        project_avg = sum(item["score"] for item in analysis_results) / len(analysis_results)
    else:
        project_avg = 100
        
    overall_score = round(project_avg)
    
    # Adjust overall score based on resume completeness rules
    if not ("linkedin.com/" in resume_data.linkedin.lower()):
        overall_score -= 5
    if not any(c.strip() for c in resume_data.certifications if c.strip()):
        overall_score -= 5
    if not any(a.strip() for a in resume_data.achievements if a.strip()):
        overall_score -= 5
        
    skills_list = [s.strip() for s in resume_data.skills.split(",") if s.strip()]
    if len(skills_list) < 3:
        overall_score -= 5
        
    overall_score = max(0, min(100, overall_score))
    
    # Analyze resume-wide strengths and suggestions
    strengths = []
    suggestions = []
    
    has_metrics = False
    has_verbs = False
    has_tech = False
    has_optimal_length = True
    
    for item in analysis_results:
        text = item["project"].lower()
        words = set(re.findall(r'[a-zA-Z0-9\.\+#]+', text))
        
        # Check metrics
        if any(kw in words or kw in text for kw in METRIC_KEYWORDS) or bool(re.search(r'\d', text)):
            has_metrics = True
        
        # Check verbs
        if any(w in ACTION_VERBS for w in words):
            has_verbs = True
            
        # Check tech
        if any(w in TECH_KEYWORDS for w in words):
            has_tech = True
            
        # Check length
        word_count = len(words)
        if word_count < 8 or word_count > 30:
            has_optimal_length = False

    # Compile Strengths
    if has_verbs:
        strengths.append("Uses active, professional action verbs to describe project contributions.")
    if has_metrics:
        strengths.append("Includes quantifiable achievements and metrics to showcase business impact.")
    if has_tech:
        strengths.append("Highlights key technical skills and tools throughout the projects.")
    if has_optimal_length and analysis_results:
        strengths.append("Maintains clear, concise, and highly readable project description lengths.")
    if len(skills_list) >= 4:
        strengths.append("Showcases a strong and diverse technical skills inventory.")
    if "linkedin.com/" in resume_data.linkedin.lower():
        strengths.append("Includes a professional LinkedIn profile link for recruiter outreach.")
    if any(c.strip() for c in resume_data.certifications if c.strip()):
        strengths.append("Highlights certifications to validate technical capabilities.")
    if any(a.strip() for a in resume_data.achievements if a.strip()):
        strengths.append("Highlights personal or professional achievements and accolades.")

    # Compile Suggestions
    if not has_verbs:
        suggestions.append("Begin project description bullet points with strong action verbs (e.g. Developed, Optimized).")
    if not has_metrics:
        suggestions.append("Add measurable metrics (e.g. performance speedups, user sizes) to quantify impact.")
    if not has_tech:
        suggestions.append("Incorporate specific technical tools and frameworks in project descriptions.")
    if not has_optimal_length and analysis_results:
        suggestions.append("Adjust project description lengths to sit within the 16-30 words sweet spot.")
    if len(skills_list) < 4:
        suggestions.append("Expand the Skills section to include a wider range of frameworks or tools.")
    if not ("linkedin.com/" in resume_data.linkedin.lower()):
        suggestions.append("Add a professional LinkedIn profile URL to build recruiter connections.")
    if not any(c.strip() for c in resume_data.certifications if c.strip()):
        suggestions.append("Consider adding technical certifications to show industry-standard knowledge.")
    if not any(a.strip() for a in resume_data.achievements if a.strip()):
        suggestions.append("Consider adding awards or hackathon wins to demonstrate competitive drive.")
        
    # ================================================================
    # ATS (Applicant Tracking System) SCORING ENGINE
    # ================================================================
    # Evaluates the resume the way an automated ATS system would,
    # checking: Contact Info, Skills, Projects, and Completeness.
    # ================================================================
    
    ats_strengths = []
    ats_issues = []
    ats_recommendations = []
    ats_score = 0
    
    # --- A) Contact Information (25 pts max) ---
    contact_score = 0
    
    # Name (5 pts)
    if resume_data.name and len(resume_data.name.strip()) >= 2:
        contact_score += 5
        ats_strengths.append("Full name is clearly provided.")
    else:
        ats_issues.append("Name is missing or too short.")
        ats_recommendations.append("Provide your complete legal name at the top of your resume.")
    
    # Email (5 pts) - check for valid format
    email = resume_data.email.strip()
    if email and "@" in email and "." in email.split("@")[-1]:
        contact_score += 5
        ats_strengths.append("Professional email address is provided.")
    else:
        ats_issues.append("Email address is missing or invalid.")
        ats_recommendations.append("Add a professional email address (e.g. firstname.lastname@domain.com).")
    
    # Phone (5 pts)
    phone_digits = re.sub(r'\D', '', resume_data.phone)
    if len(phone_digits) >= 10:
        contact_score += 5
        ats_strengths.append("Phone number with sufficient digits is provided.")
    elif len(phone_digits) >= 7:
        contact_score += 3
        ats_issues.append("Phone number may be incomplete.")
        ats_recommendations.append("Include a full phone number with area/country code.")
    else:
        ats_issues.append("Phone number is missing or too short.")
        ats_recommendations.append("Add a full contact phone number for recruiter callbacks.")
    
    # LinkedIn (10 pts)
    linkedin_lower = resume_data.linkedin.lower().strip()
    if "linkedin.com/" in linkedin_lower:
        contact_score += 10
        ats_strengths.append("LinkedIn profile URL is included.")
    elif linkedin_lower:
        contact_score += 3
        ats_issues.append("LinkedIn URL appears malformed.")
        ats_recommendations.append("Use a full LinkedIn URL (e.g. linkedin.com/in/yourname).")
    else:
        ats_issues.append("LinkedIn profile is missing.")
        ats_recommendations.append("Add your LinkedIn profile URL to boost recruiter visibility.")
    
    # --- B) Skills Section (25 pts max) ---
    skills_score = 0
    skills_list_ats = [s.strip().lower() for s in resume_data.skills.split(",") if s.strip()]
    num_skills = len(skills_list_ats)
    
    # Minimum skill count scoring
    if num_skills >= 8:
        skills_score += 10
        ats_strengths.append(f"Strong skills inventory ({num_skills} skills listed).")
    elif num_skills >= 5:
        skills_score += 7
        ats_strengths.append(f"Adequate skills listed ({num_skills} skills).")
    elif num_skills >= 3:
        skills_score += 4
        ats_issues.append(f"Only {num_skills} skills listed — may be too few for ATS filters.")
        ats_recommendations.append("List at least 6-8 relevant technical skills to pass ATS keyword scans.")
    else:
        skills_score += 1
        ats_issues.append("Very few skills listed — high risk of ATS rejection.")
        ats_recommendations.append("Expand your skills section significantly. ATS systems match candidates by keyword density.")
    
    # Technical keywords in skills
    tech_in_skills = [s for s in skills_list_ats if s in TECH_KEYWORDS]
    if len(tech_in_skills) >= 5:
        skills_score += 15
        ats_strengths.append(f"Excellent technical keyword coverage in skills ({len(tech_in_skills)} recognized).")
    elif len(tech_in_skills) >= 3:
        skills_score += 10
        ats_strengths.append(f"Good technical keyword coverage ({len(tech_in_skills)} recognized).")
    elif len(tech_in_skills) >= 1:
        skills_score += 5
        ats_issues.append("Limited technical keywords detected in the skills section.")
        ats_recommendations.append("Include industry-standard tools and frameworks (e.g. Python, React, Docker, AWS).")
    else:
        ats_issues.append("No recognized technical keywords found in skills.")
        ats_recommendations.append("Add specific programming languages, frameworks, and tools to your skills section.")
    
    # --- C) Projects Analysis (30 pts max) ---
    projects_score = 0
    total_projects = len(analysis_results)
    projects_with_verbs = 0
    projects_with_tech = 0
    projects_with_metrics = 0
    
    for item in analysis_results:
        text = item["project"].lower()
        words_set = set(re.findall(r'[a-zA-Z0-9\.\+#]+', text))
        
        if any(w in ACTION_VERBS for w in words_set):
            projects_with_verbs += 1
        if any(w in TECH_KEYWORDS for w in words_set):
            projects_with_tech += 1
        if any(kw in words_set or kw in text for kw in METRIC_KEYWORDS) or bool(re.search(r'\d', text)):
            projects_with_metrics += 1
    
    # Action verbs in projects (10 pts)
    if total_projects > 0:
        verb_ratio = projects_with_verbs / total_projects
        if verb_ratio >= 0.8:
            projects_score += 10
            ats_strengths.append("Most project descriptions begin with strong action verbs.")
        elif verb_ratio >= 0.5:
            projects_score += 6
            ats_issues.append("Some projects lack action verbs.")
            ats_recommendations.append("Start every project bullet with an action verb (Built, Developed, Designed).")
        else:
            projects_score += 2
            ats_issues.append("Most projects are missing action verbs.")
            ats_recommendations.append("Rewrite project descriptions to lead with action verbs — critical for ATS parsing.")
    
    # Technical stack in projects (10 pts)
    if total_projects > 0:
        tech_ratio = projects_with_tech / total_projects
        if tech_ratio >= 0.8:
            projects_score += 10
            ats_strengths.append("Technical stack is well-documented across projects.")
        elif tech_ratio >= 0.5:
            projects_score += 6
            ats_issues.append("Some projects don't mention specific technologies.")
            ats_recommendations.append("Name the specific tools/languages used in each project for ATS keyword matching.")
        else:
            projects_score += 2
            ats_issues.append("Projects lack technology mentions — ATS cannot determine your tech stack.")
            ats_recommendations.append("Every project should explicitly name the technologies used.")
    
    # Quantified impact in projects (10 pts)
    if total_projects > 0:
        metric_ratio = projects_with_metrics / total_projects
        if metric_ratio >= 0.8:
            projects_score += 10
            ats_strengths.append("Quantified impact and metrics are present in most projects.")
        elif metric_ratio >= 0.5:
            projects_score += 6
            ats_issues.append("Some projects lack quantified results.")
            ats_recommendations.append("Add numbers, percentages, or user counts to demonstrate measurable impact.")
        else:
            projects_score += 2
            ats_issues.append("Very few projects include measurable outcomes.")
            ats_recommendations.append("Quantify achievements (e.g. 'reduced latency by 40%', 'served 10K users').")
    
    # --- D) Resume Completeness (20 pts max) ---
    completeness_score = 0
    
    # Education (4 pts)
    has_education = any(e.strip() for e in resume_data.education if e.strip())
    if has_education:
        completeness_score += 4
        ats_strengths.append("Education section is present.")
    else:
        ats_issues.append("Education section is empty.")
        ats_recommendations.append("Add your educational background — many ATS filters require it.")
    
    # Experience (4 pts)
    has_experience = any(e.strip() for e in resume_data.experience if e.strip())
    if has_experience:
        completeness_score += 4
        ats_strengths.append("Work experience section is present.")
    else:
        ats_issues.append("Experience section is empty.")
        ats_recommendations.append("Add professional experience, internships, or relevant work history.")
    
    # Projects (4 pts)
    if total_projects >= 2:
        completeness_score += 4
        ats_strengths.append(f"{total_projects} projects documented.")
    elif total_projects == 1:
        completeness_score += 2
        ats_issues.append("Only 1 project listed.")
        ats_recommendations.append("Add at least 2-3 projects to demonstrate breadth of experience.")
    else:
        ats_issues.append("No projects listed.")
        ats_recommendations.append("Add project descriptions to showcase practical application of your skills.")
    
    # Certifications (4 pts)
    has_certs = any(c.strip() for c in resume_data.certifications if c.strip())
    if has_certs:
        completeness_score += 4
        ats_strengths.append("Certifications are listed.")
    else:
        ats_issues.append("No certifications listed.")
        ats_recommendations.append("Consider adding certifications (AWS, Google, etc.) to stand out in ATS rankings.")
    
    # Achievements (4 pts)
    has_achievements = any(a.strip() for a in resume_data.achievements if a.strip())
    if has_achievements:
        completeness_score += 4
        ats_strengths.append("Achievements section is populated.")
    else:
        ats_issues.append("No achievements listed.")
        ats_recommendations.append("Add awards, hackathon wins, or notable accomplishments.")
    
    # --- Compute final ATS score ---
    ats_score = contact_score + skills_score + projects_score + completeness_score
    ats_score = max(0, min(100, ats_score))
        
    return {
        # Legacy/Backward compatibility fields
        "score": overall_score,
        "analysis": analysis_results,
        # Resume quality dashboard fields
        "overall_score": overall_score,
        "strengths": strengths,
        "suggestions": suggestions,
        "project_feedback": analysis_results,
        # ATS scoring fields
        "ats_score": ats_score,
        "ats_strengths": ats_strengths,
        "ats_issues": ats_issues,
        "ats_recommendations": ats_recommendations
    }

from pydantic import BaseModel

class RewriteInput(BaseModel):
    text: str

@app.post("/rewrite-bullet")
def rewrite_bullet(payload: RewriteInput):
    text = payload.text
    improved, changes = rewrite_bullet_logic(text)
    return {
        "original": text,
        "improved": improved,
        "changes": changes
    }

