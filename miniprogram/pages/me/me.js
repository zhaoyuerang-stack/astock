const app = getApp();

const PLAN_NAME = {
  free: '体验版 FREE',
  pro: '基础会员 PRO',
  max: '专业版 MAX'
};

Page({
  data: {
    user: {
      nickname: '微信用户',
      avatar: 'K',
      tenantId: 'T-7F3A2B',
      joinedAt: '2026-06'
    },
    plan: 'pro',
    planName: '基础会员 PRO',
    tokenBalance: 27,
    tokenQuota: 30,
    usedTokens: 3,
    quotaPercent: 90,
    expireDate: '2026-07-28'
  },

  onLoad() {
    this.refresh();
  },

  onShow() {
    this.refresh();
  },

  refresh() {
    const g = app.globalData;
    const plan = g.plan || 'free';
    const balance = g.tokenBalance || 0;
    const quota = g.tokenQuota || 3;
    const used = quota - balance;
    const percent = quota > 0 ? Math.round((used / quota) * 100) : 0;
    this.setData({
      plan,
      planName: PLAN_NAME[plan] || '体验版 FREE',
      tokenBalance: balance,
      tokenQuota: quota,
      usedTokens: used > 0 ? used : 0,
      quotaPercent: Math.min(100, percent)
    });
  },

  onBuyTokenPack() {
    wx.showActionSheet({
      itemList: ['10 token · ¥9', '30 token · ¥25', '100 token · ¥79'],
      success: (res) => {
        const packs = [
          { tokens: 10, price: 9 },
          { tokens: 30, price: 25 },
          { tokens: 100, price: 79 }
        ];
        const pack = packs[res.tapIndex];
        wx.showModal({
          title: '确认购买',
          content: `购买 ${pack.tokens} token,支付 ¥${pack.price}?\n\n(微信支付集成开发中,MVP 演示版直接到账)`,
          success: (r) => {
            if (r.confirm) {
              // MVP 演示:直接加 token,实际调微信支付
              app.globalData.tokenBalance += pack.tokens;
              app.globalData.tokenQuota += pack.tokens;
              this.refresh();
              wx.showToast({ title: `已到账 ${pack.tokens} token`, icon: 'success' });
            }
          }
        });
      }
    });
  },

  onUpgrade() {
    wx.showModal({
      title: '升级到专业版 MAX',
      content: '¥99/月 · 每月 120 token\n· 多因子组合(≤5)\n· 三段样本深审\n· 审计对比 + 导出 PDF\n· 衰减告警 + 优先队列\n\n(微信支付集成开发中)',
      confirmText: '立即升级',
      success: (r) => {
        if (r.confirm) {
          app.globalData.plan = 'max';
          app.globalData.tokenQuota = 120;
          app.globalData.tokenBalance = 120;
          this.refresh();
          wx.showToast({ title: '已升级 MAX', icon: 'success' });
        }
      }
    });
  },

  onSubscription() {
    wx.showToast({ title: '订阅管理开发中', icon: 'none' });
  },

  onInvoices() {
    wx.showToast({ title: '账单开发中', icon: 'none' });
  },

  onHistory() {
    wx.switchTab({ url: '/pages/report/report' });
  },

  onNotify() {
    wx.openSetting({
      success: (res) => {
        console.log('订阅消息设置', res);
      }
    });
  },

  onDisclaimer() {
    wx.showModal({
      title: '研究使用声明',
      content: '本工具为研究方法学分析工具,不构成任何投资建议。\n\n· 审计结果基于公开市场历史数据,可能存在延迟或错误\n· 过去表现不代表未来收益\n· DSR/9-Gate 等指标为统计结论,不构成投资建议\n· 用户应自行承担依据本工具结果做出的任何决策风险\n\n继续使用即表示您已阅读并同意以上声明。',
      showCancel: false,
      confirmText: '我已了解'
    });
  },

  onRenew() {
    wx.showModal({
      title: '续费会员',
      content: '续费基础会员 PRO · ¥29/月\n\n(微信支付集成开发中,MVP 演示版直接续期)',
      confirmText: '确认续费',
      success: (r) => {
        if (r.confirm) {
          // MVP 演示:重置额度
          app.globalData.tokenBalance = 30;
          app.globalData.tokenQuota = 30;
          this.refresh();
          wx.showToast({ title: '续费成功', icon: 'success' });
        }
      }
    });
  }
});
