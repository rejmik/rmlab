/**
 * RM Lab – odesílání upozornění na poptávky přes Gmail (Google Workspace).
 * Nasazení: script.google.com → Nový projekt → vložit tento kód →
 *   Nastavení projektu → Vlastnosti skriptu → přidat SECRET = (dlouhý náhodný řetězec, stejný jako LF_GAS_SECRET v Railway)
 *   Nasadit → Nové nasazení → Webová aplikace → Spustit jako: Já, Přístup: Kdokoli → zkopírovat URL (…/exec) do LF_GAS_URL.
 */
function doPost(e) {
  var out = function (o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); };
  try {
    var d = JSON.parse(e.postData.contents);
    var secret = PropertiesService.getScriptProperties().getProperty('SECRET');
    if (!secret || d.secret !== secret) return out({ ok: false, error: 'bad secret' });
    if (!d.to || !d.subject) return out({ ok: false, error: 'missing fields' });
    var opts = { name: 'RM Lab' };
    if (d.replyTo) opts.replyTo = d.replyTo;
    MailApp.sendEmail(String(d.to), String(d.subject).slice(0, 200), String(d.text || ''), opts);
    return out({ ok: true });
  } catch (err) {
    return out({ ok: false, error: String(err) });
  }
}

/** Spusť jednou ručně v editoru – Google si vyžádá oprávnění k odesílání pošty. */
function test() {
  MailApp.sendEmail(Session.getActiveUser().getEmail(), 'RM Lab – test', 'Apps Script funguje.', { name: 'RM Lab' });
}
