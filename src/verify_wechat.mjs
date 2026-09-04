// Scoped to the report sender process; never changes the installed OpenClaw plugin.
import fs from 'node:fs';
const originalFetch = globalThis.fetch;
globalThis.fetch = async function(input, init) {
  const url = typeof input === 'string' ? input : (input instanceof URL ? input.href : input.url);
  if (!url.includes('/ilink/bot/sendmessage')) return originalFetch(input, init);
  const body = JSON.parse(init?.body ?? '{}');
  const message = body.msg ?? {};
  if (!process.env.DAILY_WECHAT_TARGET || message.to_user_id !== process.env.DAILY_WECHAT_TARGET)
    throw new Error('Daily report recipient mismatch; sending cancelled.');
  // The CLI does not start the channel monitor, so its in-memory context cache
  // can be empty. Reuse the exact persisted context saved by this user's Gateway.
  if (process.env.DAILY_WECHAT_ACCOUNT_FILE) {
    const account = JSON.parse(fs.readFileSync(process.env.DAILY_WECHAT_ACCOUNT_FILE,'utf8'));
    if (account.userId !== process.env.DAILY_WECHAT_TARGET || new URL(url).origin !== new URL(account.baseUrl).origin)
      throw new Error('WeChat account or endpoint mismatch; cancelled.');
    if (!message.context_token) {
      const contexts = JSON.parse(fs.readFileSync(process.env.DAILY_WECHAT_CONTEXT_FILE,'utf8'));
      const context = contexts[message.to_user_id];
      if (typeof context !== 'string' || !context) throw new Error('Saved WeChat conversation context is unavailable.');
      message.context_token=context;
      init={...init, body:JSON.stringify(body)};
    }
  }
  const response = await originalFetch(input, init);
  let result;
  try { result = await response.clone().json(); }
  catch { throw new Error('WeChat did not return a JSON acknowledgement.'); }
  // Tencent SendMessageResp permits an empty JSON object on success.
  // Current server also returns message_id; require a nonempty ID and no error.
  // Reject other unknown response shapes.
  const validObject = result !== null && typeof result === 'object' && !Array.isArray(result);
  const emptyAck = validObject && Object.keys(result).length === 0;
  const messageId = result?.message_id;
  const serverIdAck = validObject && ((typeof messageId === 'string' && messageId.trim().length > 0) || (typeof messageId === 'number' && Number.isFinite(messageId) && messageId > 0));
  const hasCode = validObject && (Object.hasOwn(result, 'ret') || Object.hasOwn(result, 'errcode'));
  const ok = response.ok && (emptyAck || hasCode || serverIdAck) && !result.errmsg && !result.message &&
    (!Object.hasOwn(result,'ret') || result.ret === 0) &&
    (!Object.hasOwn(result,'errcode') || result.errcode === 0);
  const receipt = {client_id:message.client_id, target:message.to_user_id,
    http_status:response.status, acknowledgement:emptyAck?"empty_object":serverIdAck?"server_message_id":hasCode?"explicit_code":"unknown", server_message_id:messageId, response_keys:validObject?Object.keys(result):[], ret:result?.ret, errcode:result?.errcode,
    error_message:ok?undefined:String(result?.errmsg ?? result?.message ?? '').slice(0,300),
    accepted:ok, time:new Date().toISOString()};
  fs.appendFileSync(process.env.DAILY_WECHAT_RECEIPTS, JSON.stringify(receipt)+'\n', {mode:0o600});
  if (!ok) throw new Error(`WeChat rejected report: ret=${result?.ret}, errcode=${result?.errcode}; ${receipt.error_message}`);
  return response;
};
