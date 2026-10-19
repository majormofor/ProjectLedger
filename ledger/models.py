import secrets
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

ZERO = Decimal('0.00')
def new_token():
    return secrets.token_urlsafe(32)

class Summary:
    @property
    def balance(self): return max(ZERO, self.cost - self.paid)
    @property
    def excess(self): return max(ZERO, self.paid - self.cost)
    @property
    def payment_status(self):
        if self.excess: return 'Overpaid'
        if self.cost and self.paid == self.cost: return 'Paid'
        if self.paid: return 'Part paid'
        return 'Unpaid'

class Project(models.Model, Summary):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='projects')
    name = models.CharField(max_length=150)
    client = models.CharField(max_length=120)
    location = models.CharField(max_length=180, blank=True)
    token = models.CharField(max_length=64, default=new_token, unique=True, editable=False)
    shared = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['-updated_at']
    @property
    def cost(self): return sum((s.cost for s in self.subprojects.all()), ZERO)
    @property
    def paid(self): return sum((s.paid for s in self.subprojects.all()), ZERO)
    @property
    def balance(self): return sum((s.balance for s in self.subprojects.all()), ZERO)
    @property
    def expected_date(self): return max((s.expected_date for s in self.subprojects.all()), default=None)
    @property
    def overdue_count(self): return sum(s.overdue for s in self.subprojects.all())
    @property
    def excess(self): return sum((s.excess for s in self.subprojects.all()), ZERO)
    def __str__(self): return self.name

class Subproject(models.Model, Summary):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='subprojects')
    name = models.CharField(max_length=120)
    cost_type = models.CharField('Type', max_length=10, choices=[('labour', 'Labour'), ('material', 'Material')], blank=True, default='')
    cost = models.DecimalField('Subproject cost (₦)', max_digits=16, decimal_places=2, validators=[MinValueValidator(ZERO)])
    paid = models.DecimalField('Amount paid so far (₦)', max_digits=16, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])
    expected_date = models.DateField('Expected completion')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['created_at', 'pk']
        constraints = [models.CheckConstraint(condition=models.Q(cost__gte=0), name='simple_cost_positive'), models.CheckConstraint(condition=models.Q(paid__gte=0), name='simple_paid_positive')]
    @property
    def overdue(self): return self.expected_date < timezone.localdate()
    def __str__(self): return self.name

    def clean(self):
        super().clean()
        if self.pk:
            original = Subproject.objects.get(pk=self.pk)
            locked = ('project_id', 'name', 'cost_type', 'cost', 'expected_date')
            if any(getattr(self, field) != getattr(original, field) for field in locked):
                raise ValidationError('Only the amount paid can be changed after a subproject is saved.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

class Change(models.Model):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='changes')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=100)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']

class EmailNotification(models.Model):
    change = models.OneToOneField(Change, on_delete=models.PROTECT, related_name='notification')
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(max_length=10, choices=[('pending', 'Pending'), ('sending', 'Sending'), ('sent', 'Sent')], default='pending')
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ['created_at']
