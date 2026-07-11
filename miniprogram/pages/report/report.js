const app = getApp();

const VERDICT_TEXT = {
  falsified: '不可行 · FALSIFIED',
  viable: '可行 · VIABLE',
  inconclusive: '待定 · INCONCLUSIVE'
};

const VERDICT_SUB = {
  falsified: '9 门中 4 门未通过,DSR 不显著',
  viable: '9 门全部通过,可进入前向观察',
  inconclusive: '部分门警告,证据不足'
};

const WHY_TITLE = {
  falsified: '为什么不可行',
  viable: '为什么可行',
  inconclusive: '为什么待定'
};

Page({
  data: {
    result: null,
    verdictText: '',
    verdictSub: '',
    whyTitle: ''
  },

  onLoad(options) {
    // 从全局拿最近一次审计结果(MVP)
    const result = app.globalData.lastAuditResult;
    if (result) {
      this.setData({
        result,
        verdictText: VERDICT_TEXT[result.verdict] || '',
        verdictSub: VERDICT_SUB[result.verdict] || '',
        whyTitle: WHY_TITLE[result.verdict] || '原因分析'
      });
    }
  },

  onShow() {
    // 如果全局有新结果,刷新
    const result = app.globalData.lastAuditResult;
    if (result && (!this.data.result || this.data.result.jobId !== result.jobId)) {
      this.setData({
        result,
        verdictText: VERDICT_TEXT[result.verdict] || '',
        verdictSub: VERDICT_SUB[result.verdict] || '',
        whyTitle: WHY_TITLE[result.verdict] || '原因分析'
      });
    }
  },

  onDetailTap() {
    wx.showToast({
      title: '完整详情页开发中',
      icon: 'none'
    });
  },

  goAudit() {
    wx.switchTab({ url: '/pages/index/index' });
  }
});
