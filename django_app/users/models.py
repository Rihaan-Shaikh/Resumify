from django.db import models
from django.contrib.auth.models import User

class Resume(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    linkedin = models.CharField(max_length=200)
    skills = models.TextField()

    education = models.JSONField()
    experience = models.JSONField()
    projects = models.JSONField()
    certifications = models.JSONField()
    achievements = models.JSONField()
    languages = models.JSONField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Resume of {self.name}"

class ResumeTemplate(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    category = models.CharField(max_length=50)
    latex_template = models.TextField()
    preview_image = models.CharField(max_length=255, blank=True, null=True)
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class UserTemplate(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    template = models.ForeignKey(ResumeTemplate, on_delete=models.CASCADE)
    saved_at = models.DateTimeField(auto_now_add=True)
    favorite = models.BooleanField(default=False)

    class Meta:
        unique_together = ('user', 'template')

    def __str__(self):
        return f"{self.user.username} - {self.template.name}"

class UserSelectedTemplate(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='selected_template')
    template = models.ForeignKey(ResumeTemplate, on_delete=models.CASCADE)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.template.name}"


class PasswordRecovery(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='password_recovery')
    code_hash = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.IntegerField(default=0)
    used = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Password Recoveries"

    def __str__(self):
        return f"Recovery for {self.user.username} (attempts: {self.attempts})"

