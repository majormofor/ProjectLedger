document.querySelectorAll('[data-open]').forEach(button => button.addEventListener('click', () => document.getElementById(button.dataset.open).showModal()));
document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
document.querySelectorAll('dialog[data-open-now="true"]').forEach(dialog => dialog.showModal());
function updateBalance(form) {
  const cost = Number(form.elements.cost?.value || form.dataset.cost || 0);
  const paid = Number(form.elements.paid?.value || 0);
  const output = form.querySelector('[data-balance]');
  if (output) output.textContent = (paid > cost ? 'Overpaid: ' : 'Balance: ') + new Intl.NumberFormat('en-NG', {style:'currency',currency:'NGN'}).format(Math.abs(cost-paid));
}
document.querySelectorAll('form[data-subproject]').forEach(form => { form.addEventListener('input', () => updateBalance(form)); updateBalance(form); });
document.querySelectorAll('[data-edit]').forEach(button => button.addEventListener('click', () => {
  const dialog = document.getElementById('edit-dialog');
  const form = dialog.querySelector('form');
  form.action = button.dataset.edit;
  form.elements.paid.value = button.dataset.paid;
  form.dataset.cost = button.dataset.cost;
  dialog.querySelector('[data-edit-summary]').textContent = button.dataset.name + ' · Cost: ' + new Intl.NumberFormat('en-NG', {style:'currency',currency:'NGN'}).format(Number(button.dataset.cost));
  updateBalance(form); dialog.showModal();
}));
document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => {
  const input = document.getElementById('client-link');
  try { await navigator.clipboard.writeText(input.value); button.textContent = 'Copied ✓'; }
  catch { input.select(); button.textContent = 'Copy selected link'; }
}));
document.querySelectorAll('form[data-confirm]').forEach(form => form.addEventListener('submit', event => { if (!confirm(form.dataset.confirm)) event.preventDefault(); }));
document.querySelectorAll('[data-print]').forEach(button => button.addEventListener('click', () => window.print()));
