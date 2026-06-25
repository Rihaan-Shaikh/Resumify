from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient
from .models import ResumeTemplate, UserTemplate, Resume, UserWorkspace

class TemplateAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        ResumeTemplate.objects.all().delete()
        
        # Public Template
        self.template1 = ResumeTemplate.objects.create(
            name="Test Template 1",
            category="Test Category 1",
            description="Test Description 1",
            latex_template="[[NAME]] [[EXPERIENCE]]",
            is_public=True
        )
        
        # Private Template
        self.template2 = ResumeTemplate.objects.create(
            name="Test Template 2",
            category="Test Category 2",
            description="Test Description 2",
            latex_template="[[NAME]] [[EDUCATION]]",
            is_public=False
        )

    def test_get_public_templates(self):
        """Test retrieving list of public templates"""
        url = reverse('template-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only return public templates
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], "Test Template 1")

    def test_save_template_unauthenticated(self):
        """Test saving a template fails without authentication"""
        url = reverse('save-template', kwargs={'id': self.template1.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_save_template_authenticated(self):
        """Test saving a template works for authenticated users"""
        self.client.force_authenticate(user=self.user)
        url = reverse('save-template', kwargs={'id': self.template1.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(UserTemplate.objects.filter(user=self.user, template=self.template1).exists())

    def test_save_nonexistent_template(self):
        """Test saving a template that does not exist returns 404"""
        self.client.force_authenticate(user=self.user)
        url = reverse('save-template', kwargs={'id': 999})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_my_templates(self):
        """Test retrieving user's saved templates collection"""
        self.client.force_authenticate(user=self.user)
        
        # Initially empty
        url = reverse('my-templates')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
        
        # Save a template
        UserTemplate.objects.create(user=self.user, template=self.template1)
        
        # Retrieve collection
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['template_details']['name'], "Test Template 1")

    def test_toggle_favorite_status(self):
        """Test toggling the favorite status of a template"""
        self.client.force_authenticate(user=self.user)
        url = reverse('favorite-template', kwargs={'id': self.template1.id})
        
        # First call (not saved, should create and favorite = True)
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['favorite'])
        
        # Second call (favorite = False)
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['favorite'])


import re
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.hashers import check_password
from users.models import PasswordRecovery
from users.views import generate_recovery_code

class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='resetuser',
            email='reset@example.com',
            password='oldpassword'
        )

    def test_code_generation_format(self):
        """Test that generate_recovery_code generates an 8-char uppercase code with hyphen"""
        code = generate_recovery_code()
        # Pattern: 4 uppercase chars/numbers, hyphen, 4 uppercase chars/numbers
        self.assertTrue(re.match(r'^[A-Z2-9]{4}-[A-Z2-9]{4}$', code), f"Code {code} format is invalid")
        self.assertEqual(len(code), 9) # 8 alphanumeric + 1 hyphen

    def test_forgot_password_page_loads(self):
        """Test forgot password page loads successfully"""
        url = reverse('account_reset_password')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Forgot Password")

    def test_password_reset_creates_hash_in_db(self):
        """Test that submitting an email hashes the recovery code and doesn't store plain code"""
        url = reverse('account_reset_password')
        response = self.client.post(url, {'email': 'reset@example.com'})
        
        # Verify redirect to the code display page
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('account_reset_password_code'))
        
        # Check database record
        recovery = PasswordRecovery.objects.get(user=self.user)
        self.assertFalse(recovery.used)
        self.assertEqual(recovery.attempts, 0)
        self.assertGreater(recovery.expires_at, timezone.now())
        
        # Confirm it stored only the hash
        code_in_session = self.client.session.get('recovery_code')
        self.assertIsNotNone(code_in_session)
        # Verify the database does not contain the plain code anywhere
        self.assertNotEqual(recovery.code_hash, code_in_session)
        self.assertTrue(check_password(code_in_session, recovery.code_hash))

    def test_one_time_code_display(self):
        """Test recovery code is only displayed once and removed from session immediately"""
        # Step 1: Request reset
        self.client.post(reverse('account_reset_password'), {'email': 'reset@example.com'})
        
        # Step 2: Retrieve the code page (should show code)
        code_url = reverse('account_reset_password_code')
        response = self.client.get(code_url)
        self.assertEqual(response.status_code, 200)
        code_in_session = response.context.get('code')
        self.assertIsNotNone(code_in_session)
        self.assertContains(response, code_in_session)
        
        # Step 3: Access again, it should redirect to reset because session is cleared
        response2 = self.client.get(code_url)
        self.assertEqual(response2.status_code, 302)
        self.assertEqual(response2['Location'], reverse('account_reset_password'))

    def test_new_code_invalidates_previous_one(self):
        """Test only one active recovery record can exist per user, generating new invalidates old"""
        # First request
        self.client.post(reverse('account_reset_password'), {'email': 'reset@example.com'})
        recovery1 = PasswordRecovery.objects.get(user=self.user)
        
        # Second request
        self.client.post(reverse('account_reset_password'), {'email': 'reset@example.com'})
        recovery2 = PasswordRecovery.objects.get(user=self.user)
        
        # Verify old record is deleted, only one exists
        self.assertEqual(PasswordRecovery.objects.filter(user=self.user).count(), 1)
        self.assertNotEqual(recovery1.id, recovery2.id)

    def test_non_existent_email_response(self):
        """Test user enumeration defense: non-existent email behaves identically to existing email"""
        url = reverse('account_reset_password')
        response = self.client.post(url, {'email': 'nonexistent@example.com'})
        
        # Behaves identically: redirects to code display page
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('account_reset_password_code'))
        
        # A dummy code should be present in session for the user to view once
        session_code = self.client.session.get('recovery_code')
        self.assertIsNotNone(session_code)
        
        # Fetching code page works identically
        code_response = self.client.get(reverse('account_reset_password_code'))
        self.assertEqual(code_response.status_code, 200)
        self.assertContains(code_response, session_code)
        
        # No DB record created since user does not exist
        self.assertEqual(PasswordRecovery.objects.count(), 0)

    def test_code_expiry(self):
        """Test that an expired recovery code cannot be used and gets deleted"""
        self.client.post(reverse('account_reset_password'), {'email': 'reset@example.com'})
        code = self.client.session.get('recovery_code')
        
        # Manually expire the code in the DB
        recovery = PasswordRecovery.objects.get(user=self.user)
        recovery.expires_at = timezone.now() - timedelta(minutes=1)
        recovery.save()
        
        # Try to confirm
        confirm_url = reverse('account_reset_password_confirm')
        response = self.client.post(confirm_url, {
            'email': 'reset@example.com',
            'code': code,
            'password': 'NewPassword123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "expired")
        
        # Record should be deleted from DB
        self.assertFalse(PasswordRecovery.objects.filter(user=self.user).exists())

    def test_incorrect_attempts_limit(self):
        """Test incorrect attempts increment attempts counter and delete recovery record after 5 failures"""
        self.client.post(reverse('account_reset_password'), {'email': 'reset@example.com'})
        
        # Try invalid code 4 times
        confirm_url = reverse('account_reset_password_confirm')
        for i in range(4):
            response = self.client.post(confirm_url, {
                'email': 'reset@example.com',
                'code': 'AAAA-0000',
                'password': 'NewPassword123!',
            })
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Invalid recovery code")
            
            # Check attempts incremented
            recovery = PasswordRecovery.objects.get(user=self.user)
            self.assertEqual(recovery.attempts, i + 1)
            
        # The 5th incorrect attempt should delete the record and notify the user
        response = self.client.post(confirm_url, {
            'email': 'reset@example.com',
            'code': 'AAAA-0000',
            'password': 'NewPassword123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Too many incorrect attempts")
        
        # Record is deleted
        self.assertFalse(PasswordRecovery.objects.filter(user=self.user).exists())

    def test_successful_password_reset(self):
        """Test successful verification updates password, deletes recovery record, clears session, and redirects to login"""
        # Step 1: Generate code
        self.client.post(reverse('account_reset_password'), {'email': 'reset@example.com'})
        
        # Retrieve code from session
        code = self.client.session.get('recovery_code')
        
        # Step 2: Confirm password reset
        confirm_url = reverse('account_reset_password_confirm')
        response = self.client.post(confirm_url, {
            'email': 'reset@example.com',
            'code': code,
            'password': 'NewSuperPassword123!',
        })
        
        # Should redirect to success
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('account_reset_password_success'))
        
        # Check user password updated
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewSuperPassword123!'))
        
        # Check record is deleted (one-time use enforced)
        self.assertFalse(PasswordRecovery.objects.filter(user=self.user).exists())
        
        # Check session is completely cleared of recovery variables
        self.assertNotIn('recovery_email', self.client.session)
        self.assertNotIn('recovery_code', self.client.session)
        self.assertNotIn('recovery_expires_at', self.client.session)

    def test_password_confirm_template_has_validation_rules(self):
        """Test confirm password template contains the validation rules checklist"""
        url = reverse('account_reset_password_confirm')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "8+ characters")
        self.assertContains(response, "Uppercase letter")
        self.assertContains(response, "Lowercase letter")
        self.assertContains(response, "Number")
        self.assertContains(response, "Special character")
        self.assertContains(response, "Passwords Match")

    def test_copy_then_mask_javascript_present(self):
        """Test that the copy-then-mask Javascript is present in the recovery code template"""
        self.client.post(reverse('account_reset_password'), {'email': 'reset@example.com'})
        response = self.client.get(reverse('account_reset_password_code'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '••••-••••')
        self.assertContains(response, 'This recovery code will never be shown again.')
        self.assertContains(response, 'copyCode')

    def test_countdown_expiry_timer_present(self):
        """Test that the live countdown timer element and script are present on the code page"""
        self.client.post(reverse('account_reset_password'), {'email': 'reset@example.com'})
        response = self.client.get(reverse('account_reset_password_code'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="timer-text"')
        self.assertContains(response, 'secondsRemaining')
        self.assertContains(response, 'updateTimer')

    def test_back_button_cache_protection(self):
        """Test that recovery views set Cache-Control and Pragma to prevent back-button caching"""
        # 1. Reset request page
        response1 = self.client.get(reverse('account_reset_password'))
        self.assertIn('no-store', response1.get('Cache-Control', ''))
        self.assertEqual(response1.get('Pragma'), 'no-cache')
        
        # 2. Reset confirm page
        response2 = self.client.get(reverse('account_reset_password_confirm'))
        self.assertIn('no-store', response2.get('Cache-Control', ''))
        self.assertEqual(response2.get('Pragma'), 'no-cache')

    def test_invalid_characters_rejected(self):
        """Test that recovery codes containing invalid characters are rejected immediately"""
        self.client.post(reverse('account_reset_password'), {'email': 'reset@example.com'})
        confirm_url = reverse('account_reset_password_confirm')
        
        response = self.client.post(confirm_url, {
            'email': 'reset@example.com',
            'code': 'AB7X Q91K', # space instead of hyphen
            'password': 'NewPassword123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid recovery code format")


class WorkspaceAndResumeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='workspace_user', password='password123')
        self.other_user = User.objects.create_user(username='other_user', password='password123')
        
        self.template = ResumeTemplate.objects.create(
            name="Workspace Template",
            category="Academic",
            description="A template for testing workspace features",
            latex_template="[[NAME]]",
            is_public=True
        )
        
        self.resume1 = Resume.objects.create(
            user=self.user,
            name="First Resume",
            email="user1@example.com",
            phone="12345",
            linkedin="linkedin.com/1",
            skills="Python",
            education=[],
            experience=[],
            projects=[],
            certifications=[],
            achievements=[],
            languages=[]
        )
        
        self.resume2 = Resume.objects.create(
            user=self.user,
            name="Second Resume",
            email="user2@example.com",
            phone="67890",
            linkedin="linkedin.com/2",
            skills="Django",
            education=[],
            experience=[],
            projects=[],
            certifications=[],
            achievements=[],
            languages=[]
        )

    def test_save_resume_create_new(self):
        """Test creating a new resume via SaveResumeView POST without ID"""
        self.client.force_authenticate(user=self.user)
        url = reverse('save-resume')
        data = {
            "name": "New Brand Resume",
            "email": "new@example.com",
            "phone": "555-5555",
            "linkedin": "linkedin.com/new",
            "skills": "Go, Rust",
            "education": ["B.S. CS"],
            "experience": [],
            "projects": [],
            "certifications": [],
            "achievements": [],
            "languages": []
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['name'], "New Brand Resume")
        # Verify db
        self.assertEqual(Resume.objects.filter(user=self.user, name="New Brand Resume").count(), 1)

    def test_save_resume_partial_update(self):
        """Test updating an existing resume via SaveResumeView POST with ID"""
        self.client.force_authenticate(user=self.user)
        url = reverse('save-resume')
        data = {
            "id": self.resume1.id,
            "name": "Updated Name",
            "skills": "Updated Skills",
            "education": self.resume1.education,
            "experience": self.resume1.experience,
            "projects": self.resume1.projects,
            "certifications": self.resume1.certifications,
            "achievements": self.resume1.achievements,
            "languages": self.resume1.languages
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.resume1.refresh_from_db()
        self.assertEqual(self.resume1.name, "Updated Name")
        self.assertEqual(self.resume1.skills, "Updated Skills")

    def test_save_resume_not_owned(self):
        """Test that updating a resume owned by another user fails with 404"""
        self.client.force_authenticate(user=self.other_user)
        url = reverse('save-resume')
        data = {
            "id": self.resume1.id,
            "name": "Hacked Name"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_workspace_get_creates_default(self):
        """Test GET /api/workspace/ creates a workspace if it doesn't exist"""
        # User workspace does not exist initially
        self.assertFalse(UserWorkspace.objects.filter(user=self.user).exists())
        
        self.client.force_authenticate(user=self.user)
        url = reverse('workspace')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should auto-select the most recently updated resume
        self.assertEqual(response.data['active_resume_id'], self.resume2.id)
        self.assertEqual(response.data['active_template_id'], None)
        self.assertEqual(response.data['scroll_position'], 0)
        self.assertEqual(response.data['editor_state'], {})
        
        self.assertTrue(UserWorkspace.objects.filter(user=self.user).exists())

    def test_workspace_post_updates_fields(self):
        """Test POST /api/workspace/ updates the user's workspace"""
        self.client.force_authenticate(user=self.user)
        url = reverse('workspace')
        data = {
            "active_resume_id": self.resume1.id,
            "active_template_id": self.template.id,
            "scroll_position": 250,
            "editor_state": {"section": "education"}
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['active_resume_id'], self.resume1.id)
        self.assertEqual(response.data['active_template_id'], self.template.id)
        self.assertEqual(response.data['scroll_position'], 250)
        self.assertEqual(response.data['editor_state'], {"section": "education"})
        
        workspace = UserWorkspace.objects.get(user=self.user)
        self.assertEqual(workspace.active_resume, self.resume1)
        self.assertEqual(workspace.active_template, self.template)
        self.assertEqual(workspace.scroll_position, 250)
        self.assertEqual(workspace.editor_state, {"section": "education"})

    def test_workspace_resume_ownership(self):
        """Test that a user cannot set another user's resume as their active resume"""
        self.client.force_authenticate(user=self.other_user)
        url = reverse('workspace')
        data = {
            "active_resume_id": self.resume1.id
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should be None since the resume is not owned by other_user
        self.assertEqual(response.data['active_resume_id'], None)

    def test_workspace_get_cleans_deleted_resume(self):
        """Test that GET /api/workspace/ sets active_resume to None if the resume was deleted"""
        workspace = UserWorkspace.objects.create(user=self.user, active_resume=self.resume1)
        
        # Delete resume1
        self.resume1.delete()
        
        self.client.force_authenticate(user=self.user)
        url = reverse('workspace')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['active_resume_id'], self.resume2.id)

    def test_workspace_get_auto_selects_recent_resume(self):
        """Test that GET /api/workspace/ selects the most recently edited resume"""
        workspace = UserWorkspace.objects.create(user=self.user, active_resume=None)
        
        # Touch resume1 to make it more recently updated
        self.resume1.name = "First Resume Updated"
        self.resume1.save()
        
        self.client.force_authenticate(user=self.user)
        url = reverse('workspace')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['active_resume_id'], self.resume1.id)

    def test_save_resume_blank_fields_creation(self):
        """Test that we can create a resume with completely blank optional fields"""
        self.client.force_authenticate(user=self.user)
        url = reverse('save-resume')
        data = {
            "name": "Blank Resume Name",
            "email": "",
            "phone": "",
            "linkedin": "",
            "skills": "",
            "education": [],
            "experience": [],
            "projects": [],
            "certifications": [],
            "achievements": [],
            "languages": []
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['email'], "")
        self.assertEqual(response.data['phone'], "")
        self.assertEqual(response.data['linkedin'], "")
        self.assertEqual(response.data['skills'], "")
        self.assertEqual(response.data['education'], [])
        self.assertEqual(response.data['experience'], [])
        self.assertEqual(response.data['projects'], [])
        self.assertEqual(response.data['certifications'], [])
        self.assertEqual(response.data['achievements'], [])
        self.assertEqual(response.data['languages'], [])

    def test_save_resume_blank_fields_partial_update(self):
        """Test that we can update an existing resume to clear all optional fields"""
        self.client.force_authenticate(user=self.user)
        url = reverse('save-resume')
        data = {
            "id": self.resume1.id,
            "name": "Cleared Fields Resume",
            "email": "",
            "phone": "",
            "linkedin": "",
            "skills": "",
            "education": [],
            "experience": [],
            "projects": [],
            "certifications": [],
            "achievements": [],
            "languages": []
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.resume1.refresh_from_db()
        self.assertEqual(self.resume1.email, "")
        self.assertEqual(self.resume1.phone, "")
        self.assertEqual(self.resume1.linkedin, "")
        self.assertEqual(self.resume1.skills, "")
        self.assertEqual(self.resume1.education, [])
        self.assertEqual(self.resume1.experience, [])

    def test_save_resume_email_validation_still_enforced(self):
        """Test that email format validation is still active if a non-empty invalid email is provided"""
        self.client.force_authenticate(user=self.user)
        url = reverse('save-resume')
        data = {
            "name": "Invalid Email Resume",
            "email": "invalid-email-format-without-at",
            "phone": "",
            "linkedin": "",
            "skills": "",
            "education": [],
            "experience": [],
            "projects": [],
            "certifications": [],
            "achievements": [],
            "languages": []
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_resume_naming_defaults(self):
        """Test that new resumes without a name auto-generate default numbered names"""
        self.client.force_authenticate(user=self.user)
        # Delete existing to start clean
        Resume.objects.filter(user=self.user).delete()
        
        url = reverse('save-resume')
        # 1st Untitled
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], "Untitled Resume")
        
        # 2nd Untitled
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], "Untitled Resume (2)")
        
        # 3rd Untitled
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], "Untitled Resume (3)")

    def test_resume_renaming_validation(self):
        """Test that renaming a resume trims whitespace and rejects empty names"""
        self.client.force_authenticate(user=self.user)
        url = reverse('save-resume')
        
        # Test valid rename with trimming
        data = {"id": self.resume1.id, "name": "   Trimmed Name   "}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.resume1.refresh_from_db()
        self.assertEqual(self.resume1.name, "Trimmed Name")
        
        # Test empty name rejection
        data = {"id": self.resume1.id, "name": "    "}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test missing name parameter during save does not reject partial update if other fields are updated
        data = {"id": self.resume1.id, "skills": "Go, Python"}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_duplicate_resume(self):
        """Test duplicating a resume and copying its template assignment"""
        self.client.force_authenticate(user=self.user)
        
        # Associate template with resume1
        self.resume1.template = self.template
        self.resume1.save()
        
        url = reverse('duplicate-resume', kwargs={'id': self.resume1.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], "First Resume Copy")
        self.assertEqual(response.data['template'], self.template.id)
        
        # Duplicate again
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], "First Resume Copy (2)")
        
        # Verify database
        dup = Resume.objects.get(name="First Resume Copy")
        self.assertEqual(dup.skills, self.resume1.skills)
        self.assertEqual(dup.template, self.template)

    def test_delete_resume_and_fallbacks(self):
        """Test deleting resumes, fallback selection, and automatic new blank resume generation"""
        self.client.force_authenticate(user=self.user)
        workspace = UserWorkspace.objects.create(user=self.user, active_resume=self.resume2)
        
        # Delete resume2 (currently active). It should fallback to resume1 since it's the next recent.
        url = reverse('delete-resume', kwargs={'id': self.resume2.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['active_resume_id'], self.resume1.id)
        workspace.refresh_from_db()
        self.assertEqual(workspace.active_resume, self.resume1)
        
        # Delete resume1. Now no resumes are left, a new blank resume should be auto-created.
        url = reverse('delete-resume', kwargs={'id': self.resume1.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        new_active_id = response.data['active_resume_id']
        self.assertIsNotNone(new_active_id)
        
        workspace.refresh_from_db()
        self.assertEqual(workspace.active_resume.id, new_active_id)
        self.assertEqual(workspace.active_resume.name, "Untitled Resume")
        self.assertEqual(workspace.active_resume.skills, "")




