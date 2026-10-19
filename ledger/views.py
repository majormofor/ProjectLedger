from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.db import transaction
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_safe
from .forms import ProjectForm, SubprojectForm, PaidAmountForm, RegisterForm
from .models import Project, Subproject, Change, new_token

def throttled(request, action):
    key = f'simple:{action}:{request.META.get("REMOTE_ADDR", "unknown")}'
    cache.add(key, 0, 300)
    try: count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, 300)
        count = 1
    return count > 20

class SignInView(LoginView):
    template_name = 'login.html'
    redirect_authenticated_user = True
    def post(self, request, *args, **kwargs):
        if throttled(request, 'login'):
            return HttpResponse('Too many attempts. Please try again in five minutes.', status=429)
        return super().post(request, *args, **kwargs)

def register(request):
    if request.user.is_authenticated: return redirect('home')
    if request.method == 'POST' and throttled(request, 'register'):
        return HttpResponse('Too many attempts. Please try again in five minutes.', status=429)
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.save())
        return redirect('home')
    return render(request, 'register.html', {'form': form})

def owned(request, pk):
    return get_object_or_404(Project.objects.prefetch_related('subprojects'), owner=request.user, pk=pk, deleted_at__isnull=True)

@login_required
def home(request):
    projects = list(Project.objects.filter(owner=request.user, deleted_at__isnull=True).prefetch_related('subprojects'))
    query = request.GET.get('q', '').strip().lower()
    visible = [p for p in projects if query in f'{p.name} {p.client}'.lower()]
    form = ProjectForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            project = form.save(commit=False)
            project.owner = request.user
            project.save()
            Change.objects.create(project=project, actor=request.user, action='Project created', after={'name': project.name, 'client': project.client})
        return redirect('project', pk=project.pk)
    undo_id = request.session.pop('deleted_project', None)
    undo_project = Project.objects.filter(pk=undo_id, owner=request.user, deleted_at__isnull=False).first() if undo_id else None
    return render(request, 'home.html', {'undo_project': undo_project, 'projects': visible, 'count': len(projects), 'cost': sum((p.cost for p in projects), Decimal('0')), 'paid': sum((p.paid for p in projects), Decimal('0')), 'balance': sum((p.balance for p in projects), Decimal('0')), 'form': form, 'form_open': request.method == 'POST'})

def sub_snapshot(sub):
    return {'name': sub.name, 'cost_type': sub.cost_type, 'cost': str(sub.cost), 'paid': str(sub.paid), 'expected_date': str(sub.expected_date)}

@login_required
def project(request, pk):
    obj = owned(request, pk)
    form = SubprojectForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            get_object_or_404(Project.objects.select_for_update(), pk=obj.pk, owner=request.user, deleted_at__isnull=True)
            sub = form.save(commit=False)
            sub.project = obj
            sub.full_clean()
            sub.save()
            Project.objects.filter(pk=obj.pk).update(updated_at=timezone.now())
            Change.objects.create(project=obj, actor=request.user, action='Subproject added', after=sub_snapshot(sub))
        messages.success(request, f'{sub.name} added. Your totals are up to date.')
        return redirect('project', pk=pk)
    return render(request, 'project.html', {'project': obj, 'subprojects': obj.subprojects.all(), 'form': form, 'form_open': request.method == 'POST', 'share_url': request.build_absolute_uri(reverse('client', args=[obj.token])) if obj.shared else ''})

@login_required
def edit_subproject(request, pk):
    sub = get_object_or_404(Subproject.objects.select_related('project'), pk=pk, project__owner=request.user, project__deleted_at__isnull=True)
    before = sub_snapshot(sub)
    form = PaidAmountForm(request.POST or None, instance=sub)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            get_object_or_404(Project.objects.select_for_update(), pk=sub.project_id, owner=request.user, deleted_at__isnull=True)
            # Read the current values after the project lock for an accurate history.
            before = sub_snapshot(Subproject.objects.get(pk=pk))
            sub = form.save()
            Project.objects.filter(pk=sub.project_id).update(updated_at=timezone.now())
            Change.objects.create(project=sub.project, actor=request.user, action='Subproject updated', before=before, after=sub_snapshot(sub))
        messages.success(request, f'{sub.name} updated.')
        return redirect('project', pk=sub.project_id)
    return render(request, 'edit.html', {'form': form, 'project': sub.project, 'subproject': sub, 'title': f'Update payment · {sub.name}', 'subtitle': 'Only the amount paid can be edited. Enter the total paid so far.'})

@login_required
def edit_project(request, pk):
    obj = owned(request, pk)
    before = {'name': obj.name, 'client': obj.client, 'location': obj.location}
    form = ProjectForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            get_object_or_404(Project.objects.select_for_update(), pk=obj.pk, owner=request.user, deleted_at__isnull=True)
            form.save()
            Change.objects.create(project=obj, actor=request.user, action='Project updated', before=before, after={'name': obj.name, 'client': obj.client, 'location': obj.location})
        return redirect('project', pk=pk)
    return render(request, 'edit.html', {'form': form, 'project': obj, 'title': 'Edit project', 'subtitle': 'Just the essentials. Project totals come from your subprojects.'})

@login_required
@require_POST
def share(request, pk):
    obj = owned(request, pk)
    action = request.POST.get('action')
    if action not in {'enable', 'revoke', 'renew'}: raise Http404
    with transaction.atomic():
        obj = get_object_or_404(Project.objects.select_for_update(), pk=pk, owner=request.user, deleted_at__isnull=True)
        obj.token = new_token()
        obj.shared = action != 'revoke'
        obj.save(update_fields=['token', 'shared', 'updated_at'])
        Change.objects.create(project=obj, actor=request.user, action='Client link disabled' if not obj.shared else 'Client link generated')
    messages.success(request, 'Client sharing disabled.' if not obj.shared else 'Client link is ready to copy. Previous links no longer work.')
    return redirect(reverse('project', args=[pk]) + '#sharing')

@require_safe
def client(request, token):
    obj = get_object_or_404(Project.objects.prefetch_related('subprojects'), token=token, shared=True, deleted_at__isnull=True)
    return render(request, 'project.html', {'project': obj, 'subprojects': obj.subprojects.all(), 'public': True})

@login_required
def delete_project(request, pk):
    obj = owned(request, pk)
    if request.method == 'POST':
        with transaction.atomic():
            obj = get_object_or_404(Project.objects.select_for_update(), pk=pk, owner=request.user, deleted_at__isnull=True)
            before = {'name': obj.name, 'client': obj.client, 'cost': str(obj.cost), 'paid': str(obj.paid)}
            obj.deleted_at = timezone.now()
            obj.shared = False
            obj.token = new_token()
            obj.save(update_fields=['deleted_at', 'shared', 'token', 'updated_at'])
            Change.objects.create(project=obj, actor=request.user, action='Project deleted', before=before)
        request.session['deleted_project'] = obj.pk
        return redirect('home')
    return render(request, 'delete_project.html', {'project': obj})

@login_required
@require_POST
def restore_project(request, pk):
    with transaction.atomic():
        obj = get_object_or_404(Project.objects.select_for_update(), pk=pk, owner=request.user, deleted_at__isnull=False)
        obj.deleted_at = None
        obj.save(update_fields=['deleted_at', 'updated_at'])
        Change.objects.create(project=obj, actor=request.user, action='Project restored', after={'name': obj.name})
    messages.success(request, 'Project restored. Create a new client link if you want to share it again.')
    return redirect('home')
