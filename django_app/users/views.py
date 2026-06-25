import secrets
import re
from django.shortcuts import render, redirect
from django.views import View
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.db import transaction, IntegrityError

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from rest_framework.authentication import SessionAuthentication

from .models import Resume, ResumeTemplate, UserTemplate, UserSelectedTemplate, PasswordRecovery, UserWorkspace
from .serializers import ResumeSerializer, ResumeTemplateSerializer, UserTemplateSerializer

class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return

def get_next_untitled_name(user) -> str:
    base_name = "Untitled Resume"
    existing_names = set(Resume.objects.filter(user=user, name__startswith=base_name).values_list('name', flat=True))
    if base_name not in existing_names:
        return base_name
    i = 2
    while f"{base_name} ({i})" in existing_names:
        i += 1
    return f"{base_name} ({i})"

class SaveResumeView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (CsrfExemptSessionAuthentication,)

    def post(self, request, *args, **kwargs):
        resume_id = request.data.get('id')
        instance = None
        if resume_id:
            try:
                instance = Resume.objects.get(id=resume_id, user=request.user)
            except Resume.DoesNotExist:
                return Response({"error": "Resume not found"}, status=status.HTTP_404_NOT_FOUND)
        
        # Trim name and handle defaults / empty names validation
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        name = data.get('name', '')
        if isinstance(name, str):
            name = name.strip()
            
        if not instance:
            if not name:
                name = get_next_untitled_name(request.user)
            data['name'] = name
        else:
            if 'name' in data:
                if not name:
                    return Response({"error": "Resume name cannot be empty"}, status=status.HTTP_400_BAD_REQUEST)
                data['name'] = name

        serializer = ResumeSerializer(instance, data=data, partial=True)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_200_OK if instance else status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class WorkspaceView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (CsrfExemptSessionAuthentication,)

    def get(self, request, *args, **kwargs):
        workspace, created = UserWorkspace.objects.get_or_create(user=request.user)
        
        if workspace.active_resume and not Resume.objects.filter(id=workspace.active_resume.id, user=request.user).exists():
            workspace.active_resume = None
            
        if not workspace.active_resume:
            recent_resume = Resume.objects.filter(user=request.user).order_by('-updated_at').first()
            if recent_resume:
                workspace.active_resume = recent_resume
                workspace.save()
                
        if workspace.active_template and not ResumeTemplate.objects.filter(id=workspace.active_template.id).exists():
            workspace.active_template = None
            workspace.save()

        # Determine the template associated with the active resume
        active_temp_id = None
        if workspace.active_resume:
            if workspace.active_resume.template:
                active_temp_id = workspace.active_resume.template.id
                if workspace.active_template != workspace.active_resume.template:
                    workspace.active_template = workspace.active_resume.template
                    workspace.save()
            else:
                if workspace.active_template:
                    active_temp_id = workspace.active_template.id
        else:
            if workspace.active_template:
                active_temp_id = workspace.active_template.id

        return Response({
            "active_resume_id": workspace.active_resume.id if workspace.active_resume else None,
            "active_template_id": active_temp_id,
            "scroll_position": workspace.scroll_position,
            "editor_state": workspace.editor_state
        }, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        workspace, created = UserWorkspace.objects.get_or_create(user=request.user)
        
        active_resume_id = request.data.get('active_resume_id')
        if active_resume_id is not None:
            if active_resume_id == "" or active_resume_id is False:
                workspace.active_resume = None
            else:
                try:
                    workspace.active_resume = Resume.objects.get(id=active_resume_id, user=request.user)
                    if workspace.active_resume.template:
                        workspace.active_template = workspace.active_resume.template
                except Resume.DoesNotExist:
                    workspace.active_resume = None
                    
        active_template_id = request.data.get('active_template_id')
        if active_template_id is not None:
            if active_template_id == "" or active_template_id is False:
                workspace.active_template = None
                if workspace.active_resume:
                    workspace.active_resume.template = None
                    workspace.active_resume.save()
            else:
                try:
                    template_obj = ResumeTemplate.objects.get(id=active_template_id)
                    workspace.active_template = template_obj
                    if workspace.active_resume:
                        workspace.active_resume.template = template_obj
                        workspace.active_resume.save()
                except ResumeTemplate.DoesNotExist:
                    pass
                    
        scroll_position = request.data.get('scroll_position')
        if scroll_position is not None:
            try:
                workspace.scroll_position = int(scroll_position)
            except (ValueError, TypeError):
                pass
                
        editor_state = request.data.get('editor_state')
        if editor_state is not None:
            if isinstance(editor_state, dict):
                workspace.editor_state = editor_state
                
        workspace.save()
        
        # Get active template id mapped to active resume if any
        active_temp_id = None
        if workspace.active_resume and workspace.active_resume.template:
            active_temp_id = workspace.active_resume.template.id
        elif workspace.active_template:
            active_temp_id = workspace.active_template.id

        return Response({
            "active_resume_id": workspace.active_resume.id if workspace.active_resume else None,
            "active_template_id": active_temp_id,
            "scroll_position": workspace.scroll_position,
            "editor_state": workspace.editor_state
        }, status=status.HTTP_200_OK)

class DeleteResumeView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (CsrfExemptSessionAuthentication,)

    def delete(self, request, id, *args, **kwargs):
        try:
            resume = Resume.objects.get(id=id, user=request.user)
        except Resume.DoesNotExist:
            return Response({"error": "Resume not found"}, status=status.HTTP_404_NOT_FOUND)
        
        workspace, created = UserWorkspace.objects.get_or_create(user=request.user)
        is_active = (workspace.active_resume == resume)
        
        resume.delete()
        
        fallback_resume_id = None
        if is_active:
            recent = Resume.objects.filter(user=request.user).order_by('-updated_at').first()
            if recent:
                workspace.active_resume = recent
                fallback_resume_id = recent.id
                if recent.template:
                    workspace.active_template = recent.template
                else:
                    workspace.active_template = None
            else:
                new_name = get_next_untitled_name(request.user)
                new_resume = Resume.objects.create(
                    user=request.user,
                    name=new_name,
                    email="",
                    phone="",
                    linkedin="",
                    skills=""
                )
                workspace.active_resume = new_resume
                workspace.active_template = None
                fallback_resume_id = new_resume.id
            workspace.save()
        else:
            if workspace.active_resume:
                fallback_resume_id = workspace.active_resume.id
                
        return Response({
            "success": True,
            "active_resume_id": fallback_resume_id
        }, status=status.HTTP_200_OK)

class DuplicateResumeView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (CsrfExemptSessionAuthentication,)

    def post(self, request, id, *args, **kwargs):
        try:
            original = Resume.objects.get(id=id, user=request.user)
        except Resume.DoesNotExist:
            return Response({"error": "Resume not found"}, status=status.HTTP_404_NOT_FOUND)
            
        base_name = f"{original.name} Copy"
        existing_names = set(Resume.objects.filter(user=request.user, name__startswith=base_name).values_list('name', flat=True))
        
        dup_name = base_name
        if dup_name in existing_names:
            i = 2
            while f"{base_name} ({i})" in existing_names:
                i += 1
            dup_name = f"{base_name} ({i})"
            
        duplicate = Resume.objects.create(
            user=request.user,
            name=dup_name,
            email=original.email,
            phone=original.phone,
            linkedin=original.linkedin,
            skills=original.skills,
            education=original.education,
            experience=original.experience,
            projects=original.projects,
            certifications=original.certifications,
            achievements=original.achievements,
            languages=original.languages,
            template=original.template
        )
        
        serializer = ResumeSerializer(duplicate)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class MyResumesView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (CsrfExemptSessionAuthentication,)

    def get(self, request, *args, **kwargs):
        resumes = Resume.objects.filter(user=request.user).order_by('-updated_at')
        serializer = ResumeSerializer(resumes, many=True)
        return Response(serializer.data)

class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (CsrfExemptSessionAuthentication,)

    def get(self, request, *args, **kwargs):
        return Response({"username": request.user.username})

class TemplateListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = (CsrfExemptSessionAuthentication,)

    def get(self, request, *args, **kwargs):
        templates = ResumeTemplate.objects.filter(is_public=True).order_by('id')
        serializer = ResumeTemplateSerializer(templates, many=True)
        return Response(serializer.data)

class SaveTemplateView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (CsrfExemptSessionAuthentication,)

    def post(self, request, id, *args, **kwargs):
        try:
            template = ResumeTemplate.objects.get(id=id, is_public=True)
        except ResumeTemplate.DoesNotExist:
            return Response({"error": "Template not found"}, status=status.HTTP_404_NOT_FOUND)
        
        user_template, created = UserTemplate.objects.get_or_create(user=request.user, template=template)
        serializer = UserTemplateSerializer(user_template)
        if created:
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.data, status=status.HTTP_200_OK)

class MyTemplatesView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (CsrfExemptSessionAuthentication,)

    def get(self, request, *args, **kwargs):
        user_templates = UserTemplate.objects.filter(user=request.user).order_by('-saved_at')
        serializer = UserTemplateSerializer(user_templates, many=True)
        return Response(serializer.data)

class FavoriteTemplateView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (CsrfExemptSessionAuthentication,)

    def post(self, request, id, *args, **kwargs):
        try:
            template = ResumeTemplate.objects.get(id=id)
        except ResumeTemplate.DoesNotExist:
            return Response({"error": "Template not found"}, status=status.HTTP_404_NOT_FOUND)
        
        user_template, created = UserTemplate.objects.get_or_create(user=request.user, template=template)
        if created:
            user_template.favorite = True
        else:
            user_template.favorite = not user_template.favorite
        user_template.save()
        
        serializer = UserTemplateSerializer(user_template)
        return Response(serializer.data, status=status.HTTP_200_OK)

class UserSelectedTemplateView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = (CsrfExemptSessionAuthentication,)

    def get(self, request, *args, **kwargs):
        try:
            selected = UserSelectedTemplate.objects.get(user=request.user)
            serializer = ResumeTemplateSerializer(selected.template)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except UserSelectedTemplate.DoesNotExist:
            return Response({"error": "No template selected yet"}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, *args, **kwargs):
        template_id = request.data.get('template_id')
        if not template_id:
            return Response({"error": "template_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            template = ResumeTemplate.objects.get(id=template_id)
        except ResumeTemplate.DoesNotExist:
            return Response({"error": "Template not found"}, status=status.HTTP_404_NOT_FOUND)

        selected_template, created = UserSelectedTemplate.objects.update_or_create(
            user=request.user,
            defaults={'template': template}
        )
        serializer = ResumeTemplateSerializer(template)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RecoveryCacheMixin:
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

def generate_recovery_code() -> str:
    pool = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    part1 = "".join(secrets.choice(pool) for _ in range(4))
    part2 = "".join(secrets.choice(pool) for _ in range(4))
    return f"{part1}-{part2}"

@method_decorator(never_cache, name='dispatch')
class ForgotPasswordView(RecoveryCacheMixin, View):
    def get(self, request):
        return render(request, 'account/password_reset.html')

    def post(self, request):
        email = request.POST.get('email', '').strip()
        user = User.objects.filter(email=email).first()
        
        expires_at_dt = timezone.now() + timezone.timedelta(minutes=15)
        expires_at_ts = int(expires_at_dt.timestamp())
        
        if user:
            # Generate code
            code = generate_recovery_code()
            code_hash = make_password(code)
            
            try:
                with transaction.atomic():
                    # Delete every previous PasswordRecovery record belonging to that user
                    PasswordRecovery.objects.filter(user=user).delete()
                    # Save recovery record
                    PasswordRecovery.objects.create(
                        user=user,
                        code_hash=code_hash,
                        expires_at=expires_at_dt
                    )
            except IntegrityError:
                # Concurrent request wrote a record, delete it and recreate to ensure this request's code is active
                PasswordRecovery.objects.filter(user=user).delete()
                PasswordRecovery.objects.create(
                    user=user,
                    code_hash=code_hash,
                    expires_at=expires_at_dt
                )
            
            request.session['recovery_code'] = code
            request.session['recovery_email'] = email
            request.session['recovery_expires_at'] = expires_at_ts
        else:
            # Generate fake/dummy code for user enumeration defense
            code = generate_recovery_code()
            request.session['recovery_code'] = code
            request.session['recovery_email'] = email
            request.session['recovery_expires_at'] = expires_at_ts
            
            # Call check_password on a dummy hash to protect against timing analysis
            dummy_hash = "pbkdf2_sha256$870000$dummy_salt$dummy_hash_value_here_to_mimic_real_checking"
            check_password(code, dummy_hash)

        return redirect('account_reset_password_code')

@method_decorator(never_cache, name='dispatch')
class RecoveryCodeView(RecoveryCacheMixin, View):
    def get(self, request):
        code = request.session.get('recovery_code')
        email = request.session.get('recovery_email')
        expires_at_ts = request.session.get('recovery_expires_at')
        
        if not code or not expires_at_ts:
            return redirect('account_reset_password')
            
        # Calculate remaining seconds for the live timer
        now_ts = int(timezone.now().timestamp())
        expires_in_seconds = max(0, expires_at_ts - now_ts)
        
        # Display once: remove it from session immediately
        del request.session['recovery_code']
        
        # Keep email and expiry in session for verification
        request.session['recovery_email'] = email
        request.session['recovery_expires_at'] = expires_at_ts
        
        return render(request, 'account/password_reset_code.html', {
            'code': code,
            'email': email,
            'expires_in_seconds': expires_in_seconds
        })

@method_decorator(never_cache, name='dispatch')
class ResetPasswordConfirmView(RecoveryCacheMixin, View):
    def get(self, request):
        email = request.session.get('recovery_email', '')
        return render(request, 'account/password_reset_confirm.html', {
            'email': email
        })

    def post(self, request):
        email = request.POST.get('email', '').strip()
        code = request.POST.get('code', '').strip().upper()
        password = request.POST.get('password', '')
        
        user = User.objects.filter(email=email).first()
        dummy_hash = "pbkdf2_sha256$870000$dummy_salt$dummy_hash_value_here_to_mimic_real_checking"
        
        # Reject codes containing invalid characters or incorrect format before checking hash
        if not re.match(r'^[A-Z0-9]{4}-[A-Z0-9]{4}$', code):
            # Timing attack countermeasure: still perform dummy verification
            check_password('DUMY-CODE', dummy_hash)
            return render(request, 'account/password_reset_confirm.html', {
                'error': 'Invalid recovery code format. Code must be like AB7X-Q91K.',
                'email': email
            })
            
        if user:
            recovery = PasswordRecovery.objects.filter(user=user, used=False).first()
            if recovery:
                # Check expiration
                if timezone.now() > recovery.expires_at:
                    recovery.delete()
                    return render(request, 'account/password_reset_confirm.html', {
                        'error': 'This recovery code has expired. Please request a new one.',
                        'email': email
                    })
                
                # Check attempts
                if recovery.attempts >= 5:
                    recovery.delete()
                    return render(request, 'account/password_reset_confirm.html', {
                        'error': 'Too many incorrect attempts. Please request a new recovery code.',
                        'email': email
                    })
                
                # Verify code
                if check_password(code, recovery.code_hash):
                    # Success
                    user.set_password(password)
                    user.save()
                    recovery.delete() # Delete immediately (Never keep used recovery codes)
                    
                    # Clean up every recovery-related session variable
                    for key in ['recovery_code', 'recovery_email', 'recovery_expires_at']:
                        if key in request.session:
                            del request.session[key]
                        
                    return redirect('account_reset_password_success')
                else:
                    recovery.attempts += 1
                    recovery.save()
                    
                    attempts_left = 5 - recovery.attempts
                    if attempts_left <= 0:
                        recovery.delete()
                        error_msg = 'Too many incorrect attempts. This recovery code is now invalid. Please request a new one.'
                    else:
                        error_msg = f'Invalid recovery code. Attempts remaining: {attempts_left}.'
                        
                    return render(request, 'account/password_reset_confirm.html', {
                        'error': error_msg,
                        'email': email
                    })
            else:
                check_password(code, dummy_hash)
        else:
            check_password(code, dummy_hash)
            
        return render(request, 'account/password_reset_confirm.html', {
            'error': 'Invalid email, recovery code, or code has expired.',
            'email': email
        })

@method_decorator(never_cache, name='dispatch')
class ResetPasswordSuccessView(RecoveryCacheMixin, View):
    def get(self, request):
        return render(request, 'account/password_reset_success.html')


