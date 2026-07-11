const { login } = require('./utils/auth');

App({
  globalData: {
    userInfo: null,
    tenantId: null,
    plan: 'free',
    tokenBalance: 0,
    tokenQuota: 3,
    baseUrl: 'http://localhost:8011/miniapp/v1',  // 开发期本地,正式环境改 HTTPS 域名
    mockMode: false  // true=用本地 mock 数据,无需后端;false=真实请求(已对接 factor_research/api/routers/miniapp.py)
  },

  onLaunch() {
    // 启动时静默登录
    login().then(user => {
      this.globalData.userInfo = user;
      this.globalData.tenantId = user.tenantId;
      this.globalData.plan = user.plan || 'free';
      this.globalData.tokenBalance = user.tokenBalance || 3;
      this.globalData.tokenQuota = user.tokenQuota || 3;
    }).catch(err => {
      console.warn('Login failed, fallback to mock:', err);
      // Mock 兜底
      this.globalData.userInfo = {
        nickname: '微信用户',
        avatar: 'K',
        tenantId: 'T-MOCK001'
      };
      this.globalData.tenantId = 'T-MOCK001';
      this.globalData.plan = 'pro';
      this.globalData.tokenBalance = 27;
      this.globalData.tokenQuota = 30;
    });
  }
});
