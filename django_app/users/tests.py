from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient
from .models import ResumeTemplate, UserTemplate

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


from django.core import mail

class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='resetuser', email='reset@example.com', password='oldpassword')

    def test_password_reset_page_loads(self):
        url = reverse('account_reset_password')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reset Password")

    def test_password_reset_submits_email(self):
        url = reverse('account_reset_password')
        response = self.client.post(url, {'email': 'reset@example.com'})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('account_reset_password_done'))
        
        # Follow the redirect
        redirected_response = self.client.get(reverse('account_reset_password_done'))
        self.assertEqual(redirected_response.status_code, 200)
        self.assertContains(redirected_response, "Reset Link Sent")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Password Reset Request", mail.outbox[0].subject)

