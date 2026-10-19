import re
from unittest.mock import patch
from datetime import date
from decimal import Decimal as D
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from .forms import SubprojectForm
from .models import Project, Subproject, Change

@override_settings(NOTIFICATION_EMAIL='')
class SimpleLedgerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('owner', password='Testing-a-long-password-01!')
        cls.other = User.objects.create_user('other', password='Testing-a-long-password-02!')
        cls.project = Project.objects.create(owner=cls.owner, name='House', client='Ada', location='Lagos')

    def setUp(self):
        cache.clear()
        self.client.force_login(self.owner)

    def add_sub(self, name='Foundation', cost='1000.10', paid='200.03', expected='2026-12-01'):
        return self.client.post(reverse('project', args=[self.project.pk]), {'name': name, 'cost_type': 'material', 'cost': cost, 'paid': paid, 'expected_date': expected})

    def test_registration_and_sign_out(self):
        client = Client()
        response = client.post(reverse('register'), {'username':'newowner', 'password1':'Test-long-password-1234!', 'password2':'Test-long-password-1234!'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.get('/').status_code, 200)
        self.assertEqual(client.get(reverse('logout')).status_code, 405)
        self.assertEqual(client.post(reverse('logout')).status_code, 302)
        self.assertEqual(client.get('/').status_code, 302)

    def test_project_creation_needs_only_essentials(self):
        response = self.client.post('/', {'name':'Shop', 'client':'Obi', 'location':''})
        self.assertEqual(response.status_code, 302)
        obj = Project.objects.get(name='Shop')
        self.assertEqual(obj.owner_id, self.owner.pk)
        self.assertContains(self.client.get(response.url), 'No subprojects yet.')

    def test_four_fields_add_cost_payment_balance_and_date_immediately(self):
        self.assertEqual(set(SubprojectForm().fields), {'name','cost_type','cost','paid','expected_date'})
        self.assertEqual(self.add_sub().status_code, 302)
        sub = Subproject.objects.get()
        self.assertEqual(sub.project_id, self.project.pk)
        self.assertEqual(sub.cost, D('1000.10'))
        self.assertEqual(sub.paid, D('200.03'))
        self.assertEqual(sub.balance, D('800.07'))
        self.assertEqual(sub.expected_date, date(2026,12,1))
        response = self.client.get(reverse('project', args=[self.project.pk]))
        self.assertContains(response, '₦800.07')
        self.assertNotContains(response, 'Add item')

    def test_multiple_subprojects_update_summary(self):
        self.add_sub()
        self.add_sub('Roof', '2000.20', '300.01', '2026-12-20')
        obj = Project.objects.get(pk=self.project.pk)
        self.assertEqual(obj.cost, D('3000.30'))
        self.assertEqual(obj.paid, D('500.04'))
        self.assertEqual(obj.balance, D('2500.26'))
        self.assertEqual(obj.expected_date, date(2026,12,20))

    def test_update_cumulative_paid_does_not_double_count(self):
        self.add_sub()
        sub = Subproject.objects.get()
        response = self.client.post(reverse('subproject_edit', args=[sub.pk]), {'name':sub.name,'cost_type':'material','cost':'1000.10','paid':'600.03','expected_date':'2027-01-10'})
        self.assertEqual(response.status_code, 302)
        obj = Project.objects.get(pk=self.project.pk)
        self.assertEqual(obj.paid, D('600.03'))
        self.assertEqual(obj.balance, D('400.07'))
        self.assertEqual(obj.expected_date, date(2026,12,1))
        log = Change.objects.filter(action='Subproject updated').get()
        self.assertEqual(log.before['paid'], '200.03')
        self.assertEqual(log.after['paid'], '600.03')

    def test_invalid_costs_payments_and_dates_rejected(self):
        for changes in [{'cost':'-1'}, {'paid':'-1'}, {'expected_date':'invalid'}, {'expected_date':''}, {'cost':'10.123'}]:
            data={'name':'Invalid','cost_type':'material','cost':'100','paid':'0','expected_date':'2026-12-01',**changes}
            self.assertEqual(self.client.post(reverse('project', args=[self.project.pk]), data).status_code, 200)
        self.assertEqual(Subproject.objects.count(), 0)

    def test_overpayment_explicit_and_other_balances_not_offset(self):
        self.add_sub('Overpaid', '100', '150')
        self.add_sub('Unpaid', '100', '0')
        obj=Project.objects.get(pk=self.project.pk)
        self.assertEqual(obj.balance, D('100'))
        self.assertEqual(obj.excess, D('50'))
        self.assertEqual(Subproject.objects.get(name='Overpaid').payment_status, 'Overpaid')
        self.assertContains(self.client.get(reverse('project', args=[obj.pk])), 'credit')

    def test_zero_cost_and_paid_statuses(self):
        self.add_sub(cost='0', paid='0')
        sub=Subproject.objects.get()
        self.assertEqual(sub.balance, 0)
        self.assertEqual(sub.payment_status, 'Unpaid')
        sub.cost=D('100'); sub.paid=D('100')
        self.assertEqual(sub.payment_status, 'Paid')

    def test_owner_isolation_and_no_parent_forgery(self):
        self.add_sub()
        sub=Subproject.objects.get()
        self.client.force_login(self.other)
        for name,args in [('project',[self.project.pk]),('project_edit',[self.project.pk]),('subproject_edit',[sub.pk])]:
            self.assertEqual(self.client.get(reverse(name,args=args)).status_code,404)
        self.assertEqual(self.client.post(reverse('share',args=[self.project.pk]),{'action':'enable'}).status_code,404)
        self.assertEqual(self.add_sub().status_code,404)

    def test_parent_is_assigned_by_server(self):
        other=Project.objects.create(owner=self.other,name='Other',client='Other')
        self.client.post(reverse('project',args=[self.project.pk]),{'name':'Correct','cost_type':'labour','cost':'100','paid':'0','expected_date':'2026-12-01','project':other.pk})
        self.assertEqual(Subproject.objects.get().project_id,self.project.pk)

    def enable_share(self):
        self.client.post(reverse('share',args=[self.project.pk]),{'action':'enable'})
        return Project.objects.get(pk=self.project.pk).token

    def test_client_view_is_read_only_and_compact(self):
        self.add_sub()
        token=self.enable_share()
        client=Client()
        url=reverse('client',args=[token])
        response=client.get(url)
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'₦800.07')
        for hidden in ['Add a subproject','Edit project','edit-dialog','Create client link','Sign out']:
            self.assertNotContains(response,hidden)
        self.assertEqual(client.post(url,{'name':'Hacked'}).status_code,405)

    def test_revoked_and_rotated_links_stop_working(self):
        old=self.enable_share()
        token=self.enable_share()
        self.assertNotEqual(old,token)
        self.assertEqual(Client().get(reverse('client',args=[old])).status_code,404)
        self.client.post(reverse('share',args=[self.project.pk]),{'action':'revoke'})
        self.assertEqual(Client().get(reverse('client',args=[token])).status_code,404)

    def test_sharing_is_off_by_default_and_unguessable(self):
        self.assertGreaterEqual(len(self.project.token),40)
        self.assertEqual(Client().get(reverse('client',args=[self.project.token])).status_code,404)
        self.assertEqual(self.client.get(reverse('share',args=[self.project.pk])).status_code,405)

    def test_home_totals_search_and_mobile_markup(self):
        self.add_sub()
        response=self.client.get('/')
        self.assertEqual(response.context['cost'],D('1000.10'))
        self.assertEqual(response.context['paid'],D('200.03'))
        self.assertEqual(response.context['balance'],D('800.07'))
        self.assertContains(response,'name="viewport"')
        self.assertEqual(len(self.client.get('/?q=missing').context['projects']),0)
        self.assertEqual(len(self.client.get('/?q=ada').context['projects']),1)

    def test_project_edit_keeps_financial_totals_derived(self):
        self.add_sub()
        self.client.post(reverse('project_edit',args=[self.project.pk]),{'name':'Updated','client':'Ada','location':'Abuja','cost':'1'})
        self.assertEqual(Project.objects.get(pk=self.project.pk).cost,D('1000.10'))
        self.assertEqual(Project.objects.get(pk=self.project.pk).name,'Updated')

    def test_all_forms_render_with_short_field_count(self):
        self.add_sub()
        sub=Subproject.objects.get()
        self.assertEqual(len(self.client.get(reverse('subproject_edit',args=[sub.pk])).context['form'].fields),1)
        self.assertEqual(len(self.client.get(reverse('project_edit',args=[self.project.pk])).context['form'].fields),3)

    def test_no_delete_or_item_workflow(self):
        self.assertEqual(self.client.get('/items/new/').status_code,404)
        self.assertEqual(self.client.post(reverse('project',args=[self.project.pk]),{'action':'delete'}).status_code,200)
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())

    def test_empty_summary_has_no_invented_date(self):
        self.assertIsNone(self.project.expected_date)
        self.assertEqual(self.project.cost,0)
        self.assertContains(self.client.get(reverse('project',args=[self.project.pk])),'Not set yet')

    def test_both_cost_types_create_and_display_to_owner_and_client(self):
        for kind, label in [('labour', 'Labour'), ('material', 'Material')]:
            response = self.client.post(reverse('project', args=[self.project.pk]), {'name':label, 'cost_type':kind, 'cost':'100', 'paid':'20', 'expected_date':'2026-12-01'})
            self.assertEqual(response.status_code,302)
            self.assertEqual(Subproject.objects.get(name=label).cost_type,kind)
        self.assertContains(self.client.get(reverse('project',args=[self.project.pk])), 'data-label="Type"', count=2)
        token=self.enable_share()
        response=Client().get(reverse('client',args=[token]))
        self.assertContains(response,'Labour')
        self.assertContains(response,'Material')

    def test_cost_type_required_and_invalid_type_rejected(self):
        for kind in ['', 'other', 'forged']:
            response=self.client.post(reverse('project',args=[self.project.pk]),{'name':'Bad','cost_type':kind,'cost':'100','paid':'0','expected_date':'2026-12-01'})
            self.assertEqual(response.status_code,200)
            self.assertIn('cost_type',response.context['form'].errors)
        self.assertEqual(Subproject.objects.count(),0)

    def test_forged_type_edit_is_ignored_without_affecting_money(self):
        self.add_sub()
        sub=Subproject.objects.get()
        response=self.client.post(reverse('subproject_edit',args=[sub.pk]),{'name':sub.name,'cost_type':'labour','cost':str(sub.cost),'paid':str(sub.paid),'expected_date':str(sub.expected_date)})
        self.assertEqual(response.status_code,302)
        sub.refresh_from_db()
        self.assertEqual(sub.cost_type,'material')
        self.assertEqual(sub.balance,D('800.07'))
        change=Change.objects.get(action='Subproject updated')
        self.assertEqual(change.before['cost_type'],'material')
        self.assertEqual(change.after['cost_type'],'material')

    def test_existing_unclassified_records_have_clear_label(self):
        Subproject.objects.create(project=self.project,name='Existing',cost=D('100'),paid=D('0'),expected_date=date(2026,12,1))
        self.assertContains(self.client.get(reverse('project',args=[self.project.pk])),'Not set')

    def test_forged_edit_can_only_update_paid(self):
        self.add_sub()
        sub=Subproject.objects.get()
        response=self.client.post(reverse('subproject_edit',args=[sub.pk]),{'paid':'500.03','name':'Forged name','cost_type':'labour','cost':'1','expected_date':'2030-01-01','project':'999'})
        self.assertEqual(response.status_code,302)
        sub.refresh_from_db()
        self.assertEqual(sub.paid,D('500.03'))
        self.assertEqual(sub.name,'Foundation')
        self.assertEqual(sub.cost_type,'material')
        self.assertEqual(sub.cost,D('1000.10'))
        self.assertEqual(sub.expected_date,date(2026,12,1))
        self.assertEqual(sub.project_id,self.project.pk)
        self.assertEqual(sub.balance,D('500.07'))

    def test_model_rejects_changes_to_locked_subproject_fields(self):
        self.add_sub()
        sub=Subproject.objects.get()
        for field,value in [('name','Changed'),('cost_type','labour'),('cost',D('1')),('expected_date',date(2030,1,1))]:
            sub.refresh_from_db()
            setattr(sub,field,value)
            with self.assertRaises(ValidationError): sub.save()

    def test_paid_only_form_rejects_invalid_amount_and_preserves_previous_value(self):
        self.add_sub()
        sub=Subproject.objects.get()
        response=self.client.get(reverse('subproject_edit',args=[sub.pk]))
        self.assertEqual(set(response.context['form'].fields),{'paid'})
        for value in ['-1','invalid','']:
            self.assertEqual(self.client.post(reverse('subproject_edit',args=[sub.pk]),{'paid':value}).status_code,200)
        sub.refresh_from_db()
        self.assertEqual(sub.paid,D('200.03'))

    def test_paid_only_update_works_for_legacy_unclassified_subproject(self):
        sub=Subproject.objects.create(project=self.project,name='Existing',cost=D('100'),paid=D('0'),expected_date=date(2026,12,1))
        self.assertEqual(self.client.post(reverse('subproject_edit',args=[sub.pk]),{'paid':'20'}).status_code,302)
        sub.refresh_from_db()
        self.assertEqual(sub.cost_type,'')
        self.assertEqual(sub.paid,D('20'))

    def test_delete_confirmation_only_on_project_list_and_get_preserves_records(self):
        self.add_sub()
        home=self.client.get('/')
        self.assertContains(home,reverse('project_delete',args=[self.project.pk]))
        detail=self.client.get(reverse('project',args=[self.project.pk]))
        self.assertNotContains(detail,'Delete project')
        self.assertEqual(self.client.get(reverse('project_delete',args=[self.project.pk])).status_code,200)
        self.project.refresh_from_db()
        self.assertIsNone(self.project.deleted_at)

    def test_delete_hides_scope_disables_client_link_preserves_money_and_undo(self):
        self.add_sub()
        sub=Subproject.objects.get()
        token=self.enable_share()
        response=self.client.post(reverse('project_delete',args=[self.project.pk]),follow=True)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['count'],0)
        self.assertEqual(response.context['cost'],0)
        self.assertContains(response,'Undo')
        self.project.refresh_from_db()
        self.assertIsNotNone(self.project.deleted_at)
        self.assertFalse(self.project.shared)
        self.assertEqual(self.project.cost,D('1000.10'))
        self.assertTrue(Change.objects.filter(action='Project deleted').exists())
        self.assertEqual(Client().get(reverse('client',args=[token])).status_code,404)
        self.assertEqual(self.client.get(reverse('project',args=[self.project.pk])).status_code,404)
        self.assertEqual(self.client.post(reverse('subproject_edit',args=[sub.pk]),{'paid':'1'}).status_code,404)
        self.assertEqual(self.client.post(reverse('project_restore',args=[self.project.pk])).status_code,302)
        self.assertEqual(self.client.get('/').context['count'],1)
        self.assertEqual(self.project.subprojects.count(),1)
        self.assertEqual(Client().get(reverse('client',args=[token])).status_code,404)

    def test_other_owners_cannot_delete_or_restore_projects(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('project_delete',args=[self.project.pk])).status_code,404)
        self.client.force_login(self.owner)
        self.client.post(reverse('project_delete',args=[self.project.pk]))
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('project_restore',args=[self.project.pk])).status_code,404)

    def test_delete_requires_csrf_and_restore_requires_post(self):
        client=Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(reverse('project_delete',args=[self.project.pk])).status_code,403)
        self.assertEqual(self.client.get(reverse('project_restore',args=[self.project.pk])).status_code,405)


@override_settings(NOTIFICATION_EMAIL='moformajor@gmail.com', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', DEFAULT_FROM_EMAIL='sender@example.com')
class EmailNotificationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user=User.objects.create_user('mailowner',password='Testing-a-long-password-01!')
        self.project=Project.objects.create(owner=self.user,name='Mail project',client='Client')
        self.client.force_login(self.user)

    def test_added_project_sends_to_configured_recipient_after_commit(self):
        from django.core import mail
        from .models import EmailNotification
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post('/',{'name':'New project','client':'Ada','location':''})
        self.assertEqual(len(mail.outbox),1)
        self.assertEqual(mail.outbox[0].to,['moformajor@gmail.com'])
        self.assertIn('Project created',mail.outbox[0].subject)
        self.assertEqual(EmailNotification.objects.get().status,'sent')

    def test_subproject_added_and_paid_updates_send_before_after(self):
        from django.core import mail
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('project',args=[self.project.pk]),{'name':'Labour','cost_type':'labour','cost':'100','paid':'20','expected_date':'2026-12-01'})
        sub=Subproject.objects.get()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('subproject_edit',args=[sub.pk]),{'paid':'60'})
        self.assertEqual(len(mail.outbox),2)
        self.assertIn('Subproject added',mail.outbox[0].subject)
        self.assertIn('20.00 -> 60',mail.outbox[1].body)
        self.assertNotIn(self.project.token,mail.outbox[1].body)

    def test_delivery_failure_keeps_saved_update_and_can_retry(self):
        from .models import EmailNotification
        from .notifications import deliver
        with patch('ledger.notifications.send_mail',side_effect=RuntimeError('smtp failure secret should not be stored')):
            with self.captureOnCommitCallbacks(execute=True):
                response=self.client.post('/',{'name':'Saved despite email failure','client':'Ada','location':''})
        self.assertEqual(response.status_code,302)
        self.assertTrue(Project.objects.filter(name='Saved despite email failure').exists())
        row=EmailNotification.objects.get()
        self.assertEqual(row.status,'pending')
        self.assertNotIn('secret',row.last_error)
        self.assertTrue(deliver(row.pk))
        row.refresh_from_db()
        self.assertEqual(row.status,'sent')
        self.assertFalse(deliver(row.pk))

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',EMAIL_HOST='smtp.gmail.com',EMAIL_HOST_USER='moformajor@gmail.com',EMAIL_HOST_PASSWORD='')
    def test_unconfigured_sender_queues_without_network_attempt(self):
        from .models import EmailNotification
        with patch('ledger.notifications.send_mail') as send:
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post('/',{'name':'Queued','client':'Ada','location':''})
        send.assert_not_called()
        self.assertEqual(EmailNotification.objects.get().status,'pending')

    def test_rolled_back_change_does_not_send_or_queue_email(self):
        from django.db import transaction
        from .models import EmailNotification
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    Change.objects.create(project=self.project,actor=self.user,action='Project updated')
                    raise ValueError('Rollback')
            except ValueError:
                pass
        self.assertFalse(EmailNotification.objects.exists())

@override_settings(DEBUG=True, LOCAL_EMBEDDED_PREVIEW=True)
class CsrfTests(TestCase):
    def post_form(self, token=True, origin='null', peer='127.0.0.1', host='127.0.0.1:8002'):
        client=Client(enforce_csrf_checks=True)
        page=client.get(reverse('login'),HTTP_HOST=host)
        value=re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"',page.content.decode()).group(1)
        data={'username':'','password':''}
        if token: data['csrfmiddlewaretoken']=value if token is True else token
        return client.post(reverse('login'),data,HTTP_HOST=host,HTTP_ORIGIN=origin,REMOTE_ADDR=peer)
    def test_local_preview_requires_valid_csrf_token(self):
        self.assertEqual(self.post_form().status_code,200)
        self.assertEqual(self.post_form(token=False).status_code,403)
        self.assertEqual(self.post_form(token='a'*64).status_code,403)
    def test_untrusted_origin_and_remote_peer_blocked(self):
        self.assertEqual(self.post_form(origin='https://evil.example').status_code,403)
        self.assertEqual(self.post_form(peer='192.168.0.2').status_code,403)
        self.assertEqual(self.post_form(host='testserver').status_code,403)
    @override_settings(DEBUG=False)
    def test_production_ignores_preview_flag(self):
        self.assertEqual(self.post_form().status_code,403)
    @override_settings(LOCAL_EMBEDDED_PREVIEW=False)
    def test_preview_opt_in_required(self):
        self.assertEqual(self.post_form().status_code,403)
    def test_normal_origin_works(self):
        self.assertEqual(self.post_form(origin='http://127.0.0.1:8002').status_code,200)
