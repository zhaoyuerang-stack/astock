const app = getApp();
const auditService = require('../../services/audit');

const PLAN_TEXT = {
  free: 'FREE',
  pro: 'PRO',
  max: 'MAX'
};

Page({
  data: {
    tokenBalance: 0,
    tokenQuota: 3,
    plan: 'free',
    planText: 'FREE',
    inputText: '',
    welcomeTime: '',
    messages: [],
    spec: null,
    job: null,
    scrollAnchor: ''
  },

  onLoad() {
    this.setData({
      welcomeTime: this.formatTime(new Date())
    });
    this.refreshQuota();
  },

  onShow() {
    this.refreshQuota();
  },

  refreshQuota() {
    const g = app.globalData;
    this.setData({
      tokenBalance: g.tokenBalance,
      tokenQuota: g.tokenQuota,
      plan: g.plan,
      planText: PLAN_TEXT[g.plan] || 'FREE'
    });
  },

  formatTime(date) {
    const h = String(date.getHours()).padStart(2, '0');
    const m = String(date.getMinutes()).padStart(2, '0');
    return `${h}:${m}`;
  },

  onInput(e) {
    this.setData({ inputText: e.detail.value });
  },

  onChipTap(e) {
    const text = e.currentTarget.dataset.text;
    this.setData({ inputText: text });
    this.onSend();
  },

  onSend() {
    const text = this.data.inputText.trim();
    if (!text) return;

    const userMsg = {
      id: `u${Date.now()}`,
      role: 'user',
      text: text,
      time: this.formatTime(new Date())
    };

    this.setData({
      inputText: '',
      messages: [...this.data.messages, userMsg],
      scrollAnchor: `msg-${userMsg.id}`
    });

    // 调用解析接口
    wx.showLoading({ title: '解析中...', mask: true });
    auditService.parseStrategy(text).then(res => {
      wx.hideLoading();
      this.setData({ spec: res });
      const botMsg = {
        id: `b${Date.now()}`,
        role: 'bot',
        type: 'spec',
        text: '我把你的策略解析成审计参数,请确认:',
        time: this.formatTime(new Date())
      };
      this.setData({
        messages: [...this.data.messages, botMsg],
        scrollAnchor: `msg-${botMsg.id}`
      });
    }).catch(err => {
      wx.hideLoading();
      wx.showToast({ title: err.message || '解析失败', icon: 'none' });
    });
  },

  onConfirmSubmit() {
    if (!this.data.spec) return;

    wx.showLoading({ title: '提交中...', mask: true });
    auditService.submitAudit(this.data.spec).then(res => {
      wx.hideLoading();
      this.setData({ job: res });

      // 扣 token
      app.globalData.tokenBalance = res.tokenBalanceAfter;
      this.refreshQuota();

      const jobMsg = {
        id: `b${Date.now()}`,
        role: 'bot',
        type: 'job',
        text: '已提交,正在排队审计。',
        time: this.formatTime(new Date())
      };
      this.setData({
        messages: [...this.data.messages, jobMsg],
        scrollAnchor: `msg-${jobMsg.id}`
      });

      // 模拟 12 分钟后出结果(MVP 演示用,实际由订阅消息推送)
      this.simulateAuditComplete(res.jobId);
    }).catch(err => {
      wx.hideLoading();
      wx.showToast({ title: err.message || '提交失败', icon: 'none' });
    });
  },

  onModifyCancel() {
    const cancelMsg = {
      id: `b${Date.now()}`,
      role: 'bot',
      text: '已取消。请重新描述你的策略。',
      time: this.formatTime(new Date())
    };
    this.setData({
      spec: null,
      messages: [...this.data.messages, cancelMsg]
    });
  },

  // MVP 演示:3 秒后模拟审计完成(实际是后端 worker 跑 + 订阅消息推送)
  simulateAuditComplete(jobId) {
    setTimeout(() => {
      auditService.getAuditResult(jobId).then(res => {
        // 存到全局,供报告页使用
        app.globalData.lastAuditResult = res;

        const resultMsg = {
          id: `b${Date.now()}`,
          role: 'bot',
          type: 'result',
          text: `12 分钟后 · ${this.formatTime(new Date())}\n审计完成:`,
          time: this.formatTime(new Date())
        };
        this.setData({
          messages: [...this.data.messages, resultMsg],
          scrollAnchor: `msg-${resultMsg.id}`
        });
      }).catch(err => {
        console.error('获取审计结果失败', err);
      });
    }, 3000);  // 演示用 3 秒,实际 5-20 分钟
  },

  goReport() {
    wx.switchTab({ url: '/pages/report/report' });
  }
});
