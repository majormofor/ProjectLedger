# Enable Gmail notifications

The local app is configured to notify **you@gmail.com** when projects or subprojects are added or updated, payments change, and projects are deleted or restored. Client-link changes also generate an alert. Notifications describe the change and who recorded it, without including client sharing tokens.

Store Gmail SMTP settings in the ignored local `.env`. Credentials and project records are not included in this repository. Configure and verify delivery for each installation.

1. Sign in to the Google account that should send notifications. The current sender is set to `you@gmail.com`; change EMAIL_HOST_USER and DEFAULT_FROM_EMAIL together if you want another Gmail sender.
2. Turn on 2-Step Verification if it is not already enabled. Create a dedicated ProjectLedger app password at [Google App Passwords](https://myaccount.google.com/apppasswords). Some account policies do not offer app passwords; see [Google's instructions](https://support.google.com/accounts/answer/185833).
3. In the local `.env`, set `EMAIL_HOST_PASSWORD` to that app password. Use the generated app password, not your normal Google password. Keep `.env` private and do not paste the password into chat. The remaining settings are already configured:

   ```dotenv
   NOTIFICATION_EMAIL=you@gmail.com
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=465
   EMAIL_HOST_USER=you@gmail.com
   EMAIL_USE_TLS=False
   EMAIL_USE_SSL=True
   DEFAULT_FROM_EMAIL=you@gmail.com
   ```

4. Restart the local Django server to load the password. New changes will then attempt email delivery after their database transaction commits. Check Inbox and Spam; SMTP acceptance is not a guarantee of inbox placement.
5. To send/retry older queued notifications, run:

   ```powershell
   .\.venv\Scripts\python manage.py send_notifications
   ```

If a notification fails, the project change is still saved and the email stays queued for retry. Use your host's scheduler to run the retry command regularly after deployment if unattended retry is needed. Delivery is at least once; interrupted SMTP sends may be retried.

This setting applies to project activity across this installation. Remove NOTIFICATION_EMAIL or leave it empty to disable new notification creation. Removing it does not erase existing queued messages; only run the retry command when you intend to send those messages.

## Delete project

Each project card on My projects now has a Delete project control. It opens a confirmation page. Confirmation hides the project from the workspace and excludes its figures from the dashboard, while disabling/rotating the client link. The project, subprojects, financial data and audit history remain stored for recovery. An Undo button is shown immediately after deletion. Restoring does not reactivate any previous client link. There is no subproject delete button.

The current network timed out on SMTP port 587. Gmail SSL on port 465 connected successfully and accepted the test message.
