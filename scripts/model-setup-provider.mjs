export const providers = {
  modelscope: {base: 'https://api-inference.modelscope.cn/v1', label: '魔搭免费推理'},
  openrouter: {base: 'https://openrouter.ai/api/v1', label: 'OpenRouter 免费模型'},
};

// Only return our own messages. Provider responses can echo credentials or account data.
export function diagnoseProviderFailure(status, body) {
  const message = String(body?.error?.message ?? body?.message ?? body?.Message ?? '');
  if (/email verification|verify (?:your )?email|邮箱验证|验证邮箱/i.test(message)) {
    return {reason: 'email_verification_required', status, message: '魔搭要求完成邮箱验证。请打开 https://modelscope.cn/my/settings/account，在账号设置中绑定并验证邮箱；这与阿里云实名认证是不同的一项，验证码由本人填写。完成后再测试，不用重建令牌或充值。'};
  }
  if (/bind.*(alibaba|aliyun|cloud)|绑定.*(阿里|云账号)/i.test(message)) {
    return {reason: 'account_binding_required', status, message: '请先在魔搭个人中心绑定阿里云账号，并确认已完成实名认证；完成后回到这里重试。无需充值或开通付费服务。'};
  }
  if (/real.?name|实名认证|identity verification/i.test(message)) {
    return {reason: 'identity_verification_required', status, message: '服务商要求完成账号实名认证。请在官方页面由本人完成，再回来重试；不要把身份资料发到聊天。'};
  }
  if (status === 401) return {reason: 'authentication_rejected', status, message: '身份验证未通过（HTTP 401）。请先确认魔搭已绑定阿里云账号并完成实名认证；若均已完成，再从官方访问令牌页重新复制完整的 ms- 开头令牌。查询到模型目录不代表令牌已验证。'};
  if (status === 403) return {reason: 'permission_denied', status, message: '服务商拒绝访问（HTTP 403）。请检查账号认证、访问权限和免费推理服务开通状态。'};
  if (status === 429) return {reason: 'free_quota_or_rate_limit', status, message: '免费额度或调用速率已达到上限（HTTP 429），请稍后再试；不会切换付费。'};
  if (status === 402) return {reason: 'payment_required', status, message: '服务商要求付费（HTTP 402），本次已停止。请检查免费入口和账户状态，不需要充值继续此向导。'};
  if (status === 404 || /model.*(not found|not exist|no provider)/i.test(message)) return {reason: 'model_unavailable', status, message: '当前模型已不可用，请重新查询免费目录并选择其他模型。'};
  return {reason: status >= 500 ? 'provider_unavailable' : 'request_rejected', status, message: `服务商返回 HTTP ${status}，尚未连接成功。请稍后重试或检查官方服务状态。`};
}

export class SetupError extends Error {
  constructor(message, diagnosis) {super(message); this.diagnosis = diagnosis;}
}

export function validateSetupKey(id, key) {
  if (!key) throw new SetupError('请在本机页面填写官方访问令牌。');
  if (/\s/.test(key) || key.length < 12 || key.length > 512) throw new SetupError('访问令牌格式不完整，请重新复制，不要手动输入或粘贴令牌名称。');
  if (id === 'modelscope' && !key.startsWith('ms-')) throw new SetupError('魔搭访问令牌应以 ms- 开头。请复制访问令牌内容，而不是名称、阿里云 AccessKey 或百炼密钥。');
}

export async function providerRequest(id, key, endpoint, payload, fetchImpl = fetch) {
  const p = providers[id];
  if (!p) throw new SetupError('仅支持已核实的免费服务入口。');
  let response;
  try {
    response = await fetchImpl(p.base + '/' + endpoint, {
      method: payload ? 'POST' : 'GET',
      headers: {...(key ? {Authorization: 'Bearer ' + key} : {}), 'Content-Type': 'application/json'},
      body: payload ? JSON.stringify(payload) : undefined,
      signal: AbortSignal.timeout(50000),
    });
  } catch {
    throw new SetupError('连接服务商超时或网络不可达，尚未保存配置。请检查网络后重试。', {reason: 'network_unavailable', status: null});
  }
  let body;
  try {body = await response.json();} catch {
    if (response.ok) throw new SetupError('服务商未返回有效数据，请稍后重试。', {reason: 'invalid_response', status: response.status});
  }
  if (!response.ok) {
    const diagnosis = diagnoseProviderFailure(response.status, body);
    throw new SetupError(diagnosis.message, {...diagnosis, endpoint});
  }
  return body;
}
