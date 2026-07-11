/**
 * 统一请求封装 - 带 auth + 错误处理 + mock 兜底
 */
const app = getApp();

const request = (options) => {
  return new Promise((resolve, reject) => {
    // Mock 模式:直接返回 mock 数据,不调后端(开发期无后端时用)
    if (app.globalData.mockMode) {
      const mockData = getMockData(options.url, options.method);
      if (mockData !== undefined) {
        setTimeout(() => resolve(mockData), 300);
        return;
      }
    }

    const token = wx.getStorageSync('access_token');
    wx.request({
      url: `${app.globalData.baseUrl}${options.url}`,
      method: options.method || 'GET',
      data: options.data || {},
      header: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
        ...options.header
      },
      success: (res) => {
        if (res.statusCode === 401) {
          // token 失效,重新登录后重试
          wx.removeStorageSync('access_token');
          require('./auth').login().then(() => {
            request(options).then(resolve).catch(reject);
          }).catch(reject);
          return;
        }
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
        } else {
          reject({ code: res.statusCode, message: (res.data && res.data.message) || '请求失败' });
        }
      },
      fail: (err) => {
        reject({ code: -1, message: '网络错误', detail: err });
      }
    });
  });
};

/**
 * Mock 数据(开发期不依赖后端)
 */
function getMockData(url, method) {
  // 登录
  if (url === '/auth/login' && method === 'POST') {
    return {
      user: {
        id: 'U001',
        tenantId: 'T-7F3A2B',
        nickname: '微信用户',
        avatar: 'K',
        plan: 'pro',
        tokenBalance: 27,
        tokenQuota: 30
      },
      access_token: 'mock-token-xxx',
      refresh_token: 'mock-refresh-xxx'
    };
  }

  // 解析自然语言策略
  if (url === '/audit/parse' && method === 'POST') {
    return {
      spec: {
        universe: '全 A',
        rebalance: '月频',
        factors: '小市值 × 低流动性',
        holdings: 25,
        weighting: '等权',
        neutralization: '无',
        costModel: '标准',
        sample: '2018-2022 / 2023+'
      },
      auditType: '双因子组合',
      tokenCost: 3
    };
  }

  // 提交审计
  if (url === '/audit/submit' && method === 'POST') {
    return {
      jobId: 'J-20260704-' + Math.floor(1000 + Math.random() * 9000),
      estimatedTime: '10-15 分钟',
      tokenCost: 3,
      tokenBalanceAfter: 24,
      status: 'running',
      currentStage: 'Gate 2 · 单因子验证'
    };
  }

  // 查询审计结果
  if (url.startsWith('/audit/result/') && method === 'GET') {
    return {
      jobId: url.split('/').pop(),
      verdict: 'falsified',
      summary: {
        description: '小市值低流动性月调仓',
        auditRange: '2018-01 ~ 2026-06',
        oosStart: '2023-01-01',
        auditType: '双因子组合 · 消耗 3 token',
        completedAt: '09:54'
      },
      kpi: {
        annual: '21.6%',
        sharpe: '1.38',
        maxDrawdown: '-17.7%',
        dsrP: '0.086'
      },
      gateStats: { pass: 5, warn: 2, fail: 3 },
      gates: [
        { id: 'G0', name: '数据审计', status: 'pass', detail: '通过' },
        { id: 'G1', name: '经济假设', status: 'pass', detail: '通过' },
        { id: 'G2', name: '单因子验证', status: 'pass', detail: 'ICIR 1.42' },
        { id: 'G3', name: '中性化验证', status: 'warn', detail: '留存 62%' },
        { id: 'G4', name: '多重检验 DSR', status: 'fail', detail: 'p=0.086' },
        { id: 'G5', name: '组合回测', status: 'pass', detail: '夏普 1.38' },
        { id: 'G6', name: '成本容量', status: 'fail', detail: '衰减高' },
        { id: 'G7', name: '样本外压力', status: 'warn', detail: '2018 塌陷' },
        { id: 'G7A', name: '防泄露 CV', status: 'pass', detail: '通过' },
        { id: 'G8', name: '实盘监控', status: 'warn', detail: '待前向' }
      ],
      reasons: [
        'DSR p=0.086 > 0.05,统计上无法排除过拟合',
        '成本衰减吃掉 40% alpha,容量受限',
        '2018 核心资产抱团行情下致命塌陷'
      ]
    };
  }

  return undefined;
}

module.exports = { request };
