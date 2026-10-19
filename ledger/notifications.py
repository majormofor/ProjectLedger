"""Durable change notifications; failed mail never rolls back a saved project."""
import logging
from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Change, EmailNotification

logger = logging.getLogger(__name__)

def email_ready():
    if settings.EMAIL_BACKEND == 'django.core.mail.backends.smtp.EmailBackend':
        return bool(settings.EMAIL_HOST and settings.DEFAULT_FROM_EMAIL and (not settings.EMAIL_HOST_USER or settings.EMAIL_HOST_PASSWORD))
    return settings.EMAIL_BACKEND == 'django.core.mail.backends.locmem.EmailBackend'

def deliver(notification_id):
    if not email_ready():
        EmailNotification.objects.filter(pk=notification_id, status='pending').update(last_error='Sender email is not configured. Check SMTP settings and the sender app password.')
        return False
    now = timezone.now()
    with transaction.atomic():
        row = EmailNotification.objects.select_for_update().get(pk=notification_id)
        if row.status == 'sent' or (row.status == 'sending' and row.claimed_at and row.claimed_at > now - timedelta(minutes=5)):
            return False
        row.status = 'sending'
        row.claimed_at = now
        row.attempts += 1
        row.save(update_fields=['status', 'claimed_at', 'attempts'])
    try:
        sent = send_mail(row.subject, row.body, settings.DEFAULT_FROM_EMAIL, [row.recipient], fail_silently=False)
        if sent != 1:
            raise RuntimeError('Mail backend did not accept the notification.')
    except Exception:
        # Do not store exception strings that may contain SMTP credentials or PII.
        EmailNotification.objects.filter(pk=row.pk).update(status='pending', claimed_at=None, last_error='Email delivery failed. Check sender SMTP settings and retry.')
        logger.warning('ProjectLedger email delivery failed; notification %s remains queued.', row.pk)
        return False
    EmailNotification.objects.filter(pk=row.pk).update(status='sent', sent_at=timezone.now(), claimed_at=None, last_error='')
    return True

@receiver(post_save, sender=Change, dispatch_uid='projectledger_change_notification')
def queue_notification(sender, instance, created, **kwargs):
    recipient = settings.NOTIFICATION_EMAIL
    if not created or not recipient:
        return
    project = instance.project
    subject = f'ProjectLedger: {instance.action} — {project.name}'
    lines = [instance.action, f'Project: {project.name}', f'Updated by: {instance.actor.username}', f'Date: {timezone.localtime(instance.created_at):%d %b %Y, %H:%M} (Africa/Lagos)', '']
    labels = {'name':'Name', 'client':'Client', 'location':'Location', 'cost_type':'Type', 'cost':'Cost (NGN)', 'paid':'Amount paid (NGN)', 'expected_date':'Expected completion'}
    for key, value in instance.after.items():
        if key not in labels:
            continue
        before = instance.before.get(key)
        value = str(value)
        if before is not None and str(before) != value:
            lines.append(f'{labels[key]}: {before} -> {value}')
        elif not instance.before:
            lines.append(f'{labels[key]}: {value}')
    lines += ['', 'This update was recorded in ProjectLedger. Amounts are entered by the project owner.']
    row = EmailNotification.objects.create(change=instance, recipient=recipient, subject=subject[:255], body='\n'.join(lines))
    transaction.on_commit(lambda: deliver(row.pk))
